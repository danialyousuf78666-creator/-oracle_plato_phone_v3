from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from hunter_common import Detection, Track, TrackPoint, clip


class ObservationCentricTracker:
    """Deterministic MOT for fast, non-linear chamber motion.

    The tracker keeps the simple online/Hungarian architecture, but associates each
    detection to an observation-derived short-horizon trajectory rather than only
    to the last measured point. The distance gate grows modestly during short
    occlusions and radius consistency is part of the association cost. No synthetic
    detections are inserted into a track: predictions are used for association only.
    """

    def __init__(
        self,
        max_distance: float = 55.0,
        max_missed: int = 8,
        velocity_window: int = 5,
        radius_weight: float = 0.35,
        max_radius_change: float = 0.65,
        gap_growth: float = 0.20,
    ):
        self.max_distance = float(max_distance)
        self.max_missed = int(max_missed)
        self.velocity_window = max(2, int(velocity_window))
        self.radius_weight = max(0.0, float(radius_weight))
        self.max_radius_change = max(0.05, float(max_radius_change))
        self.gap_growth = max(0.0, float(gap_growth))
        self.tracks: list[Track] = []
        self._next_id = 1

    def _new(self, d: Detection) -> Track:
        t = Track(self._next_id, [TrackPoint(d.frame, d.x, d.y, d.r, d.score)])
        self.tracks.append(t)
        self._next_id += 1
        return t

    def _predict(self, t: Track, frame: int) -> tuple[float, float]:
        pts = t.points[-self.velocity_window :]
        if len(pts) < 2:
            return float(t.last.x), float(t.last.y)
        frames = np.asarray([p.frame for p in pts], dtype=float)
        if len(np.unique(frames)) < 2:
            return float(t.last.x), float(t.last.y)
        x = np.asarray([p.x for p in pts], dtype=float)
        y = np.asarray([p.y for p in pts], dtype=float)
        tau = frames - frames[-1]
        A = np.column_stack([np.ones_like(tau), tau])
        bx, *_ = np.linalg.lstsq(A, x, rcond=None)
        by, *_ = np.linalg.lstsq(A, y, rcond=None)
        dt = max(0.0, float(frame) - frames[-1])
        return float(bx[0] + bx[1] * dt), float(by[0] + by[1] * dt)

    @staticmethod
    def _median_radius(t: Track) -> float:
        vals = [float(p.r) for p in t.points[-5:] if p.r > 0]
        return float(np.median(vals)) if vals else max(1.0, float(t.last.r))

    def update(self, detections: list[Detection]) -> list[tuple[int, Detection]]:
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

        frame = int(detections[0].frame)
        huge = 1e9
        cost = np.full((len(active), len(detections)), huge, dtype=float)
        for i, t in enumerate(active):
            px, py = self._predict(t, frame)
            gate = self.max_distance * (1.0 + self.gap_growth * min(t.missed, 5))
            med_r = self._median_radius(t)
            for j, d in enumerate(detections):
                dist = math.hypot(px - d.x, py - d.y)
                radius_delta = abs(float(d.r) - med_r) / max(float(d.r), med_r, 1.0)
                if dist > gate or radius_delta > self.max_radius_change:
                    continue
                # Normalized distance dominates; radius consistency breaks ambiguous ties.
                cost[i, j] = dist / max(gate, 1e-9) + self.radius_weight * radius_delta

        rows, cols = linear_sum_assignment(cost)
        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        for i, j in zip(rows, cols):
            if cost[i, j] >= huge / 2:
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


def track_diagnostics(track: Track, fps: float) -> dict[str, float | int]:
    pts = sorted(track.points, key=lambda p: p.frame)
    if not pts:
        return {
            "n_points": 0,
            "span_frames": 0,
            "duration_s": 0.0,
            "continuity": 0.0,
            "radius_median": 0.0,
            "radius_cv": 1.0,
        }
    span = max(1, int(pts[-1].frame - pts[0].frame + 1))
    radii = np.asarray([max(0.0, float(p.r)) for p in pts], dtype=float)
    rmed = float(np.median(radii)) if radii.size else 0.0
    rmean = float(np.mean(radii)) if radii.size else 0.0
    rcv = float(np.std(radii) / max(rmean, 1e-9)) if radii.size else 1.0
    return {
        "n_points": len(pts),
        "span_frames": span,
        "duration_s": float(span / max(float(fps), 1e-9)),
        "continuity": clip(len(pts) / span),
        "radius_median": rmed,
        "radius_cv": max(0.0, rcv),
    }


def is_eligible_track(
    track: Track,
    fps: float,
    *,
    min_points: int | None = None,
    min_duration_s: float = 0.35,
    min_continuity: float = 0.28,
    max_radius_cv: float = 0.55,
) -> bool:
    d = track_diagnostics(track, fps)
    required_points = max(5, int(round(float(fps) * 0.30))) if min_points is None else int(min_points)
    return bool(
        int(d["n_points"]) >= required_points
        and float(d["duration_s"]) >= min_duration_s
        and float(d["continuity"]) >= min_continuity
        and float(d["radius_cv"]) <= max_radius_cv
    )


def tracking_quality_summary(tracks: list[Track], fps: float, frames_processed: int, detections_total: int) -> dict[str, Any]:
    diag = {t.track_id: track_diagnostics(t, fps) for t in tracks}
    eligible_ids = [t.track_id for t in tracks if is_eligible_track(t, fps)]
    long_ids = [
        tid for tid, d in diag.items()
        if float(d["duration_s"]) >= 1.0 and float(d["continuity"]) >= 0.35
    ]
    lengths = [int(d["n_points"]) for d in diag.values()]
    continuities = [float(d["continuity"]) for d in diag.values()]
    eligible_cont = [float(diag[tid]["continuity"]) for tid in eligible_ids]
    frames = max(1, int(frames_processed))
    fragmentation_index = float(len(tracks) / max(1, len(long_ids)))
    reasons: list[str] = []
    if len(eligible_ids) < 6:
        reasons.append("fewer_than_6_trajectory_eligible_tracks")
    if detections_total / frames > 80:
        reasons.append("excessive_detections_per_frame")
    if eligible_cont and float(np.median(eligible_cont)) < 0.40:
        reasons.append("low_eligible_track_continuity")
    return {
        "tracks_total": len(tracks),
        "eligible_tracks": len(eligible_ids),
        "eligible_track_ids": eligible_ids,
        "long_tracks_1s": len(long_ids),
        "detections_per_frame": float(detections_total / frames),
        "median_track_points": float(np.median(lengths)) if lengths else 0.0,
        "median_track_continuity": float(np.median(continuities)) if continuities else 0.0,
        "median_eligible_continuity": float(np.median(eligible_cont)) if eligible_cont else 0.0,
        "fragmentation_index": fragmentation_index,
        "trajectory_gate_pass": len(eligible_ids) >= 6 and not reasons,
        "reasons": reasons,
        "per_track": {str(k): v for k, v in diag.items()},
    }
