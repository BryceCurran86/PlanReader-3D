import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wall_core_thickness_cavity_decomposition_shadow import (
    SourceWallCoreCavityDecompositionShadowAuthority,
    CompositeWallDecompositionReceipt,
    WallAssemblyType,
    WallLeafRole,
    SCHEMA_VERSION,
)


def test_decompose_cavity_brick():
    authority = SourceWallCoreCavityDecompositionShadowAuthority()

    assy = authority.decompose_cavity_brick(
        inner_leaf_thickness_pt=110.0,
        cavity_width_pt=50.0,
        outer_leaf_thickness_pt=110.0,
        inner_material="COMMON_BRICK",
        outer_material="FACE_BRICK",
    )

    assert assy.assembly_type == WallAssemblyType.CAVITY_BRICK
    assert assy.overall_thickness_pt == 270.0
    assert assy.structural_core_thickness_pt == 110.0
    assert assy.cavity_width_pt == 50.0
    assert len(assy.leaves) == 3

    inner, cav, outer = assy.leaves
    assert inner.role == WallLeafRole.STRUCTURAL_INNER_CORE
    assert inner.is_loadbearing is True
    assert cav.role == WallLeafRole.INSULATED_OR_AIR_CAVITY
    assert cav.is_loadbearing is False
    assert outer.role == WallLeafRole.ARCHITECTURAL_OUTER_VENEER
    assert outer.is_loadbearing is False


def test_decompose_brick_veneer():
    authority = SourceWallCoreCavityDecompositionShadowAuthority()

    assy = authority.decompose_brick_veneer(
        stud_core_thickness_pt=90.0,
        cavity_width_pt=40.0,
        brick_veneer_thickness_pt=110.0,
    )

    assert assy.assembly_type == WallAssemblyType.BRICK_VENEER
    assert assy.overall_thickness_pt == 240.0
    assert assy.structural_core_thickness_pt == 90.0
    assert assy.cavity_width_pt == 40.0
    assert len(assy.leaves) == 3


def test_decompose_solid_monolithic():
    authority = SourceWallCoreCavityDecompositionShadowAuthority()

    assy = authority.decompose_solid_monolithic(
        thickness_pt=200.0,
        material="PRECAST_CONCRETE",
    )

    assert assy.assembly_type == WallAssemblyType.SOLID_MONOLITHIC
    assert assy.overall_thickness_pt == 200.0
    assert assy.structural_core_thickness_pt == 200.0
    assert assy.cavity_width_pt == 0.0
    assert len(assy.leaves) == 1
    assert assy.leaves[0].is_loadbearing is True


def test_compile_decomposition_receipt():
    authority = SourceWallCoreCavityDecompositionShadowAuthority()

    a1 = authority.decompose_cavity_brick()
    a2 = authority.decompose_solid_monolithic(thickness_pt=150.0)

    receipt = authority.compile_decomposition_receipt(
        document_id="DOC_WALL_ASSY",
        revision_id="REV_2",
        source_sha256="11223344" * 8,
        assemblies=[a1, a2],
    )

    assert isinstance(receipt, CompositeWallDecompositionReceipt)
    assert receipt.total_assemblies_count == 2
    assert receipt.cavity_assemblies_count == 1
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_WALL_ASSY"
    assert len(d["assemblies"]) == 2


def test_empty_receipt_abstained():
    authority = SourceWallCoreCavityDecompositionShadowAuthority()

    receipt = authority.compile_decomposition_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        assemblies=[],
    )

    assert receipt.total_assemblies_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        CompositeWallDecompositionReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_assemblies_count=0,
            cavity_assemblies_count=0,
            assemblies=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
