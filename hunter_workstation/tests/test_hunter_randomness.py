import numpy as np
import pytest

from hunter_randomness import (
    RandomnessConfig,
    analyze_randomness,
    generate_structured_draws,
    generate_uniform_draws,
    parse_draw_text,
    quick_validation_pack,
)


def test_uniform_generation_is_deterministic_and_valid():
    a = generate_uniform_draws(80, seed=42)
    b = generate_uniform_draws(80, seed=42)
    assert np.array_equal(a, b)
    assert a.shape == (80, 6)
    assert np.all((a >= 1) & (a <= 45))
    assert all(len(set(map(int, row))) == 6 for row in a)


def test_parse_draw_text_accepts_common_separators():
    lines = []
    for i in range(30):
        row = [(i + j) % 45 + 1 for j in range(6)]
        lines.append(", ".join(map(str, row)))
    parsed = parse_draw_text("\n".join(lines))
    assert parsed.shape == (30, 6)


def test_parse_rejects_duplicate_numbers_within_draw():
    text = "\n".join(["1 2 3 4 5 5"] * 30)
    with pytest.raises(ValueError, match="unique"):
        parse_draw_text(text)


def test_random_control_is_not_forced_into_pattern_claim():
    draws = generate_uniform_draws(500, seed=2026)
    result = analyze_randomness(draws, RandomnessConfig(monte_carlo_trials=120))
    assert result["verdict"] in {"consistent_with_randomness", "inconclusive"}
    assert 0.0 < result["omnibus_p"] <= 1.0


def test_strong_frequency_bias_is_detected():
    draws = generate_structured_draws(600, seed=11, relative_bias=1.5, persistence=0.0)
    result = analyze_randomness(draws, RandomnessConfig(monte_carlo_trials=120))
    assert result["verdict"] in {"strong_departure_detected", "departure_detected"}
    assert result["strongest_component"] in {"frequency", "pair_recurrence"}


def test_serial_persistence_is_detected():
    draws = generate_structured_draws(600, seed=12, relative_bias=0.0, persistence=0.35)
    result = analyze_randomness(draws, RandomnessConfig(monte_carlo_trials=120))
    assert result["verdict"] in {"strong_departure_detected", "departure_detected"}
    assert result["strongest_component"] in {"consecutive_overlap", "lag1_dependence", "pair_recurrence"}


def test_quick_validation_pack_contains_control_and_structured_cases():
    rows = quick_validation_pack(n_draws=300, config=RandomnessConfig(monte_carlo_trials=60))
    assert [r["truth"] for r in rows] == ["random", "structured", "structured"]
    assert rows[0]["scenario"] == "Pure random control"
