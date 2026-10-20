import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_sheet_registration_alignment_shadow import (
    SourceSheetRegistrationAlignmentShadowAuthority,
    SheetRegistrationAlignmentReceipt,
    SheetControlPointRecord,
    SCHEMA_VERSION,
)


def test_pure_translation_alignment():
    authority = SourceSheetRegistrationAlignmentShadowAuthority()

    cp1 = SheetControlPointRecord("GRID_A1", local_pt=(10.0, 20.0), global_pt=(60.0, 120.0))
    cp2 = SheetControlPointRecord("GRID_B1", local_pt=(110.0, 20.0), global_pt=(160.0, 120.0))

    t = authority.compute_sheet_alignment(sheet_id="A101", control_point_1=cp1, control_point_2=cp2)

    assert t.sheet_id == "A101"
    assert math.isclose(t.scale_factor, 1.0, abs_tol=1e-5)
    assert math.isclose(t.rotation_deg, 0.0, abs_tol=1e-3)
    assert math.isclose(t.translation_x, 50.0, abs_tol=1e-3)
    assert math.isclose(t.translation_y, 100.0, abs_tol=1e-3)
    assert t.residual_error_pt < 1e-4

    # Test point projection
    pt_g = t.transform_point((50.0, 50.0))
    assert pt_g == (100.0, 150.0)


def test_scale_rotation_90deg():
    authority = SourceSheetRegistrationAlignmentShadowAuthority()

    # Local vector: (100, 0)
    # Global vector: (0, 200) -> scale=2.0, rotation=90 deg
    cp1 = SheetControlPointRecord("P1", local_pt=(0.0, 0.0), global_pt=(500.0, 1000.0))
    cp2 = SheetControlPointRecord("P2", local_pt=(100.0, 0.0), global_pt=(500.0, 1200.0))

    t = authority.compute_sheet_alignment(sheet_id="A102", control_point_1=cp1, control_point_2=cp2)

    assert math.isclose(t.scale_factor, 2.0, abs_tol=1e-4)
    assert math.isclose(t.rotation_deg, 90.0, abs_tol=1e-2)
    assert math.isclose(t.translation_x, 500.0, abs_tol=1e-2)
    assert math.isclose(t.translation_y, 1000.0, abs_tol=1e-2)

    # Midpoint (50, 0) should map to (500, 1100)
    mid_g = t.transform_point((50.0, 0.0))
    assert math.isclose(mid_g[0], 500.0, abs_tol=1e-2)
    assert math.isclose(mid_g[1], 1100.0, abs_tol=1e-2)


def test_coincident_points_raises_error():
    authority = SourceSheetRegistrationAlignmentShadowAuthority()

    cp1 = SheetControlPointRecord("P1", local_pt=(10.0, 10.0), global_pt=(100.0, 100.0))
    cp2 = SheetControlPointRecord("P2", local_pt=(10.0, 10.0), global_pt=(200.0, 200.0))

    with pytest.raises(ValueError, match="coincident"):
        authority.compute_sheet_alignment(sheet_id="A103", control_point_1=cp1, control_point_2=cp2)


def test_compile_alignment_receipt():
    authority = SourceSheetRegistrationAlignmentShadowAuthority()

    cp1 = SheetControlPointRecord("P1", local_pt=(0.0, 0.0), global_pt=(0.0, 0.0))
    cp2 = SheetControlPointRecord("P2", local_pt=(10.0, 0.0), global_pt=(10.0, 0.0))
    t1 = authority.compute_sheet_alignment(sheet_id="S1", control_point_1=cp1, control_point_2=cp2)

    receipt = authority.compile_alignment_receipt(
        document_id="DOC_ALIGN",
        revision_id="REV_1",
        source_sha256="55443322" * 8,
        transforms=[t1],
    )

    assert isinstance(receipt, SheetRegistrationAlignmentReceipt)
    assert receipt.total_registered_sheets == 1
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_ALIGN"
    assert len(d["transforms"]) == 1


def test_empty_receipt_abstained():
    authority = SourceSheetRegistrationAlignmentShadowAuthority()

    receipt = authority.compile_alignment_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        transforms=[],
    )

    assert receipt.total_registered_sheets == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        SheetRegistrationAlignmentReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_registered_sheets=0,
            transforms=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
