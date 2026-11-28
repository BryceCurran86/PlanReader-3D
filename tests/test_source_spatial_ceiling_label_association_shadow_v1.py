"""Tests for generic spatial/viewport ceiling label association shadow (Item 4)."""
from __future__ import annotations

from pathlib import Path

from pb_source_spatial_ceiling_label_association_shadow import (
    CeilingMaterialHeightObservation,
    RoomLabelSpatialObservation,
    ViewportScopeInput,
    associate_ceiling_labels_spatially_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA = "e" * 64
_VP = ViewportScopeInput(source_sha256=_SHA, page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(0, 0, 1000, 800))


def test_recovers_distinct_block_no_pairs_via_polygon_containment():
    rooms = (
        RoomLabelSpatialObservation(
            room_id="r1", room_label="ROOM_A", source_sha256=_SHA, page_id="9", viewport_id="vp_rcp_1",
            bbox_pdf_pts=(50, 50, 100, 65), block_no=10,
            room_polygon_pdf_pts=((20, 20), (200, 20), (200, 200), (20, 200)),
        ),
        RoomLabelSpatialObservation(
            room_id="r2", room_label="ROOM_B", source_sha256=_SHA, page_id="9", viewport_id="vp_rcp_1",
            bbox_pdf_pts=(300, 50, 360, 65), block_no=11,
            room_polygon_pdf_pts=((250, 20), (450, 20), (450, 200), (250, 200)),
        ),
    )
    obs = (
        CeilingMaterialHeightObservation(
            observation_id="c1", material_code="FPB", height_mm=2400, source_sha256=_SHA,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(80, 110, 130, 130), block_no=99,
        ),
        CeilingMaterialHeightObservation(
            observation_id="c2", material_code="GRID", height_mm=2700, source_sha256=_SHA,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(320, 110, 380, 130), block_no=104,
        ),
    )
    rep = associate_ceiling_labels_spatially_shadow(viewport=_VP, rooms=rooms, ceiling_observations=obs)
    assert rep.status == "SPATIAL_CEILING_ASSOCIATION_SHADOW_READY"
    assert rep.cross_block_spatial_recovered_count == 2
    assert rep.same_block_no_count == 0
    assert rep.commercial_projection_allowed is False
    by_id = {a.room_id: a for a in rep.room_associations}
    assert by_id["r1"].material_code == "FPB" and by_id["r1"].height_mm == 2400
    assert by_id["r2"].material_code == "GRID" and by_id["r2"].height_mm == 2700


def test_equidistant_ambiguous_label_and_legend_and_conflict_vetoes():
    rooms = (
        RoomLabelSpatialObservation(
            room_id="r1", room_label="ROOM_A", source_sha256=_SHA, page_id="9", viewport_id="vp_rcp_1",
            bbox_pdf_pts=(100, 100, 140, 115), block_no=1,
        ),
        RoomLabelSpatialObservation(
            room_id="r2", room_label="ROOM_B", source_sha256=_SHA, page_id="9", viewport_id="vp_rcp_1",
            bbox_pdf_pts=(200, 100, 240, 115), block_no=2,
        ),
        RoomLabelSpatialObservation(
            room_id="r3", room_label="ROOM_C", source_sha256=_SHA, page_id="9", viewport_id="vp_rcp_1",
            bbox_pdf_pts=(500, 100, 540, 115), block_no=3,
        ),
    )
    obs = (
        # Equidistant between r1 (x=120) and r2 (x=220) -> MUST be vetoed as ambiguous
        CeilingMaterialHeightObservation(
            observation_id="c_ambig", material_code="FPB", height_mm=2400, source_sha256=_SHA,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(160, 100, 180, 115), block_no=50,
        ),
        # Legend sample -> MUST be vetoed
        CeilingMaterialHeightObservation(
            observation_id="c_legend", material_code="GRID", height_mm=2700, source_sha256=_SHA,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(105, 105, 125, 115), block_no=51,
            in_legend_or_title_region=True,
        ),
        # Conflicting marks right on top of r3 -> r3 MUST abstain
        CeilingMaterialHeightObservation(
            observation_id="c_conf1", material_code="FPB", height_mm=2400, source_sha256=_SHA,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(505, 120, 535, 132), block_no=52,
        ),
        CeilingMaterialHeightObservation(
            observation_id="c_conf2", material_code="GRID", height_mm=3000, source_sha256=_SHA,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(505, 135, 535, 147), block_no=53,
        ),
        # Cross-SHA tampered observation -> MUST be vetoed out of scope
        CeilingMaterialHeightObservation(
            observation_id="c_bad_sha", material_code="FPB", height_mm=2400, source_sha256="f" * 64,
            page_id="9", viewport_id="vp_rcp_1", bbox_pdf_pts=(105, 118, 135, 130), block_no=54,
        ),
    )
    rep = associate_ceiling_labels_spatially_shadow(viewport=_VP, rooms=rooms, ceiling_observations=obs)
    assert rep.vetoed_ambiguous_observation_ids == ("c_ambig",)
    assert rep.vetoed_legend_observation_ids == ("c_legend",)
    assert rep.vetoed_out_of_scope_observation_ids == ("c_bad_sha",)
    by_id = {a.room_id: a for a in rep.room_associations}
    assert by_id["r1"].status == "ABSTAINED"
    assert by_id["r2"].status == "ABSTAINED"
    assert by_id["r3"].status == "ABSTAINED"
    assert "conflicting_or_missing_ceiling_material_in_room" in by_id["r3"].reason_codes
    assert "conflicting_ceiling_height_in_room" in by_id["r3"].reason_codes


def test_zero_job_specific_shared_source_rules():
    path = Path(__file__).resolve().parents[1] / "pb_source_spatial_ceiling_label_association_shadow.py"
    assert audit_shared_source(path.read_text(encoding="utf-8"), filename=path.name) == ()
