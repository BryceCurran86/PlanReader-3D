"""Unit and regression tests for Structural Shared Stud Pier and Multi-Opening Cluster Host Authority."""

from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_shared_stud_pier_cluster_authority import (
    ClusterHostClassification,
    PierType,
    StructuralSharedStudPierClusterAuthority,
)


@pytest.fixture
def authority() -> StructuralSharedStudPierClusterAuthority:
    return StructuralSharedStudPierClusterAuthority()


def test_positive_two_door_cluster_with_90mm_stud_pack(
    authority: StructuralSharedStudPierClusterAuthority,
) -> None:
    # Scale: 0.01764 m/pt => 1 pt ~ 56.69 mm; 90mm ~ 5.10 pt; 820mm door ~ 46.48 pt
    op1_start = (100.0, 200.0)
    op1_end = (146.48, 200.0)  # span ~ 46.48 pt
    op2_start = (151.58, 200.0)  # pier ~ 5.10 pt ~ 90 mm
    op2_end = (198.06, 200.0)  # span ~ 46.48 pt

    record = authority.evaluate_two_opening_cluster(
        op1_jamb_start=op1_start,
        op1_jamb_end=op1_end,
        op2_jamb_start=op2_start,
        op2_jamb_end=op2_end,
        host_through_wall_id="WALL_HALLWAY_NORTH",
    )
    assert record.classification == ClusterHostClassification.CLUSTER_HOST_CONFIRMED
    assert len(record.openings) == 2
    assert len(record.shared_piers) == 1
    assert record.shared_piers[0].pier_type == PierType.TWO_STUD_PACK_90MM
    assert record.shared_piers[0].pier_width_mm == pytest.approx(90.0, abs=2.0)
    assert record.status == EvidenceResolutionStatus.CANDIDATE
    assert record.shadow_only is True
    assert record.commercial_projection_allowed is False


def test_positive_two_door_cluster_with_70mm_stud_pack(
    authority: StructuralSharedStudPierClusterAuthority,
) -> None:
    # 70mm ~ 3.97 pt
    op1_start = (100.0, 200.0)
    op1_end = (146.48, 200.0)
    op2_start = (150.45, 200.0)  # pier ~ 3.97 pt ~ 70 mm
    op2_end = (196.93, 200.0)

    record = authority.evaluate_two_opening_cluster(
        op1_jamb_start=op1_start,
        op1_jamb_end=op1_end,
        op2_jamb_start=op2_start,
        op2_jamb_end=op2_end,
        host_through_wall_id="WALL_BEDROOMS",
    )
    assert record.classification == ClusterHostClassification.CLUSTER_HOST_CONFIRMED
    assert record.shared_piers[0].pier_type == PierType.TWO_STUD_PACK_70MM
    assert record.shared_piers[0].pier_width_mm == pytest.approx(70.0, abs=2.0)


def test_subminimum_pier_width_fails_closed(
    authority: StructuralSharedStudPierClusterAuthority,
) -> None:
    op1_start = (100.0, 200.0)
    op1_end = (146.48, 200.0)
    op2_start = (148.00, 200.0)  # pier = 1.52 pt (< 3.0 pt minimum)
    op2_end = (194.48, 200.0)

    record = authority.evaluate_two_opening_cluster(
        op1_jamb_start=op1_start,
        op1_jamb_end=op1_end,
        op2_jamb_start=op2_start,
        op2_jamb_end=op2_end,
        host_through_wall_id="WALL_BEDROOMS",
    )
    assert (
        record.classification
        == ClusterHostClassification.ABSTAINED_PIER_WIDTH_OUT_OF_BOUNDS
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_excessive_pier_width_fails_closed(
    authority: StructuralSharedStudPierClusterAuthority,
) -> None:
    op1_start = (100.0, 200.0)
    op1_end = (146.48, 200.0)
    op2_start = (170.00, 200.0)  # pier = 23.52 pt (> 15.0 pt maximum for stud pack)
    op2_end = (216.48, 200.0)

    record = authority.evaluate_two_opening_cluster(
        op1_jamb_start=op1_start,
        op1_jamb_end=op1_end,
        op2_jamb_start=op2_start,
        op2_jamb_end=op2_end,
        host_through_wall_id="WALL_BEDROOMS",
    )
    assert (
        record.classification
        == ClusterHostClassification.ABSTAINED_PIER_WIDTH_OUT_OF_BOUNDS
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_degenerate_opening_span_fails_closed(
    authority: StructuralSharedStudPierClusterAuthority,
) -> None:
    op1_start = (100.0, 200.0)
    op1_end = (110.0, 200.0)  # span = 10 pt (< 20 pt minimum)
    op2_start = (115.10, 200.0)
    op2_end = (161.58, 200.0)

    record = authority.evaluate_two_opening_cluster(
        op1_jamb_start=op1_start,
        op1_jamb_end=op1_end,
        op2_jamb_start=op2_start,
        op2_jamb_end=op2_end,
        host_through_wall_id="WALL_BEDROOMS",
    )
    assert (
        record.classification
        == ClusterHostClassification.ABSTAINED_DEGENERATE_OPENING_SPAN
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_to_dict_schema_invariants(
    authority: StructuralSharedStudPierClusterAuthority,
) -> None:
    op1_start = (100.0, 200.0)
    op1_end = (146.48, 200.0)
    op2_start = (151.58, 200.0)
    op2_end = (198.06, 200.0)

    record = authority.evaluate_two_opening_cluster(
        op1_jamb_start=op1_start,
        op1_jamb_end=op1_end,
        op2_jamb_start=op2_start,
        op2_jamb_end=op2_end,
        host_through_wall_id="WALL_HALLWAY_NORTH",
    )
    d = record.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == record.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert isinstance(d["openings"], list)
    assert isinstance(d["shared_piers"], list)
