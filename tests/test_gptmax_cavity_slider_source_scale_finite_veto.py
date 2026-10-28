"""MAX negative authority tests for source-free cavity-slider shadow producer."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_structural_cavity_slider_pocket_host_authority import (
    CavitySliderClassification as C, StructuralCavitySliderPocketHostAuthority,
)


def evaluate(**kwargs):
    values = dict(strike_jamb=(100.0, 200.0), pocket_mouth_jamb=(146.48, 200.0),
                  pocket_back_stud=(195.0, 200.0), host_through_wall_id="physical-wall-1")
    values.update(kwargs)
    return StructuralCavitySliderPocketHostAuthority().evaluate_cavity_slider(**values)


def test_missing_scale_keeps_geometry_but_no_metric_or_source_grant():
    r = evaluate()
    assert r.status is Status.ABSTAINED
    assert r.classification is C.ABSTAINED_UNVERIFIED_SCALE
    assert r.first_remaining_gate == "source_viewport_scale_receipt_missing"
    assert r.clear_span_m is None and r.pocket_depth_m is None
    assert r.total_frame_extent_m is None
    assert r.to_dict()["pocket_depth_m"] is None
    assert r.shadow_only and not r.takeoff_eligible and not r.commercial_projection_allowed


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "0.01764", 0, -1])
def test_invalid_scale_rejected(bad):
    with pytest.raises(ValueError, match="scale_ratio"):
        evaluate(scale_ratio=bad)


@pytest.mark.parametrize("field", ["strike_jamb", "pocket_mouth_jamb", "pocket_back_stud"])
@pytest.mark.parametrize("point", [(float("nan"), 1), (float("inf"), 1), (1, float("-inf")),
                                     (True, 1), ("1", 1), (1,), None, (10**500, 1)])
def test_malformed_or_nonfinite_points_rejected(field, point):
    with pytest.raises(ValueError, match="finite numeric coordinates"):
        evaluate(scale_ratio=0.01764, **{field: point})


@pytest.mark.parametrize("field,bad", [("host_through_wall_id", ""), ("host_through_wall_id", " "),
                                      ("host_through_wall_id", None), ("context_label", ""),
                                      ("context_label", True)])
def test_missing_host_or_context_cannot_mint_candidate(field, bad):
    with pytest.raises(ValueError, match="nonempty"):
        evaluate(scale_ratio=0.01764, **{field: bad})


@pytest.mark.parametrize("kwargs", [
    {"strike_jamb": (-1e308, 0), "pocket_mouth_jamb": (1e308, 0)},
    {"scale_ratio": 1e308},
    {"scale_ratio": 5e-324},
])
def test_finite_inputs_cannot_overflow_arithmetic(kwargs):
    with pytest.raises(ValueError, match="remain finite"):
        evaluate(**({"scale_ratio": 0.01764} | kwargs))


def test_explicit_unverified_numeric_ratio_remains_noncommercial_candidate():
    r = evaluate(scale_ratio=0.01764)
    assert r.classification is C.CAVITY_SLIDER_GEOMETRIC_CANDIDATE
    assert r.status is Status.CANDIDATE
    assert r.first_remaining_gate == "source_cavity_slider_host_and_scale_unproven"
    assert r.clear_span_m == pytest.approx(46.48 * 0.01764)
    assert r.shadow_only and not r.takeoff_eligible and not r.commercial_projection_allowed
    assert "confirmed" not in r.notes.lower()


def test_stable_id_replay_and_source_neutral_context_scale_geometry_separation():
    r = evaluate(scale_ratio=0.01764)
    assert r == evaluate(scale_ratio=0.01764)
    variants = [evaluate(scale_ratio=0.02), evaluate(scale_ratio=0.01764, context_label="other"),
                evaluate(scale_ratio=0.01764, host_through_wall_id="physical-wall-2"),
                evaluate(scale_ratio=0.01764, pocket_back_stud=(195.001, 200.0))]
    assert len({x.contract_id for x in [r, *variants]}) == 5
    assert all(x.shadow_only and not x.takeoff_eligible for x in variants)


def test_rotation_and_translation_preserve_candidate_verdict_not_source_identity():
    base = evaluate(scale_ratio=0.01764)
    def rotate(p):
        return (-p[1] + 300, p[0] - 100)
    rotated = evaluate(scale_ratio=0.01764, strike_jamb=rotate((100.0, 200.0)),
                       pocket_mouth_jamb=rotate((146.48, 200.0)),
                       pocket_back_stud=rotate((195.0, 200.0)))
    assert rotated.classification is base.classification
    assert rotated.clear_span_pt == pytest.approx(base.clear_span_pt)
    assert rotated.pocket_depth_pt == pytest.approx(base.pocket_depth_pt)
    assert rotated.contract_id != base.contract_id
