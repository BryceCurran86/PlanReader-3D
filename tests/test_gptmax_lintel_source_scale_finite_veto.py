"""Fail-closed post-merge lintel geometry: no guessed source scale or FIRM bearing.

These are source-neutral negative/positive shadow controls, not original-positive
PDF, wall, schedule, customer or frozen Full Plan V2 verification.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_structural_lintel_pier_bearing_authority import (
    LintelBearingClassification as Class,
    LintelMaterialType,
    StructuralLintelPierBearingAuthority,
)


def _eval(**overrides):
    values = {
        "jamb_a": (100.0, 200.0),
        "jamb_b": (200.0, 200.0),
        "left_pier_width_pt": 25.0,
        "right_pier_width_pt": 25.0,
        "left_bearing_length_pt": 8.5,
        "right_bearing_length_pt": 8.5,
        "left_pier_id": "left-original",
        "right_pier_id": "right-original",
        "context_label": "opening-one",
        "lintel_material": LintelMaterialType.STEEL_ANGLE,
    }
    values.update(overrides)
    return StructuralLintelPierBearingAuthority().evaluate_lintel_bearing(**values)


def test_default_missing_scale_abstains_and_never_invents_metric_area_or_length():
    r = _eval()
    assert r.status is S.ABSTAINED
    assert r.classification is Class.ABSTAINED_UNVERIFIED_SCALE
    assert r.first_remaining_gate == "source_viewport_scale_receipt_missing"
    assert r.clear_span_m is None
    assert r.total_lintel_length_m is None
    assert r.left_bearing.pier_width_m is None
    assert r.left_bearing.bearing_length_m is None
    assert r.right_bearing.bearing_length_m is None
    assert r.to_dict()["clear_span_m"] is None
    assert r.to_dict()["left_bearing"]["bearing_length_m"] is None
    assert r.commercial_projection_allowed is False
    assert r.takeoff_eligible is False
    assert r.shadow_only is True


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), float("-inf"), 0.0, -0.1, True, "0.01764"])
def test_invalid_explicit_scale_never_constructs_candidate(scale):
    with pytest.raises(ValueError, match="scale_ratio"):
        _eval(scale_ratio=scale)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "25"])
@pytest.mark.parametrize("name", [
    "left_pier_width_pt", "right_pier_width_pt",
    "left_bearing_length_pt", "right_bearing_length_pt",
])
def test_nonfinite_or_non_numeric_bearing_and_pier_support_rejected(name, bad):
    with pytest.raises(ValueError, match="finite nonnegative"):
        _eval(scale_ratio=0.01764, **{name: bad})


@pytest.mark.parametrize("name", [
    "left_pier_width_pt", "right_pier_width_pt",
    "left_bearing_length_pt", "right_bearing_length_pt",
])
def test_negative_bearing_and_pier_support_rejected(name):
    with pytest.raises(ValueError, match="finite nonnegative"):
        _eval(scale_ratio=0.01764, **{name: -1.0})


@pytest.mark.parametrize("bad_point", [
    (float("nan"), 200.0), (float("inf"), 200.0),
    (100.0, float("-inf")), (True, 200.0), ("100", 200.0),
    (1.0,), None,
])
@pytest.mark.parametrize("name", ["jamb_a", "jamb_b"])
def test_nonfinite_malformed_jambs_rejected(name, bad_point):
    with pytest.raises(ValueError, match="finite numeric coordinates"):
        _eval(scale_ratio=0.01764, **{name: bad_point})


@pytest.mark.parametrize("field", ["left_pier_id", "right_pier_id", "context_label"])
@pytest.mark.parametrize("invalid", ["", " ", None, 8])
def test_missing_scope_labels_cannot_make_stable_source_identity(field, invalid):
    with pytest.raises(ValueError, match="nonempty"):
        _eval(scale_ratio=0.01764, **{field: invalid})


def test_no_source_positive_or_code_compliance_claim_even_with_explicit_numeric_scale():
    r = _eval(scale_ratio=0.01764)
    assert r.status is S.CANDIDATE
    assert r.classification is Class.LINTEL_BEARING_GEOMETRIC_CANDIDATE
    assert r.first_remaining_gate == "source_lintel_host_scale_and_specification_unproven"
    assert r.clear_span_m == pytest.approx(1.764)
    assert r.left_bearing.is_bearing_compliant is False
    assert r.right_bearing.is_bearing_compliant is False
    assert "not authenticated" in r.notes
    assert r.commercial_projection_allowed is False
    assert r.takeoff_eligible is False
    assert r.shadow_only is True
    assert r.to_dict()["classification"] != "lintel_bearing_confirmed"


def test_geometry_and_numeric_scale_identity_cannot_alias_other_piers():
    a = _eval(scale_ratio=0.01764)
    repeat = _eval(scale_ratio=0.01764)
    assert a == repeat
    changes = (
        _eval(scale_ratio=0.01),
        _eval(scale_ratio=0.01764, left_pier_id="other-physical-pier"),
        _eval(scale_ratio=0.01764, right_pier_id="other-physical-pier"),
        _eval(scale_ratio=0.01764, context_label="other-opening"),
        _eval(scale_ratio=0.01764, lintel_callout_text="LVL header"),
    )
    assert len({x.contract_id for x in (a, *changes)}) == len(changes) + 1
    assert a.contract_id == _eval(
        scale_ratio=0.01764, jamb_a=(200.0, 200.0), jamb_b=(100.0, 200.0)
    ).contract_id
    assert a.clear_span_m != changes[0].clear_span_m


def test_reference_minimum_uses_explicit_scale_not_hardcoded_page_points():
    # Both draw 8.5pt of bearing. At 1cm/pt it is below the 100mm
    # shadow example; at 2cm/pt it is above. Neither proves approved code.
    small = _eval(scale_ratio=0.01)
    large = _eval(scale_ratio=0.02)
    assert small.status is S.ABSTAINED
    assert small.classification is Class.ABSTAINED_INSUFFICIENT_BEARING
    assert large.status is S.CANDIDATE
    assert large.classification is Class.LINTEL_BEARING_GEOMETRIC_CANDIDATE


def test_overhang_reference_scales_with_units_and_stays_source_unverified():
    r = _eval(
        scale_ratio=0.01, left_bearing_length_pt=25.0,
        right_bearing_length_pt=12.0,
        left_pier_width_pt=30.0, right_pier_width_pt=30.0,
    )
    assert r.status is S.CANDIDATE
    assert r.first_remaining_gate == "source_lintel_host_scale_and_specification_unproven"


def test_unproven_or_invalid_material_cannot_promote_unsupported_kind():
    with pytest.raises(ValueError, match="lintel_material"):
        _eval(scale_ratio=0.01764, lintel_material="steel_angle")
    with pytest.raises(ValueError, match="lintel_callout_text"):
        _eval(scale_ratio=0.01764, lintel_callout_text=12)


def test_missing_pier_remains_distinct_negative_with_explicit_scale():
    r = _eval(scale_ratio=0.01764, left_pier_width_pt=0)
    assert r.status is S.ABSTAINED
    assert r.classification is Class.ABSTAINED_MISSING_HOST_PIER
    assert r.takeoff_eligible is False
