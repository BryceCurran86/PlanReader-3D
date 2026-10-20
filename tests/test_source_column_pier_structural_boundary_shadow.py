import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_column_pier_structural_boundary_shadow import (
    SourceColumnPierStructuralBoundaryShadowAuthority,
    ColumnPierInventoryReceipt,
    StructuralColumnProfile,
    ColumnPlacement,
    SCHEMA_VERSION,
)


def test_circular_column_creation():
    authority = SourceColumnPierStructuralBoundaryShadowAuthority()

    col = authority.create_circular_column(
        center_pt=(150.0, 250.0),
        diameter_pt=20.0,
        height_pt=100.0,
        placement=ColumnPlacement.ISOLATED_IN_ROOM,
        material="CONCRETE",
    )

    expected_area = math.pi * (10.0 ** 2)
    assert col.profile == StructuralColumnProfile.CIRCULAR
    assert col.placement == ColumnPlacement.ISOLATED_IN_ROOM
    assert math.isclose(col.cross_sectional_area_pt2, expected_area, rel_tol=1e-3)
    assert math.isclose(col.volume_pt3, expected_area * 100.0, rel_tol=1e-3)
    assert col.centroid == (150.0, 250.0)
    assert len(col.boundary_polygon) == 16
    assert col.material == "CONCRETE"


def test_polygonal_rectangular_column_creation():
    authority = SourceColumnPierStructuralBoundaryShadowAuthority()

    rect_poly = ((10.0, 10.0), (30.0, 10.0), (30.0, 40.0), (10.0, 40.0))
    col = authority.create_polygonal_column(
        profile=StructuralColumnProfile.RECTANGULAR,
        boundary_polygon=rect_poly,
        height_pt=100.0,
        placement=ColumnPlacement.EMBEDDED_IN_WALL,
        material="REINFORCED_CONCRETE",
    )

    assert col.profile == StructuralColumnProfile.RECTANGULAR
    assert col.placement == ColumnPlacement.EMBEDDED_IN_WALL
    assert col.cross_sectional_area_pt2 == 600.0
    assert col.volume_pt3 == 60000.0
    assert col.centroid == (20.0, 25.0)


def test_engaged_masonry_pier_creation():
    authority = SourceColumnPierStructuralBoundaryShadowAuthority()

    pier_poly = ((100.0, 100.0), (120.0, 100.0), (120.0, 120.0), (100.0, 120.0))
    pier = authority.create_polygonal_column(
        profile=StructuralColumnProfile.MASONRY_PIER,
        boundary_polygon=pier_poly,
        height_pt=90.0,
        placement=ColumnPlacement.ENGAGED_PIER,
        material="BRICKWORK",
    )

    assert pier.profile == StructuralColumnProfile.MASONRY_PIER
    assert pier.placement == ColumnPlacement.ENGAGED_PIER
    assert pier.cross_sectional_area_pt2 == 400.0
    assert pier.volume_pt3 == 36000.0


def test_compile_column_inventory_receipt():
    authority = SourceColumnPierStructuralBoundaryShadowAuthority()

    col1 = authority.create_circular_column(
        center_pt=(50.0, 50.0),
        diameter_pt=10.0,
        height_pt=100.0,
        placement=ColumnPlacement.ISOLATED_IN_ROOM,
    )
    col2 = authority.create_polygonal_column(
        profile=StructuralColumnProfile.RECTANGULAR,
        boundary_polygon=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        height_pt=100.0,
        placement=ColumnPlacement.EMBEDDED_IN_WALL,
    )
    col3 = authority.create_polygonal_column(
        profile=StructuralColumnProfile.MASONRY_PIER,
        boundary_polygon=((20.0, 20.0), (30.0, 20.0), (30.0, 30.0), (20.0, 30.0)),
        height_pt=100.0,
        placement=ColumnPlacement.ENGAGED_PIER,
    )

    receipt = authority.compile_column_inventory_receipt(
        document_id="DOC_COLUMNS",
        revision_id="REV_A",
        source_sha256="aabbccdd" * 8,
        columns=[col1, col2, col3],
    )

    assert isinstance(receipt, ColumnPierInventoryReceipt)
    assert receipt.total_columns_count == 3
    assert receipt.isolated_columns_count == 1
    assert receipt.embedded_columns_count == 1
    assert receipt.engaged_piers_count == 1
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_COLUMNS"
    assert len(d["columns"]) == 3


def test_column_inventory_receipt_empty():
    authority = SourceColumnPierStructuralBoundaryShadowAuthority()

    receipt = authority.compile_column_inventory_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        columns=[],
    )

    assert receipt.total_columns_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_column_inventory_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        ColumnPierInventoryReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_columns_count=0,
            isolated_columns_count=0,
            embedded_columns_count=0,
            engaged_piers_count=0,
            total_column_volume_pt3=0.0,
            columns=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
