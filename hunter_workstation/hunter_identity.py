from __future__ import annotations
import math, re
from typing import Any
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from hunter_common import Detection
try:
    import pytesseract
except Exception:
    pytesseract=None

def _tesseract_available() -> bool:
    if pytesseract is None:
        return False
    try:
        _ = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _safe_ball_crop(frame: np.ndarray, d: Detection, scale: float = 1.35) -> np.ndarray | None:
    h, w = frame.shape[:2]
    rr = max(6, int(round(d.r * scale)))
    x0, x1 = max(0, int(round(d.x)) - rr), min(w, int(round(d.x)) + rr + 1)
    y0, y1 = max(0, int(round(d.y)) - rr), min(h, int(round(d.y)) + rr + 1)
    if x1 - x0 < 12 or y1 - y0 < 12:
        return None
    return frame[y0:y1, x0:x1].copy()


def ocr_ball_number(frame: np.ndarray, d: Detection) -> list[dict[str, Any]]:
    """Deterministic OCR evidence only. Never invent a number when OCR is weak."""
    if not _tesseract_available():
        return []
    crop = _safe_ball_crop(frame, d)
    if crop is None:
        return []
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.copyMakeBorder(gray, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = 255 - otsu
    variants = [clahe, otsu, inv]
    results = []
    config = "--psm 10 -c tessedit_char_whitelist=0123456789"
    for vi, img in enumerate(variants):
        try:
            data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        for txt, conf in zip(data.get("text", []), data.get("conf", [])):
            m = re.search(r"\d{1,2}", str(txt))
            if not m:
                continue
            n = int(m.group(0))
            try:
                c = float(conf)
            except Exception:
                c = -1.0
            if 1 <= n <= 45 and c >= 0:
                results.append({"number": n, "confidence": c, "variant": vi})
    best = {}
    for row in results:
        n = row["number"]
        if n not in best or row["confidence"] > best[n]["confidence"]:
            best[n] = row
    return sorted(best.values(), key=lambda r: (-r["confidence"], r["number"]))


def identity_probabilities_from_ocr(
    observations: dict[int, list[dict[str, Any]]],
    min_observations: int = 2,
    min_mean_confidence: float = 20.0,
    min_top_share: float = 0.55,
    min_margin: float = 0.12,
) -> tuple[dict[int, int], dict[str, Any]]:
    """Conservative per-track OCR posterior + global one-to-one assignment."""
    track_ids = sorted(observations)
    numbers = list(range(1, 46))
    qualified: list[int] = []
    row_probs: list[np.ndarray] = []
    diagnostics: dict[str, Any] = {"tracks": {}, "global_assignment": {}, "abstained": []}
    for tid in track_ids:
        obs = observations.get(tid, [])
        mass = np.ones(45, dtype=float) * 1e-3
        strong_count = 0
        confs = []
        for o in obs:
            n, conf = int(o["number"]), max(0.0, float(o["confidence"]))
            if 1 <= n <= 45:
                mass[n - 1] += max(0.01, conf / 100.0)
                if conf >= min_mean_confidence:
                    strong_count += 1
                    confs.append(conf)
        p = mass / mass.sum()
        order = np.argsort(-p)
        top_i, second_i = int(order[0]), int(order[1])
        top_share, margin = float(p[top_i]), float(p[top_i] - p[second_i])
        mean_conf = float(np.mean(confs)) if confs else 0.0
        diagnostics["tracks"][str(tid)] = {
            "raw_observations": len(obs),
            "strong_observations": strong_count,
            "mean_strong_confidence": round(mean_conf, 3),
            "top_number": top_i + 1,
            "top_probability": round(top_share, 6),
            "margin": round(margin, 6),
        }
        if strong_count >= min_observations and mean_conf >= min_mean_confidence and top_share >= min_top_share and margin >= min_margin:
            qualified.append(tid)
            row_probs.append(p)
        else:
            diagnostics["abstained"].append(tid)
    if not qualified:
        return {}, diagnostics
    mat = np.vstack(row_probs)
    cost = -np.log(np.clip(mat, 1e-12, 1.0))
    rows, cols = linear_sum_assignment(cost)
    out: dict[int, int] = {}
    for r, c in zip(rows, cols):
        tid = qualified[r]
        prob = float(mat[r, c])
        top = float(np.max(mat[r]))
        if prob >= max(0.25, 0.70 * top):
            out[tid] = numbers[c]
            diagnostics["global_assignment"][str(tid)] = {"number": numbers[c], "probability": round(prob, 6)}
        else:
            diagnostics["abstained"].append(tid)
    diagnostics["abstained"] = sorted(set(diagnostics["abstained"]))
    return out, diagnostics


def resolve_external_identity_probs(identity_probs: dict[str, Any] | None) -> dict[int, int]:
    if not identity_probs:
        return {}
    tids = [int(x) for x in identity_probs["track_ids"]]
    nums = [int(x) for x in identity_probs.get("numbers", list(range(1, 46)))]
    p = np.asarray(identity_probs["probabilities"], dtype=float)
    if p.ndim != 2 or p.shape != (len(tids), len(nums)):
        raise ValueError("identity probability matrix shape mismatch")
    cost = -np.log(np.clip(p, 1e-12, 1.0))
    rows, cols = linear_sum_assignment(cost)
    return {tids[r]: nums[c] for r, c in zip(rows, cols)}
