from molt_gic.core import AXES, bits_from_states, classify_baseline, classify_candidate, changing_lines


def test_candidate_classifier_exhaustive_edge_case():
    assert classify_candidate(0.80, 0.80, 0, -0.09) == "young_yin"


def test_classifier_boundaries():
    assert classify_baseline(0.91, 0.50, 0) == "old_yang"
    assert classify_baseline(0.40, 0.90, 0) == "old_yin"
    assert classify_baseline(0.75, 0.80, 0) == "young_yang"
    assert classify_baseline(0.65, 0.80, 0) == "young_yin"


def test_bits_and_changing_lines_one_indexed():
    states = {a: "young_yang" for a in AXES}
    states["planning"] = "old_yin"
    bits = bits_from_states(states)
    assert bits == "110111"
    stabilities = {a: 1.0 for a in AXES}
    hrr = {a: 0.0 for a in AXES}
    assert changing_lines(states, stabilities, hrr) == [3]
