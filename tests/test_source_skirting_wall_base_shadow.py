import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_skirting_wall_base_shadow import (
    SourceSkirtingWallBaseShadowAuthority,
    SkirtingWallBaseReceipt,
    SkirtingMaterialProfile,
    SCHEMA_VERSION,
)


def test_standard_room_skirting_with_deductions():
    authority = SourceSkirtingWallBaseShadowAuthority()

    rec = authority.compute_room_skirting(
        room_id="ROOM_BED_01",
        gross_perimeter_pt=200.0,
        doorway_widths_pt=[25.0],
        joinery_lengths_pt=[60.0],
        profile=SkirtingMaterialProfile.TIMBER_MDF_BEVELLED,
        internal_corners_count=4,
        external_corners_count=0,
    )

    assert rec.room_id == "ROOM_BED_01"
    assert rec.gross_perimeter_pt == 200.0
    assert rec.doorways_deduction_pt == 25.0
    assert rec.joinery_deduction_pt == 60.0
    assert rec.net_skirting_length_pt == 115.0
    assert rec.skirting_profile == SkirtingMaterialProfile.TIMBER_MDF_BEVELLED
    assert rec.internal_corners_count == 4
    assert rec.external_corners_count == 0


def test_deductions_exceeding_perimeter_clamped():
    authority = SourceSkirtingWallBaseShadowAuthority()

    rec = authority.compute_room_skirting(
        room_id="ROOM_ALCOVE",
        gross_perimeter_pt=50.0,
        doorway_widths_pt=[40.0],
        joinery_lengths_pt=[30.0],
    )

    assert rec.net_skirting_length_pt == 0.0
    assert rec.internal_corners_count == 0


def test_omitted_internal_corners_do_not_invent_rectangle():
    authority = SourceSkirtingWallBaseShadowAuthority()

    rec = authority.compute_room_skirting(
        room_id="ROOM_UNKNOWN",
        gross_perimeter_pt=80.0,
    )

    assert rec.internal_corners_count == 0
    assert rec.external_corners_count == 0
    assert rec.skirting_profile == SkirtingMaterialProfile.UNKNOWN


def test_compile_skirting_receipt():
    authority = SourceSkirtingWallBaseShadowAuthority()

    r1 = authority.compute_room_skirting(
        room_id="R1",
        gross_perimeter_pt=100.0,
        doorway_widths_pt=[20.0],
    )

    receipt = authority.compile_skirting_receipt(
        document_id="DOC_SKIRTING",
        revision_id="REV_1",
        source_sha256="55661122" * 8,
        records=[r1],
    )

    assert isinstance(receipt, SkirtingWallBaseReceipt)
    assert receipt.total_rooms_count == 1
    assert receipt.total_gross_perimeter_pt == 100.0
    assert receipt.total_doorways_deducted_pt == 20.0
    assert receipt.total_net_skirting_length_pt == 80.0
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_SKIRTING"
    assert len(d["records"]) == 1


def test_empty_receipt_abstained():
    authority = SourceSkirtingWallBaseShadowAuthority()

    receipt = authority.compile_skirting_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        records=[],
    )

    assert receipt.total_rooms_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        SkirtingWallBaseReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_rooms_count=0,
            total_gross_perimeter_pt=0.0,
            total_doorways_deducted_pt=0.0,
            total_net_skirting_length_pt=0.0,
            total_internal_corners_count=0,
            total_external_corners_count=0,
            records=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
