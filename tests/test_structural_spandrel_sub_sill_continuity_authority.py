"""Unit and regression tests for Structural Infill Spandrel Wall and Window Sub-Sill Continuity Authority."""

from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_spandrel_sub_sill_continuity_authority import (
    SpandrelSubSillClassification,
    StructuralSpandrelSubSillContinuityAuthority,
)


@pytest.fixture
def authority() -> StructuralSpandrelSubSillContinuityAuthority:
    return StructuralSpandrelSubSillContinuityAuthority()


def test_positive_window_over_900mm_spandrel_wall(
    authority: StructuralSpandrelSubSillContinuityAuthority,
) -> None:
    # 100 pt clear span ~ 1.764 m; sill = 900mm (0.9m); head = 2100mm (2.1m)
    eval_res = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="WALL_LIVING_NORTH",
        scale_ratio=0.01764,
    )
    assert (
        eval_res.classification
        == SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    )
    assert eval_res.clear_span_pt == pytest.approx(100.0, abs=0.01)
    assert eval_res.clear_span_m == pytest.approx(1.764, abs=0.001)
    assert eval_res.glazing_height_mm == pytest.approx(1200.0, abs=0.1)
    assert eval_res.glazing_aperture_area_sqm == pytest.approx(2.1168, abs=0.001)
    assert eval_res.spandrel_wall_area_sqm == pytest.approx(1.5876, abs=0.001)
    assert eval_res.total_wall_opening_area_sqm == pytest.approx(2.1168, abs=0.001)
    assert eval_res.status == EvidenceResolutionStatus.CANDIDATE
    assert eval_res.shadow_only is True
    assert eval_res.commercial_projection_allowed is False


def test_inverted_vertical_levels_fails_closed(
    authority: StructuralSpandrelSubSillContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        sill_height_mm=2100.0,  # inverted: sill >= head
        head_height_mm=900.0,
        host_through_wall_id="WALL_LIVING_NORTH",
        scale_ratio=0.01764,
    )
    assert (
        eval_res.classification
        == SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED
    assert "Invalid vertical levels" in eval_res.notes


def test_degenerate_span_fails_closed(
    authority: StructuralSpandrelSubSillContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0),
        jamb_b=(110.0, 200.0),  # clear span = 10 pt (< 20 pt minimum)
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="WALL_LIVING_NORTH",
        scale_ratio=0.01764,
    )
    assert (
        eval_res.classification
        == SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_jamb_ordering_invariance(
    authority: StructuralSpandrelSubSillContinuityAuthority,
) -> None:
    eval_fwd = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="WALL_LIVING_NORTH",
        scale_ratio=0.01764,
    )
    eval_rev = authority.evaluate_spandrel_sub_sill(
        jamb_a=(200.0, 200.0),
        jamb_b=(100.0, 200.0),
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="WALL_LIVING_NORTH",
        scale_ratio=0.01764,
    )
    assert eval_fwd.contract_id == eval_rev.contract_id
    assert eval_fwd.clear_span_pt == eval_rev.clear_span_pt
    assert eval_fwd.glazing_aperture_area_sqm == eval_rev.glazing_aperture_area_sqm
    assert eval_fwd.spandrel_wall_area_sqm == eval_rev.spandrel_wall_area_sqm


def test_to_dict_schema_invariants(
    authority: StructuralSpandrelSubSillContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="WALL_LIVING_NORTH",
        scale_ratio=0.01764,
    )
    d = eval_res.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == eval_res.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["jamb_left"], list)
    assert isinstance(d["jamb_right"], list)


@pytest.mark.parametrize("ratio", [float("nan"), float("inf"), -1.0, 0.0, True])
def test_unverified_or_invalid_scale_never_creates_metric_claim(authority, ratio):
    with pytest.raises(ValueError):
        authority.evaluate_spandrel_sub_sill(
            jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
            sill_height_mm=900.0, head_height_mm=2100.0,
            host_through_wall_id="HOST", scale_ratio=ratio)


def test_missing_scale_returns_typed_abstention_with_null_metrics(authority):
    kw = dict(jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
              sill_height_mm=900.0, head_height_mm=2100.0,
              host_through_wall_id="HOST", scale_ratio=None)
    record = authority.evaluate_spandrel_sub_sill(**kw)
    assert record.classification == SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert record.first_remaining_gate == "original_source_scale_authority_unverified"
    assert record.clear_span_pt == pytest.approx(100.0)
    for name in ("clear_span_m", "glazing_height_mm", "glazing_aperture_area_sqm",
                 "spandrel_wall_area_sqm", "total_wall_opening_area_sqm"):
        assert getattr(record, name) is None
        assert record.to_dict()[name] is None
    assert record.shadow_only and not record.takeoff_eligible
    assert not record.commercial_projection_allowed
    assert record.contract_id == authority.evaluate_spandrel_sub_sill(**kw).contract_id
    assert record.contract_id == authority.evaluate_spandrel_sub_sill(
        **(kw | dict(jamb_a=kw["jamb_b"], jamb_b=kw["jamb_a"]))).contract_id
    assert record.contract_id != authority.evaluate_spandrel_sub_sill(
        **(kw | dict(jamb_b=(200.001, 200.0)))).contract_id


@pytest.mark.parametrize("field", ["scale_ratio", "sill_height_mm", "head_height_mm", "jamb_a"])
def test_extremely_large_integer_cannot_bypass_finite_validation(authority, field):
    kw = dict(jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
              sill_height_mm=900.0, head_height_mm=2100.0,
              host_through_wall_id="HOST", scale_ratio=0.01764)
    kw[field] = (10 ** 1000, 200.0) if field == "jamb_a" else 10 ** 1000
    with pytest.raises(ValueError):
        authority.evaluate_spandrel_sub_sill(**kw)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "bad"])
def test_nonfinite_and_malformed_jamb_fail_closed(authority, bad):
    with pytest.raises(ValueError):
        authority.evaluate_spandrel_sub_sill(
            jamb_a=(bad, 200.0), jamb_b=(200.0, 200.0),
            sill_height_mm=900.0, head_height_mm=2100.0,
            host_through_wall_id="HOST", scale_ratio=0.01764)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "900"])
def test_nonfinite_and_malformed_level_fail_closed(authority, bad):
    with pytest.raises(ValueError):
        authority.evaluate_spandrel_sub_sill(
            jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
            sill_height_mm=bad, head_height_mm=2100.0,
            host_through_wall_id="HOST", scale_ratio=0.01764)


def test_overflowed_geometry_and_metric_fail_closed(authority):
    for a, b, scale in [
        ((-1e308, 0.0), (1e308, 0.0), 0.01764),
        ((100.0, 200.0), (200.0, 200.0), 1e308),
    ]:
        with pytest.raises(ValueError):
            authority.evaluate_spandrel_sub_sill(
                jamb_a=a, jamb_b=b, sill_height_mm=900.0,
                head_height_mm=2100.0, host_through_wall_id="HOST",
                scale_ratio=scale)


def test_shadow_identity_binds_scale_subcentipoint_and_host(authority):
    kw = dict(jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
              sill_height_mm=900.0, head_height_mm=2100.0,
              host_through_wall_id="HOST", scale_ratio=0.01764)
    base = authority.evaluate_spandrel_sub_sill(**kw)
    assert base.classification == SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    assert base.status == EvidenceResolutionStatus.CANDIDATE
    for change in [dict(scale_ratio=0.018), dict(jamb_b=(200.001, 200.0)),
                   dict(host_through_wall_id="OTHER"),
                   dict(head_height_mm=2100.01)]:
        assert authority.evaluate_spandrel_sub_sill(**(kw | change)).contract_id != base.contract_id
    assert authority.evaluate_spandrel_sub_sill(**(kw | dict(
        jamb_a=kw["jamb_b"], jamb_b=kw["jamb_a"]))).contract_id == base.contract_id
    assert base.total_wall_opening_area_sqm == base.glazing_aperture_area_sqm
    assert base.spandrel_wall_area_sqm > 0
    assert not base.takeoff_eligible and not base.commercial_projection_allowed


@pytest.mark.parametrize(
    "levels, right_jamb, expected_class, expected_gate",
    [
        ((2100.0, 900.0), (200.0, 200.0),
         SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS,
         "vertical_levels_inverted_or_negative"),
        ((900.0, 2100.0), (110.0, 200.0),
         SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN,
         "clear_span_out_of_bounds"),
    ],
)
def test_rejected_aperture_never_serializes_hypothetical_metric_quantity(
    authority, levels, right_jamb, expected_class, expected_gate
):
    kwargs = dict(
        jamb_a=(100.0, 200.0), jamb_b=right_jamb,
        sill_height_mm=levels[0], head_height_mm=levels[1],
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    rejected = authority.evaluate_spandrel_sub_sill(**kwargs)
    assert rejected.classification == expected_class
    assert rejected.status == EvidenceResolutionStatus.ABSTAINED
    assert rejected.first_remaining_gate == expected_gate
    for field in ("clear_span_m", "glazing_height_mm",
                  "glazing_aperture_area_sqm", "spandrel_wall_area_sqm",
                  "total_wall_opening_area_sqm"):
        assert getattr(rejected, field) is None
        assert rejected.to_dict()[field] is None
    assert rejected.contract_id == authority.evaluate_spandrel_sub_sill(
        **(kwargs | dict(jamb_a=right_jamb, jamb_b=kwargs["jamb_a"]))).contract_id
    assert rejected.shadow_only and not rejected.takeoff_eligible
    assert not rejected.commercial_projection_allowed
    positive = authority.evaluate_spandrel_sub_sill(
        **(kwargs | dict(jamb_b=(200.0, 200.0),
                        sill_height_mm=900.0, head_height_mm=2100.0)))
    assert positive.classification == SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    assert positive.glazing_aperture_area_sqm is not None
    assert not positive.takeoff_eligible and not positive.commercial_projection_allowed


def test_distinct_large_integer_source_inputs_cannot_alias_shadow_id(authority):
    kw = dict(jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
              sill_height_mm=900.0, head_height_mm=2100.0,
              host_through_wall_id="HOST", scale_ratio=0.01764)
    for field in ("jamb_a", "sill_height_mm", "head_height_mm", "scale_ratio"):
        for huge in (2**53 + 1, 2**53 + 2):
            changed = (huge, 200.0) if field == "jamb_a" else huge
            with pytest.raises(ValueError):
                authority.evaluate_spandrel_sub_sill(**(kw | {field: changed}))


def test_positive_subround_metric_receipts_never_serialize_as_zero(authority):
    record = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=1e-8,
    )
    assert record.classification == SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    for field in ("clear_span_m", "glazing_aperture_area_sqm",
                  "spandrel_wall_area_sqm", "total_wall_opening_area_sqm"):
        assert getattr(record, field) > 0
        assert record.to_dict()[field] > 0
    assert not record.takeoff_eligible and not record.commercial_projection_allowed


def test_positive_vertical_metric_underflow_is_rejected(authority):
    with pytest.raises(ValueError, match="underflowed positive vertical"):
        authority.evaluate_spandrel_sub_sill(
            jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
            sill_height_mm=5e-324, head_height_mm=1e-323,
            host_through_wall_id="HOST", scale_ratio=0.01764,
        )


def test_frozen_shadow_receipt_does_not_alias_mutated_caller_lists(authority):
    a, b = [100.0, 200.0], [200.0, 200.0]
    record = authority.evaluate_spandrel_sub_sill(
        jamb_a=a, jamb_b=b, sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    before = record.to_dict()
    a[0] = 999.0
    b[0] = 888.0
    assert record.to_dict() == before
    assert record.jamb_left == (100.0, 200.0)
    assert record.jamb_right == (200.0, 200.0)
    assert not record.takeoff_eligible and not record.commercial_projection_allowed


def test_serialized_spandrel_jamb_and_level_preserve_exact_source_hypotheses(authority):
    kwargs = dict(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    base = authority.evaluate_spandrel_sub_sill(**kwargs)
    shifted = authority.evaluate_spandrel_sub_sill(
        **(kwargs | {"jamb_b": (200.001, 200.0)})
    )
    raised = authority.evaluate_spandrel_sub_sill(
        **(kwargs | {"head_height_mm": 2100.01})
    )
    assert base.contract_id != shifted.contract_id
    assert base.to_dict()["jamb_right"] != shifted.to_dict()["jamb_right"]
    assert shifted.to_dict()["jamb_right"] == [200.001, 200.0]
    assert base.to_dict()["clear_span_pt"] != shifted.to_dict()["clear_span_pt"]
    assert base.contract_id != raised.contract_id
    assert base.to_dict()["head_height_mm"] != raised.to_dict()["head_height_mm"]
    assert raised.to_dict()["head_height_mm"] == 2100.01
    for rec in (base, shifted, raised):
        assert rec.classification == SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
        assert rec.shadow_only and not rec.takeoff_eligible
        assert not rec.commercial_projection_allowed


def test_serialized_spandrel_metric_preserves_close_scale_hypotheses(authority):
    kwargs = dict(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    base = authority.evaluate_spandrel_sub_sill(**kwargs)
    close = authority.evaluate_spandrel_sub_sill(
        **(kwargs | {"scale_ratio": 0.017640001})
    )
    assert base.contract_id != close.contract_id
    for key in ("clear_span_m", "glazing_aperture_area_sqm",
                "spandrel_wall_area_sqm", "total_wall_opening_area_sqm"):
        assert base.to_dict()[key] != close.to_dict()[key]
        assert base.to_dict()[key] == getattr(base, key)
        assert close.to_dict()[key] == getattr(close, key)
    assert not base.takeoff_eligible and not close.takeoff_eligible


def test_serialized_spandrel_abstention_keeps_native_geometry_and_null_metrics(authority):
    record = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0), jamb_b=(200.001, 200.0),
        sill_height_mm=900.01, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=None,
    )
    payload = record.to_dict()
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert payload["jamb_right"] == [200.001, 200.0]
    assert payload["sill_height_mm"] == 900.01
    assert payload["clear_span_m"] is None
    assert payload["glazing_aperture_area_sqm"] is None
    assert payload["spandrel_wall_area_sqm"] is None
    assert payload["shadow_only"] and not payload["takeoff_eligible"]

@pytest.mark.parametrize(
    "jamb_b, sill_mm, head_mm, expected_class, expected_gate",
    [
        ((110.0, 200.0), 900.0, 2100.0,
         SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN,
         "clear_span_out_of_bounds"),
        ((200.0, 200.0), 2100.0, 900.0,
         SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS,
         "vertical_levels_inverted_or_negative"),
        ((200.0, 200.0), 1e308, 900.0,
         SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS,
         "vertical_levels_inverted_or_negative"),
    ],
)
def test_rejected_spandrel_abstains_before_extreme_metric_arithmetic(
    authority, jamb_b, sill_mm, head_mm, expected_class, expected_gate
):
    """A rejected geometry/level cannot be replaced by overflow from caller scale."""
    kwargs = dict(
        jamb_a=(100.0, 200.0), jamb_b=jamb_b,
        sill_height_mm=sill_mm, head_height_mm=head_mm,
        host_through_wall_id="HOST", scale_ratio=1e308,
    )
    result = authority.evaluate_spandrel_sub_sill(**kwargs)
    assert result.classification == expected_class
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.first_remaining_gate == expected_gate
    assert result.shadow_only and not result.takeoff_eligible
    assert not result.commercial_projection_allowed
    for field in (
        "clear_span_m", "glazing_height_mm", "glazing_aperture_area_sqm",
        "spandrel_wall_area_sqm", "total_wall_opening_area_sqm",
    ):
        assert getattr(result, field) is None
        assert result.to_dict()[field] is None
    assert result.contract_id == authority.evaluate_spandrel_sub_sill(
        **(kwargs | {"jamb_a": jamb_b, "jamb_b": kwargs["jamb_a"]})
    ).contract_id


def test_valid_spandrel_still_rejects_extreme_metric_overflow(authority):
    with pytest.raises(ValueError, match="nonfinite or underflowed metric conversion"):
        authority.evaluate_spandrel_sub_sill(
            jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
            sill_height_mm=900.0, head_height_mm=2100.0,
            host_through_wall_id="HOST", scale_ratio=1e308,
        )


@pytest.mark.parametrize("sill,head", [
    (0.0, 2100.0),
    (-0.0, 2100.0),
    (-1e-12, 2100.0),
    (900.0, 900.0),
])
def test_no_positive_subsill_height_never_creates_spandrel_candidate(authority, sill, head):
    # A zero-height sill is not a physical sub-sill spandrel, even with
    # an explicitly supplied but still unverified metric scale.
    record = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=sill, head_height_mm=head,
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    assert record.classification == SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert record.first_remaining_gate == "vertical_levels_inverted_or_negative"
    assert record.glazing_aperture_area_sqm is None
    assert record.spandrel_wall_area_sqm is None
    assert record.total_wall_opening_area_sqm is None
    assert record.to_dict()["commercial_projection_allowed"] is False
    assert record.to_dict()["takeoff_eligible"] is False
    assert record.to_dict()["shadow_only"] is True


def test_positive_subsill_height_retains_only_shadow_geometric_candidate(authority):
    record = authority.evaluate_spandrel_sub_sill(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    assert record.classification == SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    assert record.status is EvidenceResolutionStatus.CANDIDATE
    assert record.spandrel_wall_area_sqm is not None
    assert record.spandrel_wall_area_sqm > 0
    assert record.shadow_only
    assert not record.commercial_projection_allowed
    assert not record.takeoff_eligible


@pytest.mark.parametrize("jamb_field", ["jamb_a", "jamb_b"])
@pytest.mark.parametrize("huge", [float(2**53) + 2.0, -(float(2**53) + 2.0)])
def test_oversized_native_float_jambs_cannot_alias_shadow_identity(authority, jamb_field, huge):
    # Native floats above the exact source-coordinate boundary cannot be
    # authenticated as distinct source points after binary64 conversion.
    kwargs = dict(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=0.01764,
    )
    caller_point = [huge, 200.0]
    with pytest.raises(ValueError, match=f"{jamb_field} must contain finite real coordinates"):
        authority.evaluate_spandrel_sub_sill(**(kwargs | {jamb_field: caller_point}))
    assert caller_point == [huge, 200.0]
    # Invalid input cannot create a source-free commercial receipt.


def test_inclusive_source_coordinate_boundary_preserves_shadow_only_receipt(authority):
    # Exactly 2**53 is the established inclusive native coordinate boundary.
    kwargs = dict(
        jamb_a=(float(2**53) - 100.0, 200.0),
        jamb_b=(float(2**53), 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="HOST", scale_ratio=None,
    )
    first = authority.evaluate_spandrel_sub_sill(**kwargs)
    second = authority.evaluate_spandrel_sub_sill(**kwargs)
    assert first == second
    assert first.jamb_right == (float(2**53), 200.0)
    assert first.classification == SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE
    assert first.clear_span_pt == 100.0
    assert first.clear_span_m is None
    assert first.glazing_aperture_area_sqm is None
    assert first.spandrel_wall_area_sqm is None
    assert first.shadow_only and not first.takeoff_eligible
    assert not first.commercial_projection_allowed


def _spandrel_identity_kwargs():
    return dict(
        jamb_a=[100.0, 200.0],
        jamb_b=[200.0, 200.0],
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="HOST_A",
        context_label="SPANDREL_WINDOW",
        scale_ratio=0.01764,
    )


@pytest.mark.parametrize("field", ["host_through_wall_id", "context_label"])
@pytest.mark.parametrize("bad", [
    "", " ", " HOST_A", "HOST_A ", "HOST\nA", "HOST\tA",
    "HOST\x00A", "HOST\u200bA", True, None, 123,
])
def test_spandrel_host_identity_rejects_padded_and_control_aliases(
    authority, field, bad,
):
    kw = _spandrel_identity_kwargs()
    before = (tuple(kw["jamb_a"]), tuple(kw["jamb_b"]))
    with pytest.raises(ValueError, match="exact printable"):
        authority.evaluate_spandrel_sub_sill(**(kw | {field: bad}))
    assert before == (tuple(kw["jamb_a"]), tuple(kw["jamb_b"]))


def test_spandrel_exact_host_identity_is_stable_and_noncommercial(authority):
    kw = _spandrel_identity_kwargs()
    first = authority.evaluate_spandrel_sub_sill(**kw)
    second = authority.evaluate_spandrel_sub_sill(**kw)
    swapped = authority.evaluate_spandrel_sub_sill(**(
        kw | {"jamb_a": kw["jamb_b"], "jamb_b": kw["jamb_a"]}
    ))
    other = authority.evaluate_spandrel_sub_sill(**(
        kw | {"host_through_wall_id": "HOST_B"}
    ))
    assert first == second
    assert first.contract_id == swapped.contract_id
    assert first.contract_id != other.contract_id
    assert first.host_through_wall_id == "HOST_A"
    assert first.to_dict()["host_through_wall_id"] == "HOST_A"
    assert first.classification is SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    assert first.first_remaining_gate == "original_source_spandrel_host_scale_levels_unverified"
    assert first.status is EvidenceResolutionStatus.CANDIDATE
    assert first.shadow_only and not first.takeoff_eligible
    assert not first.commercial_projection_allowed
    assert kw["jamb_a"] == [100.0, 200.0]
    assert kw["jamb_b"] == [200.0, 200.0]


def test_spandrel_missing_scale_keeps_null_metric_after_identity_guard(authority):
    kw = _spandrel_identity_kwargs()
    kw["scale_ratio"] = None
    result = authority.evaluate_spandrel_sub_sill(**kw)
    assert result.classification is SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.clear_span_m is None
    assert result.glazing_aperture_area_sqm is None
    assert result.spandrel_wall_area_sqm is None
    assert result.to_dict()["total_wall_opening_area_sqm"] is None
    assert result.shadow_only and not result.takeoff_eligible
    assert not result.commercial_projection_allowed


def test_spandrel_identity_rejects_string_subclass(authority):
    class Impostor(str):
        pass

    kw = _spandrel_identity_kwargs()
    with pytest.raises(ValueError, match="exact printable"):
        authority.evaluate_spandrel_sub_sill(**(
            kw | {"host_through_wall_id": Impostor("HOST_A")}
        ))


def test_public_spandrel_record_replacement_cannot_mint_source_or_commercial_authority(
    authority: StructuralSpandrelSubSillContinuityAuthority,
) -> None:
    from dataclasses import replace

    common = dict(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="WALL_SHADOW",
    )
    candidate = authority.evaluate_spandrel_sub_sill(**common, scale_ratio=0.01764)
    abstained = authority.evaluate_spandrel_sub_sill(**common)
    assert candidate.classification is SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
    assert candidate.status is EvidenceResolutionStatus.CANDIDATE
    assert abstained.classification is SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE
    assert abstained.status is EvidenceResolutionStatus.ABSTAINED
    assert replace(candidate) == candidate
    assert replace(abstained) == abstained
    for changes in (
        {"classification": SpandrelSubSillClassification.SPANDREL_SUB_SILL_CONFIRMED},
        {"status": EvidenceResolutionStatus.CORROBORATED},
        {"commercial_projection_allowed": True},
        {"takeoff_eligible": True},
        {"shadow_only": False},
    ):
        with pytest.raises(ValueError, match="source-neutral spandrel"):
            replace(candidate, **changes)
    for changes in (
        {"first_remaining_gate": "none"},
        {"first_remaining_gate": "caller_source_verified"},
        {"status": EvidenceResolutionStatus.ABSTAINED},
    ):
        with pytest.raises(ValueError, match="classification and source gate conflict"):
            replace(candidate, **changes)
    for changes in (
        {"status": EvidenceResolutionStatus.CANDIDATE},
        {"first_remaining_gate": "none"},
        {"clear_span_m": 1.764},
        {"spandrel_wall_area_sqm": 1.5876},
    ):
        with pytest.raises(ValueError, match="classification and source gate conflict"):
            replace(abstained, **changes)
    for record in (candidate, abstained):
        assert record.shadow_only is True
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False
    assert authority.evaluate_spandrel_sub_sill(**common, scale_ratio=0.01764) == candidate


def test_spandrel_public_numeric_replacement_rejected_without_changing_abstention(authority):
    from dataclasses import replace

    common = dict(
        jamb_a=(100.0, 200.0), jamb_b=(200.0, 200.0),
        sill_height_mm=900.0, head_height_mm=2100.0,
        host_through_wall_id="WALL_SHADOW",
    )
    candidate = authority.evaluate_spandrel_sub_sill(**common, scale_ratio=0.01764)
    abstained = authority.evaluate_spandrel_sub_sill(**common)
    for record in (candidate, abstained):
        assert replace(record) == record
        for field in ("clear_span_pt", "sill_height_mm", "head_height_mm"):
            for bad in (float("nan"), float("inf")):
                with pytest.raises(ValueError, match="numeric evidence"):
                    replace(record, **{field: bad})
        for bad in (float("nan"), float("inf"), float(2**53) + 2.0):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(record, jamb_left=(bad, 200.0))
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(record, clear_span_pt=record.clear_span_pt + 100.0)
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(record, clear_span_pt=-1.0)
    for field in (
        "clear_span_m", "glazing_height_mm", "glazing_aperture_area_sqm",
        "spandrel_wall_area_sqm", "total_wall_opening_area_sqm",
    ):
        for bad in (float("nan"), float("inf"), 0.0, -1.0):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(candidate, **{field: bad})
    with pytest.raises(ValueError, match="numeric evidence"):
        replace(candidate, sill_height_mm=0.0)
    with pytest.raises(ValueError, match="numeric evidence"):
        replace(candidate, glazing_height_mm=candidate.glazing_height_mm + 10.0)
    invalid = authority.evaluate_spandrel_sub_sill(
        **(common | {"sill_height_mm": -1.0}), scale_ratio=0.01764,
    )
    assert invalid.classification is SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS
    assert invalid.clear_span_m is None
    assert replace(invalid) == invalid
    assert candidate.shadow_only and not candidate.takeoff_eligible
    assert abstained.shadow_only and not abstained.commercial_projection_allowed
    assert authority.evaluate_spandrel_sub_sill(**common, scale_ratio=0.01764) == candidate
