import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_waste_drainage_shadow import (
    SourceFloorWasteDrainageShadowAuthority,
    FloorWasteDrainageReceipt,
    DrainKind,
    SCHEMA_VERSION,
)


def test_bathroom_floor_waste_gully():
    authority = SourceFloorWasteDrainageShadowAuthority()

    w = authority.compute_floor_waste(
        room_id="ROOM_BATH_01",
        drain_kind=DrainKind.FLOOR_WASTE_GULLY,
        location_pt=(120.0, 150.0),
        pipe_diameter_pt=2.27,
        has_puddle_flange=True,
        requires_fire_collar=False,
        grate_finish="CHROME_ROUND_GRATE",
        sleeve_oversize_pt=0.71,
    )

    assert w.room_id == "ROOM_BATH_01"
    assert w.drain_kind == DrainKind.FLOOR_WASTE_GULLY
    assert w.pipe_diameter_pt == 2.27
    assert math.isclose(w.slab_penetration_diameter_pt, 2.98, abs_tol=1e-3)
    assert w.has_puddle_flange is True
    assert w.requires_fire_collar is False
    assert w.grate_finish == "CHROME_ROUND_GRATE"


def test_multi_storey_shower_waste_with_fire_collar():
    authority = SourceFloorWasteDrainageShadowAuthority()

    w = authority.compute_floor_waste(
        room_id="ROOM_ENSUITE_01",
        drain_kind=DrainKind.FLOOR_WASTE_SHOWER,
        location_pt=(50.0, 80.0),
        pipe_diameter_pt=1.42,  # 50mm
        requires_fire_collar=True,
        grate_finish="TILE_INSERT_SQUARE",
    )

    assert w.requires_fire_collar is True
    assert w.grate_finish == "TILE_INSERT_SQUARE"


def test_compile_waste_receipt():
    authority = SourceFloorWasteDrainageShadowAuthority()

    w1 = authority.compute_floor_waste(
        room_id="R1",
        drain_kind=DrainKind.FLOOR_WASTE_GULLY,
        location_pt=(10.0, 10.0),
        has_puddle_flange=True,
        requires_fire_collar=True,
    )

    receipt = authority.compile_waste_receipt(
        document_id="DOC_DRAINAGE",
        revision_id="REV_1",
        source_sha256="44558899" * 8,
        drains=[w1],
    )

    assert isinstance(receipt, FloorWasteDrainageReceipt)
    assert receipt.total_drains_count == 1
    assert receipt.total_core_penetrations_count == 1
    assert receipt.total_puddle_flanges_count == 1
    assert receipt.total_fire_collars_count == 1
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_DRAINAGE"
    assert len(d["drains"]) == 1


def test_empty_receipt_abstained():
    authority = SourceFloorWasteDrainageShadowAuthority()

    receipt = authority.compile_waste_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        drains=[],
    )

    assert receipt.total_drains_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        FloorWasteDrainageReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_drains_count=0,
            total_core_penetrations_count=0,
            total_puddle_flanges_count=0,
            total_fire_collars_count=0,
            drains=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
