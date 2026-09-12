from __future__ import annotations

import hunter_engine as h


def test_same_frame_ocr_variants_do_not_count_as_independent_evidence():
    obs={1:[
        {"number":25,"confidence":91,"frame":10,"variant":0},
        {"number":25,"confidence":86,"frame":10,"variant":1},
        {"number":25,"confidence":80,"frame":10,"variant":2},
    ]}
    out,diag=h.identity_probabilities_from_ocr(obs)
    assert out == {}
    assert 1 in diag["abstained"]
    assert diag["tracks"]["1"]["independent_frames"] == 1


def test_repeated_number_on_independent_frames_can_qualify():
    obs={1:[
        {"number":25,"confidence":80,"frame":10,"variant":0},
        {"number":25,"confidence":75,"frame":18,"variant":0},
        {"number":14,"confidence":10,"frame":20,"variant":0},
    ]}
    out,diag=h.identity_probabilities_from_ocr(obs)
    assert out[1] == 25
    assert diag["tracks"]["1"]["top_support_frames"] == 2
