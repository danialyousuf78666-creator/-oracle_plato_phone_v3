from __future__ import annotations
import json, math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
from scipy.special import ndtr
from hunter_common import Track, clip, EXTRACTED

def track_features(track: Track, fps: float, frame_w: float, frame_h: float, zone) -> dict[str, float]:
    pts = sorted(track.points, key=lambda p: p.frame)
    if len(pts) < 3:
        return {k: 0.0 for k in ["quality", "zone", "proximity", "approach", "speed", "circulation", "acceleration", "dwell", "distance_slope"]}
    frames = np.array([p.frame for p in pts], float)
    xy = np.array([[p.x, p.y] for p in pts], float)
    t = frames / fps
    x0, y0, x1, y1 = zone
    ex, ey = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    vx = np.gradient(xy[:, 0], t)
    vy = np.gradient(xy[:, 1], t)
    ax = np.gradient(vx, t)
    ay = np.gradient(vy, t)
    speed = np.hypot(vx, vy)
    acc = np.hypot(ax, ay)
    d = np.hypot(xy[:, 0] - ex, xy[:, 1] - ey)
    diag = max(math.hypot(frame_w, frame_h), 1.0)
    proximity = 1.0 - float(np.clip(np.mean(d) / diag, 0, 1))
    inside = (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1)
    zone_score = float(np.mean(inside))
    dwell = clip(np.sum(inside) / (fps * 2.0))
    vec = np.column_stack([ex - xy[:, 0], ey - xy[:, 1]])
    norm = np.linalg.norm(vec, axis=1)
    norm[norm == 0] = 1
    unit = vec / norm[:, None]
    approach_raw = vx * unit[:, 0] + vy * unit[:, 1]
    approach = clip(np.mean(np.maximum(approach_raw, 0)) / (np.percentile(speed, 90) + 1e-6))
    speed_score = clip(np.mean(speed) / (diag * 0.15 + 1e-6))
    acc_score = clip(np.mean(acc) / (diag * fps * 0.08 + 1e-6))
    angles = np.unwrap(np.arctan2(xy[:, 1] - frame_h / 2, xy[:, 0] - frame_w / 2))
    circulation = clip(np.std(np.diff(angles)) * 3) if len(angles) > 2 else 0.0
    quality = clip(len(pts) / (fps * 2.0))
    if len(d) >= 3:
        slope = float(np.polyfit(t - t[-1], d / diag, 1)[0])
        distance_slope = clip(max(0.0, -slope) / 0.5)
    else:
        distance_slope = 0.0
    return {
        "quality": quality,
        "zone": zone_score,
        "proximity": proximity,
        "approach": approach,
        "speed": speed_score,
        "circulation": circulation,
        "acceleration": acc_score,
        "dwell": dwell,
        "distance_slope": distance_slope,
    }


@dataclass
class MarkovModel:
    states: list[str]
    transition: np.ndarray

    @classmethod
    def neutral(cls):
        return cls([EXTRACTED], np.array([[1.0]], float))

    @classmethod
    def load(cls, path: str | Path):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        m = np.asarray(d["transition"], float)
        if m.ndim != 2 or m.shape[0] != m.shape[1] or m.shape[0] != len(d["states"]):
            raise ValueError("invalid Markov transition shape")
        rows = m.sum(axis=1)
        if np.any(rows <= 0):
            raise ValueError("Markov row with zero mass")
        m = m / rows[:, None]
        return cls(list(d["states"]), m)

    def absorption_probability(self, start: str | None, horizon: int = 30) -> float:
        if start is None or start not in self.states or EXTRACTED not in self.states:
            return 0.0
        idx = {s: i for i, s in enumerate(self.states)}
        v = np.zeros(len(self.states), float)
        v[idx[start]] = 1.0
        for _ in range(max(0, int(horizon))):
            v = v @ self.transition
        return clip(v[idx[EXTRACTED]])


def discretize_state(x, y, vx, vy, w, h, grid=3) -> str:
    gx = min(grid - 1, max(0, int((x / max(w, 1e-9)) * grid)))
    gy = min(grid - 1, max(0, int((y / max(h, 1e-9)) * grid)))
    direction = ("R" if vx >= 0 else "L") if abs(vx) >= abs(vy) else ("D" if vy >= 0 else "U")
    return f"{gx}:{gy}:{direction}"


def track_state(track: Track, fps: float, w: float, h: float) -> str | None:
    pts = sorted(track.points, key=lambda p: p.frame)
    if len(pts) < 2:
        return None
    a, b = pts[-2], pts[-1]
    dt = max((b.frame - a.frame) / fps, 1e-9)
    return discretize_state(b.x, b.y, (b.x - a.x) / dt, (b.y - a.y) / dt, w, h)


def radiation_score(track: Track, fps: float, zone, horizon=1.0, steps=20, diffusion=30.0) -> dict[str, Any]:
    pts = sorted(track.points, key=lambda p: p.frame)
    if len(pts) < 3:
        return {"score": 0.0, "peak_zone_probability": 0.0, "time_to_peak_s": None}
    pts = pts[-8:]
    t = np.array([p.frame for p in pts], float) / fps
    x = np.array([p.x for p in pts], float)
    y = np.array([p.y for p in pts], float)
    tau = t - t[-1]
    A = np.column_stack([np.ones_like(tau), tau])
    bx, *_ = np.linalg.lstsq(A, x, rcond=None)
    by, *_ = np.linalg.lstsq(A, y, rcond=None)
    residual = np.concatenate([x - A @ bx, y - A @ by])
    sigma0 = float(np.sqrt(np.mean(residual * residual))) if residual.size else 0.0
    x0, y0, x1, y1 = map(float, zone)
    ts = np.linspace(horizon / steps, horizon, steps)
    probs, weights = [], []
    for dt in ts:
        mx, my = bx[0] + bx[1] * dt, by[0] + by[1] * dt
        sigma = math.sqrt(max(2.0, sigma0) ** 2 + 2 * max(diffusion, 0) * dt)
        px = float(ndtr((x1 - mx) / sigma) - ndtr((x0 - mx) / sigma))
        py = float(ndtr((y1 - my) / sigma) - ndtr((y0 - my) / sigma))
        probs.append(clip(px * py))
        weights.append(math.exp(-dt / 0.7))
    arr = np.asarray(probs)
    ww = np.asarray(weights)
    score = float(np.sum(arr * ww) / max(np.sum(ww), 1e-12))
    k = int(np.argmax(arr))
    return {
        "score": clip(score),
        "peak_zone_probability": float(arr[k]),
        "time_to_peak_s": float(ts[k]),
        "sigma0_px": sigma0,
    }


def base_score(f: dict[str, float], markov: float) -> float:
    weights = {
        "zone": 0.20,
        "proximity": 0.18,
        "approach": 0.18,
        "distance_slope": 0.10,
        "markov": 0.16,
        "speed": 0.07,
        "acceleration": 0.04,
        "circulation": 0.03,
        "quality": 0.04,
    }
    vals = dict(f)
    vals["markov"] = markov
    return clip(sum(weights[k] * float(vals.get(k, 0)) for k in weights))
