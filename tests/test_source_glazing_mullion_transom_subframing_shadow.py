import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_glazing_mullion_transom_subframing_shadow import (
    SourceGlazingMullionTransomSubframingShadowAuthority,
    WindowSubframingReceipt,
    SCHEMA_VERSION,
)


def test_monolithic_single_lite_window():
    authority = SourceGlazingMullionTransomSubframingShadowAuthority()

    assy = authority.partition_window_subframe(
        window_id="W01_MONO",
        total_width_pt=100.0,
        total_height_pt=100.0,
        mullion_count=0,
        transom_count=0,
        frame_profile_thickness_pt=2.0,
    )

    assert assy.window_id == "W01_MONO"
    assert assy.mullion_count == 0
    assert assy.transom_count == 0
    assert len(assy.glass_lites) == 1
    assert assy.mullion_linear_pt == 0.0
    assert assy.transom_linear_pt == 0.0
    assert assy.outer_frame_perimeter_pt == 400.0

    lite = assy.glass_lites[0]
    assert lite.width_pt == 96.0
    assert lite.height_pt == 96.0
    assert lite.area_pt2 == 96.0 * 96.0
    assert lite.aspect_ratio == 1.0


def test_storefront_multi_lite_partition():
    authority = SourceGlazingMullionTransomSubframingShadowAuthority()

    # Total width 304 pt, height 204 pt
    # Outer frame 2.0 pt -> clear_w = 300 pt, clear_h = 200 pt
    # 2 mullions of 3 pt -> net glass w = 300 - 6 = 294 pt / 3 bays = 98 pt each
    # 1 transom of 2 pt -> net glass h = 200 - 2 = 198 pt / 2 tiers = 99 pt each
    assy = authority.partition_window_subframe(
        window_id="STOREFRONT_01",
        total_width_pt=304.0,
        total_height_pt=204.0,
        mullion_count=2,
        transom_count=1,
        frame_profile_thickness_pt=2.0,
        mullion_profile_width_pt=3.0,
        transom_profile_height_pt=2.0,
    )

    assert assy.mullion_count == 2
    assert assy.transom_count == 1
    assert len(assy.glass_lites) == 6  # 3 bays * 2 tiers
    assert assy.mullion_linear_pt == 2 * 200.0  # 400.0
    assert assy.transom_linear_pt == 1 * 300.0  # 300.0

    for lite in assy.glass_lites:
        assert math.isclose(lite.width_pt, 98.0, abs_tol=1e-3)
        assert math.isclose(lite.height_pt, 99.0, abs_tol=1e-3)
        assert math.isclose(lite.area_pt2, 98.0 * 99.0, abs_tol=1e-3)


def test_compile_subframing_receipt():
    authority = SourceGlazingMullionTransomSubframingShadowAuthority()

    a1 = authority.partition_window_subframe(
        window_id="W1",
        total_width_pt=100.0,
        total_height_pt=100.0,
        mullion_count=1,
    )

    receipt = authority.compile_subframing_receipt(
        document_id="DOC_SUBFRAME",
        revision_id="REV_1",
        source_sha256="77889900" * 8,
        assemblies=[a1],
    )

    assert isinstance(receipt, WindowSubframingReceipt)
    assert receipt.total_windows_evaluated == 1
    assert receipt.total_lites_count == 2
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_SUBFRAME"
    assert len(d["assemblies"]) == 1


def test_empty_receipt_abstained():
    authority = SourceGlazingMullionTransomSubframingShadowAuthority()

    receipt = authority.compile_subframing_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        assemblies=[],
    )

    assert receipt.total_windows_evaluated == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        WindowSubframingReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_windows_evaluated=0,
            total_lites_count=0,
            total_mullion_linear_pt=0.0,
            total_transom_linear_pt=0.0,
            total_glazing_area_pt2=0.0,
            assemblies=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
