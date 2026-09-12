from hunter_randomness_v2 import HunterRandomnessConfig, analyze_hunter_randomness, generate_uniform_draws, generate_alternative, validation_suite


def cfg():
    return HunterRandomnessConfig(monte_carlo_trials=80, calibration_seed=918273)


def test_null_control_not_forced_into_pattern_claim():
    c=cfg()
    draws=generate_uniform_draws(400,config=c,seed=20260913)
    r=analyze_hunter_randomness(draws,c)
    assert r["verdict"] in {"consistent_with_null","inconclusive"}
    assert len(r["persistent_signals"]) == 0
    assert len(r["specialists"]) == 11


def test_frequency_bias_detected():
    c=cfg()
    draws=generate_alternative(400,config=c,seed=20260914,kind="frequency_bias",strength=.40)
    r=analyze_hunter_randomness(draws,c)
    assert r["verdict"] in {"persistent_departure","strong_persistent_departure"}
    assert "M1_FREQUENCY" in r["persistent_signals"]


def test_serial_persistence_detected():
    c=cfg()
    draws=generate_alternative(400,config=c,seed=20260915,kind="serial_persistence",strength=.40)
    r=analyze_hunter_randomness(draws,c)
    assert r["verdict"] in {"persistent_departure","strong_persistent_departure"}
    assert any(x in r["persistent_signals"] for x in {"M2_GAPS","M3_SERIAL","M4_MARKOV"})


def test_periodic_modulation_reaches_periodicity_specialist():
    c=cfg()
    draws=generate_alternative(500,config=c,seed=20260916,kind="periodicity",strength=.45)
    r=analyze_hunter_randomness(draws,c)
    assert r["verdict"] in {"persistent_departure","strong_persistent_departure"}
    assert "M9_PERIODICITY" in r["persistent_signals"]


def test_repeatability_same_data_and_config():
    c=cfg()
    draws=generate_uniform_draws(300,config=c,seed=33)
    a=analyze_hunter_randomness(draws,c)
    b=analyze_hunter_randomness(draws,c)
    assert a["global_p"] == b["global_p"]
    assert a["persistent_signals"] == b["persistent_signals"]


def test_validation_pack_contains_null_and_four_alternatives():
    c=cfg()
    pack=validation_suite(c,n_draws=350,seed=20260913)
    assert len(pack)==5
    assert pack[0]["truth"]=="random"
    assert all(x["truth"]=="structured" for x in pack[1:])
