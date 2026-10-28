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
    )
    assert (
        eval_res.classification
        == SpandrelSubSillClassification.SPANDREL_SUB_SILL_CONFIRMED
    )
    assert eval_res.clear_span_pt == pytest.approx(100.0, abs=0.01)
    assert eval_res.clear_span_m == pytest.approx(1.764, abs=0.001)
    assert eval_res.glazing_height_mm == pytest.approx(1200.0, abs=0.1)
    assert eval_res.glazing_aperture_area_sqm == pytest.approx(2.1168, abs=0.001)
    assert eval_res.spandrel_wall_area_sqm == pytest.approx(1.5876, abs=0.001)
    assert eval_res.total_wall_opening_area_sqm == pytest.approx(3.7044, abs=0.001)
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
    )
    eval_rev = authority.evaluate_spandrel_sub_sill(
        jamb_a=(200.0, 200.0),
        jamb_b=(100.0, 200.0),
        sill_height_mm=900.0,
        head_height_mm=2100.0,
        host_through_wall_id="WALL_LIVING_NORTH",
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
    )
    d = eval_res.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == eval_res.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["jamb_left"], list)
    assert isinstance(d["jamb_right"], list)
