"""Source-neutral proof that the default-off native-edge-support veto compares the raster footprint polygon with the
native drawing rows in ONE space on turned, UserUnit-scaled and cropped pages.

The raster polygon is in DISPLAY space and the ``get_drawings()`` rows are in NATIVE page space. Both are in
UserUnit-scaled points, but PyMuPDF's own ``page.derotation_matrix`` translates by the UNSCALED page extent, so
carrying the polygon across with it displaces the outline on a turned page whose /UserUnit is not 1 and the veto
silently fails open. The veto therefore uses the frame the trace itself records (``_read_page_frame``), through
``footprint_polygon_in_native_space``, like every other comparison site of the chain.

Every scene is synthetic and is authored from the PDF contract (rotation, /UserUnit, CropBox). No private drawing,
project name, page number or expected quantity enters an expectation.
"""
from __future__ import annotations

import ast
import functools
import hashlib
import importlib
import inspect
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import fitz
import pytest

import pb_external_footprint_first_trace as footprint
from pb_external_footprint_first_trace import trace_external_footprint_first

W, H = 1000, 800
BLACK = (0, 0, 0)
ROTATIONS = (0, 90, 180, 270)
TURNED = (90, 180, 270)
UNITS = (1, 2, 1.5)
CROP = (20.0, 40.0, 30.0, 60.0)  # left, top, right, bottom margins of an offset CropBox in the unrotated, y-down page space
CROPS = (None, CROP)
CANDIDATE = "CANDIDATE"
VETO = ("ABSTAINED", "external_footprint_unverified_native_wall_edges")
FRAME_UNREADABLE = ("ABSTAINED", "external_footprint_rotated_page_frame_unreadable")
SUPPORT_MODULE = "pb_source_footprint_native_edge_support_shadow"


# --- synthetic pages ---------------------------------------------------------------------------------------------

def _centre(width, height, crop):
    """The centre of the VISIBLE (cropped) page in the unrotated, y-down authoring space."""
    left, top, right, bottom = crop or (0.0, 0.0, 0.0, 0.0)
    return (left + width - right) / 2.0, (top + height - bottom) / 2.0


def _lines(page, segments, pen, *, split=False, reverse=False):
    ordered = list(reversed(segments)) if reverse else list(segments)
    for p, q in ordered:
        if reverse:
            p, q = q, p
        if split:
            mid = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
            page.draw_line(p, mid, color=BLACK, width=pen)
            page.draw_line(mid, q, color=BLACK, width=pen)
        else:
            page.draw_line(p, q, color=BLACK, width=pen)


def _scene(page, scene, crop, *, split=False, reverse=False, far=False):
    """A 500 x 340 building centred in the visible page, so that no quarter turn moves it into the title band."""
    cx, cy = _centre(page.rect.width, page.rect.height, crop)
    x0, y0, x1, y1 = cx - 250, cy - 170, cx + 250, cy + 170
    frame = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    options = {"split": split, "reverse": reverse}
    walls = [((cx, cy - 130), (cx, cy + 130)), ((cx - 210, cy), (cx, cy)), ((cx + 20, cy - 60), (cx + 210, cy - 60))]
    if scene == "false_frame":  # a hairline outline around bold wall linework: the veto must fire
        _lines(page, frame, 1.5, **options)
        _lines(page, walls, 4, **options)
    elif scene == "real_enclosure":  # the outline is drawn in the wall pen
        _lines(page, frame, 4, **options)
        _lines(page, [((cx, cy - 170), (cx, cy + 170)), ((cx - 250, cy), (cx, cy))], 3, **options)
    elif scene == "lighter_frame":  # one pen step lighter than the walls is not a conflict
        _lines(page, frame, 2, **options)
        _lines(page, walls, 3, **options)
    elif scene == "strip_enclosure":  # the outline and the walls are filled strips
        t = 3.0
        for rect in ((x0, y0 - t, x1, y0 + t), (x0, y1 - t, x1, y1 + t), (x0 - t, y0, x0 + t, y1), (x1 - t, y0, x1 + t, y1),
                     (cx - t, y0 + t, cx + t, y1 - t), (x0 + t, cy - t, cx - t, cy + t)):
            page.draw_rect(fitz.Rect(*rect), color=None, fill=BLACK)
    elif scene in ("t_outline", "plus_outline"):  # hairline contours of 8 and of 12 vertices
        outline = {
            "t_outline": [(-250, -170), (250, -170), (250, -40), (90, -40), (90, 170), (-90, 170), (-90, -40), (-250, -40)],
            "plus_outline": [(-80, -170), (80, -170), (80, -60), (250, -60), (250, 60), (80, 60), (80, 170), (-80, 170),
                             (-80, 60), (-250, 60), (-250, -60), (-80, -60)],
        }[scene]
        points = [(cx + a, cy + b) for a, b in outline]
        _lines(page, list(zip(points, points[1:] + points[:1])), 1.5, **options)
        inside = [((cx, cy - 130), (cx, cy + 130))]  # inside both shapes
        if scene == "plus_outline":
            inside += [((cx - 210, cy), (cx - 20, cy)), ((cx + 20, cy), (cx + 210, cy))]
        _lines(page, inside, 4, **options)
    else:
        raise AssertionError(scene)
    if far:  # unrelated content, far from the building and inside every CropBox used here
        page.draw_line((60, 70), (200, 70), color=BLACK, width=4)


def _finish(doc, page, rotation, user_unit, crop, width, height):
    if crop:
        page.set_cropbox(fitz.Rect(crop[0], crop[1], width - crop[2], height - crop[3]))
    if user_unit != 1:
        doc.xref_set_key(page.xref, "UserUnit", str(user_unit))  # any raw text, so that an unreadable unit can be written
    if rotation:
        page.set_rotation(rotation)
    raw = doc.tobytes()
    doc.close()
    return raw


@functools.lru_cache(maxsize=None)
def pdf(scene, rotation=0, user_unit=1, crop=None, options=()):
    """One page drawn in unrotated, unscaled points; ``options`` is a tuple of (name, value) pairs."""
    options = dict(options)
    width, height = options.pop("width", W), options.pop("height", H)
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    _scene(page, scene, crop, **options)
    return _finish(doc, page, rotation, user_unit, crop, width, height)


@functools.lru_cache(maxsize=None)
def raster_only_pdf(rotation, user_unit):
    """The false frame as a picture: a page with no native ink at all."""
    with fitz.open(stream=pdf("false_frame"), filetype="pdf") as source:
        picture = source[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.insert_image(page.rect, pixmap=picture)
    return _finish(doc, page, rotation, user_unit, None, W, H)


def hairline_site_frame_pdf(user_unit):
    """The fixture of #4650 (``_rotated_hairline_site_frame``) at /Rotate 90, optionally with a /UserUnit."""
    doc = fitz.open()
    page = doc.new_page(width=1100, height=780)
    page.draw_rect(fitz.Rect(100, 105, 800, 605), color=BLACK, width=1.5)
    for p, q in (((450, 105), (450, 605)), ((100, 350), (450, 350)), ((460, 200), (790, 200))):
        page.draw_line(p, q, color=BLACK, width=4)
    return _finish(doc, page, 90, user_unit, None, 1100, 780)


def run(raw, **kwargs):
    (result,) = trace_external_footprint_first(
        raw, source_sha256=hashlib.sha256(raw).hexdigest(), page_indices=(0,), **kwargs)
    return result


@functools.lru_cache(maxsize=None)
def traced(scene, rotation=0, user_unit=1, crop=None, flag=False, options=()):
    return run(pdf(scene, rotation, user_unit, crop, options), require_native_edge_support=flag)


def decision(scene, rotation=0, user_unit=1, crop=None, flag=True, **options):
    result = traced(scene, rotation, user_unit, crop, flag, tuple(sorted(options.items())))
    return result.status, result.reason


def _support():
    """The check module as it is registered NOW (another test may have removed it from ``sys.modules``)."""
    return importlib.import_module(SUPPORT_MODULE)


def _spy_assessment(monkeypatch):
    module = _support()
    original = module.assess_footprint_native_edge_support
    calls = []

    def spy(polygon, rows):
        calls.append((tuple(tuple(p) for p in polygon), len(rows)))
        return original(polygon, rows)

    monkeypatch.setattr(module, "assess_footprint_native_edge_support", spy)
    return calls


def _native_bounds(raw):
    with fitz.open(stream=raw, filetype="pdf") as doc:
        rects = [row["rect"] for row in doc[0].get_drawings()]
    return (min(r.x0 for r in rects), min(r.y0 for r in rects), max(r.x1 for r in rects), max(r.y1 for r in rects))


# --- the veto fires at every rotation, /UserUnit and CropBox --------------------------------------------------------

@pytest.mark.parametrize("crop", CROPS)
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_the_false_frame_is_vetoed_at_every_rotation_unit_and_crop(rotation, unit, crop):
    vetoed = traced("false_frame", rotation, unit, crop, True)
    assert (vetoed.status, vetoed.reason) == VETO
    assert vetoed.polygon_pdf_pts == () and vetoed.bbox_pdf_pts is None and vetoed.page_derotation_matrix is None
    assert vetoed.page_drawings_examined > 0
    assert vetoed.measurement_authorized is False and vetoed.commercial_publishable is False
    # The same drawing authored upright at /UserUnit 1 is decided the same way (rotation, scale and translation are
    # metamorphic here), and with the flag off the candidate is kept: the veto is the only difference.
    assert decision("false_frame", rotation, unit, crop) == decision("false_frame") == VETO
    assert traced("false_frame", rotation, unit, crop, False).status == CANDIDATE


@pytest.mark.parametrize("unit", (1, 2))
def test_the_reviewed_hairline_site_frame_at_rotate_90_is_vetoed_at_any_user_unit(unit):
    raw = hairline_site_frame_pdf(unit)
    assert run(raw).status == CANDIDATE
    flagged = run(raw, require_native_edge_support=True)
    assert (flagged.status, flagged.reason) == VETO


# --- look-alikes are left alone ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("crop", CROPS)
@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_an_outline_drawn_in_the_wall_pen_is_left_alone_at_every_rotation_unit_and_crop(rotation, unit, crop):
    kept, plain = traced("real_enclosure", rotation, unit, crop, True), traced("real_enclosure", rotation, unit, crop, False)
    assert kept == plain and kept.status == CANDIDATE
    assert kept.to_dict() == plain.to_dict()
    assert kept.measurement_authorized is False and kept.commercial_publishable is False
    if rotation == 0:  # an upright page is unframed and its output has no frame key
        assert kept.page_derotation_matrix is None and "page_derotation_matrix" not in kept.to_dict()


@pytest.mark.parametrize("scene", ("strip_enclosure", "lighter_frame"))
@pytest.mark.parametrize("rotation", TURNED)
def test_filled_strips_and_a_one_step_lighter_frame_are_left_alone_on_a_turned_scaled_cropped_page(scene, rotation):
    kept, plain = traced(scene, rotation, 2, CROP, True), traced(scene, rotation, 2, CROP, False)
    assert kept == plain and kept.status == CANDIDATE


@pytest.mark.parametrize("unit", (1, 2))
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_a_page_with_no_native_ink_is_never_vetoed(rotation, unit):
    raw = raster_only_pdf(rotation, unit)
    with fitz.open(stream=raw, filetype="pdf") as doc:
        assert doc[0].get_drawings() == []
    plain = run(raw)
    assert plain.status == CANDIDATE
    assert run(raw, require_native_edge_support=True) == plain


# --- the transform itself, independent of the verdict ---------------------------------------------------------------------

@pytest.mark.parametrize("crop", CROPS)
@pytest.mark.parametrize("unit", (1, 2))
@pytest.mark.parametrize("rotation", ROTATIONS)
def test_the_polygon_the_veto_assesses_lies_on_the_native_building(rotation, unit, crop, monkeypatch):
    calls = _spy_assessment(monkeypatch)
    raw = pdf("false_frame", rotation, unit, crop)
    run(raw, require_native_edge_support=True)
    assert len(calls) == 1
    polygon, rows = calls[0]
    assert rows > 0
    bx0, by0, bx1, by1 = _native_bounds(raw)
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    hug = 8.0 * unit  # the traced contour hugs the ink: half a pen plus the raster step, in scaled points
    assert max(abs(min(xs) - bx0), abs(min(ys) - by0), abs(max(xs) - bx1), abs(max(ys) - by1)) <= hug


# --- missing or unestablished evidence is never a veto ---------------------------------------------------------------------

@pytest.mark.parametrize("raw_unit", ("(abc)", "-2"))
@pytest.mark.parametrize("rotation", TURNED)
def test_an_unreadable_user_unit_gives_the_frame_reason_with_the_flag_on_and_off(rotation, raw_unit):
    raw = pdf("false_frame", rotation, raw_unit)
    on, off = run(raw, require_native_edge_support=True), run(raw)
    assert (on.status, on.reason) == FRAME_UNREADABLE and on == off  # never the veto reason


@pytest.mark.parametrize("rotation", TURNED)
def test_a_frame_that_cannot_carry_the_outline_is_no_veto_and_the_assessment_is_not_called(rotation, monkeypatch):
    monkeypatch.setattr(footprint, "_read_page_frame", lambda page: (True, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)))
    calls = _spy_assessment(monkeypatch)
    raw = pdf("false_frame", rotation, 2, CROP)
    on, off = run(raw, require_native_edge_support=True), run(raw)
    assert on == off and on.status == CANDIDATE and on.page_derotation_matrix == (0.0,) * 6
    assert calls == []


def test_a_reader_failure_is_missing_evidence_not_a_veto(monkeypatch):
    def broken(self, *args, **kwargs):
        raise RuntimeError("the drawing reader failed")

    monkeypatch.setattr(fitz.Page, "get_drawings", broken)
    raw = pdf("false_frame", 90, 2, CROP)
    assert run(raw, require_native_edge_support=True) == run(raw)


@pytest.mark.parametrize("scene,vertices,rows_are_read", (("t_outline", 8, True), ("plus_outline", 12, False)))
@pytest.mark.parametrize("rotation", (0, 90))
def test_native_rows_are_read_for_at_most_eight_vertices_and_a_complex_contour_is_never_vetoed(
        scene, vertices, rows_are_read, rotation, monkeypatch):
    calls = _spy_assessment(monkeypatch)
    raw = pdf(scene, rotation, 2, CROP)
    plain = run(raw)
    assert plain.status == CANDIDATE and len(plain.polygon_pdf_pts) == vertices
    flagged = run(raw, require_native_edge_support=True)
    assert len(calls) == 1 and (calls[0][1] > 0) is rows_are_read  # eight vertices are still assessed, twelve are not
    if not rows_are_read:
        assert flagged == plain


# --- invariances ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("scene,expected", (("false_frame", VETO), ("real_enclosure", (CANDIDATE, "external_footprint_ink_trace_needs_physical_wall_owner_and_scale"))))
@pytest.mark.parametrize("rotation", (90, 270))
def test_the_decision_does_not_depend_on_page_size_far_content_or_segmentation(scene, expected, rotation):
    assert decision(scene, rotation, 2, CROP) == expected
    assert decision(scene, rotation, 2, CROP, width=1200, height=960) == expected  # a larger page, same drawing
    assert decision(scene, rotation, 2, CROP, far=True) == expected  # unrelated content far from the building
    assert decision(scene, rotation, 2, CROP, split=True, reverse=True) == expected  # reversed, split into collinear pieces


@pytest.mark.parametrize("scene", ("false_frame", "real_enclosure"))
def test_replay_is_deterministic_and_the_trace_is_immutable(scene):
    first = run(pdf(scene, 90, 2, CROP), require_native_edge_support=True)
    again = run(pdf(scene, 90, 2, CROP), require_native_edge_support=True)
    assert first == again and first.to_dict() == again.to_dict()
    with pytest.raises(FrozenInstanceError):
        first.status = "X"  # type: ignore[misc]


# --- default-off and the live callers ---------------------------------------------------------------------------------------

def test_default_off_is_unchanged_and_does_not_even_import_the_check():
    raw = pdf("false_frame", 90, 2, CROP)
    sys.modules.pop(SUPPORT_MODULE, None)
    default = run(raw)
    assert SUPPORT_MODULE not in sys.modules
    assert default == run(raw, require_native_edge_support=False)
    ok, matrix = footprint._read_page_frame(fitz.open(stream=raw, filetype="pdf")[0])
    assert ok and default.status == CANDIDATE and default.page_derotation_matrix == matrix


def test_the_flag_is_keyword_only_default_off_and_no_production_module_passes_it():
    parameter = inspect.signature(trace_external_footprint_first).parameters["require_native_edge_support"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY and parameter.default is False
    offenders = []
    for path in sorted(Path(__file__).resolve().parents[1].glob("*.py")):
        if path.name == "pb_external_footprint_first_trace.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "require_native_edge_support" not in text:
            continue
        for node in ast.walk(ast.parse(text, filename=str(path))):
            if isinstance(node, ast.Call) and any(k.arg == "require_native_edge_support" for k in node.keywords):
                offenders.append(path.name)
    assert offenders == []  # live predictions cannot change: nothing enables the veto
