"""Source-neutral proof for the footprint native-edge-support shadow check and its default-off first-trace flag.

Every scene is synthetic. No private drawing, project name, page number, benchmark answer or area enters
the expectations. A false frame is a candidate whose long edges are drawn in a much lighter pen than the
wall linework inside it; the reference pen comes from the candidate's own interior only.
"""
from __future__ import annotations

import copy
import hashlib
import random
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import fitz
import pytest

import pb_source_footprint_native_edge_support_shadow as support
from pb_external_footprint_first_trace import trace_external_footprint_first
from pb_source_footprint_native_edge_support_shadow import (
    NATIVE_PRIMITIVE_CAP,
    STATUS_NOT_APPLICABLE,
    STATUS_SUPPORTED,
    STATUS_UNSUPPORTED,
    STATUS_UNVERIFIABLE,
    assess_footprint_native_edge_support,
)

BOX = (100.0, 100.0, 700.0, 500.0)  # 600 x 400: the shorter side is 400


def _bounds(*points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def line(p, q, width, color=(0.0, 0.0, 0.0)):
    return {"type": "s", "color": color, "fill": None, "width": width,
            "items": [("l", p, q)], "rect": _bounds(p, q)}


def strip(x0, y0, x1, y1, fill=(0.0, 0.0, 0.0)):
    return {"type": "f", "color": None, "fill": fill, "width": None,
            "items": [("re", (x0, y0, x1, y1), 1)], "rect": (x0, y0, x1, y1)}


def polygon(box=BOX):
    x0, y0, x1, y1 = box
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def frame_lines(width, box=BOX, color=(0.0, 0.0, 0.0)):
    x0, y0, x1, y1 = box
    return [line((x0, y0), (x1, y0), width, color), line((x1, y0), (x1, y1), width, color),
            line((x1, y1), (x0, y1), width, color), line((x0, y1), (x0, y0), width, color)]


def interior_walls(width, color=(0.0, 0.0, 0.0)):
    """880 pt of interior wall run in one pen, clear of the frame (the shorter side is 400)."""
    return [line((400.0, 130.0), (400.0, 470.0), width, color), line((130.0, 300.0), (670.0, 300.0), width, color)]


def one_pen(width):
    return frame_lines(width) + interior_walls(width)


def lighter_frame(frame_width, wall_width):
    return frame_lines(frame_width) + interior_walls(wall_width)


def strip_frame(thickness, box=BOX):
    x0, y0, x1, y1 = box
    h = thickness / 2.0
    return [strip(x0, y0 - h, x1, y0 + h), strip(x0, y1 - h, x1, y1 + h),
            strip(x0 - h, y0, x0 + h, y1), strip(x1 - h, y0, x1 + h, y1)]


def strip_walls(thickness):
    h = thickness / 2.0
    return [strip(400.0 - h, 130.0, 400.0 + h, 470.0), strip(130.0, 300.0 - h, 670.0, 300.0 + h)]


def far_content():
    """Heavy lines, a title block and a swarm of hairline ticks, all outside the candidate."""
    rows = [line((800.0, 100.0 + 40.0 * i), (1400.0, 100.0 + 40.0 * i), 9.0) for i in range(6)]
    rows += [line((800.0 + 3.0 * i, 700.0), (800.0 + 3.0 * i, 712.0), 0.2) for i in range(400)]
    return rows


def run(rows, box=BOX):
    return assess_footprint_native_edge_support(polygon(box), rows)


# --- positives -----------------------------------------------------------------------------------------------

def test_walls_in_one_bold_pen_are_supported():
    result = run(one_pen(4.0))
    assert (result.status, result.reason) == (STATUS_SUPPORTED, support.REASON_SUPPORTED)
    assert result.reference_thickness == 4.0
    assert all(edge.backed_cover == 1.0 for edge in result.edges)


def test_filled_wall_strips_are_the_wall_pen():
    result = run(strip_frame(6.0) + strip_walls(6.0))
    assert result.status == STATUS_SUPPORTED
    assert result.reference_thickness == 6.0


def test_a_thick_wall_whose_centre_line_is_half_a_thickness_inside_the_outer_face_is_supported():
    # The raster contour follows the outer face; a 10 pt stroke centred 4.5 pt inside it is 4.5 pt from the edge,
    # beyond a flat 2.5 pt snap but within the snap plus half the stroke's own thickness.
    x0, y0, x1, y1 = BOX
    inset = 4.5
    frame = [line((x0, y0 + inset), (x1, y0 + inset), 10.0), line((x1 - inset, y0), (x1 - inset, y1), 10.0),
             line((x1, y1 - inset), (x0, y1 - inset), 10.0), line((x0 + inset, y1), (x0 + inset, y0), 10.0)]
    assert run(frame + interior_walls(10.0)).status == STATUS_SUPPORTED


def test_a_page_in_one_pen_never_reports_a_conflict():
    assert run(one_pen(0.35)).status == STATUS_SUPPORTED


def test_one_pen_step_lighter_is_not_a_conflict_and_two_steps_is_the_inclusive_boundary():
    assert run(lighter_frame(2.0, 2.8)).status == STATUS_SUPPORTED  # 1.4 x: one step of the usual series
    assert run(lighter_frame(1.0, 2.0)).status == STATUS_SUPPORTED  # exactly 2 x: inclusive
    assert run(lighter_frame(0.99, 2.0)).status == STATUS_UNSUPPORTED  # just beyond 2 x


def test_heavier_content_outside_the_candidate_cannot_change_the_verdict():
    # A page-wide statistic would move; the reference comes from the candidate's own interior only.
    assert run(one_pen(4.0) + far_content()).status == STATUS_SUPPORTED
    assert run(lighter_frame(0.5, 3.0) + far_content()).status == STATUS_UNSUPPORTED


# --- the false frame ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("rows", [
    lighter_frame(0.5, 3.0),
    frame_lines(0.5) + strip_walls(6.0),
    [strip(0, 0, 0.0001, 0.0001)] + lighter_frame(0.5, 3.0),
])
def test_a_hairline_frame_around_bold_interior_walls_is_unsupported(rows):
    result = run(rows)
    assert (result.status, result.reason) == (STATUS_UNSUPPORTED, support.REASON_UNSUPPORTED)
    assert all(edge.backed_cover == 0.0 and edge.any_ink_cover == 1.0 for edge in result.edges)


def test_one_hairline_edge_is_enough_to_call_the_outline_false():
    rows = frame_lines(4.0)[:3] + [line((100.0, 500.0), (100.0, 100.0), 0.5)] + interior_walls(4.0)  # left edge: hairline
    assert run(rows).status == STATUS_UNSUPPORTED
    # With no ink at all on that edge the outline is unknown, not conflicting.
    assert run(frame_lines(4.0)[:3] + interior_walls(4.0)).reason == support.REASON_EDGE_UNKNOWN


# --- never a veto without a positive conflict ----------------------------------------------------------------

def test_complex_contour_is_not_applicable():
    stairs = ((100, 100), (400, 100), (400, 200), (700, 200), (700, 300), (500, 300), (500, 400), (300, 400),
              (300, 500), (200, 500), (200, 300), (100, 300))
    result = assess_footprint_native_edge_support(stairs, one_pen(4.0))
    assert (result.status, result.reason) == (STATUS_NOT_APPLICABLE, support.REASON_COMPLEX)


def test_a_contour_without_four_long_axis_aligned_edges_is_not_applicable():
    diamond = ((400, 100), (700, 300), (400, 500), (100, 300))
    result = assess_footprint_native_edge_support(diamond, one_pen(4.0))
    assert (result.status, result.reason) == (STATUS_NOT_APPLICABLE, support.REASON_FEW_EDGES)


def test_a_raster_only_page_has_nothing_to_compare_and_is_unverifiable():
    result = run(())
    assert (result.status, result.reason) == (STATUS_UNVERIFIABLE, support.REASON_NO_INK)


def test_a_frame_without_interior_wall_linework_has_no_reference():
    result = run(frame_lines(0.5))
    assert (result.status, result.reason) == (STATUS_UNVERIFIABLE, support.REASON_NO_REFERENCE)
    short_run = frame_lines(0.5) + [line((200.0, 300.0), (400.0, 300.0), 3.0)]  # 200 < the 400 pt shorter side
    assert run(short_run).reason == support.REASON_NO_REFERENCE


def test_green_and_light_ink_never_form_the_reference():
    green_walls = interior_walls(4.0, color=(0.0, 0.7, 0.0))
    light_walls = interior_walls(4.0, color=(0.8, 0.8, 0.8))
    assert run(frame_lines(0.5) + green_walls).reason == support.REASON_NO_REFERENCE
    assert run(frame_lines(0.5) + light_walls).reason == support.REASON_NO_REFERENCE
    assert run(frame_lines(0.5, color=(0.0, 0.7, 0.0)) + green_walls).reason == support.REASON_NO_INK


def test_edges_with_no_native_ink_at_all_are_unknown_not_conflicting():
    result = run(interior_walls(4.0))
    assert (result.status, result.reason) == (STATUS_UNVERIFIABLE, support.REASON_EDGE_UNKNOWN)


def test_edges_covered_only_by_unreadable_dark_fill_are_ambiguous():
    quarter = lambda x0, y0, x1, y1: {  # noqa: E731 - a filled polygon the strip reader cannot read
        "type": "f", "color": None, "fill": (0.0, 0.0, 0.0), "width": None,
        "items": [("re", (x0, y0, x1, y1), 1)], "rect": (x0, y0, x1, y1)}
    blobs = [quarter(100, 100, 400, 300), quarter(400, 100, 700, 300),
             quarter(100, 300, 400, 500), quarter(400, 300, 700, 500)]
    result = run(interior_walls(4.0) + blobs)
    assert (result.status, result.reason) == (STATUS_UNVERIFIABLE, support.REASON_AMBIGUOUS)


def test_native_primitive_cap_is_respected_at_the_boundary():
    inert = {"type": "s", "color": (1.0, 1.0, 1.0), "fill": None, "width": 1.0, "items": [], "rect": (0, 0, 0, 0)}
    base = one_pen(4.0)
    at_cap = base + [inert] * (NATIVE_PRIMITIVE_CAP - len(base))
    assert len(at_cap) == NATIVE_PRIMITIVE_CAP and run(at_cap).status == STATUS_SUPPORTED
    over = run(at_cap + [inert])
    assert (over.status, over.reason) == (STATUS_UNVERIFIABLE, support.REASON_OVER_CAP)


@pytest.mark.parametrize("bad", [
    ((0, 0), (10, 0), (10, 10)),
    ((0, 0), (10, 0), (10, float("nan")), (0, 10)),
    ((0, 0), (0, 0), (0, 0), (0, 0)),
])
def test_an_invalid_polygon_is_unverifiable(bad):
    assert assess_footprint_native_edge_support(bad, one_pen(4.0)).reason == support.REASON_BAD_POLYGON


def test_malformed_rows_are_ignored_without_error():
    junk = [None, 7, {}, {"type": "s"}, {"type": "s", "color": (0, 0, 0), "width": float("nan"), "items": [("l", (0, 0), (5, 0))]},
            {"type": "s", "color": (0, 0, 0), "width": 2.0, "items": [("l", (0, 0), (float("nan"), 1))]},
            {"type": "f", "fill": (0, 0, 0), "rect": None, "items": []}, {"type": "s", "color": "black", "width": 1.0, "items": []}]
    assert run(lighter_frame(0.5, 3.0) + junk).status == STATUS_UNSUPPORTED
    assert run(one_pen(4.0) + junk).status == STATUS_SUPPORTED


# --- metamorphic: the verdict belongs to the drawing, not to where or how it is stored --------------------

SCENES = {
    "supported": (one_pen(4.0), STATUS_SUPPORTED),
    "strips": (strip_frame(6.0) + strip_walls(6.0), STATUS_SUPPORTED),
    "unsupported": (lighter_frame(0.5, 3.0), STATUS_UNSUPPORTED),
    "unsupported_strips": (frame_lines(0.5) + strip_walls(6.0), STATUS_UNSUPPORTED),
}


def _map_row(row, f, k=1.0):
    new = dict(row)
    items = []
    for item in row["items"]:
        if item[0] == "l":
            items.append(("l", f(item[1]), f(item[2])))
        else:
            a, b = f((item[1][0], item[1][1])), f((item[1][2], item[1][3]))
            items.append(("re", _bounds(a, b), item[2]))
    new["items"] = items
    new["rect"] = _bounds(f((row["rect"][0], row["rect"][1])), f((row["rect"][2], row["rect"][3])))
    if row.get("width"):
        new["width"] = row["width"] * k
    return new


def _transform(rows, f, k=1.0):
    return [_map_row(r, f, k) for r in rows], tuple(f(p) for p in polygon())


TRANSFORMS = {
    "translate": lambda p: (p[0] + 1234.5, p[1] - 987.25),
    "rotate90": lambda p: (-p[1], p[0]),
    "mirror": lambda p: (-p[0], p[1]),
    "flip": lambda p: (p[0], -p[1]),
}


@pytest.mark.parametrize("scene", sorted(SCENES))
@pytest.mark.parametrize("name", sorted(TRANSFORMS))
def test_translation_rotation_and_mirror_keep_the_verdict(scene, name):
    rows, expected = SCENES[scene]
    mapped_rows, mapped_polygon = _transform(rows, TRANSFORMS[name])
    result = assess_footprint_native_edge_support(mapped_polygon, mapped_rows)
    assert result.status == expected
    assert result.reference_thickness == assess_footprint_native_edge_support(polygon(), rows).reference_thickness


@pytest.mark.parametrize("scene", sorted(SCENES))
@pytest.mark.parametrize("k", [0.25, 4.0])
def test_uniform_scale_keeps_the_verdict(scene, k):
    rows, expected = SCENES[scene]
    mapped_rows, mapped_polygon = _transform(rows, lambda p: (p[0] * k, p[1] * k), k)
    assert assess_footprint_native_edge_support(mapped_polygon, mapped_rows).status == expected


@pytest.mark.parametrize("scene", sorted(SCENES))
def test_row_order_does_not_change_the_result(scene):
    rows, _ = SCENES[scene]
    baseline = run(rows).to_dict()
    for seed in range(5):
        shuffled = list(rows)
        random.Random(seed).shuffle(shuffled)
        assert run(shuffled).to_dict() == baseline


def _split(row, parts):
    if row["items"][0][0] != "l":
        x0, y0, x1, y1 = row["rect"]
        step = (x1 - x0) / parts if x1 - x0 >= y1 - y0 else None
        if step is None:
            step = (y1 - y0) / parts
            return [strip(x0, y0 + i * step, x1, y0 + (i + 1) * step) for i in range(parts)]
        return [strip(x0 + i * step, y0, x0 + (i + 1) * step, y1) for i in range(parts)]
    (_, p, q) = row["items"][0]
    return [line((p[0] + (q[0] - p[0]) * i / parts, p[1] + (q[1] - p[1]) * i / parts),
                 (p[0] + (q[0] - p[0]) * (i + 1) / parts, p[1] + (q[1] - p[1]) * (i + 1) / parts), row["width"])
            for i in range(parts)]


@pytest.mark.parametrize("scene", sorted(SCENES))
def test_splitting_walls_into_collinear_pieces_does_not_change_the_verdict(scene):
    rows, expected = SCENES[scene]
    pieces = [piece for row in rows for piece in _split(row, 3)]
    result = run(pieces)
    assert result.status == expected
    assert result.reference_thickness == run(rows).reference_thickness


def test_far_content_and_a_swarm_of_ticks_do_not_change_any_scene():
    for rows, expected in SCENES.values():
        assert run(rows + far_content()).status == expected


def test_replay_is_deterministic_and_the_inputs_are_not_mutated():
    for rows, _ in SCENES.values():
        before = copy.deepcopy(rows)
        first, second = run(rows), run(rows)
        assert first == second and first.to_dict() == second.to_dict()
        assert rows == before


def test_fitz_like_points_and_rects_give_the_same_result_as_tuples():
    def objectify(row):
        new = dict(row)
        items = []
        for item in row["items"]:
            if item[0] == "l":
                items.append(("l", SimpleNamespace(x=item[1][0], y=item[1][1]), SimpleNamespace(x=item[2][0], y=item[2][1])))
            else:
                r = item[1]
                items.append(("re", SimpleNamespace(x0=r[0], y0=r[1], x1=r[2], y1=r[3]), item[2]))
        new["items"] = items
        r = row["rect"]
        new["rect"] = SimpleNamespace(x0=r[0], y0=r[1], x1=r[2], y1=r[3])
        return new

    for rows, expected in SCENES.values():
        objs = [objectify(r) for r in rows]
        result = assess_footprint_native_edge_support([SimpleNamespace(x=x, y=y) for x, y in polygon()], objs)
        assert result.status == expected


def test_every_verdict_carries_no_authority_and_is_immutable():
    for rows in ([], one_pen(4.0), lighter_frame(0.5, 3.0), interior_walls(4.0)):
        result = run(rows)
        d = result.to_dict()
        assert d["commercial_publishable"] is False and d["measurement_authorized"] is False
        assert d["deduction_authority"] is False
        with pytest.raises(FrozenInstanceError):
            result.status = "X"  # type: ignore[misc]


# --- the first-trace flag (default OFF) on real PDF pages ------------------------------------------------

def _pdf(draw, *, rotation=0, width=1100, height=780):
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    draw(page)
    if rotation:
        page.set_rotation(rotation)
    raw = doc.tobytes()
    doc.close()
    return raw


def _bold_lines(page, segments, width):
    for p, q in segments:
        page.draw_line(p, q, color=(0, 0, 0), width=width)


def _hairline_site_frame(page):
    page.draw_rect(fitz.Rect(145, 105, 950, 605), color=(0, 0, 0), width=1.5)
    _bold_lines(page, [((250, 210), (500, 210)), ((630, 215), (865, 215)), ((500, 210), (500, 400)),
                       ((250, 430), (850, 430))], 4)


def _bold_enclosure(page):
    page.draw_rect(fitz.Rect(145, 105, 950, 605), color=(0, 0, 0), width=4)
    _bold_lines(page, [((545, 105), (545, 605)), ((145, 350), (545, 350))], 3)


def _strip_enclosure(page):
    for rect in ((145, 105, 950, 111), (145, 599, 950, 605), (145, 105, 151, 605), (944, 105, 950, 605),
                 (497, 111, 503, 599), (151, 300, 497, 306)):
        page.draw_rect(fitz.Rect(*rect), color=None, fill=(0, 0, 0))


def _rotated_hairline_site_frame(page):
    # Drawn in the UNROTATED space and kept left of the title-band cut-off after a 90 degree turn.
    page.draw_rect(fitz.Rect(100, 105, 800, 605), color=(0, 0, 0), width=1.5)
    _bold_lines(page, [((450, 105), (450, 605)), ((100, 350), (450, 350)), ((460, 200), (790, 200))], 4)


def _trace(raw, **kwargs):
    (trace,) = trace_external_footprint_first(
        raw, source_sha256=hashlib.sha256(raw).hexdigest(), page_indices=(0,), **kwargs)
    return trace


def test_default_off_leaves_the_false_frame_candidate_exactly_as_before():
    raw = _pdf(_hairline_site_frame)
    sys.modules.pop("pb_source_footprint_native_edge_support_shadow", None)
    default = _trace(raw)
    assert default.status == "CANDIDATE"
    assert "pb_source_footprint_native_edge_support_shadow" not in sys.modules  # not even imported
    assert default == _trace(raw, require_native_edge_support=False)


def test_opt_in_abstains_on_the_hairline_site_frame_without_any_authority():
    raw = _pdf(_hairline_site_frame)
    trace = _trace(raw, require_native_edge_support=True)
    assert trace.status == "ABSTAINED"
    assert trace.reason == "external_footprint_unverified_native_wall_edges"
    assert trace.polygon_pdf_pts == () and trace.bbox_pdf_pts is None
    assert trace.page_drawings_examined > 0
    assert trace.measurement_authorized is False and trace.commercial_publishable is False


@pytest.mark.parametrize("draw", [_bold_enclosure, _strip_enclosure])
def test_opt_in_keeps_a_real_enclosure_drawn_in_the_wall_pen(draw):
    raw = _pdf(draw)
    kept = _trace(raw, require_native_edge_support=True)
    assert kept.status == "CANDIDATE" and kept == _trace(raw)


def test_opt_in_compares_in_one_coordinate_space_on_a_rotated_page():
    raw = _pdf(_rotated_hairline_site_frame, rotation=90)
    page = fitz.open(stream=raw, filetype="pdf")[0]
    assert page.rotation == 90
    default = _trace(raw)
    assert default.status == "CANDIDATE"
    # Without derotation the raster polygon (visible space) would sit away from every native row (unrotated space).
    flagged = _trace(raw, require_native_edge_support=True)
    assert (flagged.status, flagged.reason) == ("ABSTAINED", "external_footprint_unverified_native_wall_edges")


def test_opt_in_never_abstains_on_a_page_with_no_native_ink():
    source = fitz.open(stream=_pdf(_hairline_site_frame), filetype="pdf")
    pix = source[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    doc = fitz.open()
    page = doc.new_page(width=1100, height=780)
    page.insert_image(page.rect, pixmap=pix)
    raw = doc.tobytes()
    doc.close()
    assert fitz.open(stream=raw, filetype="pdf")[0].get_drawings() == []
    default = _trace(raw)
    assert default.status == "CANDIDATE"
    assert _trace(raw, require_native_edge_support=True) == default


def test_one_pen_step_lighter_frame_is_left_alone_on_a_real_page():
    def draw(page):
        page.draw_rect(fitz.Rect(145, 105, 950, 605), color=(0, 0, 0), width=2)
        _bold_lines(page, [((250, 210), (500, 210)), ((630, 215), (865, 215)), ((500, 210), (500, 400)),
                           ((250, 430), (850, 430))], 3)

    raw = _pdf(draw)
    assert _trace(raw, require_native_edge_support=True) == _trace(raw)


# --- item shapes and the vertex boundary --------------------------------------------------------------------

def test_an_eight_vertex_contour_is_still_assessed_and_a_ninth_vertex_is_not():
    eight = ((100, 100), (400, 100), (700, 100), (700, 300), (700, 500), (400, 500), (100, 500), (100, 300))
    assert assess_footprint_native_edge_support(eight, one_pen(4.0)).status == STATUS_SUPPORTED
    assert assess_footprint_native_edge_support(eight, lighter_frame(0.5, 3.0)).status == STATUS_UNSUPPORTED
    nine = eight[:1] + ((250, 100),) + eight[1:]
    assert assess_footprint_native_edge_support(nine, one_pen(4.0)).reason == support.REASON_COMPLEX


def test_a_stroked_rectangle_item_is_read_as_four_edges():
    frame = {"type": "s", "color": (0.0, 0.0, 0.0), "fill": None, "width": 4.0,
             "items": [("re", BOX, 1)], "rect": BOX}
    assert run([frame] + interior_walls(4.0)).status == STATUS_SUPPORTED
    assert run([dict(frame, width=0.5)] + interior_walls(4.0)).status == STATUS_UNSUPPORTED


def test_a_quad_item_is_read_as_four_edges():
    x0, y0, x1, y1 = BOX
    quad = SimpleNamespace(ul=SimpleNamespace(x=x0, y=y0), ur=SimpleNamespace(x=x1, y=y0),
                           lr=SimpleNamespace(x=x1, y=y1), ll=SimpleNamespace(x=x0, y=y1))
    frame = {"type": "s", "color": (0.0, 0.0, 0.0), "fill": None, "width": 4.0, "items": [("qu", quad)], "rect": BOX}
    assert run([frame] + interior_walls(4.0)).status == STATUS_SUPPORTED
    assert run([dict(frame, width=0.5)] + interior_walls(4.0)).status == STATUS_UNSUPPORTED
