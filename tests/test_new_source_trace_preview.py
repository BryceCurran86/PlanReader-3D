"""The original app only consumes source-native new tracing for automatic preview."""
from __future__ import annotations

import ast
from pathlib import Path

import fitz
import pytest

from pb_new_source_trace_preview import source_native_trace_preview, _full_page_source_tiles


def _floor_plan(tmp_path: Path) -> Path:
    pdf = tmp_path / "drawing.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=790, height=590)
        for rect in (
            fitz.Rect(160, 120, 165, 420),
            fitz.Rect(530, 120, 535, 420),
            fitz.Rect(165, 120, 530, 125),
            fitz.Rect(165, 415, 530, 420),
        ):
            page.draw_rect(rect, color=None, fill=(0, 0, 0))
        doc.save(pdf)
    return pdf


def test_new_source_preview_on_original_pdf_does_not_issue_quantities(tmp_path):
    pdf = _floor_plan(tmp_path)
    result, png = source_native_trace_preview(pdf, 0)
    assert len(png) > 1000 and png[:8] == b"\x89PNG\r\n\x1a\n"
    assert result["page_index"] == 0
    assert len(result["source_sha256"]) == 64
    assert result["producer"].endswith("build_layered_wall_doorway_room_rings")
    assert result["legacy_envelope_used"] is False
    assert result["legacy_fallback_allowed"] is False
    assert result["quantity_authorized"] is False
    assert result["commercial_publishable"] is False
    assert result["primitive_cap_per_tile"] == 20000
    assert result["source_tile_count"] > 0


def test_new_preview_rejects_non_original_pdf_without_legacy_fallback(tmp_path):
    with pytest.raises(ValueError, match="original_pdf_required_no_legacy_fallback"):
        source_native_trace_preview(tmp_path / "floorplan.png", 0)


def test_new_preview_rejects_wrong_page_without_fallback(tmp_path):
    pdf = _floor_plan(tmp_path)
    with pytest.raises(ValueError, match="original_page_index_invalid"):
        source_native_trace_preview(pdf, 10)


def test_source_tiles_are_generic_whole_sheet_and_bounded():
    tiles = _full_page_source_tiles(1200.0, 800.0, 7000)
    assert len(tiles) == 9
    assert min(t[0] for t in tiles) == 0.0
    assert min(t[1] for t in tiles) == 0.0
    assert max(t[2] for t in tiles) == 1200.0
    assert max(t[3] for t in tiles) == 800.0


def test_actual_original_app_drawing_page_has_no_old_auto_envelope_button():
    source = (Path(__file__).resolve().parents[1] / "pb_planreader_3d_app.py").read_text(encoding="utf8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "plan_mapper_page")
    text = ast.get_source_segment(source, fn)
    assert text is not None
    assert "Auto-detect building envelope" not in text
    assert "auto_detect_envelope_shapes(" not in text
    assert "source_native_trace_preview(" in text
    assert "Re-run new native wall trace" in text
    assert "No building envelope could be detected" not in text


def test_app_legacy_shape_generator_is_not_a_required_preview_dependency():
    src = (Path(__file__).resolve().parents[1] / "pb_new_source_trace_preview.py").read_text(encoding="utf-8-sig")
    call_names = {
        n.func.id
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "auto_detect_building_envelope" not in call_names
    assert "auto_detect_envelope_shapes" not in call_names


def test_existing_black_source_wall_pr_is_in_new_trace_producer():
    from pb_next_wall_ring_preview import build_layered_wall_doorway_room_rings
    from tests.test_original_anonymous_wall_door_source_20261112 import (
        door_room,
    )
    from tests.test_original_live_dark_filled_wall_rooms_20261112 import (
        _dark_rect_room,
    )
    from tests.test_layered_wall_doorway_room_ring_shadow_v1 import SHA

    black = [dict(row, fill=(0., 0., 0.)) for row in _dark_rect_room()]
    traced = build_layered_wall_doorway_room_rings(
        black, source_sha256=SHA, page_index=0, stroke_pair_wall_faces=True,
    )
    assert traced.wall_strip_count == 4
    assert len(traced.rings) == 1
    assert all(not room.metric_area_issued for room in traced.rings)

    swing = build_layered_wall_doorway_room_rings(
        door_room(), source_sha256=SHA, page_index=0,
        stroke_pair_wall_faces=True,
    )
    assert swing.wall_strip_count == 5
    assert len(swing.closures) == 1
    assert len(swing.rings) == 1
    assert all(not ring.commercial_projection_allowed for ring in swing.rings)


def test_outlined_vector_filter_keeps_original_path_ids_and_curves(monkeypatch):
    from pb_new_typed_vector_ink_scope import scope_outlined_vector_lettering
    import pb_new_typed_vector_ink_scope as scope

    class Sheet:
        class Rect:
            width = 1100
            height = 800
        rect = Rect()
        def get_text(self, variant):
            assert variant == "words"
            return []

    line = {"type": "s", "color": (0, 0, 0), "fill": None,
            "items": (("l", (0, 0), (5, 5)),)}
    curved = {"type": "s", "color": (0, 0, 0), "fill": None,
              "items": (("c", (1, 1), (3, 2), (4, 1)),)}
    filled = {"type": "f", "color": None, "fill": (0, 0, 0),
              "items": (("re", (0, 0, 1, 1), 1),)}
    drawings = [line, line, filled, curved] + [
        {"type": "s", "color": None, "fill": None, "items": ()}
        for _ in range(5000)
    ]
    native = [{"path_index": 0, "item_index": 0}] * 9999
    native.extend([{"path_index": 1, "item_index": 0}])
    monkeypatch.setattr(scope, "extract_native_page",
                        lambda page: {"segments": native})
    monkeypatch.setattr(
        scope, "_filter_repeated_non_physical_drafting_primitives",
        lambda segments, **opts: [segments[-1]],
    )
    result = scope_outlined_vector_lettering(Sheet(), drawings)
    assert result.applied is True
    assert result.discarded_simple_stroke_paths == 1
    assert len(result.drawings) == len(drawings)
    assert result.drawings[0].get("items") == ()
    assert result.drawings[1] is line
    assert result.drawings[2] is filled
    assert result.drawings[3] is curved


def test_no_vector_prefilter_on_normal_pdf_text(monkeypatch):
    from pb_new_typed_vector_ink_scope import scope_outlined_vector_lettering
    import pb_new_typed_vector_ink_scope as scope

    class Sheet:
        def get_text(self, variant):
            return [("word",)] * 21

    monkeypatch.setattr(scope, "extract_native_page",
                        lambda page: (_ for _ in ()).throw(AssertionError()))
    rows = [{"type": "s", "items": ()}] * 5000
    result = scope_outlined_vector_lettering(Sheet(), rows)
    assert result.applied is False
    assert len(result.drawings) == 5000


def test_source_hygiene_then_outer_walls_before_inner_room_trace(tmp_path, monkeypatch):
    import pb_new_source_trace_preview as preview
    order = []
    outer = preview.attempt_source_native_outer_wall_first
    vector = preview.scope_outlined_vector_lettering
    inner = preview.build_layered_wall_doorway_room_rings

    def outer_first(drawings):
        order.append("outer")
        return outer(drawings)

    def source_hygiene(page, drawings):
        order.append("source_hygiene")
        return vector(page, drawings)

    def inner_last(*args, **kwargs):
        order.append("internal")
        return inner(*args, **kwargs)

    monkeypatch.setattr(preview, "attempt_source_native_outer_wall_first", outer_first)
    monkeypatch.setattr(preview, "scope_outlined_vector_lettering", source_hygiene)
    monkeypatch.setattr(preview, "build_layered_wall_doorway_room_rings", inner_last)
    source_native_trace_preview(_floor_plan(tmp_path), 0)
    assert order == ["source_hygiene", "outer", "internal"]


def _unfilled_double_wall_drawings(*, open_right=False, extra_box=False):
    import fitz
    lines = []
    def line(ax, ay, bx, by):
        lines.append({
            "type": "s", "color": (0., 0., 0.),
            "fill": None, "width": 0.7, "stroke_opacity": 1.,
            "layer": "",
            "rect": fitz.Rect(min(ax,bx),min(ay,by),max(ax,bx),max(ay,by)),
            "items": (("l",fitz.Point(ax,ay),fitz.Point(bx,by)),),
        })
    def box_lines(x0,y0,x1,y1):
        for y in (y0,y0+3,y1-3,y1):
            line(x0,y,x1,y)
        for x in (x0,x0+3,x1-3,x1):
            if open_right and x==x1:
                continue
            line(x,y0,x,y1)
    box_lines(100,100,400,350)
    if extra_box:
        box_lines(500,100,650,280)
    return lines


def test_external_wall_first_traces_source_native_double_stroke_not_ink_hull():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    result = attempt_source_native_outer_wall_first(
        _unfilled_double_wall_drawings()
    )
    assert result.source_stroke_pair_band_count >= 4
    assert result.source_wall_band_count >= 4
    assert result.source_wall_path_count >= 4
    assert result.measurement_authorized is False
    assert result.internal_wall_filter_authorized is False
    assert result.physical_wall_authenticated is False
    assert result.status in ("CANDIDATE","ABSTAINED")
    # Never construct the sheet bbox or a non-source enclosing rectangle.
    if result.polygon_pdf_pts:
        assert 95 <= min(p[0] for p in result.polygon_pdf_pts) <= 105
        assert 345 <= max(p[1] for p in result.polygon_pdf_pts) <= 355


def test_external_wall_first_never_bridges_open_wall_or_rival_building():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    open_wall = attempt_source_native_outer_wall_first(
        _unfilled_double_wall_drawings(open_right=True)
    )
    rival = attempt_source_native_outer_wall_first(
        _unfilled_double_wall_drawings(extra_box=True)
    )
    assert open_wall.status == "ABSTAINED"
    assert rival.status == "ABSTAINED"
    assert not open_wall.polygon_pdf_pts and not rival.polygon_pdf_pts
    assert not open_wall.measurement_authorized
    assert not rival.internal_wall_filter_authorized

def test_viewport_inert_rows_do_not_crash_sliding_frame_detector():
    from pb_next_wall_ring_preview import (
        _clip_drawings,
        build_layered_wall_doorway_room_rings,
    )
    from tests.test_original_anonymous_wall_door_source_20261112 import (
        door_room,
    )
    from tests.test_layered_wall_doorway_room_ring_shadow_v1 import SHA

    source = door_room()
    # The original geometry is inside the requested viewport. An unrelated
    # drawing row outside that viewport used to become None and crash inside
    # _sliding_leaf_evidence even with the engine's source cap respected.
    unrelated = dict(source[0])
    unrelated["rect"] = fitz.Rect(500, 500, 700, 700)
    source.append(unrelated)
    selected = _clip_drawings(
        source, viewport=(0., 0., 125., 125.),
    )
    assert len(selected) == len(source)
    assert selected[-1].get("items") == ()
    assert all(x is not None for x in selected)
    result = build_layered_wall_doorway_room_rings(
        source, source_sha256=SHA, page_index=0,
        stroke_pair_wall_faces=True,
        sliding_leaf_frame_closure=True,
        viewport_pdf_pts=(0., 0., 125., 125.),
    )
    assert result is not None
    assert result.wall_strip_count >= 1
    assert not any(r.commercial_projection_allowed for r in result.rings)

def test_item_viewport_clip_returns_inert_source_rows_not_none():
    from pb_next_wall_ring_preview import _clip_drawing_items

    outside = {
        "type": "s", "color": (0., 0., 0.), "fill": None,
        "items": (("l", fitz.Point(500, 500), fitz.Point(650, 650)),),
        "rect": fitz.Rect(500, 500, 650, 650),
    }
    inside = {
        "type": "s", "color": (0., 0., 0.), "fill": None,
        "items": (("l", fitz.Point(20, 20), fitz.Point(70, 20)),),
        "rect": fitz.Rect(20, 20, 70, 20),
    }
    result = _clip_drawing_items(
        (outside,inside), (0., 0., 100., 100.),
    )
    assert len(result) == 2
    assert all(row is not None for row in result)
    assert result[0]["items"] == ()
    assert len(result[1]["items"]) == 1
    assert outside["items"] and inside["items"]


def test_original_exterior_wall_graph_reports_actual_free_source_endpoints():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    partial = attempt_source_native_outer_wall_first(
        _unfilled_double_wall_drawings(open_right=True)
    )
    graph = partial.graph
    assert partial.status == "ABSTAINED"
    assert graph.component_count >= 1
    assert graph.largest_component_band_count >= 2
    assert graph.largest_component_open_endpoints_pdf_pts
    assert graph.measurement_authorized is False
    assert graph.outside_ink_filter_authorized is False
    assert all(
        99 <= pt[0] <= 401 and 99 <= pt[1] <= 351
        for pt in graph.largest_component_open_endpoints_pdf_pts
    )


def test_exterior_graph_does_not_call_bbox_a_traced_building():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    rival = attempt_source_native_outer_wall_first(
        _unfilled_double_wall_drawings(extra_box=True)
    )
    assert rival.status == "ABSTAINED"
    assert rival.graph.component_count >= 2
    assert not rival.polygon_pdf_pts
    assert not rival.graph.outside_ink_filter_authorized


def test_wall_graph_inert_path_preserves_false_authentication():
    from pb_new_wall_graph_diagnostic import inspect_native_wall_graph
    assert inspect_native_wall_graph(()).component_count == 0
    assert inspect_native_wall_graph(()).measurement_authorized is False


def test_numbered_source_key_generic_pairing_indoor_outdoor_unissued():
    from pb_new_numbered_space_key import parse_numbered_key
    from pb_portable_raster_ocr_authority import OCRLine

    def line(t, x, y, w=12., h=8.):
        return OCRLine(text=t, confidence=.99, bbox_px=(x,y,x+w,y+h),
                       bbox_pt=(x,y,x+w,y+h))
    # Local crop is anchored by a real source KEY; source page coords
    # have a nonzero offset and must not be reinterpreted as page origin.
    crop = [
        line("1",3,10,5), line("LIVING",20,10,36),
        line("2",3,22,5), line("COURTYARD",20,22,52),
        line("3",3,34,5), line("BEDROOM",20,34,44),
    ]
    full = [
        line("1",300,150,5), line("2",450,275,5),
        line("3",570,320,5),
    ]
    got = parse_numbered_key(
        crop,full,anchor_bbox_pdf_pts=(40.,45.,65.,52.),
        crop_origin_pdf_pts=(40.,48.),
        source_sha256="a"*64,page_index=5,
    )
    assert got.status=="CANDIDATE"
    assert [(e.number,e.name) for e in got.entries]==[
        (1,"LIVING"),(2,"COURTYARD"),(3,"BEDROOM"),
    ]
    assert got.matched_number_count==3
    assert got.entries[1].semantic_role=="outdoor_or_nonroom_candidate"
    assert all(not e.physical_room_authenticated and not e.area_authorized for e in got.entries)
    assert not got.commercial_publishable
    assert got.entries[0].key_label_bbox_pdf_pts[0]==60.


def test_numbered_key_conflicting_name_and_skipped_number_vetoes():
    from pb_new_numbered_space_key import parse_numbered_key
    from pb_portable_raster_ocr_authority import OCRLine

    def line(t,x,y):
        return OCRLine(t,.99,(x,y,x+6,y+6),(x,y,x+6,y+6))
    shared=dict(anchor_bbox_pdf_pts=(0.,0.,20.,8.),
                crop_origin_pdf_pts=(0.,0.),
                source_sha256="b"*64,page_index=0)
    conflicting=[
        line("1",5,18),line("LOUNGE",30,18),line("1",5,28),
        line("GARAGE",30,28),line("2",5,38),line("BATHROOM",30,38),
        line("3",5,48),line("BEDROOM",30,48),
    ]
    assert "conflict" in parse_numbered_key(conflicting,(),**shared).reason
    nonconsecutive=[
        line("1",5,18),line("LOUNGE",30,18),line("5",5,28),
        line("GARAGE",30,28),line("9",5,38),line("BATHROOM",30,38),
    ]
    assert "sequence" in parse_numbered_key(nonconsecutive,(),**shared).reason


def test_sparse_original_plan_does_not_start_ocr(tmp_path,monkeypatch):
    from pb_new_numbered_space_key import detect_numbered_space_key
    import pb_portable_raster_ocr_authority as ocr
    monkeypatch.setattr(ocr,"RapidOCRBackend",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected OCR")))
    with fitz.open(_floor_plan(tmp_path)) as source:
        got = detect_numbered_space_key(
            source[0],page_index=0,source_sha256="c"*64)
    assert got.status=="ABSTAINED"
    assert got.reason=="numbered_key_no_source_printed_glyph_evidence"


def test_tracing_attempts_exterior_before_numbered_key_and_room(tmp_path,monkeypatch):
    import pb_new_source_trace_preview as preview
    from pb_new_numbered_space_key import NumberedSpaceKeyResult
    order=[]
    outer=preview.attempt_source_native_outer_wall_first
    inner=preview.build_layered_wall_doorway_room_rings
    def first(drawings):
        order.append("exterior")
        return outer(drawings)
    def second(page,*,page_index,source_sha256):
        order.append("key")
        return NumberedSpaceKeyResult(
            "ABSTAINED","mock_no_source_key",page_index,source_sha256)
    def third(*args,**kwargs):
        order.append("rooms")
        return inner(*args,**kwargs)
    monkeypatch.setattr(preview,"attempt_source_native_outer_wall_first",first)
    monkeypatch.setattr(preview,"detect_numbered_space_key",second)
    monkeypatch.setattr(preview,"build_layered_wall_doorway_room_rings",third)
    summary,png=preview.source_native_trace_preview(_floor_plan(tmp_path),0)
    assert order == ["exterior","key","rooms"]
    assert summary["numbered_space_key"]["reason"]=="mock_no_source_key"
    assert summary["quantity_authorized"] is False and png[:8]==b"\x89PNG\r\n\x1a\n"


def test_source_heavy_black_strokes_are_wall_bands_not_double_line_dependent():
    from pb_next_wall_ring_preview import (
        _collect_source_heavy_stroke_strips,
        build_layered_wall_doorway_room_rings,
    )
    from tests.test_layered_wall_doorway_room_ring_shadow_v1 import SHA

    def row(x0,y0,x1,y1, *, width=1.92, color=(0.,0.,0.), opacity=1.):
        return {
            "type":"s","layer":"","fill":None,"color":color,
            "width":width,"stroke_opacity":opacity,
            "rect":fitz.Rect(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1)),
            "items":(("l",fitz.Point(x0,y0),fitz.Point(x1,y1)),),
        }
    walls=[
        row(100,100,400,100),row(400,100,400,350),
        row(400,350,100,350),row(100,350,100,100),
    ]
    assert len(_collect_source_heavy_stroke_strips(walls))==4
    result=build_layered_wall_doorway_room_rings(
        walls,source_sha256=SHA,page_index=0,stroke_pair_wall_faces=True,
    )
    assert result.wall_strip_count>=4
    assert len(result.rings)>=1
    assert all(not x.commercial_projection_allowed for x in result.rings)
    negatives=[
        row(0,0,50,0,width=.48),
        row(0,10,60,10,color=(.1,.9,.1)),
        row(0,20,60,20,opacity=.5),
        row(0,30,60,30,width=1.92,color=(.8,.1,0)),
        row(0,40,10,40,width=1.92),
    ]
    assert _collect_source_heavy_stroke_strips(negatives)==[]


def test_outer_first_includes_source_heavy_black_stroke_ring_without_hull():
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
    walls=[]
    for x0,y0,x1,y1 in (
        (100,100,400,100),(400,100,400,350),
        (400,350,100,350),(100,350,100,100),
    ):
        walls.append({
            "type":"s","layer":"","fill":None,"color":(0.,0.,0.),
            "width":1.92,"stroke_opacity":1.,
            "rect":fitz.Rect(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1)),
            "items":(("l",fitz.Point(x0,y0),fitz.Point(x1,y1)),),
        })
    got=attempt_source_native_outer_wall_first(walls)
    assert got.source_heavy_stroke_band_count>=4
    assert got.graph.component_count>=1
    assert got.physical_wall_authenticated is False
    assert got.measurement_authorized is False


def test_source_wall_near_miss_reports_original_paths_without_minting_join():
    """A 1pt gap is a witnessed candidate, never a new physical segment."""
    from types import SimpleNamespace
    from shapely.geometry import box
    from pb_new_wall_graph_diagnostic import inspect_native_wall_graph

    def strip(source_id, bounds):
        return SimpleNamespace(
            polygon=box(*bounds),
            native_path_indices=lambda: (source_id,),
        )

    separated = inspect_native_wall_graph((
        strip(101, (0, 0, 10, 1)),
        strip(102, (11, 0, 21, 1)),
    ))
    assert separated.component_count == 2
    assert separated.endpoint_near_miss_total >= 1
    candidate = next(hit for hit in separated.endpoint_near_misses
                     if hit.native_path_ids == (101,))
    assert candidate.nearby_native_path_ids == (102,)
    assert candidate.tip_pdf_pts == (10.0, 0.5)
    assert candidate.separation_pdf_pts == 1.0
    assert candidate.physical_join_authenticated is False
    assert candidate.measurement_authorized is False

    far = inspect_native_wall_graph((
        strip(101, (0, 0, 10, 1)),
        strip(102, (18, 0, 28, 1)),
    ))
    assert far.component_count == 2
    assert far.endpoint_near_miss_total == 0
    touched = inspect_native_wall_graph((
        strip(101, (0, 0, 10, 1)),
        strip(102, (10, 0, 20, 1)),
    ))
    assert touched.component_count == 1
    assert touched.endpoint_near_miss_total == 0


def test_source_wall_near_miss_resists_source_path_identity_alias():
    from types import SimpleNamespace
    from shapely.geometry import box
    from pb_new_wall_graph_diagnostic import inspect_native_wall_graph
    same_source_renderings = (
        SimpleNamespace(polygon=box(0, 0, 10, 1),
                        native_path_indices=lambda: (55,)),
        SimpleNamespace(polygon=box(11, 0, 21, 1),
                        native_path_indices=lambda: (55,)),
    )
    result = inspect_native_wall_graph(same_source_renderings)
    assert result.component_count == 2
    assert result.endpoint_near_miss_total == 0


def test_source_wall_near_miss_rejects_nonslender_fills():
    from types import SimpleNamespace
    from shapely.geometry import box
    from pb_new_wall_graph_diagnostic import inspect_native_wall_graph
    bars = (
        SimpleNamespace(polygon=box(0, 0, 4, 4), native_path_indices=lambda: (9,)),
        SimpleNamespace(polygon=box(5, 0, 9, 4), native_path_indices=lambda: (10,)),
    )
    result = inspect_native_wall_graph(bars)
    assert result.endpoint_near_miss_total == 0
    assert result.component_count == 2
