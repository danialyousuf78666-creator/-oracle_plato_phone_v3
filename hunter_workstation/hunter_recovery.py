from __future__ import annotations
import json, math
from pathlib import Path
from typing import Any
import numpy as np
from hunter_common import SPECIALISTS, clip, sha256_file

class RecoveryState:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.files = self._load()
        self.legacy_reliability = self._legacy_reliability()

    def _load(self) -> dict[str, dict[str, Any]]:
        out = {}
        names = [
            "shared_memory.json", "session_report.json", "deep_signatures.jsonl", "screen_signatures.jsonl",
            "V0_2_7_CANDIDATE_FREEZE.json", "LEGACY_RECOVERY_MANIFEST.json", "legacy_reliability.json",
        ]
        for name in names:
            p = self.root / name
            if p.exists():
                meta = {"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size}
                if p.suffix == ".jsonl":
                    try:
                        meta["records"] = sum(1 for line in p.open(errors="ignore") if line.strip())
                    except Exception:
                        pass
                out[name] = meta
        return out

    def _legacy_reliability(self) -> dict[str, float]:
        p = self.root / "shared_memory.json"
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out = {}
                for name, rows in (d.get("specialist_history") or {}).items():
                    vals = [clip(r.get("evidence_score", 0)) for r in rows if isinstance(r, dict) and r.get("applicable")]
                    if vals:
                        out[name] = float(np.mean(vals))
                if out:
                    return out
            except Exception:
                pass
        # Public/sanitized fallback: only aggregate specialist reliability, no raw session/video data.
        profile = self.root / "legacy_reliability.json"
        if profile.exists():
            try:
                d = json.loads(profile.read_text(encoding="utf-8"))
                raw = d.get("specialist_reliability") or {}
                return {str(k): clip(v) for k, v in raw.items() if str(k) in SPECIALISTS}
            except Exception:
                pass
        return {}

    def audit(self) -> dict[str, Any]:
        return {
            "recovery_root": str(self.root),
            "loaded_files": self.files,
            "legacy_state_present": bool(self.legacy_reliability),
            "legacy_specialist_reliability": self.legacy_reliability,
        }


class HeadRouter:
    """Compatibility head. Old state calibrates reliability; physical evidence remains current-video evidence."""

    def __init__(self, recovery: RecoveryState, global_context: dict[str, Any] | None = None):
        self.recovery = recovery
        self.global_context = global_context or {}

    def evaluate(self, rec: dict[str, Any], peers: list[dict[str, Any]]) -> dict[str, Any]:
        f = rec["features"]
        q, prox, app = clip(f.get("quality")), clip(f.get("proximity")), clip(f.get("approach"))
        sp, circ, zone = clip(f.get("speed")), clip(f.get("circulation")), clip(f.get("zone"))
        mk, rad = clip(rec.get("markov")), clip(rec.get("radiation", {}).get("score"))
        peer = [float(p.get("base_score", 0)) for p in peers if p is not rec]
        relation = clip(1 - abs(float(rec.get("base_score", 0)) - sum(peer) / len(peer))) if peer else 0.0
        gc = self.global_context
        mf = gc.get("motion_frequency") or {}
        freq_score = clip(math.log1p(float(mf.get("strength", 0))) / math.log(100.0)) if mf.get("validated") else 0.0
        optical_reliability = 1.0 - clip(gc.get("optical_nuisance_score", 0.0))
        acoustic = clip(gc.get("acoustic_activity_score", 0.0))
        resonance = clip(gc.get("resonance_candidate_score", 0.0))
        av_corr = clip(abs(float((gc.get("audio_visual") or {}).get("correlation", 0.0))))
        scores = {
            "M1_VISUAL": q,
            "M2_MOTION": clip(0.55 * app + 0.45 * sp),
            "M3_FREQUENCY": clip(0.65 * freq_score + 0.35 * circ),
            "M4_OPTICAL": clip(0.55 * optical_reliability + 0.25 * q + 0.20 * prox),
            "M5_GEOMETRY": clip(0.50 * prox + 0.35 * zone + 0.15 * f.get("distance_slope", 0)),
            "M6_ACOUSTIC": acoustic,
            "M7_RESONANCE": resonance,
            "M8_ANOMALY": clip(q * (1 - abs(app - prox)) * (0.6 + 0.4 * optical_reliability)),
            "M9_PROPAGATION": clip(0.55 * mk + 0.45 * rad),
            "M10_RELATIONSHIP": clip(0.65 * relation + 0.35 * av_corr),
            "M11_CHALLENGER": clip(prox * (0.75 + 0.25 * optical_reliability)),
        }
        base_weights = {
            "M1_VISUAL": 0.10, "M2_MOTION": 0.16, "M3_FREQUENCY": 0.06, "M4_OPTICAL": 0.08,
            "M5_GEOMETRY": 0.15, "M6_ACOUSTIC": 0.03, "M7_RESONANCE": 0.03, "M8_ANOMALY": 0.07,
            "M9_PROPAGATION": 0.17, "M10_RELATIONSHIP": 0.08, "M11_CHALLENGER": 0.09,
        }
        # Old learned state is allowed to down/up-weight reliability but never substitutes for current-video evidence.
        rel = self.recovery.legacy_reliability
        weights = {
            k: w * (0.60 + 0.40 * clip(rel.get(k, 1.0))) if w > 0 else 0.0
            for k, w in base_weights.items()
        }
        denom = sum(weights.values()) or 1.0
        fusion = clip(sum(scores[k] * weights[k] for k in SPECIALISTS) / denom)
        return {
            "scores": scores,
            "weights": weights,
            "fusion": fusion,
            "mode": "legacy_reliability_plus_current_physics" if rel else "current_physics_compatibility",
            "random_completion": False,
        }
