"""Unit and regression tests for Structural Cavity Slider Lead Jamb and Split-Stud Pocket Host Authority."""

from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_cavity_slider_pocket_host_authority import (
    CavitySliderClassification,
    StructuralCavitySliderPocketHostAuthority,
)


@pytest.fixture
def authority() -> StructuralCavitySliderPocketHostAuthority:
    return StructuralCavitySliderPocketHostAuthority()


def test_positive_compliant_cavity_slider(
    authority: StructuralCavitySliderPocketHostAuthority,
) -> None:
    # 820mm passage door ~ 46.48 pt; pocket depth ~ 48.52 pt; scale 0.01764 m/pt
    strike = (100.0, 200.0)
    mouth = (146.48, 200.0)
    back = (195.0, 200.0)

    record = authority.evaluate_cavity_slider(
        strike_jamb=strike,
        pocket_mouth_jamb=mouth,
        pocket_back_stud=back,
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )
    assert (
        record.classification == CavitySliderClassification.CAVITY_SLIDER_GEOMETRIC_CANDIDATE
    )
    assert record.clear_span_pt == pytest.approx(46.48, abs=0.01)
    assert record.pocket_depth_pt == pytest.approx(48.52, abs=0.01)
    assert record.total_frame_extent_pt == pytest.approx(95.0, abs=0.01)
    assert record.status == EvidenceResolutionStatus.CANDIDATE
    assert record.shadow_only is True
    assert record.commercial_projection_allowed is False


def test_insufficient_pocket_depth_fails_closed(
    authority: StructuralCavitySliderPocketHostAuthority,
) -> None:
    strike = (100.0, 200.0)
    mouth = (146.48, 200.0)
    back = (170.0, 200.0)  # pocket depth = 23.52 pt (< 46.48 pt clear span)

    record = authority.evaluate_cavity_slider(
        strike_jamb=strike,
        pocket_mouth_jamb=mouth,
        pocket_back_stud=back,
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )
    assert (
        record.classification
        == CavitySliderClassification.ABSTAINED_INSUFFICIENT_POCKET_DEPTH
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert "insufficient for door leaf span" in record.notes


def test_misaligned_pocket_axis_fails_closed(
    authority: StructuralCavitySliderPocketHostAuthority,
) -> None:
    strike = (100.0, 200.0)
    mouth = (146.48, 200.0)
    back = (195.0, 215.0)  # angled pocket (deviates by ~17 deg)

    record = authority.evaluate_cavity_slider(
        strike_jamb=strike,
        pocket_mouth_jamb=mouth,
        pocket_back_stud=back,
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )
    assert (
        record.classification
        == CavitySliderClassification.ABSTAINED_MISALIGNED_POCKET_AXIS
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_degenerate_clear_span_fails_closed(
    authority: StructuralCavitySliderPocketHostAuthority,
) -> None:
    strike = (100.0, 200.0)
    mouth = (110.0, 200.0)  # span = 10 pt (< 20 pt minimum)
    back = (125.0, 200.0)

    record = authority.evaluate_cavity_slider(
        strike_jamb=strike,
        pocket_mouth_jamb=mouth,
        pocket_back_stud=back,
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )
    assert record.classification == CavitySliderClassification.ABSTAINED_DEGENERATE_SPAN
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_metamorphic_rotation_and_translation_invariance(
    authority: StructuralCavitySliderPocketHostAuthority,
) -> None:
    strike = (100.0, 200.0)
    mouth = (146.48, 200.0)
    back = (195.0, 200.0)

    base_rec = authority.evaluate_cavity_slider(
        strike_jamb=strike,
        pocket_mouth_jamb=mouth,
        pocket_back_stud=back,
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )

    # Rotate 90 deg: (x, y) -> (-y + 300, x - 100)
    def rot(p: tuple[float, float]) -> tuple[float, float]:
        return -p[1] + 300.0, p[0] - 100.0

    rot_rec = authority.evaluate_cavity_slider(
        strike_jamb=rot(strike),
        pocket_mouth_jamb=rot(mouth),
        pocket_back_stud=rot(back),
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )
    assert (
        rot_rec.classification
        == CavitySliderClassification.CAVITY_SLIDER_GEOMETRIC_CANDIDATE
    )
    assert rot_rec.clear_span_pt == pytest.approx(base_rec.clear_span_pt, abs=0.01)
    assert rot_rec.pocket_depth_pt == pytest.approx(base_rec.pocket_depth_pt, abs=0.01)
    assert rot_rec.total_frame_extent_pt == pytest.approx(
        base_rec.total_frame_extent_pt, abs=0.01
    )


def test_to_dict_schema_invariants(
    authority: StructuralCavitySliderPocketHostAuthority,
) -> None:
    strike = (100.0, 200.0)
    mouth = (146.48, 200.0)
    back = (195.0, 200.0)

    record = authority.evaluate_cavity_slider(
        strike_jamb=strike,
        pocket_mouth_jamb=mouth,
        pocket_back_stud=back,
        host_through_wall_id="WALL_ENSUITE",
        scale_ratio=0.01764,
    )
    d = record.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == record.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["strike_jamb"], list)
    assert isinstance(d["pocket_mouth_jamb"], list)
    assert isinstance(d["pocket_back_stud"], list)
