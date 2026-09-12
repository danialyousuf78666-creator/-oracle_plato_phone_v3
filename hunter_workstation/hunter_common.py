from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
SPECIALISTS=["M1_VISUAL","M2_MOTION","M3_FREQUENCY","M4_OPTICAL","M5_GEOMETRY","M6_ACOUSTIC","M7_RESONANCE","M8_ANOMALY","M9_PROPAGATION","M10_RELATIONSHIP","M11_CHALLENGER"]
EXTRACTED="E"
ENGINE_VERSION="hunter-workstation-0.4.0"
try:
    cv2.setNumThreads(1); cv2.setRNGSeed(0)
except Exception:
    pass

def clip(x: Any) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return 0.0


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def lock_report(report_path: str | Path) -> Path:
    p = Path(report_path)
    out = p.with_suffix(p.suffix + ".lock.json")
    report = json.loads(p.read_text(encoding="utf-8"))
    payload = {
        "report": str(p),
        "report_sha256": sha256_file(p),
        "input_sha256": report.get("input_sha256"),
        "config_sha256": report.get("config_sha256"),
        "engine_version": report.get("version"),
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "post_draw_adjustment": False,
        "random_ticket_fallback": False,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out


@dataclass
class Detection:
    frame: int
    x: float
    y: float
    r: float
    score: float = 1.0
    source: str = "hough"


@dataclass
class TrackPoint:
    frame: int
    x: float
    y: float
    r: float
    score: float = 1.0


@dataclass
class Track:
    track_id: int
    points: list[TrackPoint] = field(default_factory=list)
    missed: int = 0
    active: bool = True

    @property
    def last(self) -> TrackPoint:
        return self.points[-1]


class EnsembleBallDetector:
    """Deterministic union of Hough circles + saturation/roundness contours."""

    def __init__(
        self,
        min_radius: int = 5,
        max_radius: int = 80,
        min_dist: float = 12,
        param1: float = 120,
        param2: float = 22,
        use_color_contours: bool = True,
    ):
        self.min_radius = int(min_radius)
        self.max_radius = int(max_radius)
        self.min_dist = float(min_dist)
        self.param1 = float(param1)
        self.param2 = float(param2)
        self.use_color_contours = bool(use_color_contours)

    def _hough(self, frame: np.ndarray, frame_index: int) -> list[Detection]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 1.2)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=self.min_dist,
            param1=self.param1,
            param2=self.param2,
            minRadius=self.min_radius,
            maxRadius=self.max_radius,
        )
        if circles is None:
            return []
        return [
            Detection(frame_index, float(x), float(y), float(r), 1.0, "hough")
            for x, y, r in circles[0]
        ]

    def _color_contours(self, frame: np.ndarray, frame_index: int) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        # Broadcast lottery balls are usually substantially more saturated than chamber background.
        mask = ((sat >= 55) & (val >= 45)).astype(np.uint8) * 255
        mask = cv2.medianBlur(mask, 5)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out: list[Detection] = []
        for c in contours:
            area = float(cv2.contourArea(c))
            if area <= 0:
                continue
            per = float(cv2.arcLength(c, True))
            if per <= 0:
                continue
            circularity = 4.0 * math.pi * area / (per * per)
            (x, y), r = cv2.minEnclosingCircle(c)
            if r < self.min_radius or r > self.max_radius or circularity < 0.48:
                continue
            fill = area / max(math.pi * r * r, 1e-9)
            if fill < 0.45:
                continue
            out.append(Detection(frame_index, float(x), float(y), float(r), clip(circularity), "color"))
        return out

    @staticmethod
    def _dedupe(items: list[Detection]) -> list[Detection]:
        items = sorted(items, key=lambda d: (-d.score, d.source, d.x, d.y))
        kept: list[Detection] = []
        for d in items:
            duplicate = False
            for k in kept:
                dist = math.hypot(d.x - k.x, d.y - k.y)
                if dist <= max(4.0, 0.55 * min(d.r, k.r)):
                    duplicate = True
                    break
            if not duplicate:
                kept.append(d)
        return sorted(kept, key=lambda d: (d.x, d.y, d.r, d.source))

    def detect(self, frame: np.ndarray, frame_index: int) -> list[Detection]:
        found = self._hough(frame, frame_index)
        if self.use_color_contours:
            found.extend(self._color_contours(frame, frame_index))
        return self._dedupe(found)


class HungarianTracker:
    def __init__(self, max_distance: float = 55, max_missed: int = 4):
        self.max_distance = float(max_distance)
        self.max_missed = int(max_missed)
        self.tracks: list[Track] = []
        self._next_id = 1

    def _new(self, d: Detection) -> Track:
        t = Track(self._next_id, [TrackPoint(d.frame, d.x, d.y, d.r, d.score)])
        self.tracks.append(t)
        self._next_id += 1
        return t

    def update(self, detections: list[Detection]) -> list[tuple[int, Detection]]:
        """Update tracker and return deterministic detection->track assignments."""
        assigned: list[tuple[int, Detection]] = []
        active = [t for t in self.tracks if t.active]
        if not active:
            for d in detections:
                t = self._new(d)
                assigned.append((t.track_id, d))
            return assigned
        if not detections:
            for t in active:
                t.missed += 1
                if t.missed > self.max_missed:
                    t.active = False
            return assigned

        cost = np.array(
            [[math.hypot(t.last.x - d.x, t.last.y - d.y) for d in detections] for t in active],
            dtype=float,
        )
        rows, cols = linear_sum_assignment(cost)
        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        for i, j in zip(rows, cols):
            if cost[i, j] > self.max_distance:
                continue
            t, d = active[i], detections[j]
            t.points.append(TrackPoint(d.frame, d.x, d.y, d.r, d.score))
            t.missed = 0
            matched_tracks.add(t.track_id)
            matched_dets.add(j)
            assigned.append((t.track_id, d))
        for t in active:
            if t.track_id not in matched_tracks:
                t.missed += 1
                if t.missed > self.max_missed:
                    t.active = False
        for j, d in enumerate(detections):
            if j not in matched_dets:
                t = self._new(d)
                assigned.append((t.track_id, d))
        assigned.sort(key=lambda z: z[0])
        return assigned


def mask_frame(frame: np.ndarray, chamber_roi=None, overlay_masks=None) -> np.ndarray:
    h, w = frame.shape[:2]
    out = np.zeros_like(frame)
    if chamber_roi is None:
        out[:] = frame
    else:
        x0, y0, x1, y1 = [int(round(v)) for v in chamber_roi]
        x0, x1 = max(0, min(w, x0)), max(0, min(w, x1))
        y0, y1 = max(0, min(h, y0)), max(0, min(h, y1))
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = frame[y0:y1, x0:x1]
    for r in overlay_masks or []:
        x0, y0, x1, y1 = [int(round(v)) for v in r]
        x0, x1 = max(0, min(w, x0)), max(0, min(w, x1))
        y0, y1 = max(0, min(h, y0)), max(0, min(h, y1))
        out[y0:y1, x0:x1] = 0
    return out
