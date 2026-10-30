"""Fail-closed shadow regressions for wall-thickness step/reveal hypotheses."""

from __future__ import annotations

import math

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_wall_thickness_step_reveal_authority import (
    RevealAlignmentDatum,
    SteppedWallApertureClassification,
    StructuralWallThicknessStepRevealAuthority,
)


@pytest.fixture
def authority() -> StructuralWallThicknessStepRevealAuthority:
    return StructuralWallThicknessStepRevealAuthority()


def inputs(**changes):
    kwargs = dict(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(200.0, 200.0),
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
        datum_offset_pt=0.0,
        datum_alignment=RevealAlignmentDatum.EXTERIOR_FLUSH,
        scale_ratio=0.01764,
        context_label="STEPPED_WALL_OPENING",
    )
    kwargs.update(changes)
    return kwargs


METRIC_FIELDS = (
    "clear_span_m", "left_wall_thickness_mm",
    "right_wall_thickness_mm", "reveal_depth_mm",
)


def assert_shadow(record):
    assert record.shadow_only is True
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False


def assert_null_metrics(record):
    for field in METRIC_FIELDS:
        assert getattr(record, field) is None
        assert record.to_dict()[field] is None


def test_explicit_geometry_is_candidate_not_confirmed(authority):
    result = authority.evaluate_stepped_wall_aperture(**inputs())
    assert result.classification == SteppedWallApertureClassification.GEOMETRIC_CANDIDATE
    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert result.first_remaining_gate == "original_source_host_scale_and_reveal_unverified"
    assert result.clear_span_pt == pytest.approx(100.0)
    assert result.clear_span_m == pytest.approx(1.764)
    assert result.reveal_depth_pt == pytest.approx(8.5)
    assert result.reveal_depth_mm == pytest.approx(149.94)
    assert result.centerline_step_offset_pt == pytest.approx(4.25)
    assert "NOT a source-confirmed" in result.notes
    assert_shadow(result)


@pytest.mark.parametrize("missing", [
    {"scale_ratio": None},
    {"datum_offset_pt": None},
    {"datum_alignment": None},
    {"scale_ratio": None, "datum_offset_pt": None, "datum_alignment": None},
])
def test_missing_source_inputs_abstain_without_metric_claim(authority, missing):
    record = authority.evaluate_stepped_wall_aperture(**inputs(**missing))
    assert record.classification == SteppedWallApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert record.first_remaining_gate == "original_source_scale_or_datum_unverified"
    assert record.clear_span_pt == pytest.approx(100.0)
    assert_null_metrics(record)
    assert_shadow(record)
    assert record.contract_id == authority.evaluate_stepped_wall_aperture(**inputs(**missing)).contract_id


def test_no_default_scale_or_datum_can_mint_confirmed_opening(authority):
    record = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0), jamb_datum_b=(200.0, 200.0),
        left_thickness_pt=13.6, right_thickness_pt=5.1,
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert record.classification != SteppedWallApertureClassification.STEPPED_WALL_APERTURE_CONFIRMED
    assert_null_metrics(record)
    assert_shadow(record)


@pytest.mark.parametrize("field,value", [
    ("scale_ratio", float("nan")), ("scale_ratio", float("inf")),
    ("scale_ratio", -1.0), ("scale_ratio", 0.0),
    ("scale_ratio", True), ("scale_ratio", 10 ** 1000),
    ("datum_offset_pt", float("nan")), ("datum_offset_pt", float("inf")),
    ("datum_offset_pt", True), ("datum_offset_pt", 10 ** 1000),
    ("left_thickness_pt", float("nan")),
    ("left_thickness_pt", float("inf")),
    ("left_thickness_pt", 0.0),
    ("left_thickness_pt", -1.0),
    ("left_thickness_pt", True),
    ("left_thickness_pt", 10 ** 1000),
    ("right_thickness_pt", float("-inf")),
    ("right_thickness_pt", 0.0),
    ("right_thickness_pt", 10 ** 1000),
    ("datum_alignment", "exterior_flush"),
    ("context_label", ""),
])
def test_malformed_or_untrusted_numeric_and_enum_inputs_fail_closed(authority, field, value):
    with pytest.raises(ValueError):
        authority.evaluate_stepped_wall_aperture(**inputs(**{field: value}))


@pytest.mark.parametrize("point", [
    (float("nan"), 200.0),
    (float("inf"), 200.0),
    (10 ** 1000, 200.0),
    (True, 200.0),
    ("100", 200.0),
    (100.0,),
    None,
])
def test_malformed_jamb_fails_closed(authority, point):
    with pytest.raises(ValueError):
        authority.evaluate_stepped_wall_aperture(**inputs(jamb_datum_a=point))


def test_overflowed_geometric_span_and_metric_conversion_fail_closed(authority):
    for changed in (
        {"jamb_datum_a": (-1e308, 0.0), "jamb_datum_b": (1e308, 0.0)},
        {"scale_ratio": 1e308},
    ):
        with pytest.raises(ValueError):
            authority.evaluate_stepped_wall_aperture(**inputs(**changed))


@pytest.mark.parametrize("changed,expected,gate", [
    ({"jamb_datum_b": (110.0, 200.0)},
     SteppedWallApertureClassification.ABSTAINED_DEGENERATE_SPAN,
     "clear_span_out_of_bounds"),
    ({"datum_offset_pt": 3.5},
     SteppedWallApertureClassification.ABSTAINED_UNALIGNED_DATUM,
     "datum_faces_divergent"),
    ({"left_thickness_pt": 25.0, "right_thickness_pt": 5.0},
     SteppedWallApertureClassification.ABSTAINED_EXCESSIVE_THICKNESS_DISCREPANCY,
     "thickness_step_excessive"),
])
def test_rejected_hypotheses_never_serialize_hypothetical_metric_values(
    authority, changed, expected, gate
):
    result = authority.evaluate_stepped_wall_aperture(**inputs(**changed))
    assert result.classification == expected
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.first_remaining_gate == gate
    assert_null_metrics(result)
    assert_shadow(result)


def test_diagnostic_identity_is_full_precision_scale_datum_and_context_bound(authority):
    original = inputs()
    first = authority.evaluate_stepped_wall_aperture(**original)
    reversed_jambs = inputs(
        jamb_datum_a=original["jamb_datum_b"],
        jamb_datum_b=original["jamb_datum_a"],
    )
    assert first.contract_id == authority.evaluate_stepped_wall_aperture(**reversed_jambs).contract_id
    for changed in (
        {"jamb_datum_b": (200.001, 200.0)},
        {"left_thickness_pt": 13.601},
        {"datum_offset_pt": 0.001},
        {"scale_ratio": 0.018},
        {"context_label": "ANOTHER_CONTEXT"},
        {"datum_alignment": RevealAlignmentDatum.INTERIOR_FLUSH},
    ):
        assert first.contract_id != authority.evaluate_stepped_wall_aperture(
            **inputs(**changed)
        ).contract_id
    assert_shadow(first)


def test_translation_rotation_and_input_order_do_not_change_physical_span(authority):
    base = authority.evaluate_stepped_wall_aperture(**inputs())
    translated = authority.evaluate_stepped_wall_aperture(**inputs(
        jamb_datum_a=(1000.0, -300.0), jamb_datum_b=(1100.0, -300.0)))
    rotated = authority.evaluate_stepped_wall_aperture(**inputs(
        jamb_datum_a=(0.0, 0.0), jamb_datum_b=(0.0, 100.0)))
    assert translated.clear_span_pt == rotated.clear_span_pt == base.clear_span_pt
    assert translated.reveal_depth_pt == rotated.reveal_depth_pt == base.reveal_depth_pt
    assert translated.contract_id != base.contract_id
    assert rotated.contract_id != base.contract_id


def test_inputs_are_unchanged_and_record_has_no_commercial_authority(authority):
    kw = inputs()
    before = dict(kw)
    first = authority.evaluate_stepped_wall_aperture(**kw)
    second = authority.evaluate_stepped_wall_aperture(**kw)
    assert kw == before
    assert first == second
    assert math.isfinite(first.clear_span_pt)
    assert first.to_dict()["takeoff_eligible"] is False
    assert first.to_dict()["commercial_projection_allowed"] is False


def test_subround_positive_shadow_metrics_remain_nonzero_on_serialization(authority):
    record = authority.evaluate_stepped_wall_aperture(
        **inputs(scale_ratio=1e-8))
    assert record.status == EvidenceResolutionStatus.CANDIDATE
    payload = record.to_dict()
    for field in METRIC_FIELDS:
        assert getattr(record, field) > 0
        assert payload[field] > 0
        assert payload[field] == getattr(record, field)
    assert_shadow(record)


@pytest.mark.parametrize("coordinate", [2**53 + 1, 2**53 + 2, -(2**53 + 1)])
def test_unrepresentable_integer_jambs_cannot_alias_shadow_identity(authority, coordinate):
    with pytest.raises(ValueError, match="finite real coordinates"):
        authority.evaluate_stepped_wall_aperture(
            **inputs(jamb_datum_a=(coordinate, 200.0)))


def test_positive_metric_conversion_underflow_fails_closed(authority):
    with pytest.raises(ValueError, match="underflow"):
        authority.evaluate_stepped_wall_aperture(
            **inputs(left_thickness_pt=5e-324, right_thickness_pt=5e-324))


def test_genuine_zero_reveal_remains_zero_without_false_positive(authority):
    record = authority.evaluate_stepped_wall_aperture(
        **inputs(left_thickness_pt=5.1, right_thickness_pt=5.1))
    assert record.status == EvidenceResolutionStatus.CANDIDATE
    assert record.reveal_depth_pt == 0
    assert record.to_dict()["reveal_depth_mm"] == 0
    assert_shadow(record)


def test_shadow_receipt_retains_full_precision_native_and_metric_evidence(authority):
    """Distinct exact-ID hypotheses must not serialize as the same evidence."""
    original = authority.evaluate_stepped_wall_aperture(**inputs())
    original_payload = original.to_dict()
    assert original_payload["jamb_right_datum"] == [200.0, 200.0]
    assert original_payload["datum_offset_pt"] == 0.0
    assert original_payload["scale_ratio"] == 0.01764
    assert original_payload["context_label"] == "STEPPED_WALL_OPENING"

    for change in (
        {"jamb_datum_b": (200.000001, 200.0)},
        {"left_thickness_pt": 13.600001},
        {"right_thickness_pt": 5.100001},
        {"scale_ratio": 0.017640000001},
        {"datum_offset_pt": 0.000001},
        {"context_label": "STEPPED_WALL_OPENING_OTHER"},
    ):
        distinct = authority.evaluate_stepped_wall_aperture(**inputs(**change))
        assert distinct.contract_id != original.contract_id
        assert distinct.to_dict() != original_payload
        assert distinct.to_dict()["commercial_projection_allowed"] is False
        assert distinct.to_dict()["takeoff_eligible"] is False


def test_shadow_serialization_keeps_small_nonzero_values_and_true_zero(authority):
    first = authority.evaluate_stepped_wall_aperture(
        **inputs(left_thickness_pt=5.10000001, right_thickness_pt=5.1,
                 scale_ratio=1e-8))
    serialized = first.to_dict()
    assert serialized["reveal_depth_pt"] == first.reveal_depth_pt > 0
    assert serialized["centerline_step_offset_pt"] == first.centerline_step_offset_pt > 0
    assert serialized["reveal_depth_mm"] == first.reveal_depth_mm > 0
    assert serialized["clear_span_m"] == first.clear_span_m > 0
    assert serialized["left_wall_thickness_mm"] == first.left_wall_thickness_mm > 0
    assert serialized["right_wall_thickness_mm"] == first.right_wall_thickness_mm > 0
    assert_shadow(first)

    zero = authority.evaluate_stepped_wall_aperture(
        **inputs(left_thickness_pt=5.1, right_thickness_pt=5.1))
    assert zero.to_dict()["reveal_depth_pt"] == 0
    assert zero.to_dict()["reveal_depth_mm"] == 0


def test_abstention_receipt_preserves_missing_inputs_without_metrics(authority):
    record = authority.evaluate_stepped_wall_aperture(
        **inputs(scale_ratio=None, datum_offset_pt=None, datum_alignment=None))
    payload = record.to_dict()
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert payload["scale_ratio"] is None
    assert payload["datum_offset_pt"] is None
    assert payload["datum_alignment"] is None
    assert_null_metrics(record)
    assert_shadow(record)


def test_shadow_serialized_coordinate_lists_cannot_mutate_frozen_record(authority):
    record = authority.evaluate_stepped_wall_aperture(**inputs())
    before = record.to_dict()
    before["jamb_left_datum"][0] = -12345.0
    before["jamb_right_datum"][1] = -12345.0
    assert record.jamb_left_datum == (100.0, 200.0)
    assert record.jamb_right_datum == (200.0, 200.0)
    assert record.to_dict()["jamb_left_datum"] == [100.0, 200.0]
    assert record.to_dict()["jamb_right_datum"] == [200.0, 200.0]
    assert_shadow(record)


@pytest.mark.parametrize("field", ["jamb_datum_a", "jamb_datum_b"])
@pytest.mark.parametrize("huge", [float(2**53) + 2.0, -(float(2**53) + 2.0)])
def test_oversized_float_jamb_coordinates_rejected_before_shadow_identity(authority, field, huge):
    # Oversized native floats can alias distinct source coordinates.
    point = [huge, 200.0]
    with pytest.raises(ValueError, match=f"{field} requires finite real coordinates"):
        authority.evaluate_stepped_wall_aperture(**inputs(**{field: point}))
    assert point == [huge, 200.0]


def test_inclusive_float_coordinate_identity_boundary_is_shadow_only(authority):
    kwargs = inputs(
        jamb_datum_a=(float(2**53) - 100.0, 200.0),
        jamb_datum_b=(float(2**53), 200.0),
        scale_ratio=None,
    )
    before = dict(kwargs)
    first = authority.evaluate_stepped_wall_aperture(**kwargs)
    second = authority.evaluate_stepped_wall_aperture(**kwargs)
    assert kwargs == before
    assert first == second
    assert first.jamb_right_datum == (float(2**53), 200.0)
    assert first.clear_span_pt == 100.0
    assert first.classification == SteppedWallApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
    assert first.first_remaining_gate == "original_source_scale_or_datum_unverified"
    assert_null_metrics(first)
    assert_shadow(first)


@pytest.mark.parametrize("bad", [
    "", " ", " STEPPED_WALL_OPENING", "STEPPED_WALL_OPENING ",
    "STEPPED\nWALL", "STEPPED\tWALL", "STEPPED\x00WALL",
    "STEPPED\u200bWALL", True, None, 123,
])
def test_stepped_wall_context_identity_rejects_padding_and_controls(
    authority, bad,
):
    kw = inputs()
    before = dict(kw)
    with pytest.raises(ValueError, match="exact printable source identity"):
        authority.evaluate_stepped_wall_aperture(
            **(kw | {"context_label": bad})
        )
    assert kw == before


def test_stepped_wall_context_exact_identity_replay_and_no_commercial(
    authority,
):
    kw = inputs()
    first = authority.evaluate_stepped_wall_aperture(**kw)
    second = authority.evaluate_stepped_wall_aperture(**kw)
    swapped = authority.evaluate_stepped_wall_aperture(**(
        kw | {
            "jamb_datum_a": kw["jamb_datum_b"],
            "jamb_datum_b": kw["jamb_datum_a"],
        }
    ))
    other = authority.evaluate_stepped_wall_aperture(**(
        kw | {"context_label": "ANOTHER_CONTEXT"}
    ))
    assert first == second
    assert first.contract_id == swapped.contract_id
    assert first.contract_id != other.contract_id
    assert first.context_label == "STEPPED_WALL_OPENING"
    assert first.to_dict()["context_label"] == "STEPPED_WALL_OPENING"
    assert first.classification is SteppedWallApertureClassification.GEOMETRIC_CANDIDATE
    assert first.first_remaining_gate == "original_source_host_scale_and_reveal_unverified"
    assert_shadow(first)
    assert kw == inputs()


def test_stepped_wall_missing_scale_keeps_null_metrics_with_exact_context(
    authority,
):
    result = authority.evaluate_stepped_wall_aperture(
        **inputs(scale_ratio=None)
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.classification is SteppedWallApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
    assert result.first_remaining_gate == "original_source_scale_or_datum_unverified"
    assert_null_metrics(result)
    assert_shadow(result)


def test_stepped_wall_context_rejects_string_subclass(authority):
    class Impostor(str):
        pass

    with pytest.raises(ValueError, match="exact printable source identity"):
        authority.evaluate_stepped_wall_aperture(
            **inputs(context_label=Impostor("STEPPED_WALL_OPENING"))
        )


def test_public_reveal_record_replacement_cannot_mint_source_or_commercial_authority(
    authority: StructuralWallThicknessStepRevealAuthority,
):
    from dataclasses import replace

    candidate = authority.evaluate_stepped_wall_aperture(**inputs())
    abstained = authority.evaluate_stepped_wall_aperture(**inputs(scale_ratio=None))
    assert candidate.classification is SteppedWallApertureClassification.GEOMETRIC_CANDIDATE
    assert candidate.status is EvidenceResolutionStatus.CANDIDATE
    assert abstained.classification is SteppedWallApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
    assert abstained.status is EvidenceResolutionStatus.ABSTAINED
    assert replace(candidate) == candidate and replace(abstained) == abstained
    for changes in (
        {"classification": SteppedWallApertureClassification.STEPPED_WALL_APERTURE_CONFIRMED},
        {"status": EvidenceResolutionStatus.CORROBORATED},
        {"commercial_projection_allowed": True},
        {"takeoff_eligible": True},
        {"shadow_only": False},
    ):
        with pytest.raises(ValueError, match="source-neutral reveal"):
            replace(candidate, **changes)
    for changes in (
        {"first_remaining_gate": "none"},
        {"first_remaining_gate": "source_verified_by_caller"},
        {"status": EvidenceResolutionStatus.ABSTAINED},
    ):
        with pytest.raises(ValueError, match="classification and source gate conflict"):
            replace(candidate, **changes)
    for changes in (
        {"first_remaining_gate": "none"},
        {"status": EvidenceResolutionStatus.CANDIDATE},
        {"clear_span_m": 1.764},
        {"reveal_depth_mm": 149.94},
    ):
        with pytest.raises(ValueError, match="classification and source gate conflict"):
            replace(abstained, **changes)
    for record in (candidate, abstained):
        assert record.shadow_only is True
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False
    assert authority.evaluate_stepped_wall_aperture(**inputs()) == candidate


def test_public_reveal_numeric_record_replacements_fail_closed(authority):
    from dataclasses import replace

    candidate = authority.evaluate_stepped_wall_aperture(**inputs())
    abstained = authority.evaluate_stepped_wall_aperture(**inputs(scale_ratio=None))
    for record in (candidate, abstained):
        assert replace(record) == record
        for field in (
            "clear_span_pt", "left_wall_thickness_pt", "right_wall_thickness_pt",
            "reveal_depth_pt", "centerline_step_offset_pt",
        ):
            for bad in (float("nan"), float("inf"), -1.0):
                with pytest.raises(ValueError, match="numeric evidence"):
                    replace(record, **{field: bad})
        for bad in (float("nan"), float("inf"), float(2**53) + 2.0):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(record, jamb_left_datum=(bad, 200.0))
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(record, datum_offset_pt=bad)
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(record, clear_span_pt=record.clear_span_pt + 100.0)
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(record, reveal_depth_pt=record.reveal_depth_pt + 10.0)
    for field in METRIC_FIELDS:
        for bad in (float("nan"), float("inf"), -1.0):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(candidate, **{field: bad})
    for field in ("clear_span_m", "left_wall_thickness_mm", "right_wall_thickness_mm"):
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(candidate, **{field: 0.0})
    with pytest.raises(ValueError, match="numeric evidence"):
        replace(candidate, scale_ratio=float("nan"))
    with pytest.raises(ValueError, match="numeric evidence"):
        replace(candidate, datum_alignment="exterior_flush")
    zero_reveal = authority.evaluate_stepped_wall_aperture(**inputs(
        left_thickness_pt=10.0, right_thickness_pt=10.0,
    ))
    assert zero_reveal.reveal_depth_pt == 0.0
    assert zero_reveal.reveal_depth_mm == 0.0
    assert replace(zero_reveal) == zero_reveal
    assert candidate.shadow_only and not candidate.takeoff_eligible
    assert abstained.shadow_only and not abstained.commercial_projection_allowed
    assert authority.evaluate_stepped_wall_aperture(**inputs()) == candidate
