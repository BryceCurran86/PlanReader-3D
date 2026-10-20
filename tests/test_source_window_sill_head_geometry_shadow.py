import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_window_sill_head_geometry_shadow import (
    SourceWindowSillHeadGeometryShadowAuthority,
    WindowVerticalGeometryReceipt,
    SCHEMA_VERSION,
)


def test_standard_window_vertical_partition():
    authority = SourceWindowSillHeadGeometryShadowAuthority()

    w = authority.compute_window_vertical_partition(
        window_id="WIN_01",
        wall_id="WALL_EXT_01",
        opening_length_pt=50.0,
        wall_thickness_pt=10.0,
        wall_height_pt=100.0,
        sill_height_pt=30.0,
        head_height_pt=80.0,
    )

    assert w.window_id == "WIN_01"
    assert w.wall_id == "WALL_EXT_01"
    assert w.aperture_height_pt == 50.0
    assert w.sub_sill_apron_height_pt == 30.0
    assert w.overhead_lintel_height_pt == 20.0

    # Footprint area = 50.0 * 10.0 = 500.0 pt2
    total_vol = 500.0 * 100.0  # 50000.0
    assert w.aperture_void_volume_pt3 == 500.0 * 50.0  # 25000.0
    assert w.retained_wall_volume_pt3 == 500.0 * 50.0  # 25000.0
    assert math.isclose(w.aperture_void_volume_pt3 + w.retained_wall_volume_pt3, total_vol)


def test_full_height_glazing_no_apron_no_lintel():
    authority = SourceWindowSillHeadGeometryShadowAuthority()

    w = authority.compute_window_vertical_partition(
        window_id="SLIDER_01",
        wall_id="WALL_EXT_02",
        opening_length_pt=80.0,
        wall_thickness_pt=10.0,
        wall_height_pt=100.0,
        sill_height_pt=0.0,
        head_height_pt=100.0,
    )

    assert w.sub_sill_apron_height_pt == 0.0
    assert w.overhead_lintel_height_pt == 0.0
    assert w.aperture_height_pt == 100.0
    assert w.retained_wall_volume_pt3 == 0.0
    assert w.aperture_void_volume_pt3 == 80.0 * 10.0 * 100.0


def test_clamped_vertical_bounds():
    authority = SourceWindowSillHeadGeometryShadowAuthority()

    w = authority.compute_window_vertical_partition(
        window_id="WIN_OVERSHOOT",
        wall_id="WALL_01",
        opening_length_pt=40.0,
        wall_thickness_pt=10.0,
        wall_height_pt=100.0,
        sill_height_pt=-10.0,
        head_height_pt=150.0,
    )

    assert w.sill_height_pt == 0.0
    assert w.head_height_pt == 100.0
    assert w.overhead_lintel_height_pt == 0.0


def test_compile_vertical_geometry_receipt():
    authority = SourceWindowSillHeadGeometryShadowAuthority()

    w1 = authority.compute_window_vertical_partition(
        window_id="W1",
        wall_id="WALL_1",
        opening_length_pt=30.0,
        wall_thickness_pt=10.0,
        wall_height_pt=100.0,
        sill_height_pt=20.0,
        head_height_pt=80.0,
    )

    receipt = authority.compile_vertical_geometry_receipt(
        document_id="DOC_WIN_GEO",
        revision_id="REV_1",
        source_sha256="44332211" * 8,
        windows=[w1],
    )

    assert isinstance(receipt, WindowVerticalGeometryReceipt)
    assert receipt.total_windows_count == 1
    assert receipt.total_glazing_void_volume_pt3 == 30.0 * 10.0 * 60.0
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_WIN_GEO"
    assert len(d["windows"]) == 1


def test_empty_receipt_abstained():
    authority = SourceWindowSillHeadGeometryShadowAuthority()

    receipt = authority.compile_vertical_geometry_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        windows=[],
    )

    assert receipt.total_windows_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        WindowVerticalGeometryReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_windows_count=0,
            total_glazing_void_volume_pt3=0.0,
            total_retained_wall_volume_pt3=0.0,
            windows=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
