"""Unit and regression tests for Structural Wall Thickness Step and Opening Reveal Alignment Authority."""

from __future__ import annotations

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


def test_positive_brick_veneer_to_partition_stepped_wall(
    authority: StructuralWallThicknessStepRevealAuthority,
) -> None:
    # 240mm brick veneer ~ 13.6 pt; 90mm partition ~ 5.1 pt; scale 0.01764 m/pt
    eval_res = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(200.0, 200.0),  # clear span = 100 pt
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
        datum_offset_pt=0.0,
        datum_alignment=RevealAlignmentDatum.EXTERIOR_FLUSH,
    )
    assert (
        eval_res.classification
        == SteppedWallApertureClassification.STEPPED_WALL_APERTURE_CONFIRMED
    )
    assert eval_res.clear_span_pt == pytest.approx(100.0, abs=0.01)
    assert eval_res.reveal_depth_pt == pytest.approx(8.5, abs=0.01)
    assert eval_res.reveal_depth_mm == pytest.approx(150.0, abs=1.0)
    assert eval_res.centerline_step_offset_pt == pytest.approx(4.25, abs=0.01)
    assert eval_res.status == EvidenceResolutionStatus.CANDIDATE
    assert eval_res.shadow_only is True
    assert eval_res.commercial_projection_allowed is False


def test_unaligned_exterior_datum_fails_closed(
    authority: StructuralWallThicknessStepRevealAuthority,
) -> None:
    eval_res = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(200.0, 200.0),
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
        datum_offset_pt=3.5,  # > 2.0 pt tolerance
    )
    assert (
        eval_res.classification
        == SteppedWallApertureClassification.ABSTAINED_UNALIGNED_DATUM
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_excessive_thickness_discrepancy_fails_closed(
    authority: StructuralWallThicknessStepRevealAuthority,
) -> None:
    eval_res = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(200.0, 200.0),
        left_thickness_pt=25.0,  # delta = 20 pt (> 15 pt maximum)
        right_thickness_pt=5.0,
    )
    assert (
        eval_res.classification
        == SteppedWallApertureClassification.ABSTAINED_EXCESSIVE_THICKNESS_DISCREPANCY
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_degenerate_span_fails_closed(
    authority: StructuralWallThicknessStepRevealAuthority,
) -> None:
    eval_res = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(110.0, 200.0),  # clear span = 10 pt (< 20 pt minimum)
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
    )
    assert (
        eval_res.classification
        == SteppedWallApertureClassification.ABSTAINED_DEGENERATE_SPAN
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_jamb_ordering_invariance(
    authority: StructuralWallThicknessStepRevealAuthority,
) -> None:
    eval_fwd = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(200.0, 200.0),
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
    )
    eval_rev = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(200.0, 200.0),
        jamb_datum_b=(100.0, 200.0),
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
    )
    assert eval_fwd.contract_id == eval_rev.contract_id
    assert eval_fwd.clear_span_pt == eval_rev.clear_span_pt
    assert eval_fwd.reveal_depth_pt == eval_rev.reveal_depth_pt


def test_to_dict_schema_invariants(
    authority: StructuralWallThicknessStepRevealAuthority,
) -> None:
    eval_res = authority.evaluate_stepped_wall_aperture(
        jamb_datum_a=(100.0, 200.0),
        jamb_datum_b=(200.0, 200.0),
        left_thickness_pt=13.6,
        right_thickness_pt=5.1,
    )
    d = eval_res.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == eval_res.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["jamb_left_datum"], list)
    assert isinstance(d["jamb_right_datum"], list)
