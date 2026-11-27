"""A20/A22/A23/A25 tests: multi-sheet source admission packet, finish thickness, wall extent, and elevation material witnesses."""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_finish_specification_witness_shadow import (
    extract_external_elevation_material_witness,
    extract_finish_thickness_witness,
    extract_wall_finish_extent_witness,
)
from pb_source_floor_plan_page_scope import classify_source_floor_plan_pages
from tests.test_source_floor_plan_page_scope import _doc


def test_a25_drawing_set_without_finish_specs_abstains_cleanly() -> None:
    # Structural/setout drawing set (floor, section, setout, schedule) with NO finish spec/RCP
    doc = _doc("FLOOR PLAN", "SECTION A-A", "SLAB SETOUT PLAN", "DOOR SCHEDULE")
    try:
        scope = classify_source_floor_plan_pages(doc, range(4))
        packet = scope.build_source_set_admission_packet()
        assert packet.floor_plan_pages == (0,)
        assert packet.section_pages == (1,)
        assert packet.setout_or_detail_pages == (2,)
        assert packet.schedule_pages == (3,)
        assert packet.has_finish_specification_source is False
        assert packet.finish_specification_status == "abstained_no_finish_specification_source"
        assert packet.commercial_quantity_authority is False
    finally:
        doc.close()


def test_a25_drawing_set_with_rcp_or_finish_plan_marks_finish_source_present() -> None:
    doc = _doc("FLOOR PLAN", "REFLECTED CEILING PLAN", "ELEVATIONS")
    try:
        scope = classify_source_floor_plan_pages(doc, range(3))
        packet = scope.build_source_set_admission_packet()
        assert packet.floor_plan_pages == (0,)
        assert packet.rcp_pages == (1,)
        assert packet.elevation_pages == (2,)
        assert packet.has_finish_specification_source is True
        assert packet.finish_specification_status == "finish_specification_source_present"
        assert packet.commercial_quantity_authority is False
    finally:
        doc.close()


def test_a20_finish_thickness_positive_and_conflict_abstention() -> None:
    ok = extract_finish_thickness_witness("10mm PLASTERBOARD LINING TO ALL INTERNAL WALLS")
    assert ok.status == EvidenceResolutionStatus.CORROBORATED
    assert ok.thickness_mm == 10.0
    assert ok.material_label == "plasterboard"
    assert ok.commercial_authority_granted is False

    conflict = extract_finish_thickness_witness("10mm PLASTERBOARD OR 13mm PLASTERBOARD")
    assert conflict.status == EvidenceResolutionStatus.CONFLICT
    assert conflict.thickness_mm is None

    empty = extract_finish_thickness_witness("PAINTED WALL")
    assert empty.status == EvidenceResolutionStatus.ABSTAINED


def test_a22_wall_finish_extent_full_partial_wet_area_and_conflict() -> None:
    full = extract_wall_finish_extent_witness("FULL HEIGHT TILES TO BATHROOM SHOWER")
    assert full.status == EvidenceResolutionStatus.CORROBORATED
    assert full.extent_mode == "full_height"
    assert full.wet_area_indicated is True

    partial = extract_wall_finish_extent_witness("WATERPROOFING TO 1.8M AND DADO TO 1,800mm")
    assert partial.status == EvidenceResolutionStatus.CORROBORATED
    assert partial.extent_mode == "partial_height"
    assert partial.extent_height_mm == 1800
    assert partial.wet_area_indicated is True

    conflict = extract_wall_finish_extent_witness("FULL HEIGHT TILES / TILES TO 1200mm")
    assert conflict.status == EvidenceResolutionStatus.CONFLICT
    assert conflict.extent_mode is None


def test_a23_external_elevation_material_scope_and_revision_guards() -> None:
    ok = extract_external_elevation_material_witness(
        text="FACE BRICK LOWER WALL WITH COLORBOND CLADDING UPPER",
        view_type="elevation",
        document_id="doc-1",
        revision_id="rev-2",
        source_sha256="e" * 64,
        expected_revision_id="rev-2",
    )
    assert ok.status == EvidenceResolutionStatus.CORROBORATED
    assert ok.materials == ("face_brick", "metal_cladding")
    assert ok.commercial_authority_granted is False

    wrong_view = extract_external_elevation_material_witness(
        text="FACE BRICK",
        view_type="floor_plan",
        document_id="doc-1",
        revision_id="rev-2",
        source_sha256="e" * 64,
    )
    assert wrong_view.status == EvidenceResolutionStatus.ABSTAINED

    wrong_rev = extract_external_elevation_material_witness(
        text="FACE BRICK",
        view_type="elevation",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="e" * 64,
        expected_revision_id="rev-2",
    )
    assert wrong_rev.status == EvidenceResolutionStatus.CONFLICT
