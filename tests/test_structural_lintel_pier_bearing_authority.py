"""Unit and regression tests for Structural Lintel-to-Pier Bearing and Head Wall Vertical Continuity Authority."""

from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_lintel_pier_bearing_authority import (
    LintelBearingClassification,
    LintelMaterialType,
    StructuralLintelPierBearingAuthority,
)


@pytest.fixture
def authority() -> StructuralLintelPierBearingAuthority:
    return StructuralLintelPierBearingAuthority()


def test_positive_compliant_lintel_bearing(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),  # clear span = 100 pt
        left_pier_width_pt=20.0,  # 350mm pier
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,  # 150mm bearing
        right_bearing_length_pt=8.50,
        lintel_material=LintelMaterialType.STEEL_PFC,
        lintel_callout_text="200 PFC LINTEL",
    )
    assert (
        eval_res.classification == LintelBearingClassification.LINTEL_BEARING_CONFIRMED
    )
    assert eval_res.clear_span_pt == pytest.approx(100.0, abs=0.01)
    assert eval_res.total_lintel_length_pt == pytest.approx(117.0, abs=0.01)
    assert eval_res.left_bearing.is_bearing_compliant is True
    assert eval_res.right_bearing.is_bearing_compliant is True
    assert eval_res.status == EvidenceResolutionStatus.CANDIDATE
    assert eval_res.shadow_only is True
    assert eval_res.commercial_projection_allowed is False


def test_subminimum_bearing_length_fails_closed(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        left_pier_width_pt=20.0,
        right_pier_width_pt=20.0,
        left_bearing_length_pt=4.0,  # < 5.67 pt (~100mm)
        right_bearing_length_pt=8.50,
    )
    assert (
        eval_res.classification
        == LintelBearingClassification.ABSTAINED_INSUFFICIENT_BEARING
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED
    assert "below minimum" in eval_res.notes


def test_pier_narrower_than_bearing_fails_closed(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        left_pier_width_pt=7.0,  # pier width (7.0 pt) < bearing length (8.5 pt)
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,
        right_bearing_length_pt=8.50,
    )
    assert (
        eval_res.classification
        == LintelBearingClassification.ABSTAINED_INSUFFICIENT_PIER_WIDTH
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_missing_flanking_pier_fails_closed(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        left_pier_width_pt=0.0,  # missing host pier
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,
        right_bearing_length_pt=8.50,
    )
    assert (
        eval_res.classification
        == LintelBearingClassification.ABSTAINED_MISSING_HOST_PIER
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_excessive_overhang_fails_closed(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        left_pier_width_pt=30.0,
        right_pier_width_pt=30.0,
        left_bearing_length_pt=25.0,  # > 20.0 pt max
        right_bearing_length_pt=8.50,
    )
    assert (
        eval_res.classification
        == LintelBearingClassification.ABSTAINED_EXCESSIVE_OVERHANG
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_degenerate_clear_span_fails_closed(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(110.0, 200.0),  # clear span = 10 pt (< 20 pt minimum)
        left_pier_width_pt=20.0,
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,
        right_bearing_length_pt=8.50,
    )
    assert (
        eval_res.classification == LintelBearingClassification.ABSTAINED_DEGENERATE_SPAN
    )
    assert eval_res.status == EvidenceResolutionStatus.ABSTAINED


def test_jamb_ordering_invariance(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_fwd = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        left_pier_width_pt=20.0,
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,
        right_bearing_length_pt=8.50,
    )
    eval_rev = authority.evaluate_lintel_bearing(
        jamb_a=(200.0, 200.0),
        jamb_b=(100.0, 200.0),
        left_pier_width_pt=20.0,
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,
        right_bearing_length_pt=8.50,
    )
    assert eval_fwd.contract_id == eval_rev.contract_id
    assert eval_fwd.clear_span_pt == eval_rev.clear_span_pt
    assert eval_fwd.total_lintel_length_pt == eval_rev.total_lintel_length_pt


def test_to_dict_schema_invariants(
    authority: StructuralLintelPierBearingAuthority,
) -> None:
    eval_res = authority.evaluate_lintel_bearing(
        jamb_a=(100.0, 200.0),
        jamb_b=(200.0, 200.0),
        left_pier_width_pt=20.0,
        right_pier_width_pt=20.0,
        left_bearing_length_pt=8.50,
        right_bearing_length_pt=8.50,
        lintel_material=LintelMaterialType.STEEL_ANGLE,
    )
    d = eval_res.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == eval_res.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["left_bearing"], dict)
    assert isinstance(d["right_bearing"], dict)
