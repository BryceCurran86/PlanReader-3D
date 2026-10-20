import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wall_acoustic_insulation_shadow import (
    SourceWallAcousticInsulationShadowAuthority,
    WallAcousticInsulationReceipt,
    SCHEMA_VERSION,
)


def test_acoustic_wall_with_opening_deduction():
    authority = SourceWallAcousticInsulationShadowAuthority()

    rec = authority.compute_wall_insulation(
        wall_id="WALL_ACOUSTIC_01",
        wall_type="TYPE_W4_ACOUSTIC",
        wall_length_pt=100.0,
        wall_height_pt=80.0,
        openings_area_pt2=1500.0,
        cavity_thickness_pt=3.0,
        r_value=2.5,
        rw_rating=52,
    )

    assert rec.wall_id == "WALL_ACOUSTIC_01"
    assert rec.wall_type == "TYPE_W4_ACOUSTIC"
    assert rec.gross_wall_area_pt2 == 8000.0
    assert rec.openings_deduction_area_pt2 == 1500.0
    assert rec.net_insulation_area_pt2 == 6500.0
    assert rec.insulation_volume_pt3 == 19500.0
    assert rec.r_value == 2.5
    assert rec.rw_rating == 52


def test_opening_exceeding_wall_area_clamped():
    authority = SourceWallAcousticInsulationShadowAuthority()

    rec = authority.compute_wall_insulation(
        wall_id="WALL_SMALL",
        wall_type="TYPE_W1",
        wall_length_pt=10.0,
        wall_height_pt=10.0,
        openings_area_pt2=150.0,
    )

    assert rec.gross_wall_area_pt2 == 100.0
    assert rec.net_insulation_area_pt2 == 0.0
    assert rec.insulation_volume_pt3 == 0.0


def test_compile_insulation_receipt():
    authority = SourceWallAcousticInsulationShadowAuthority()

    r1 = authority.compute_wall_insulation(
        wall_id="W1",
        wall_type="W4",
        wall_length_pt=50.0,
        wall_height_pt=50.0,
        openings_area_pt2=500.0,
        cavity_thickness_pt=2.0,
    )

    receipt = authority.compile_insulation_receipt(
        document_id="DOC_INSULATION",
        revision_id="REV_1",
        source_sha256="77881122" * 8,
        records=[r1],
    )

    assert isinstance(receipt, WallAcousticInsulationReceipt)
    assert receipt.total_insulated_walls_count == 1
    assert receipt.total_net_insulation_area_pt2 == 2000.0
    assert receipt.total_insulation_volume_pt3 == 4000.0
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_INSULATION"
    assert len(d["records"]) == 1


def test_empty_receipt_abstained():
    authority = SourceWallAcousticInsulationShadowAuthority()

    receipt = authority.compile_insulation_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        records=[],
    )

    assert receipt.total_insulated_walls_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        WallAcousticInsulationReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_insulated_walls_count=0,
            total_net_insulation_area_pt2=0.0,
            total_insulation_volume_pt3=0.0,
            records=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
