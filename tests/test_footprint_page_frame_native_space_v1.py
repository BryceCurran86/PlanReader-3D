"""Source-neutral proof that the footprint chain compares display-space and native-space geometry in one space.

The raster footprint polygon is in DISPLAY space; ``get_drawings()`` rows are in NATIVE page space. On a rotated
page the trace now records PyMuPDF's derotation matrix and the four comparison sites convert through it. Every
scene is synthetic: no private drawing, project name, page number or expected quantity enters an expectation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from dataclasses import replace

import fitz
import pytest

import pb_external_footprint_first_trace as footprint
import pb_page_frame_shadow as frame_shadow
from pb_external_footprint_first_trace import (
    ExternalFootprintTrace,
    bound_native_drawings_to_footprint,
    footprint_bbox_in_native_space,
    footprint_polygon_in_native_space,
    native_points_to_display_space,
    refine_external_footprint_against_wall_ink,
    trace_external_footprint_first,
)
from pb_source_native_exterior_edge_path_ownership import own_exterior_contour_native_paths
from pb_source_native_wall_role_and_junction_shadow import (
    ROLE_ATTACHED_STRUCTURE,
    identify_source_wall_junctions_and_roles,
)

W, H = 1000, 800
ROTATIONS = (90, 180, 270)
BASE_KEYS = {
    "source_sha256", "page_index", "status", "reason", "polygon_pdf_pts", "bbox_pdf_pts", "candidate_count",
    "page_drawings_examined", "commercial_publishable", "measurement_authorized",
}
# An off-centre building (rows 0-2), three decoys that sit inside the WRONG window for one rotation each
# (rows 3-5) and two far rows (6-7).
OPS = (
    ("rect", (200, 200, 550, 450), 4), ("line", (375, 200, 375, 450), 3), ("line", (200, 325, 375, 325), 3),
    ("line", (585, 480, 585, 520), 3), ("line", (300, 480, 380, 480), 3), ("line", (700, 520, 760, 520), 3),
    ("line", (60, 60, 160, 60), 3), ("line", (880, 720, 960, 720), 3),
)
BUILDING = (0, 1, 2)


def derotation(rotation, w=W, h=H):
    """PyMuPDF's derotation matrix for a native w x h page, from first principles (display -> native)."""
    return {0: (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), 90: (0.0, -1.0, 1.0, 0.0, 0.0, float(h)),
            180: (-1.0, 0.0, 0.0, -1.0, float(w), float(h)), 270: (0.0, 1.0, -1.0, 0.0, float(w), 0.0)}[rotation]


def to_display(points, rotation, w=W, h=H):
    extent = frame_shadow.NativePageExtent(w, h)
    out = []
    for x, y in points:
        p = frame_shadow.native_to_display(frame_shadow.NativePoint(x, y), native_extent=extent, rotation=rotation)
        out.append((p.x, p.y))
    return tuple(out)


def build_pdf(rotation, *, width=W, height=H, ops=OPS):
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    for kind, geometry, pen in ops:
        if kind == "rect":
            page.draw_rect(fitz.Rect(*geometry), color=(0, 0, 0), width=pen)
        else:
            page.draw_line((geometry[0], geometry[1]), (geometry[2], geometry[3]), color=(0, 0, 0), width=pen)
    if rotation:
        page.set_rotation(rotation)
    raw = doc.tobytes()
    doc.close()
    return raw


def scene(rotation, **kwargs):
    raw = build_pdf(rotation, **kwargs)
    sha = hashlib.sha256(raw).hexdigest()
    (trace,) = trace_external_footprint_first(raw, source_sha256=sha, page_indices=(0,))
    page = fitz.open(stream=raw, filetype="pdf")[0]
    return trace, tuple(page.get_drawings()), sha, page


def selected_rects(scope, rows):
    return sorted(tuple(round(float(v), 1) for v in rows[i]["rect"]) for i in scope.selected_source_path_indices)


def manual_trace(polygon, bbox, matrix, sha="a" * 64):
    return ExternalFootprintTrace(sha, 0, "CANDIDATE", "visual_only", polygon_pdf_pts=polygon, bbox_pdf_pts=bbox,
                                  page_derotation_matrix=matrix)


# --- pure helpers ---------------------------------------------------------------------------------------------

def test_an_upright_trace_is_its_own_native_space_and_the_inputs_come_back_untouched():
    polygon = ((10.0, 10.0), (100.0, 10.0), (100.0, 90.0), (10.0, 90.0))
    trace = manual_trace(polygon, (10.0, 10.0, 100.0, 90.0), None)
    assert footprint_polygon_in_native_space(trace) is polygon
    assert footprint_bbox_in_native_space(trace) is trace.bbox_pdf_pts
    assert native_points_to_display_space(trace, polygon) == polygon
    assert footprint_bbox_in_native_space(replace(trace, bbox_pdf_pts=None)) is None


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_display_and_native_space_round_trip_for_every_rotation(rotation):
    rng = random.Random(rotation)
    native = tuple((rng.uniform(0, W), rng.uniform(0, H)) for _ in range(8))
    shown = to_display(native, rotation)
    trace = manual_trace(shown, (0.0, 0.0, 1.0, 1.0), derotation(rotation))
    back = footprint_polygon_in_native_space(trace)
    assert all(math.isclose(a, b, abs_tol=1e-9) for p, q in zip(back, native) for a, b in zip(p, q))
    again = native_points_to_display_space(trace, native)
    assert all(math.isclose(a, b, abs_tol=0.001) for p, q in zip(again, shown) for a, b in zip(p, q))


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_the_helper_agrees_with_pymupdf_and_with_the_page_frame_vocabulary(rotation):
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.set_rotation(rotation)
    matrix = tuple(float(v) + 0.0 for v in page.derotation_matrix)
    assert matrix == derotation(rotation)
    extent = frame_shadow.DisplayPageExtent(page.rect.width, page.rect.height)
    trace = manual_trace(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), (0.0, 0.0, 1.0, 1.0), matrix)
    for x, y in ((12.5, 40.0), (300.25, 700.75), (0.0, 0.0), (page.rect.width, page.rect.height)):
        probe = replace(trace, polygon_pdf_pts=((x, y),))
        mine = footprint_polygon_in_native_space(probe)[0]
        pymupdf = fitz.Point(x, y) * page.derotation_matrix
        canonical = frame_shadow.display_to_native(frame_shadow.DisplayPoint(x, y), display_extent=extent, rotation=rotation)
        assert math.isclose(mine[0], pymupdf.x, abs_tol=1e-6) and math.isclose(mine[1], pymupdf.y, abs_tol=1e-6)
        assert math.isclose(mine[0], canonical.x, abs_tol=1e-6) and math.isclose(mine[1], canonical.y, abs_tol=1e-6)


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_the_native_bbox_is_the_bbox_of_the_mapped_corners(rotation):
    native_box = (200.0, 120.0, 560.0, 430.0)
    corners = ((native_box[0], native_box[1]), (native_box[2], native_box[1]),
               (native_box[2], native_box[3]), (native_box[0], native_box[3]))
    shown = to_display(corners, rotation)
    display_box = (min(p[0] for p in shown), min(p[1] for p in shown), max(p[0] for p in shown), max(p[1] for p in shown))
    trace = manual_trace(shown, display_box, derotation(rotation))
    mapped = footprint_bbox_in_native_space(trace)
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(mapped, native_box))


@pytest.mark.parametrize("bad", [
    (1.0, 0.0, 0.0, 1.0, 0.0), (1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0), [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
    (1.0, 0.0, 0.0, 1.0, 0.0, float("nan")), (float("inf"), 0.0, 0.0, 1.0, 0.0, 0.0), (0.0,) * 6,
    (1.0, 2.0, 2.0, 4.0, 0.0, 0.0), ("1", 0, 0, 1, 0, 0),
])
def test_an_invalid_frame_is_refused_not_guessed(bad):
    trace = manual_trace(((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0)), (0.0, 0.0, 9.0, 9.0), bad)
    assert footprint_polygon_in_native_space(trace) is None
    assert footprint_bbox_in_native_space(trace) is None
    assert native_points_to_display_space(trace, trace.polygon_pdf_pts) is None


def test_a_boolean_is_not_a_frame_number():
    trace = manual_trace(((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0)), (0.0, 0.0, 9.0, 9.0), (True, 0, 0, True, 0, 0.5))
    assert footprint_polygon_in_native_space(trace) is None


# --- trace and serialisation ------------------------------------------------------------------------------------

def test_an_upright_page_leaves_the_trace_and_its_serialisation_unchanged():
    trace, _rows, _sha, _page = scene(0)
    assert trace.status == "CANDIDATE" and trace.page_derotation_matrix is None
    assert set(trace.to_dict()) == BASE_KEYS


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_a_rotated_page_records_the_pymupdf_frame(rotation):
    trace, _rows, _sha, page = scene(rotation)
    assert trace.status == "CANDIDATE"
    assert trace.page_derotation_matrix == tuple(float(v) + 0.0 for v in page.derotation_matrix) == derotation(rotation)
    assert not any(v == 0 and math.copysign(1.0, v) < 0 for v in trace.page_derotation_matrix)
    payload = trace.to_dict()
    assert set(payload) == BASE_KEYS | {"page_derotation_matrix"}
    assert json.loads(json.dumps(payload))["page_derotation_matrix"] == list(derotation(rotation))
    assert replace(trace, reason="x").page_derotation_matrix == trace.page_derotation_matrix


def test_construction_without_a_frame_still_works_positionally():
    trace = ExternalFootprintTrace("a" * 64, 1, "CANDIDATE", "visual_only", ((0.0, 0.0),), (0.0, 0.0, 1.0, 1.0), 2, 3)
    assert trace.page_derotation_matrix is None and trace.candidate_count == 2 and trace.page_drawings_examined == 3


def test_a_rotated_page_whose_frame_cannot_be_read_abstains(monkeypatch):
    monkeypatch.setattr(footprint, "_read_page_frame", lambda page: (False, None))
    trace, _rows, _sha, _page = scene(90)
    assert (trace.status, trace.reason) == ("ABSTAINED", "external_footprint_rotated_page_frame_unreadable")
    assert trace.polygon_pdf_pts == () and trace.page_derotation_matrix is None


# --- page-rotation invariance ----------------------------------------------------------------------------------

@pytest.mark.parametrize("rotation", (0, *ROTATIONS))
def test_the_bounded_scope_selects_the_same_rows_on_a_page_turned_any_way(rotation):
    trace, rows, sha, _page = scene(rotation)
    scope = bound_native_drawings_to_footprint(rows, trace=trace, expected_source_sha256=sha)
    assert scope.status == "CANDIDATE"
    assert scope.selected_source_path_indices == BUILDING
    native = footprint_bbox_in_native_space(trace)
    upright_trace, *_ = scene(0)
    assert all(math.isclose(a, b, abs_tol=0.01) for a, b in zip(native, upright_trace.bbox_pdf_pts))


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_without_a_frame_a_rotated_page_scopes_the_wrong_rows(rotation):
    """Documents the hazard the frame removes: the unconverted display window picks decoys and loses walls."""
    trace, rows, sha, _page = scene(rotation)
    blind = bound_native_drawings_to_footprint(
        rows, trace=replace(trace, page_derotation_matrix=None), expected_source_sha256=sha)
    assert blind.selected_source_path_indices != BUILDING


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_edge_ownership_is_page_rotation_invariant_and_in_native_space(rotation):
    upright, upright_rows, *_ = scene(0)
    baseline = sorted((e.classification, e.native_path_indices) for e in own_exterior_contour_native_paths(upright_rows, upright))
    trace, rows, *_ = scene(rotation)
    edges = own_exterior_contour_native_paths(rows, trace)
    assert sorted((e.classification, e.native_path_indices) for e in edges) == baseline
    x0, y0, x1, y1 = footprint_bbox_in_native_space(trace)
    assert all(x0 - 3 <= p[0] <= x1 + 3 and y0 - 3 <= p[1] <= y1 + 3 for e in edges for p in (e.start_pdf_pts, e.end_pdf_pts))
    shown = native_points_to_display_space(trace, [p for e in edges for p in (e.start_pdf_pts, e.end_pdf_pts)])
    dx0, dy0, dx1, dy1 = trace.bbox_pdf_pts
    assert all(dx0 - 3 <= p[0] <= dx1 + 3 and dy0 - 3 <= p[1] <= dy1 + 3 for p in shown)


def _wall_layer_row(x0, y0, x1, y1):
    return {"layer": "Enclosure_WallExternal", "color": (0.0, 0.0, 0.0), "fill": None, "width": 3.0,
            "items": (("l", fitz.Point(x0, y0), fitz.Point(x1, y1)),), "rect": fitz.Rect(x0, y0, x1, y1)}


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_the_wall_role_window_is_page_rotation_invariant(rotation):
    extra = (_wall_layer_row(585, 480, 585, 520), _wall_layer_row(300, 480, 380, 480), _wall_layer_row(700, 520, 760, 520))
    upright, upright_rows, sha, _ = scene(0)
    expected = identify_source_wall_junctions_and_roles(
        upright_rows + extra, source_sha256=sha, page_index=0, trace=upright).path_roles[len(upright_rows):]
    trace, rows, sha, _ = scene(rotation)
    got = identify_source_wall_junctions_and_roles(
        rows + extra, source_sha256=sha, page_index=0, trace=trace).path_roles[len(rows):]
    assert [r.role for r in got] == [r.role for r in expected]
    assert {r.role for r in expected} == {ROLE_ATTACHED_STRUCTURE}


def _line_rows(rotation):
    trace, rows, sha, _ = scene(rotation)
    return trace, rows, sha


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_refine_collapses_the_same_detour_in_a_rotated_frame(rotation):
    polygon = ((328.0, 140.0), (328.0, 449.0), (311.0, 450.0), (910.0, 450.0), (903.9, 448.9), (903.9, 140.0))
    drawings = ({
        "layer": "Enclosure_WallExternal", "color": (0.05, 0.05, 0.05), "fill": None,
        "items": (("l", fitz.Point(328.0, 140.0), fitz.Point(328.0, 449.0)),
                  ("l", fitz.Point(328.0, 449.0), fitz.Point(904.0, 449.0)),
                  ("l", fitz.Point(331.0, 449.5), fitz.Point(311.0, 449.5)),
                  ("l", fitz.Point(904.0, 140.0), fitz.Point(904.0, 449.0)),
                  ("l", fitz.Point(328.0, 140.0), fitz.Point(904.0, 140.0))),
    },)
    upright = manual_trace(polygon, (310.0, 138.0, 912.0, 452.0), None, "e" * 64)
    expected, expected_receipt = refine_external_footprint_against_wall_ink(upright, drawings)
    assert expected_receipt["collapsed_detour_count"] >= 1
    shown = to_display(polygon, rotation)
    box = (min(p[0] for p in shown), min(p[1] for p in shown), max(p[0] for p in shown), max(p[1] for p in shown))
    rotated = manual_trace(tuple((round(x, 3), round(y, 3)) for x, y in shown), box, derotation(rotation), "e" * 64)
    refined, receipt = refine_external_footprint_against_wall_ink(rotated, drawings)
    assert receipt["collapsed_detour_count"] == expected_receipt["collapsed_detour_count"]
    assert set(receipt["reason_codes"]) == set(expected_receipt["reason_codes"])
    want = to_display(expected.polygon_pdf_pts, rotation)
    assert len(refined.polygon_pdf_pts) == len(want)
    assert all(math.isclose(a, b, abs_tol=0.002) for p, q in zip(refined.polygon_pdf_pts, want) for a, b in zip(p, q))
    assert [tuple(p) for p in receipt["polygon_pdf_pts"]] == [tuple(p) for p in refined.polygon_pdf_pts]
    assert refined.page_derotation_matrix == derotation(rotation)
    assert all(round(v, 3) == v and not (v == 0 and math.copysign(1.0, v) < 0) for p in refined.polygon_pdf_pts for v in p)
    assert refined.measurement_authorized is False and refined.commercial_publishable is False


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_an_unrefined_rotated_receipt_is_reported_in_the_trace_space(rotation):
    polygon = ((0.0, 100.0), (200.0, 100.0), (200.0, 300.0), (0.0, 300.0))
    shown = to_display(polygon, rotation)
    box = (min(p[0] for p in shown), min(p[1] for p in shown), max(p[0] for p in shown), max(p[1] for p in shown))
    trace = manual_trace(tuple((round(x, 3), round(y, 3)) for x, y in shown), box, derotation(rotation))
    refined, receipt = refine_external_footprint_against_wall_ink(trace, ())
    assert refined is trace and receipt["collapsed_detour_count"] == 0
    assert all(math.isclose(a, b, abs_tol=0.002) for p, q in zip(receipt["polygon_pdf_pts"], shown) for a, b in zip(p, q))


@pytest.mark.parametrize("rotation", ROTATIONS)
def test_display_coordinates_are_rounded_and_never_carry_a_negative_zero(rotation):
    trace = manual_trace(((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0)), (0.0, 0.0, 9.0, 9.0), derotation(rotation))
    corners = ((0.0, 0.0), (float(W), 0.0), (0.0, float(H)), (float(W), float(H)), (123.45678, 98.76543),
               (-0.0, -5.0), (-5.0, -0.0))
    shown = native_points_to_display_space(trace, corners)
    assert all(round(v, 3) == v and not (v == 0 and math.copysign(1.0, v) < 0) for p in shown for v in p)


# --- fail closed ------------------------------------------------------------------------------------------------

BAD_FRAME = (1.0, 0.0, 0.0, 1.0, 0.0, float("nan"))


def test_an_invalid_frame_abstains_at_every_comparison_site():
    polygon = ((10.0, 10.0), (100.0, 10.0), (100.0, 100.0), (10.0, 100.0))
    trace = manual_trace(polygon, (10.0, 10.0, 100.0, 100.0), BAD_FRAME, "b" * 64)
    row = {"rect": fitz.Rect(20, 20, 30, 20), "layer": "Enclosure_WallExternal", "color": (0, 0, 0), "fill": None,
           "items": (("l", fitz.Point(20, 20), fitz.Point(30, 20)),)}
    scope = bound_native_drawings_to_footprint((row,), trace=trace, expected_source_sha256="b" * 64)
    assert (scope.status, scope.reason, scope.drawings, scope.selected_source_path_indices) == (
        "ABSTAINED", "footprint_frame_matrix_invalid", (), ())
    refined, receipt = refine_external_footprint_against_wall_ink(trace, (row,))
    assert refined is trace and receipt["reason_codes"] == ["footprint_frame_matrix_invalid"]
    assert own_exterior_contour_native_paths((row,), trace) == ()
    report = identify_source_wall_junctions_and_roles((row,), source_sha256="b" * 64, page_index=0, trace=trace)
    assert all(r.role != ROLE_ATTACHED_STRUCTURE for r in report.path_roles)


def test_an_explicit_identity_frame_equals_no_frame():
    trace, rows, sha, _ = scene(0)
    explicit = replace(trace, page_derotation_matrix=derotation(0))
    assert bound_native_drawings_to_footprint(rows, trace=explicit, expected_source_sha256=sha).selected_source_path_indices == \
        bound_native_drawings_to_footprint(rows, trace=trace, expected_source_sha256=sha).selected_source_path_indices
    assert [(e.classification, e.native_path_indices) for e in own_exterior_contour_native_paths(rows, explicit)] == \
        [(e.classification, e.native_path_indices) for e in own_exterior_contour_native_paths(rows, trace)]


# --- metamorphic: the selection belongs to the drawing, not to how it is stored -----------------------------------

def _scope(rotation, **kwargs):
    trace, rows, sha, _ = scene(rotation, **kwargs)
    return trace, rows, bound_native_drawings_to_footprint(rows, trace=trace, expected_source_sha256=sha)


def test_unrelated_far_content_does_not_change_the_selection():
    base_trace, base_rows, base = _scope(90)
    extra = tuple(("line", (900, 100 + 40 * i, 980, 100 + 40 * i), 3) for i in range(5))
    _trace, rows, scope = _scope(90, ops=OPS + extra)
    assert scope.status == "CANDIDATE" and selected_rects(scope, rows) == selected_rects(base, base_rows)


def test_a_larger_page_with_the_same_drawing_does_not_change_the_selection():
    _t, base_rows, base = _scope(90)
    _trace, rows, scope = _scope(90, width=1400, height=1100)
    assert scope.status == "CANDIDATE" and selected_rects(scope, rows) == selected_rects(base, base_rows)


@pytest.mark.parametrize("seed", range(3))
def test_the_order_of_the_rows_does_not_change_the_selected_geometry(seed):
    _t, base_rows, base = _scope(90)
    ops = list(OPS)
    random.Random(seed).shuffle(ops)
    _trace, rows, scope = _scope(90, ops=tuple(ops))
    assert scope.status == "CANDIDATE" and selected_rects(scope, rows) == selected_rects(base, base_rows)


@pytest.mark.parametrize("k", [0.5, 2.0])
def test_uniform_scale_does_not_change_which_rows_are_selected(k):
    ops = tuple((kind, tuple(v * k for v in g), pen * k) for kind, g, pen in OPS)
    _trace, _rows, scope = _scope(90, width=W * k, height=H * k, ops=ops)
    assert scope.status == "CANDIDATE" and scope.selected_source_path_indices == BUILDING


def test_splitting_walls_into_collinear_pieces_does_not_change_the_selected_length():
    _t, base_rows, base = _scope(90)
    length = lambda rows, scope: round(sum(  # noqa: E731
        (rows[i]["rect"].width + rows[i]["rect"].height) for i in scope.selected_source_path_indices), 1)
    split = (OPS[0], ("line", (375, 200, 375, 325), 3), ("line", (375, 325, 375, 450), 3),
             ("line", (200, 325, 290, 325), 3), ("line", (290, 325, 375, 325), 3)) + OPS[3:]
    _trace, rows, scope = _scope(90, ops=split)
    assert scope.status == "CANDIDATE" and length(rows, scope) == length(base_rows, base)


def test_replay_is_deterministic_and_the_inputs_are_not_mutated():
    trace, rows, sha, _ = scene(90)
    trace_before, rows_before = copy.deepcopy(trace), copy.deepcopy(rows)
    first = bound_native_drawings_to_footprint(rows, trace=trace, expected_source_sha256=sha)
    second = bound_native_drawings_to_footprint(rows, trace=trace, expected_source_sha256=sha)
    assert first == second
    own_exterior_contour_native_paths(rows, trace)
    refine_external_footprint_against_wall_ink(trace, rows)
    assert trace == trace_before and rows == rows_before


def test_the_footprint_stays_review_only_in_every_rotation():
    for rotation in (0, *ROTATIONS):
        trace, rows, sha, _ = scene(rotation)
        scope = bound_native_drawings_to_footprint(rows, trace=trace, expected_source_sha256=sha)
        assert trace.measurement_authorized is False and trace.commercial_publishable is False
        assert trace.to_dict()["measurement_authorized"] is False and scope.commercial_publishable is False
