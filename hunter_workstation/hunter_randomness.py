from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RandomnessConfig:
    pool_size: int = 45
    draw_size: int = 6
    monte_carlo_trials: int = 300
    calibration_seed: int = 918273


def _validate_draws(draws: np.ndarray, pool_size: int) -> np.ndarray:
    arr = np.asarray(draws, dtype=np.int16)
    if arr.ndim != 2:
        raise ValueError("draws must be a two-dimensional array")
    if arr.shape[0] < 30:
        raise ValueError("at least 30 draws are required for a meaningful randomness check")
    if arr.shape[1] < 2:
        raise ValueError("each draw must contain at least two numbers")
    if np.any(arr < 1) or np.any(arr > pool_size):
        raise ValueError(f"all numbers must be between 1 and {pool_size}")
    for row in arr:
        if len(set(int(x) for x in row)) != len(row):
            raise ValueError("numbers within each draw must be unique")
    arr = np.sort(arr, axis=1)
    return arr


def parse_draw_text(text: str, pool_size: int = 45, draw_size: int = 6) -> np.ndarray:
    rows: list[list[int]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        for token in [",", ";", "\t", "|"]:
            line = line.replace(token, " ")
        vals = [int(x) for x in line.split()]
        if len(vals) != draw_size:
            raise ValueError(f"each line must contain exactly {draw_size} numbers")
        rows.append(vals)
    if not rows:
        raise ValueError("no draws were found")
    return _validate_draws(np.asarray(rows, dtype=np.int16), pool_size)


def generate_uniform_draws(
    n_draws: int = 600,
    *,
    pool_size: int = 45,
    draw_size: int = 6,
    seed: int = 1,
) -> np.ndarray:
    if not 2 <= draw_size < pool_size:
        raise ValueError("draw_size must be between 2 and pool_size - 1")
    if n_draws < 30:
        raise ValueError("n_draws must be at least 30")
    rng = np.random.default_rng(seed)
    scores = rng.random((n_draws, pool_size))
    draws = np.argpartition(scores, kth=draw_size - 1, axis=1)[:, :draw_size] + 1
    draws.sort(axis=1)
    return draws.astype(np.int16)


def generate_structured_draws(
    n_draws: int = 600,
    *,
    pool_size: int = 45,
    draw_size: int = 6,
    seed: int = 2,
    bias_number: int = 7,
    relative_bias: float = 0.0,
    persistence: float = 0.0,
) -> np.ndarray:
    if not 1 <= bias_number <= pool_size:
        raise ValueError("bias_number is outside the pool")
    if relative_bias < 0:
        raise ValueError("relative_bias cannot be negative")
    if not 0.0 <= persistence <= 1.0:
        raise ValueError("persistence must be between 0 and 1")

    rng = np.random.default_rng(seed)
    weights = np.ones(pool_size, dtype=np.float64)
    weights[bias_number - 1] *= 1.0 + float(relative_bias)
    base_p = weights / weights.sum()
    population = np.arange(1, pool_size + 1)
    out = np.empty((n_draws, draw_size), dtype=np.int16)
    out[0] = np.sort(rng.choice(population, draw_size, replace=False, p=base_p))

    for i in range(1, n_draws):
        forced: list[int] = []
        if persistence > 0 and rng.random() < persistence:
            forced.append(int(rng.choice(out[i - 1])))
        allowed = population[np.isin(population, forced, invert=True)]
        p = base_p[allowed - 1]
        p = p / p.sum()
        rest = rng.choice(allowed, draw_size - len(forced), replace=False, p=p)
        row = np.asarray(forced + rest.tolist(), dtype=np.int16)
        row.sort()
        out[i] = row
    return out


def _metrics(draws: np.ndarray, pool_size: int) -> dict[str, float]:
    n_draws, draw_size = draws.shape
    counts = np.bincount(draws.ravel(), minlength=pool_size + 1)[1:]
    expected = n_draws * draw_size / pool_size
    frequency_chi2 = float(np.sum((counts - expected) ** 2 / expected))

    left = draws[:-1, None, :]
    right = draws[1:, :, None]
    overlaps = np.equal(left, right).any(axis=2).sum(axis=1).astype(np.float64)
    mean_overlap = float(overlaps.mean())

    indicators = np.zeros((n_draws, pool_size), dtype=np.float32)
    indicators[np.arange(n_draws)[:, None], draws - 1] = 1.0
    a = indicators[:-1] - indicators[:-1].mean(axis=0)
    b = indicators[1:] - indicators[1:].mean(axis=0)
    den = np.sqrt((a * a).sum(axis=0) * (b * b).sum(axis=0))
    corr = np.divide((a * b).sum(axis=0), den, out=np.zeros(pool_size), where=den > 1e-9)
    max_lag1_abs = float(np.max(np.abs(corr)))

    pair_ids: list[np.ndarray] = []
    for i in range(draw_size):
        for j in range(i + 1, draw_size):
            pair_ids.append((draws[:, i] - 1) * pool_size + (draws[:, j] - 1))
    pair_counts = np.bincount(np.concatenate(pair_ids), minlength=pool_size * pool_size)
    pair_collision = float(np.sum(pair_counts * (pair_counts - 1) / 2.0))

    probs = counts / counts.sum()
    entropy = float(-np.sum(probs[probs > 0] * np.log2(probs[probs > 0])))
    normalized_entropy = float(entropy / math.log2(pool_size))

    return {
        "frequency_chi2": frequency_chi2,
        "mean_consecutive_overlap": mean_overlap,
        "max_lag1_abs": max_lag1_abs,
        "pair_collision": pair_collision,
        "normalized_entropy": normalized_entropy,
    }


def _null_metrics(config: RandomnessConfig, n_draws: int, draw_size: int) -> np.ndarray:
    rng = np.random.default_rng(config.calibration_seed)
    out = np.empty((config.monte_carlo_trials, 4), dtype=np.float64)
    for i in range(config.monte_carlo_trials):
        scores = rng.random((n_draws, config.pool_size))
        d = np.argpartition(scores, kth=draw_size - 1, axis=1)[:, :draw_size] + 1
        d.sort(axis=1)
        m = _metrics(d.astype(np.int16), config.pool_size)
        out[i] = [
            m["frequency_chi2"],
            m["mean_consecutive_overlap"],
            m["max_lag1_abs"],
            m["pair_collision"],
        ]
    return out


def analyze_randomness(draws: np.ndarray, config: RandomnessConfig | None = None) -> dict:
    config = config or RandomnessConfig()
    arr = _validate_draws(draws, config.pool_size)
    metrics = _metrics(arr, config.pool_size)
    null = _null_metrics(config, len(arr), arr.shape[1])

    center = null.mean(axis=0)
    scale = null.std(axis=0, ddof=1)
    scale = np.where(scale > 1e-12, scale, 1.0)
    observed = np.asarray([
        metrics["frequency_chi2"],
        metrics["mean_consecutive_overlap"],
        metrics["max_lag1_abs"],
        metrics["pair_collision"],
    ])

    z = np.asarray([
        (observed[0] - center[0]) / scale[0],
        abs(observed[1] - center[1]) / scale[1],
        (observed[2] - center[2]) / scale[2],
        (observed[3] - center[3]) / scale[3],
    ])
    null_z = np.column_stack([
        (null[:, 0] - center[0]) / scale[0],
        np.abs(null[:, 1] - center[1]) / scale[1],
        (null[:, 2] - center[2]) / scale[2],
        (null[:, 3] - center[3]) / scale[3],
    ])
    observed_max = float(np.max(z))
    null_max = np.max(null_z, axis=1)
    omnibus_p = float((1 + np.count_nonzero(null_max >= observed_max)) / (config.monte_carlo_trials + 1))

    if omnibus_p < 0.01:
        verdict = "strong_departure_detected"
        label = "Strong departure from the random control"
    elif omnibus_p < 0.05:
        verdict = "departure_detected"
        label = "Departure detected — investigate"
    elif omnibus_p < 0.10:
        verdict = "inconclusive"
        label = "Weak departure / inconclusive"
    else:
        verdict = "consistent_with_randomness"
        label = "Consistent with the random control"

    component_names = ["frequency", "consecutive_overlap", "lag1_dependence", "pair_recurrence"]
    strongest_idx = int(np.argmax(z))
    return {
        "verdict": verdict,
        "label": label,
        "omnibus_p": omnibus_p,
        "strongest_component": component_names[strongest_idx],
        "strongest_z": float(z[strongest_idx]),
        "component_z": {name: float(value) for name, value in zip(component_names, z)},
        "metrics": metrics,
        "n_draws": int(arr.shape[0]),
        "draw_size": int(arr.shape[1]),
        "pool_size": int(config.pool_size),
        "monte_carlo_trials": int(config.monte_carlo_trials),
        "calibration_seed": int(config.calibration_seed),
        "claim_boundary": (
            "This is a calibrated departure-from-randomness test, not a probability that a process is random "
            "and not evidence of lottery predictability."
        ),
    }


def quick_validation_pack(
    *,
    n_draws: int = 600,
    seed: int = 20260913,
    config: RandomnessConfig | None = None,
) -> list[dict]:
    config = config or RandomnessConfig()
    scenarios = [
        (
            "Pure random control",
            "random",
            generate_uniform_draws(n_draws, pool_size=config.pool_size, draw_size=config.draw_size, seed=seed),
        ),
        (
            "Injected frequency bias",
            "structured",
            generate_structured_draws(
                n_draws,
                pool_size=config.pool_size,
                draw_size=config.draw_size,
                seed=seed + 1,
                bias_number=7,
                relative_bias=1.0,
                persistence=0.0,
            ),
        ),
        (
            "Injected serial persistence",
            "structured",
            generate_structured_draws(
                n_draws,
                pool_size=config.pool_size,
                draw_size=config.draw_size,
                seed=seed + 2,
                bias_number=7,
                relative_bias=0.0,
                persistence=0.25,
            ),
        ),
    ]
    results: list[dict] = []
    for name, truth, draws in scenarios:
        analysis = analyze_randomness(draws, config)
        results.append({"scenario": name, "truth": truth, **analysis})
    return results
