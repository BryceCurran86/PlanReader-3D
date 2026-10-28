"""Unit and regression tests for Structural Door Threshold vs Wall Continuity Discrimination Authority."""

from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_door_threshold_wall_continuity_authority import (
    DoorThresholdClassification,
    StructuralDoorThresholdWallContinuityAuthority,
)


@pytest.fixture
def authority() -> StructuralDoorThresholdWallContinuityAuthority:
    return StructuralDoorThresholdWallContinuityAuthority()


def test_positive_synthetic_door_opening_vetoes_threshold_bridge(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(145.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    assert (
        eval_res.classification == DoorThresholdClassification.DOOR_APERTURE_CONFIRMED
    )
    assert eval_res.is_bridging_stroke_vetoed_as_wall is True
    assert eval_res.status == EvidenceResolutionStatus.CANDIDATE
    assert eval_res.clear_span_pt == pytest.approx(45.0, abs=0.01)
    assert eval_res.shadow_only is True
    assert eval_res.commercial_projection_allowed is False


def test_synthetic_solid_wall_continuity_rejects_aperture(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(145.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.96,  # heavy structural stroke across gap
    )
    assert eval_res.classification == DoorThresholdClassification.SOLID_WALL_CONTINUITY
    assert eval_res.is_bridging_stroke_vetoed_as_wall is False
    assert eval_res.status == EvidenceResolutionStatus.CANDIDATE


def test_ambiguous_stroke_fails_closed(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(145.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.62,  # ambiguous: between 0.55 and 0.70
    )
    assert (
        eval_res.classification
        == DoorThresholdClassification.ABSTAINED_AMBIGUOUS_STROKE
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED
    assert eval_res.is_bridging_stroke_vetoed_as_wall is False


def test_substructural_wall_stroke_fails_closed(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(145.0, 200.0),
        wall_stroke_width_pt=0.45,  # insufficient wall thickness
        bridging_stroke_width_pt=0.30,
    )
    assert (
        eval_res.classification
        == DoorThresholdClassification.ABSTAINED_INSUFFICIENT_STRUCTURAL_WALL
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_degenerate_span_bounds(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    # Sub-span (< 20.0 pt)
    eval_small = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(110.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    assert (
        eval_small.classification
        == DoorThresholdClassification.ABSTAINED_DEGENERATE_SPAN
    )

    # Over-span (> 150.0 pt)
    eval_large = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(300.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    assert (
        eval_large.classification
        == DoorThresholdClassification.ABSTAINED_DEGENERATE_SPAN
    )


def test_maryborough_d17_multiview_positive(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    # Exact Maryborough p7 coordinates
    p7_left = (476.16, 1175.12)
    p7_right = (521.52, 1175.12)

    # p11 translated by authenticated +77.76 pt
    p11_left = (476.16 + 77.76, 1175.12)
    p11_right = (521.52 + 77.76, 1175.12)

    eval_res = authority.evaluate_multiview_aperture(
        jamb_a_view1=p7_left,
        jamb_b_view1=p7_right,
        jamb_a_view2=p11_left,
        jamb_b_view2=p11_right,
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    assert (
        eval_res.classification == DoorThresholdClassification.DOOR_APERTURE_CONFIRMED
    )
    assert eval_res.multiview_confirmed is True
    assert eval_res.translation_dx_pt == pytest.approx(77.76, abs=0.01)
    assert eval_res.clear_span_pt == pytest.approx(45.36, abs=0.01)
    assert eval_res.status == EvidenceResolutionStatus.CORROBORATED


def test_maryborough_rival_translation_fails_closed(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    p7_left = (476.16, 1175.12)
    p7_right = (521.52, 1175.12)

    # Rival offset +43.92 pt
    p11_left = (476.16 + 43.92, 1175.12)
    p11_right = (521.52 + 43.92, 1175.12)

    eval_res = authority.evaluate_multiview_aperture(
        jamb_a_view1=p7_left,
        jamb_b_view1=p7_right,
        jamb_a_view2=p11_left,
        jamb_b_view2=p11_right,
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    assert (
        eval_res.classification
        == DoorThresholdClassification.ABSTAINED_MULTIVIEW_MISMATCH
    )
    assert eval_res.multiview_confirmed is False
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_jamb_ordering_invariance(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    eval_fwd = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(145.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    eval_rev = authority.evaluate_aperture(
        jamb_a=(145.0, 200.0),
        jamb_b=(100.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    assert eval_fwd.contract_id == eval_rev.contract_id
    assert eval_fwd.jamb_left == eval_rev.jamb_left
    assert eval_fwd.jamb_right == eval_rev.jamb_right
    assert eval_fwd.clear_span_pt == eval_rev.clear_span_pt


def test_to_dict_schema_invariants(
    authority: StructuralDoorThresholdWallContinuityAuthority,
) -> None:
    eval_res = authority.evaluate_aperture(
        jamb_a=(100.0, 200.0),
        jamb_b=(145.0, 200.0),
        wall_stroke_width_pt=0.96,
        bridging_stroke_width_pt=0.48,
    )
    d = eval_res.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == eval_res.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["jamb_left"], list)
    assert isinstance(d["jamb_right"], list)
