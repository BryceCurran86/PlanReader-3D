"""Comprehensive regression and accuracy test suite for the PlanReader Surface Accuracy Lane.

Verifies the live production path:
SOURCE GEOMETRY -> ROOM FACE -> CANONICAL SPACE -> FLOOR / CEILING / FINISH SURFACE -> QUANTITY -> CUSTOMER OUTPUT

Invariants verified:
1. Unstroked CAD text wipeout masks are ignored and do not produce micro-rooms.
2. Stroked wall linework produces authoritative RoomFace objects.
3. CanonicalSpace and CanonicalCeiling are synthesized from room faces.
4. Primary floor finishes (FLOOR_TIMBER, FLOOR_CARPET, FLOOR_TILES, FLOOR_VINYL, FLOOR_EPOXY)
   receive row_role="floor_area" without double-counting secondary accessories (underlay, screed, waterproofing).
5. Ceilings (CEILING_PLASTERBOARD_LINING, CEILING_INSULATED_PANEL) receive row_role="ceiling_area".
6. Insulated panel finishes (IP / sandwich panel) correctly map to CEILING_INSULATED_PANEL.
7. Epoxy finishes (EPX / epoxy) correctly map to FLOOR_EPOXY.
8. Small wet areas (< 5 m²) are preserved and not dropped.
"""
from __future__ import annotations

import fitz
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pb_canonical_building import (
    CanonicalBuilding,
    CanonicalCeiling,
    CanonicalLevel,
    CanonicalProject,
    CanonicalSpace,
    Vector2D,
)
from pb_canonical_persistence import (
    canonicalize_evidence_snapshot,
    compute_workspace_source_fingerprint,
)
from pb_production_3d_adapter_legacy import (
    collect_workspace_3d_evidence,
    planreader_to_canonical_model,
)
from pb_room_face_takeoff import (
    extract_and_calibrate_rooms,
    extract_room_faces_from_page,
    page_scale_info,
)


class MockApp:
    def __init__(self, pdf_path: Path, pages: List[Dict[str, Any]], docs: List[Dict[str, Any]]):
        self.pdf_path = pdf_path
        self.pages = pages
        self.docs = docs
        self.fitz = fitz
        self._settings: Dict[str, Any] = {}

    def lquery(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        q = query.lower()
        if "from workspaces" in q:
            return [{"id": params[0], "job_no": "TEST-01", "job_name": "Test Job"}]
        if "from documents" in q:
            if "where id=?" in q:
                return [d for d in self.docs if d.get("id") == params[0]]
            return self.docs
        if "from pages" in q:
            return self.pages
        return []

    def workspace_setting(self, wid: int, key: str, default: Any = None) -> Any:
        return self._settings.get(f"{wid}:{key}", default)

    def set_workspace_setting(self, wid: int, key: str, val: Any) -> None:
        self._settings[f"{wid}:{key}"] = val


def _create_mock_pdf_with_wipeout(pdf_path: Path) -> Path:
    """Create a vector PDF with a real room and an unstroked text wipeout mask inside."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)

    # 1. Stroked room rectangle (4.0m x 3.0m at 1:100 scale: 113.39pt x 85.04pt)
    # Using 100, 100 to 250, 200 (150 pt x 100 pt)
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(100, 100, 250, 200))
    shape.finish(color=(0, 0, 0), width=1.0)
    shape.commit()

    # 2. Unstroked filled wipeout rectangle around text (e.g. 150, 140 to 200, 160)
    shape2 = page.new_shape()
    shape2.draw_rect(fitz.Rect(150, 140, 200, 160))
    shape2.finish(fill=(1, 1, 1), color=None)  # unstroked wipeout mask: color=None, width=None
    shape2.commit()

    # 3. Insert room label text
    page.insert_text((155, 155), "BED 2", fontsize=10, fontname="helv")

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_unstroked_wipeout_mask_is_skipped(tmp_path: Path):
    """Verify that unstroked CAD text wipeout masks do not generate line segments."""
    pdf_path = tmp_path / "wipeout_test.pdf"
    _create_mock_pdf_with_wipeout(pdf_path)

    page_dict = {
        "id": 1,
        "workspace_id": 100,
        "document_id": 1,
        "page_no": 1,
        "page_label": "Floor Plan",
        "page_type": "floor_plan",
        "px_per_m": 28.346,
        "render_zoom": 1.0,
        "scale_text": "1:100",
    }
    doc_dict = {"id": 1, "workspace_id": 100, "path": str(pdf_path)}
    app = MockApp(pdf_path, [page_dict], [doc_dict])

    rooms = extract_room_faces_from_page(app, page_dict)

    # Should detect exactly 1 room (BED), NOT the 0.14 m² wipeout box!
    assert len(rooms) == 1
    assert "BED" in rooms[0].label
    assert rooms[0].floor_area_m2 > 1.0


def test_primary_floor_finish_row_role_isolation():
    """Verify that only primary floor finishes receive row_role='floor_area'."""
    project = CanonicalProject(id="p1", name="Test Project")
    bld = CanonicalBuilding(id="b1", name="Building 1")
    lvl = CanonicalLevel(id="lvl_1", name="Ground", level_index=0)

    # Space 1: Timber floor
    s_timber = CanonicalSpace(
        id="sp_timber",
        name="Living Room",
        boundary_polygon=[Vector2D(0, 0), Vector2D(5, 0), Vector2D(5, 4), Vector2D(0, 4)],
        specified_floor_area_m2=20.0,
        finish_assignments={"floor": "timber"},
    )
    # Space 2: Carpet floor
    s_carpet = CanonicalSpace(
        id="sp_carpet",
        name="Bed 2",
        boundary_polygon=[Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 3), Vector2D(0, 3)],
        specified_floor_area_m2=12.0,
        finish_assignments={"floor": "carpet"},
    )
    # Space 3: Tiled wet area
    s_tiles = CanonicalSpace(
        id="sp_tiles",
        name="Ensuite",
        boundary_polygon=[Vector2D(0, 0), Vector2D(2, 0), Vector2D(2, 2.5), Vector2D(0, 2.5)],
        specified_floor_area_m2=5.0,
        finish_assignments={"floor": "tiles"},
    )
    # Space 4: Cold Room epoxy
    s_epoxy = CanonicalSpace(
        id="sp_epoxy",
        name="Cold Room",
        boundary_polygon=[Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 6), Vector2D(0, 6)],
        specified_floor_area_m2=24.0,
        finish_assignments={"floor": "epoxy"},
    )

    lvl.spaces = [s_timber, s_carpet, s_tiles, s_epoxy]
    bld.levels = [lvl]
    project.buildings = [bld]

    rows = project.generate_takeoff_rows(workspace_id=1)

    # Collect floor_area rows
    floor_area_rows = [r for r in rows if r.get("row_role") == "floor_area"]

    # Each of the 4 spaces should produce exactly ONE primary floor_area row:
    # 20.0 (timber), 12.0 (carpet), 5.0 (tiles), 24.0 (epoxy)
    assert len(floor_area_rows) == 4
    quantities = sorted(r["quantity"] for r in floor_area_rows)
    assert quantities == [5.0, 12.0, 20.0, 24.0]

    # Secondary rows (underlays, screed, waterproofing) must have row_role == ""
    underlay_rows = [r for r in rows if "UNDERLAY" in r.get("source_reference", "")]
    assert len(underlay_rows) >= 2
    for r in underlay_rows:
        assert r.get("row_role") == ""

    wp_rows = [r for r in rows if "WATERPROOFING" in r.get("source_reference", "")]
    assert len(wp_rows) == 1
    assert wp_rows[0].get("row_role") == ""


def test_insulated_panel_ceiling_derivation():
    """Verify Phase 2 finish authority:
    1. Bare IP without applicable legend must ABSTAIN.
    2. Conflicting IP definitions must CONFLICT.
    3. Authenticated IP via legend/schedule derives CEILING_INSULATED_PANEL.
    4. Semantic insulated panel derives CEILING_INSULATED_PANEL.
    5. Standard ceiling derives CEILING_PLASTERBOARD_LINING.
    """
    # 1. Bare IP without applicable legend -> ABSTAIN
    c_bare_ip = CanonicalCeiling(
        id="ceil_bare",
        name="Ceiling Room",
        polygon=[Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 6), Vector2D(0, 6)],
        specified_floor_area_m2=24.0,
        finish="ip",
        metadata={"ceiling_finish": "ip"},
    )
    assert c_bare_ip.derive_trade_quantities() == []

    # 2. Conflicting IP definitions -> CONFLICT (ABSTAIN / 0 quantity)
    c_conflict_ip = CanonicalCeiling(
        id="ceil_conflict",
        name="Ceiling Room",
        polygon=[Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 6), Vector2D(0, 6)],
        specified_floor_area_m2=24.0,
        finish="ip",
        metadata={"ceiling_finish": "ip", "legend_status": "Conflict"},
    )
    assert c_conflict_ip.derive_trade_quantities() == []

    # 3. Authenticated IP via legend -> PASS
    c_auth_ip = CanonicalCeiling(
        id="ceil_auth",
        name="Ceiling Cold Room",
        polygon=[Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 6), Vector2D(0, 6)],
        specified_floor_area_m2=24.0,
        finish="ip",
        metadata={
            "ceiling_finish": "ip",
            "legend_status": "Confirmed",
            "legend_definition": "Insulated Panel",
        },
    )
    bindings_auth = c_auth_ip.derive_trade_quantities()
    item_codes_auth = {b.item_code for b in bindings_auth}
    assert "CEILING_INSULATED_PANEL" in item_codes_auth
    assert "CEILING_INSULATED_PANEL_TRIM" in item_codes_auth
    assert "CEILING_PLASTERBOARD_LINING" not in item_codes_auth

    # 4. Semantic insulated panel -> PASS
    c_sem = CanonicalCeiling(
        id="ceil_sem",
        name="Ceiling Cold Room",
        polygon=[Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 6), Vector2D(0, 6)],
        specified_floor_area_m2=24.0,
        finish="insulated_panel",
    )
    bindings_sem = c_sem.derive_trade_quantities()
    item_codes_sem = {b.item_code for b in bindings_sem}
    assert "CEILING_INSULATED_PANEL" in item_codes_sem

    # 5. Plasterboard ceiling check
    c_pb = CanonicalCeiling(
        id="ceil_living",
        name="Ceiling Living",
        polygon=[Vector2D(0, 0), Vector2D(5, 0), Vector2D(5, 4), Vector2D(0, 4)],
        specified_floor_area_m2=20.0,
        finish="plasterboard",
    )
    bindings_pb = c_pb.derive_trade_quantities()
    item_codes_pb = {b.item_code for b in bindings_pb}
    assert "CEILING_PLASTERBOARD_LINING" in item_codes_pb
    assert "CEILING_INSULATED_PANEL" not in item_codes_pb


def test_flooring_raw_abbreviation_authority():
    """Verify Phase 2 flooring finish authority:
    1. Bare EPX without legend must ABSTAIN.
    2. Conflicting EPX must CONFLICT.
    3. Authenticated EPX derives FLOOR_EPOXY.
    4. Unannotated space does NOT guess from room name.
    """
    poly = [Vector2D(0, 0), Vector2D(4, 0), Vector2D(4, 6), Vector2D(0, 6)]

    # 1. Bare EPX -> ABSTAIN
    sp_bare = CanonicalSpace(
        id="sp_bare",
        name="Cold Room",
        boundary_polygon=poly,
        finish_assignments={"floor": "epx"},
    )
    assert sp_bare.derive_trade_quantities() == []

    # 2. Conflicting EPX -> CONFLICT
    sp_conflict = CanonicalSpace(
        id="sp_conflict",
        name="Cold Room",
        boundary_polygon=poly,
        finish_assignments={"floor": "epx"},
        metadata={"legend_status": "Conflict"},
    )
    assert sp_conflict.derive_trade_quantities() == []

    # 3. Authenticated EPX -> FLOOR_EPOXY
    sp_auth = CanonicalSpace(
        id="sp_auth",
        name="Cold Room",
        boundary_polygon=poly,
        finish_assignments={"floor": "epx"},
        metadata={"legend_status": "Confirmed", "legend_definition": "Epoxy floor finish"},
    )
    bindings = sp_auth.derive_trade_quantities()
    assert any(b.item_code == "FLOOR_EPOXY" for b in bindings)

    # 4. Unannotated space does not guess from room name
    sp_unannotated = CanonicalSpace(
        id="sp_unannotated",
        name="Cold Room",
        boundary_polygon=poly,
    )
    assert sp_unannotated.derive_trade_quantities() == []


def test_evidence_snapshot_canonicalization_with_spaces_and_ceilings():
    """Verify that spaces and ceilings are properly included in the evidence snapshot fingerprint."""
    snap1 = {
        "workspace_metadata": {"id": 1},
        "documents": [],
        "pages": [],
        "registered_walls": [],
        "mapper_shapes": [],
        "evidence_observations": [],
        "roof_data": None,
        "takeoff_rows": [],
        "spaces": [{"id": "space_1", "name": "Room A", "boundary_polygon": [{"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 3, "y": 3}]}],
        "ceilings": [{"id": "ceil_1", "name": "Ceiling A", "polygon": [{"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 3, "y": 3}]}],
    }
    fp1 = compute_workspace_source_fingerprint(snap1)

    # Different polygon vertices should alter fingerprint
    snap2 = {
        **snap1,
        "spaces": [{"id": "space_1", "name": "Room A", "boundary_polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}]}],
    }
    fp2 = compute_workspace_source_fingerprint(snap2)

    assert fp1 != fp2


def test_cold_room_and_freezer_surface_accuracy():
    """Verify Cold Room and Freezer derive epoxy floor and insulated panel ceiling."""
    payload = {
        "workspace_id": 999,
        "spaces": [
            {
                "id": "space_cold_room",
                "name": "Cold Room",
                "boundary_polygon": [{"x": 0, "y": 0}, {"x": 3.95, "y": 0}, {"x": 3.95, "y": 6.425}, {"x": 0, "y": 6.425}],
                "specified_floor_area_m2": 25.38,
                "finish_assignments": {"floor": "epoxy", "ceiling": "ip"},
                "takeoff_eligible": True,
            },
            {
                "id": "space_freezer",
                "name": "Freezer",
                "boundary_polygon": [{"x": 0, "y": 0}, {"x": 1.70, "y": 0}, {"x": 1.70, "y": 3.876}, {"x": 0, "y": 3.876}],
                "specified_floor_area_m2": 6.59,
                "finish_assignments": {"floor": "epoxy", "ceiling": "ip"},
                "takeoff_eligible": True,
            },
        ],
        "ceilings": [
            {
                "id": "ceiling_cold_room",
                "name": "Ceiling Cold Room",
                "polygon": [{"x": 0, "y": 0}, {"x": 3.95, "y": 0}, {"x": 3.95, "y": 6.425}, {"x": 0, "y": 6.425}],
                "specified_floor_area_m2": 25.38,
                "finish": "ip",
                "metadata": {"ceiling_finish": "ip", "legend_status": "Confirmed", "legend_definition": "Insulated Panel"},
                "takeoff_eligible": True,
            },
            {
                "id": "ceiling_freezer",
                "name": "Ceiling Freezer",
                "polygon": [{"x": 0, "y": 0}, {"x": 1.70, "y": 0}, {"x": 1.70, "y": 3.876}, {"x": 0, "y": 3.876}],
                "specified_floor_area_m2": 6.59,
                "finish": "ip",
                "metadata": {"ceiling_finish": "ip", "legend_status": "Confirmed", "legend_definition": "Insulated Panel"},
                "takeoff_eligible": True,
            },
        ],
    }

    project, skipped = planreader_to_canonical_model(payload, is_validated_internal_workspace=True)
    assert not skipped

    rows = project.generate_takeoff_rows(workspace_id=999)

    floor_rows = [r for r in rows if r.get("row_role") == "floor_area"]
    ceiling_rows = [r for r in rows if r.get("row_role") == "ceiling_area"]

    assert len(floor_rows) == 2
    assert len(ceiling_rows) == 2

    # Check floor epoxy rows
    cold_fl = next(r for r in floor_rows if "Cold Room" in r["location"])
    assert cold_fl["quantity"] == 25.38
    assert "Flooring" in cold_fl["element"] or "Floor Epoxy" in cold_fl["element"]

    frz_fl = next(r for r in floor_rows if "Freezer" in r["location"])
    assert frz_fl["quantity"] == 6.59

    # Check insulated panel ceiling rows
    cold_cl = next(r for r in ceiling_rows if "ceiling_cold_room" in r["location"])
    assert cold_cl["quantity"] == 25.38
    assert "insulated sandwich panel" in cold_cl["element"].lower()

    frz_cl = next(r for r in ceiling_rows if "ceiling_freezer" in r["location"])
    assert frz_cl["quantity"] == 6.59
    assert "insulated sandwich panel" in frz_cl["element"].lower()


def test_wipeout_mask_negative_regressions():
    """Verify Phase 3 multi-factor authority:
    1. Legitimate filled structural plinth survives (no text overlap).
    2. Stroked physical rectangle survives.
    3. Real short wall survives.
    4. Dark/colored fill survives.
    5. Unstroked white text wipeout mask is skipped.
    """
    from pb_room_face_takeoff import _is_cad_text_wipeout_mask

    words = [{"text": "BED 1", "bbox": [100.0, 100.0, 140.0, 120.0]}]

    # 1. Structural plinth: unstroked white fill, but NO text overlap -> SURVIVES (False)
    plinth_drawing = {"fill": (1.0, 1.0, 1.0), "color": None, "width": 0.0}
    plinth_rect = fitz.Rect(500.0, 500.0, 700.0, 700.0)
    assert _is_cad_text_wipeout_mask(plinth_drawing, plinth_rect, words) is False

    # 2. Stroked physical rectangle (column/pier): has stroke authority -> SURVIVES (False)
    stroked_drawing = {"fill": (1.0, 1.0, 1.0), "color": (0.0, 0.0, 0.0), "width": 1.0}
    stroked_rect = fitz.Rect(95.0, 95.0, 145.0, 125.0)
    assert _is_cad_text_wipeout_mask(stroked_drawing, stroked_rect, words) is False

    # 3. Real short wall: stroked line/box -> SURVIVES (False)
    wall_drawing = {"fill": None, "color": (0.0, 0.0, 0.0), "width": 1.5}
    wall_rect = fitz.Rect(100.0, 100.0, 150.0, 110.0)
    assert _is_cad_text_wipeout_mask(wall_drawing, wall_rect, words) is False

    # 4. Colored/dark fill (e.g. hatched/shaded region) -> SURVIVES (False)
    shaded_drawing = {"fill": (0.7, 0.7, 0.7), "color": None, "width": 0.0}
    shaded_rect = fitz.Rect(95.0, 95.0, 145.0, 125.0)
    assert _is_cad_text_wipeout_mask(shaded_drawing, shaded_rect, words) is False

    # 5. True CAD wipeout mask: unstroked, white fill, text-sized, OVERLAPS text -> SKIPPED (True)
    wipeout_drawing = {"fill": (1.0, 1.0, 1.0), "color": None, "width": 0.0}
    wipeout_rect = fitz.Rect(95.0, 95.0, 145.0, 125.0)  # tightly wraps BED 1
    assert _is_cad_text_wipeout_mask(wipeout_drawing, wipeout_rect, words) is True


def test_small_wet_area_preservation():
    """Verify that small wet areas (< 5 m²) are not dropped by room filtering."""
    from pb_room_face_takeoff import filter_face

    # 1.3m x 1.33m WC = 1.73 m²
    # At 1:100 scale: 1.3 / 0.03528 = 36.85 pt, 1.33 / 0.03528 = 37.70 pt
    scale_info = {"real_metres_per_page_mm": 0.1, "scale_text": "1:100"}
    wc_poly = [(100.0, 100.0), (136.85, 100.0), (136.85, 137.70), (100.0, 137.70)]

    res = filter_face(
        polygon_pdf_pts=wc_poly,
        scale_info=scale_info,
        page_width_pt=842.0,
        page_height_pt=595.0,
        label="WC",
    )

    assert res.is_room is True
    assert 1.6 < res.area_m2 < 1.9


def test_q5446_aggregate_controls_remain_fail_closed():
    """Verify that unresolved aggregate controls remain UNRESOLVED in Q5446."""
    import json
    report_path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "frozen_holdout"
        / "full_plan_v2"
        / "projects"
        / "au_qld_q5446_armstrong32_harlequin"
        / "verification_report.json"
    )
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        checks = {row["object_ref"]: row for row in report.get("measurement_closure_checks", [])}
        assert checks["q5446:candidate:garage"]["status"] == "UNRESOLVED"
        assert checks["q5446:candidate:porch"]["status"] == "UNRESOLVED"
        assert checks["q5446:candidate:ground_floor"]["status"] == "UNRESOLVED"
        assert checks["q5446:candidate:first_floor"]["status"] == "UNRESOLVED"


def test_internal_elevation_wall_tile_cluster_generic_fixture(tmp_path: Path):
    """Generic regression fixture verifying the 8-case internal elevation chain:
    internal elevation viewport -> wall-face identity -> room/wall binding
    -> tile finish extent -> physical dimensions -> wall tile quantity -> customer output.
    """
    from pb_internal_elevation_tile_authority import (
        discover_internal_elevation_viewports,
        extract_internal_elevation_tile_faces,
        extract_internal_elevation_tile_items,
    )

    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)

    # 1. Bathroom C: 900 SHW x 2100 TILES shower net
    page.insert_text((900, 360), "Bathroom C", fontsize=12)
    page.insert_text((900, 250), "900 SHW", fontsize=10)
    page.insert_text((900, 200), "2,100 TILES", fontsize=10)

    # 2. Ensuite A: 1680 wide x 2700 ceiling less 400x600 niche
    page.insert_text((430, 360), "Ensuite A", fontsize=12)
    page.insert_text((430, 250), "1,680", fontsize=10)
    page.insert_text((430, 200), "NICHE 400 x 600", fontsize=10)
    page.insert_text((430, 150), "SHOWER TILES TO RUN UP TO CEILING", fontsize=10)

    # 3. Ensuite B: 900 SHW x 2700 shower return
    page.insert_text((650, 360), "Ensuite B", fontsize=12)
    page.insert_text((650, 250), "900 SHW", fontsize=10)
    page.insert_text((650, 150), "SHOWER TILES TO RUN UP TO CEILING", fontsize=10)

    # 4. Laundry D: 3080 wide x 190 TILE SKIRTING
    page.insert_text((800, 700), "Laundry D", fontsize=12)
    page.insert_text((800, 600), "3,080", fontsize=10)
    page.insert_text((800, 550), "190 TILES TILE SKIRTING", fontsize=10)

    # 5. Unannotated view (negative regression): must ABSTAIN (0 wall tile derived)
    page.insert_text((430, 700), "Laundry C", fontsize=12)
    page.insert_text((430, 600), "1,680", fontsize=10)

    pdf_file = tmp_path / "internal_elev_test.pdf"
    doc.save(str(pdf_file))
    doc.close()

    doc_test = fitz.open(str(pdf_file))
    items = extract_internal_elevation_tile_items(doc_test, project_id="test_proj", default_ceiling_height_m=2.70)
    doc_test.close()

    assert len(items) == 4
    by_ref = {it.object_refs[0]: it for it in items}

    # 1. Bathroom C shower net: 0.9 x 2.1 = 1.89 m²
    assert "test_proj:surface:wall_tile:bathroom_C_shower_net" in by_ref
    assert by_ref["test_proj:surface:wall_tile:bathroom_C_shower_net"].value == 1.89

    # 2. Ensuite rear flat after niche: (1.68 * 2.7) - 0.24 = 4.296 m²
    assert "test_proj:surface:wall_tile:ensuite_rear_flat_after_niche" in by_ref
    assert by_ref["test_proj:surface:wall_tile:ensuite_rear_flat_after_niche"].value == 4.296

    # 3. Ensuite B shower return: 0.9 x 2.7 = 2.43 m²
    assert "test_proj:surface:wall_tile:ensuite_B_shower_return_net" in by_ref
    assert by_ref["test_proj:surface:wall_tile:ensuite_B_shower_return_net"].value == 2.43

    # 4. Laundry D skirting: 3.08 x 0.19 = 0.5852 m²
    assert "test_proj:surface:wall_tile:laundry_D_skirting" in by_ref
    assert by_ref["test_proj:surface:wall_tile:laundry_D_skirting"].value == 0.5852

    # Unannotated Laundry C produced NO spurious tiles
    assert not any("laundry_C" in it.object_refs[0] for it in items)


def test_page_scale_info_authority():
    """Verify scale authority hardening:
    1. Conflicting ratios without viewport isolation -> CONFLICT / ABSTAIN.
    2. Viewport-isolated scale overrides sheet conflict.
    3. Exactly one scale candidate -> calibrated.
    """
    from pb_room_face_takeoff import page_scale_info

    # 1. Conflicting ratios on sheet -> conflict
    page_conflict = {
        "px_per_m": 0.0,
        "scale_text": "Scale 1:100 & 1:50",
    }
    info1 = page_scale_info(page_conflict)
    assert info1["status"] == "conflict"
    assert info1["real_metres_per_page_mm"] is None

    # 2. Viewport-authenticated scale isolates the ratio
    vp_auth = {"scale_text": "1:50", "ratio": 50.0}
    info2 = page_scale_info(page_conflict, viewport=vp_auth)
    assert info2["status"] == "calibrated"
    assert info2["real_metres_per_page_mm"] == 0.05
    assert info2["source"] == "viewport.ratio"

    # 3. Single candidate scale -> calibrated
    page_single = {
        "px_per_m": 0.0,
        "scale_text": "Floor Plan 1:100",
    }
    info3 = page_scale_info(page_single)
    assert info3["status"] == "calibrated"
    assert info3["real_metres_per_page_mm"] == 0.10


def test_cad_vector_text_takeoff_authority_generic_fixture(tmp_path: Path):
    """Verify generic CAD vector-outline text floor surface takeoff authority:
    1. Extracts areas table entry (Alfresco 12.00 m²).
    2. Associates figured dimensions to wet-area rooms (Ensuite, Bath, Laundry).
    3. Associates figured dimensions to living room (porcelain tile).
    4. Binds trade categories: outdoor -> flooring, wet area/living -> tiling.
    5. Fully deterministic IDs and lineage.
    """
    from pb_cad_vector_text_takeoff_authority import (
        extract_cad_vector_text_floor_items,
        _find_areas_table_entry,
        _find_room_dimensions,
        ProducedTakeoffItemV2,
    )
    from pb_portable_raster_ocr_authority import OCRLine

    # 1. Test areas table helper directly
    mock_lines = (
        OCRLine(text="AREAS.", confidence=0.99, bbox_px=(0, 0, 10, 10), bbox_pt=(959.0, 691.0, 990.0, 700.0)),
        OCRLine(text="Alfresco:", confidence=1.0, bbox_px=(0, 0, 10, 10), bbox_pt=(978.4, 697.8, 1014.4, 709.8)),
        OCRLine(text="12.00", confidence=1.0, bbox_px=(0, 0, 10, 10), bbox_pt=(1048.6, 696.6, 1074.4, 709.2)),
        OCRLine(text="sq.m", confidence=1.0, bbox_px=(0, 0, 10, 10), bbox_pt=(1074.4, 698.4, 1090.0, 709.8)),
    )
    alf_area = _find_areas_table_entry(mock_lines, "Alfresco")
    assert alf_area == 12.0

    # 2. Test figured dimensions association
    room_ens = [OCRLine(text="ENS'", confidence=1.0, bbox_px=(0, 0, 10, 10), bbox_pt=(476.0, 498.0, 507.0, 515.0))]
    all_dims = (
        room_ens[0],
        OCRLine(text="2320", confidence=1.0, bbox_px=(0, 0, 10, 10), bbox_pt=(472.0, 535.0, 495.0, 545.0)),
        OCRLine(text="1820", confidence=1.0, bbox_px=(0, 0, 10, 10), bbox_pt=(479.0, 517.0, 502.0, 528.0)),
    )
    dims = _find_room_dimensions(room_ens, all_dims)
    assert dims is not None
    assert round(dims[0] * dims[1], 4) == 4.2224


