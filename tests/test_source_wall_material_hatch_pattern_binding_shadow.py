import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wall_material_hatch_pattern_binding_shadow import (
    SourceWallMaterialHatchPatternBindingShadowAuthority,
    WallMaterialBindingReceipt,
    WallHatchType,
    SCHEMA_VERSION,
)


def test_bind_solid_fill_concrete():
    authority = SourceWallMaterialHatchPatternBindingShadowAuthority()

    b = authority.bind_wall_hatch(
        wall_id="WALL_CORE_01",
        hatch_type=WallHatchType.SOLID_FILL,
    )

    assert b.detected_hatch == WallHatchType.SOLID_FILL
    assert b.bound_material == "REINFORCED_CONCRETE"
    assert b.confidence >= 0.95
    assert b.is_structural is True


def test_bind_diagonal_brickwork():
    authority = SourceWallMaterialHatchPatternBindingShadowAuthority()

    b = authority.bind_wall_hatch(
        wall_id="WALL_BRICK_01",
        hatch_type=WallHatchType.DIAGONAL_SINGLE,
        interior_lines_count=6,
        average_spacing_pt=5.0,
    )

    assert b.detected_hatch == WallHatchType.DIAGONAL_SINGLE
    assert b.bound_material == "BRICK_MASONRY"
    assert b.confidence == 0.90
    assert b.is_structural is True
    assert b.spacing_pt == 5.0


def test_bind_insulated_sandwich_panel():
    authority = SourceWallMaterialHatchPatternBindingShadowAuthority()

    b = authority.bind_wall_hatch(
        wall_id="FREEZER_WALL_01",
        hatch_type=WallHatchType.INSULATION_BATT_OR_ZIGZAG,
        interior_lines_count=10,
    )

    assert b.detected_hatch == WallHatchType.INSULATION_BATT_OR_ZIGZAG
    assert b.bound_material == "INSULATED_SANDWICH_PANEL"
    assert b.confidence >= 0.90
    assert b.is_structural is True


def test_bind_unhatched_drywall():
    authority = SourceWallMaterialHatchPatternBindingShadowAuthority()

    b = authority.bind_wall_hatch(
        wall_id="PARTITION_01",
        hatch_type=WallHatchType.EMPTY_OR_UNHATCHED,
    )

    assert b.detected_hatch == WallHatchType.EMPTY_OR_UNHATCHED
    assert b.bound_material == "LIGHTWEIGHT_STUD_DRYWALL"
    assert b.is_structural is False


def test_compile_hatch_binding_receipt():
    authority = SourceWallMaterialHatchPatternBindingShadowAuthority()

    b1 = authority.bind_wall_hatch(wall_id="W1", hatch_type=WallHatchType.SOLID_FILL)
    b2 = authority.bind_wall_hatch(wall_id="W2", hatch_type=WallHatchType.EMPTY_OR_UNHATCHED)

    receipt = authority.compile_hatch_binding_receipt(
        document_id="DOC_HATCH",
        revision_id="REV_1",
        source_sha256="55667788" * 8,
        bindings=[b1, b2],
    )

    assert isinstance(receipt, WallMaterialBindingReceipt)
    assert receipt.total_walls_evaluated == 2
    assert receipt.bound_materials_count == 1
    assert receipt.unhatched_count == 1
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_HATCH"
    assert len(d["bindings"]) == 2


def test_empty_receipt_abstained():
    authority = SourceWallMaterialHatchPatternBindingShadowAuthority()

    receipt = authority.compile_hatch_binding_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        bindings=[],
    )

    assert receipt.total_walls_evaluated == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        WallMaterialBindingReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_walls_evaluated=0,
            bound_materials_count=0,
            unhatched_count=0,
            bindings=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
