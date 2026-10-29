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
