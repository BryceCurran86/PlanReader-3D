import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_curtain_wall_spandrel_vision_shadow import (
    SourceCurtainWallSpandrelVisionShadowAuthority,
    CurtainWallSpandrelVisionReceipt,
    SCHEMA_VERSION,
)


def test_standard_curtain_wall_bay_partition():
    authority = SourceCurtainWallSpandrelVisionShadowAuthority()

    bay = authority.compute_curtain_wall_bay(
        bay_id="BAY_01",
        wall_id="CW_NORTH_01",
        bay_width_pt=40.0,
        story_height_pt=100.0,
        vision_sill_height_pt=30.0,
        vision_head_height_pt=70.0,
        spandrel_insulation_thickness_pt=1.5,
    )

    assert bay.bay_id == "BAY_01"
    assert bay.bay_width_pt == 40.0
    assert bay.story_height_pt == 100.0
    assert bay.vision_area_pt2 == 1600.0    # 40 * 40
    assert bay.spandrel_area_pt2 == 2400.0  # 40 * (30 + 30)
    assert bay.vision_area_pt2 + bay.spandrel_area_pt2 == 4000.0 # 40 * 100
    assert bay.spandrel_insulation_volume_pt3 == 3600.0 # 2400 * 1.5
    assert bay.slab_edge_firestop_length_pt == 40.0


def test_clamped_bounds():
    authority = SourceCurtainWallSpandrelVisionShadowAuthority()

    bay = authority.compute_curtain_wall_bay(
        bay_id="BAY_CLAMP",
        wall_id="CW_02",
        bay_width_pt=50.0,
        story_height_pt=100.0,
        vision_sill_height_pt=-10.0,
        vision_head_height_pt=150.0,
    )

    assert bay.vision_sill_height_pt == 0.0
    assert bay.vision_head_height_pt == 100.0
    assert bay.vision_area_pt2 == 5000.0
    assert bay.spandrel_area_pt2 == 0.0


def test_omitted_bay_geometry_does_not_invent_typical_heights():
    authority = SourceCurtainWallSpandrelVisionShadowAuthority()

    bay = authority.compute_curtain_wall_bay(
        bay_id="BAY_UNKNOWN",
        wall_id="CW_UNKNOWN",
    )

    assert bay.bay_width_pt == 0.0
    assert bay.story_height_pt == 0.0
    assert bay.vision_sill_height_pt == 0.0
    assert bay.vision_head_height_pt == 0.0
    assert bay.vision_area_pt2 == 0.0
    assert bay.spandrel_glass_finish == ""


def test_compile_curtain_wall_receipt():
    authority = SourceCurtainWallSpandrelVisionShadowAuthority()

    b1 = authority.compute_curtain_wall_bay(
        bay_id="B1",
        wall_id="CW1",
        bay_width_pt=30.0,
        story_height_pt=90.0,
        vision_sill_height_pt=30.0,
        vision_head_height_pt=60.0,
    )

    receipt = authority.compile_curtain_wall_receipt(
        document_id="DOC_CW",
        revision_id="REV_1",
        source_sha256="aabb5544" * 8,
        bays=[b1],
    )

    assert isinstance(receipt, CurtainWallSpandrelVisionReceipt)
    assert receipt.total_bays_count == 1
    assert receipt.total_vision_area_pt2 == 900.0  # 30 * 30
    assert receipt.total_spandrel_area_pt2 == 1800.0 # 30 * 60
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_CW"
    assert len(d["bays"]) == 1


def test_empty_receipt_abstained():
    authority = SourceCurtainWallSpandrelVisionShadowAuthority()

    receipt = authority.compile_curtain_wall_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        bays=[],
    )

    assert receipt.total_bays_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        CurtainWallSpandrelVisionReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_bays_count=0,
            total_vision_area_pt2=0.0,
            total_spandrel_area_pt2=0.0,
            total_spandrel_insulation_volume_pt3=0.0,
            bays=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
