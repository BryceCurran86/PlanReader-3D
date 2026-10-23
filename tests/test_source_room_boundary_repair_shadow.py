import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_boundary_repair_shadow import (
    SourceRoomBoundaryRepairShadowAuthority,
    RoomBoundaryRepairReceipt,
    BoundaryDefectKind,
    SCHEMA_VERSION,
)


def test_clean_rectangle_room():
    authority = SourceRoomBoundaryRepairShadowAuthority()

    pts = [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0)]
    rec = authority.repair_room_boundary(room_id="ROOM_CLEAN", vertices=pts)

    assert rec.room_id == "ROOM_CLEAN"
    assert rec.was_repaired is False
    assert len(rec.defects_detected) == 0
    assert len(rec.repaired_polygons) == 1
    assert rec.total_area_pt2 == 5000.0


def test_micro_vertex_removal():
    authority = SourceRoomBoundaryRepairShadowAuthority(snap_tolerance_pt=2.5)

    # (100.0, 0.0) followed by jitter (100.5, 0.5) within 2.5 pt
    pts = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.5, 0.5),
        (100.0, 50.0),
        (0.0, 50.0),
    ]
    rec = authority.repair_room_boundary(room_id="ROOM_MICRO", vertices=pts)

    assert rec.was_repaired is True
    assert BoundaryDefectKind.DUPLICATE_OR_MICRO_VERTEX in rec.defects_detected
    assert len(rec.repaired_polygons[0]) == 4


def test_antenna_spike_pruning():
    authority = SourceRoomBoundaryRepairShadowAuthority(snap_tolerance_pt=2.5)

    # Antenna spike into wall cavity at (50.0, -20.0) and back to (50.0, 0.0)
    pts = [
        (0.0, 0.0),
        (50.0, 0.0),
        (50.0, -20.0),  # spike tip
        (50.0, 0.0),    # backtrack
        (100.0, 0.0),
        (100.0, 50.0),
        (0.0, 50.0),
    ]
    rec = authority.repair_room_boundary(room_id="ROOM_SPIKE", vertices=pts)

    assert rec.was_repaired is True
    assert BoundaryDefectKind.COLLAPSED_ANTENNA_SPIKE in rec.defects_detected
    assert rec.total_area_pt2 == 5000.0


def test_bowtie_self_intersection_split():
    authority = SourceRoomBoundaryRepairShadowAuthority()

    # Bowtie figure eight: (0,0) -> (100, 100) -> (0, 100) -> (100, 0)
    pts = [
        (0.0, 0.0),
        (100.0, 100.0),
        (0.0, 100.0),
        (100.0, 0.0),
    ]
    rec = authority.repair_room_boundary(room_id="ROOM_BOWTIE", vertices=pts)

    assert rec.was_repaired is True
    assert BoundaryDefectKind.BOWTIE_SELF_INTERSECTION in rec.defects_detected
    assert len(rec.repaired_polygons) == 2
    # Two triangles meeting at (50, 50), each with area 2500 -> total 5000
    assert math.isclose(rec.total_area_pt2, 5000.0, abs_tol=1e-2)


def test_compile_repair_receipt():
    authority = SourceRoomBoundaryRepairShadowAuthority()

    r1 = authority.repair_room_boundary(
        room_id="R1",
        vertices=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
    )
    r2 = authority.repair_room_boundary(
        room_id="R2",
        vertices=[(0.0, 0.0), (10.0, 0.0), (10.5, 0.2), (10.0, 10.0), (0.0, 10.0)],
    )

    receipt = authority.compile_repair_receipt(
        document_id="DOC_REPAIR",
        revision_id="REV_1",
        source_sha256="11002299" * 8,
        records=[r1, r2],
    )

    assert isinstance(receipt, RoomBoundaryRepairReceipt)
    assert receipt.total_rooms_evaluated == 2
    assert receipt.repaired_rooms_count == 1
    assert receipt.clean_rooms_count == 1
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_REPAIR"
    assert len(d["records"]) == 2


def test_empty_receipt_abstained():
    authority = SourceRoomBoundaryRepairShadowAuthority()

    receipt = authority.compile_repair_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        records=[],
    )

    assert receipt.total_rooms_evaluated == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        RoomBoundaryRepairReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_rooms_evaluated=0,
            repaired_rooms_count=0,
            clean_rooms_count=0,
            total_repaired_area_pt2=0.0,
            records=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
