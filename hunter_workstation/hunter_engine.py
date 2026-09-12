from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from hunter_common import Detection, TrackPoint, Track, EnsembleBallDetector, mask_frame, clip, sha256_file, canonical_hash, lock_report
from hunter_physics import track_features, MarkovModel, track_state, radiation_score, base_score
from hunter_signals import _validated_frequency, _extract_audio_envelope, _resample_signal, _lagged_correlation, _global_signal_context
from hunter_recovery import RecoveryState, HeadRouter
from hunter_identity import _tesseract_available, ocr_ball_number, identity_probabilities_from_ocr, resolve_external_identity_probs
from hunter_tracking import ObservationCentricTracker, tracking_quality_summary

ENGINE_VERSION = "hunter-workstation-0.5.0"


def _collision_candidates(tracks: list[Track], threshold_px: float = 28.0) -> dict[int, int]:
    by_frame: dict[int, list[tuple[int, float, float]]] = {}
    for t in tracks:
        for p in t.points:
            by_frame.setdefault(p.frame, []).append((t.track_id, p.x, p.y))
    counts = {t.track_id: 0 for t in tracks}
    for pts in by_frame.values():
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                a, b = pts[i], pts[j]
                if math.hypot(a[1] - b[1], a[2] - b[2]) <= threshold_px:
                    counts[a[0]] += 1
                    counts[b[0]] += 1
    return counts


def analyze_video(
    video_path: str | Path,
    extraction_zone,
    identity_map: dict[int, int] | None = None,
    identity_probs: dict[str, Any] | None = None,
    markov_model: MarkovModel | None = None,
    chamber_roi=None,
    overlay_masks=None,
    cutoff_seconds: float | None = None,
    radiation_weight: float = 0.10,
    specialist_weight: float = 0.20,
    recovery_dir: str | Path = "recovery",
    auto_ocr: bool = True,
    ocr_every_n_frames: int = 8,
    detector_config: dict[str, Any] | None = None,
    tracker_config: dict[str, Any] | None = None,
    cutoff_verified_by_operator: bool = False,
) -> dict[str, Any]:
    """Analyze only the supplied pre-cutoff video evidence.

    The engine never receives actual winning numbers. A numbered Top-6 is emitted
    only when at least six identities are attached to trajectory-eligible tracks.
    """
    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    w = float(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = float(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if not math.isfinite(fps) or fps <= 0:
        raise RuntimeError("invalid FPS")

    dcfg = dict(detector_config or {})
    tcfg = dict(tracker_config or {})
    detector = EnsembleBallDetector(**dcfg)
    tracker = ObservationCentricTracker(**tcfg)
    ocr_obs: dict[int, list[dict[str, Any]]] = {}
    brightness_series: list[float] = []
    motion_series: list[float] = []
    row_artifact_series: list[float] = []
    prev_centroid: tuple[float, float] | None = None
    fi = 0
    detections_total = 0
    cutoff_frames = None if cutoff_seconds is None else max(1, int(float(cutoff_seconds) * fps))
    ocr_enabled = bool(auto_ocr and _tesseract_available())

    while True:
        ok, frame = cap.read()
        if not ok or (cutoff_frames is not None and fi >= cutoff_frames):
            break
        masked = mask_frame(frame, chamber_roi, overlay_masks)
        gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
        active_pixels = gray[gray > 0]
        brightness_series.append(float(np.mean(active_pixels)) if active_pixels.size else 0.0)
        row_mean = np.mean(gray.astype(float), axis=1)
        denom = float(np.std(gray.astype(float))) + 1e-9
        row_artifact_series.append(clip(float(np.std(np.diff(row_mean))) / denom))

        detections = detector.detect(masked, fi)
        detections_total += len(detections)
        if detections:
            centroid = (
                float(np.mean([d.x for d in detections])),
                float(np.mean([d.y for d in detections])),
            )
            if prev_centroid is None:
                motion_series.append(0.0)
            else:
                motion_series.append(float(math.hypot(centroid[0] - prev_centroid[0], centroid[1] - prev_centroid[1])))
            prev_centroid = centroid
        else:
            motion_series.append(0.0)

        assignments = tracker.update(detections)
        if ocr_enabled and (fi % max(1, int(ocr_every_n_frames)) == 0):
            for tid, d in assignments:
                for evidence in ocr_ball_number(masked, d):
                    row = dict(evidence)
                    row["frame"] = fi
                    ocr_obs.setdefault(tid, []).append(row)
        fi += 1
    cap.release()

    tracking_qc = tracking_quality_summary(tracker.tracks, fps, fi, detections_total)
    eligible_ids = {int(x) for x in tracking_qc.get("eligible_track_ids", [])}
    global_context = _global_signal_context(
        brightness_series, motion_series, fps, video_path, cutoff_seconds, row_artifact_series
    )
    markov = markov_model or MarkovModel.neutral()
    rw = max(0.0, min(0.25, float(radiation_weight)))
    sw = max(0.0, min(0.40, float(specialist_weight)))
    recovery = RecoveryState(recovery_dir)
    head = HeadRouter(recovery, global_context)

    direct = {int(k): int(v) for k, v in (identity_map or {}).items()}
    external = resolve_external_identity_probs(identity_probs)
    auto_map, ocr_diag = identity_probabilities_from_ocr(ocr_obs) if ocr_enabled else (
        {}, {"tracks": {}, "global_assignment": {}, "abstained": []}
    )
    # Explicit/direct evidence has precedence. No unknown track is ever randomly numbered.
    resolved = dict(auto_map)
    resolved.update(external)
    resolved.update(direct)
    identity_mode = "direct_map" if direct else (
        "external_global_assignment" if external else (
            "auto_ocr_global_assignment" if auto_map else "anonymous"
        )
    )

    collisions = _collision_candidates(tracker.tracks)
    ranked: list[dict[str, Any]] = []
    number_scores: dict[int, float] = {}
    for t in tracker.tracks:
        f = track_features(t, fps, w, h, extraction_zone)
        st = track_state(t, fps, w, h)
        mk = markov.absorption_probability(st, 30)
        bs = base_score(f, mk)
        rad = radiation_score(t, fps, extraction_zone)
        ranked.append({
            "track_id": t.track_id,
            "trajectory_eligible": t.track_id in eligible_ids,
            "tracking_diagnostics": tracking_qc.get("per_track", {}).get(str(t.track_id), {}),
            "number": resolved.get(t.track_id),
            "base_score": bs,
            "markov": mk,
            "radiation": rad,
            "state": st,
            "features": f,
            "n_points": len(t.points),
            "collision_candidates": int(collisions.get(t.track_id, 0)),
            "ocr_observations": len(ocr_obs.get(t.track_id, [])),
        })

    for rec in ranked:
        spec = head.evaluate(rec, ranked)
        rec["specialists"] = spec
        f = rec["features"]
        b1 = float(f.get("proximity", 0))
        b2 = float(0.60 * f.get("approach", 0) + 0.40 * f.get("speed", 0))
        b3 = float(base_score(f, 0.0))
        b4 = float(rec["base_score"])
        b5 = (1 - rw) * b4 + rw * float(rec["radiation"]["score"])
        b6 = float(spec["fusion"])
        final = (1 - sw) * b5 + sw * b6
        rec["score"] = float(final)
        rec["baselines"] = {
            "B0_uniform_expected_hits": 0.8,
            "B1_distance": b1,
            "B2_motion": b2,
            "B3_physical": b3,
            "B4_physical_markov": b4,
            "B5_plus_radiation": b5,
            "B6_specialists": b6,
            "B7_full_hybrid": float(final),
        }
        if rec["trajectory_eligible"] and rec["number"] is not None and 1 <= int(rec["number"]) <= 45:
            n = int(rec["number"])
            number_scores[n] = max(number_scores.get(n, -1.0), float(final))

    # Put scientifically usable trajectories first; retain every fragment for audit.
    ranked.sort(key=lambda r: (not bool(r["trajectory_eligible"]), -r["score"], r["track_id"]))
    valid = sorted(number_scores.items(), key=lambda x: (-x[1], x[0]))
    top6 = sorted(n for n, _ in valid[:6]) if len(valid) >= 6 else []

    if not tracking_qc.get("trajectory_gate_pass"):
        top6_status = "tracking_quality_gate_failed"
        top6 = []
    elif len(top6) < 6:
        top6_status = "insufficient_numbered_tracks"
    else:
        top6_status = "locked_candidate"

    numbered_eligible = sum(
        1 for rec in ranked
        if rec.get("trajectory_eligible") and rec.get("number") is not None
    )
    identity_qc = {
        "numbered_eligible_tracks": numbered_eligible,
        "required_for_top6": 6,
        "pass": numbered_eligible >= 6,
        "abstention_enforced": numbered_eligible < 6,
    }

    config = {
        "extraction_zone": list(map(float, extraction_zone)),
        "chamber_roi": None if chamber_roi is None else list(map(float, chamber_roi)),
        "overlay_masks": [list(map(float, x)) for x in (overlay_masks or [])],
        "cutoff_seconds": cutoff_seconds,
        "cutoff_verified_by_operator": bool(cutoff_verified_by_operator),
        "cutoff_policy": "pre_extraction_and_pre_result_required",
        "radiation_weight": rw,
        "specialist_weight": sw,
        "auto_ocr": bool(auto_ocr),
        "ocr_every_n_frames": int(ocr_every_n_frames),
        "detector_config": dcfg,
        "tracker_config": tcfg,
    }
    report = {
        "game": "Saturday Lotto",
        "version": ENGINE_VERSION,
        "scientific_status": "experimental_no_predictive_edge_claim",
        "random_ticket_fallback": False,
        "post_draw_adjustment": False,
        "input_sha256": sha256_file(video_path),
        "config_sha256": canonical_hash(config),
        "protocol": {
            "cutoff_policy": "pre_extraction_and_pre_result_required",
            "cutoff_verified_by_operator": bool(cutoff_verified_by_operator),
            "actual_result_available_to_engine": False,
            "prediction_must_be_locked_before_scoring": True,
        },
        "broadcast_protection": {
            "chamber_roi": chamber_roi,
            "overlay_masks": overlay_masks or [],
            "cutoff_seconds": cutoff_seconds,
        },
        "video": {
            "fps": fps,
            "width": int(w),
            "height": int(h),
            "reported_total_frames": total_frames,
            "frames_processed": fi,
        },
        "detector": {
            "type": "hough_plus_color_contours",
            "detections_total": detections_total,
            "tracks_total": len(tracker.tracks),
            "config": dcfg,
        },
        "tracker": {
            "type": "observation_centric_hungarian_v0_5",
            "config": tcfg,
            "quality": tracking_qc,
        },
        "quality_gate": {
            "trajectory": {
                k: v for k, v in tracking_qc.items() if k != "per_track"
            },
            "identity": identity_qc,
            "top6_allowed": bool(tracking_qc.get("trajectory_gate_pass") and identity_qc["pass"]),
        },
        "markov_trained": len(markov.states) > 1,
        "radiation_weight": rw,
        "specialist_weight": sw,
        "identity_mode": identity_mode,
        "ocr": {
            "requested": bool(auto_ocr),
            "available": _tesseract_available(),
            "enabled": ocr_enabled,
            "observations_total": sum(len(v) for v in ocr_obs.values()),
            "diagnostics": ocr_diag,
        },
        "signals": global_context,
        "anonymous_track_ranking": ranked,
        "top6_status": top6_status,
        "top6": top6,
        "audit": recovery.audit(),
        "config": config,
    }
    return report


def save_report(report: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def score_locked_report(report: dict[str, Any], actual_numbers: list[int] | set[int]) -> dict[str, Any]:
    actual = {int(x) for x in actual_numbers}
    if len(actual) != 6 or any(x < 1 or x > 45 for x in actual):
        raise ValueError("actual result must contain exactly six unique numbers from 1 to 45")
    pred = set(report.get("top6") or [])
    ranked = [
        r.get("number") for r in report.get("anonymous_track_ranking", [])
        if r.get("trajectory_eligible") and r.get("number") is not None
    ]
    return {
        "top6_hits": len(pred & actual),
        "top10_capture": len(actual & set(ranked[:10])),
        "top15_capture": len(actual & set(ranked[:15])),
        "prediction_available": len(pred) == 6,
        "top6_status": report.get("top6_status"),
    }
