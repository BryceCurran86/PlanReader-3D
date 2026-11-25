"""Synthetic source-role, heavy-stroke, junction, false-bridge and title-band frame tests."""
from __future__ import annotations

import ast
import copy
import json
import math
import os
import random
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_source_native_wall_role_and_junction_shadow as role_module
from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_merged_collinear_dark_face_strips,
    _collect_source_heavy_stroke_strips,
    _owner_excluded_green_ink,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_native_page_frame import effective_pdf_rotation
from pb_source_native_wall_role_and_junction_shadow import (
    ROLE_ATTACHED_STRUCTURE,
    ROLE_DIAGONAL_BRIDGE,
    ROLE_EXCLUSION,
    ROLE_EXTERIOR_OUTER_FACE,
    ROLE_INTERNAL_WALL,
    ROLE_UNKNOWN,
    classify_native_path_role,
    identify_source_wall_junctions_and_roles,
)
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import SHA, WALL, strip

ROOT = Path(__file__).resolve().parent.parent


def _stroke(a, b, *, width=1.92, color=(0.0, 0.0, 0.0), opacity=1.0, dashes="", layer=""):
    return {
        "type": "s",
        "layer": layer,
        "fill": None,
        "color": color,
        "width": width,
        "stroke_opacity": opacity,
        "dashes": dashes,
        "rect": fitz.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])),
        "items": (("l", fitz.Point(*a), fitz.Point(*b)),),
    }


def test_heavy_black_strokes_are_wall_bands_not_double_line_dependent():
    walls = [
        _stroke((100, 100), (400, 100)),
        _stroke((400, 100), (400, 350)),
        _stroke((400, 350), (100, 350)),
        _stroke((100, 350), (100, 100)),
    ]
    assert len(_collect_source_heavy_stroke_strips(walls)) == 4
    result = build_layered_wall_doorway_room_rings(
        walls, source_sha256=SHA, page_index=0,
        source_heavy_stroke_wall_bands=True,
    )
    assert result.wall_strip_count >= 4
    assert all(not ring.commercial_projection_allowed for ring in result.rings)
    negatives = [
        _stroke((0, 0), (50, 0), width=0.48),
        _stroke((0, 10), (60, 10), color=(0.1, 0.9, 0.1)),
        _stroke((0, 20), (60, 20), opacity=0.5),
        _stroke((0, 30), (60, 30), width=1.92, color=(0.8, 0.1, 0.0)),
        _stroke((0, 40), (10, 40), width=1.92),
        _stroke((0, 50), (40, 90), width=1.92),
    ]
    assert _collect_source_heavy_stroke_strips(negatives) == []
    # Long medium-width black face is admitted; short medium is not.
    long_medium = [_stroke((0, 0), (100, 0), width=0.84)]
    assert len(_collect_source_heavy_stroke_strips(long_medium)) == 1


def test_drafting_pocket_rings_are_slivered_not_candidate_rooms():
    """Wall-cavity pockets that survive half-thickness inset must not be rooms."""
    # Outer room plus an inner ~3×3 cavity formed by four thick wall bars.
    rows = (
        strip(0, 0, 80, 4)
        + strip(0, 4, 4, 76)
        + strip(0, 76, 80, 80)
        + strip(76, 4, 80, 76)
        + strip(20, 20, 32, 23)
        + strip(20, 23, 23, 32)
        + strip(20, 32, 32, 35)
        + strip(29, 23, 32, 32)
    )
    result = build_layered_wall_doorway_room_rings(
        rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True,
    )
    assert result.drafting_pocket_sliver_count >= 1
    assert all(
        rec.area_pt2 >= 50.0
        for rec in result.rings
        if rec.status is EvidenceResolutionStatus.CANDIDATE
    )
    assert (
        result.ring_area_tier_lt_100_count
        + result.ring_area_tier_100_to_1000_count
        + result.ring_area_tier_ge_1000_count
    ) == len(result.rings)


def test_merged_collinear_dashed_dark_face_becomes_topology_strip():
    dashes = [
        _stroke((200, 100), (200, 130), width=0.48, dashes="[3 2] 0"),
        _stroke((200, 133.5), (200, 163.5), width=0.48, dashes="[3 2] 0"),
        _stroke((200, 167), (200, 197), width=0.48, dashes="[3 2] 0"),
        _stroke((200, 200.5), (200, 240), width=0.48, dashes="[3 2] 0"),
    ]
    strips = _collect_merged_collinear_dark_face_strips(dashes)
    assert len(strips) == 1
    assert strips[0].path_indices == (0, 1, 2, 3)
    assert strips[0].vertical
    # Short single tick and non-dark paint stay out.
    assert _collect_merged_collinear_dark_face_strips([
        _stroke((0, 0), (20, 0), width=0.48, dashes="[3 2] 0"),
        _stroke((0, 10), (80, 10), width=0.48, color=(0.1, 0.9, 0.1)),
    ]) == []
    room = (
        strip(0, 0, 120, 2)
        + strip(0, 2, 2, 98)
        + strip(0, 98, 120, 100)
        + strip(118, 2, 120, 98)
        + dashes
    )
    result = build_layered_wall_doorway_room_rings(
        room, source_sha256=SHA, page_index=0, dark_painted_wall_source=True,
    )
    assert result.merged_collinear_dark_face_strip_count >= 1
    assert result.free_space_part_count >= 1
    assert all(not ring.metric_area_issued for ring in result.rings)
    assert all(not ring.commercial_projection_allowed for ring in result.rings)


def test_default_off_heavy_stroke_flag_does_not_change_named_wall_rooms():
    rows = strip(0, 0, 100, 2) + strip(0, 2, 2, 98) + strip(0, 98, 100, 100) + strip(98, 2, 100, 98)
    off = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    on = build_layered_wall_doorway_room_rings(
        rows, source_sha256=SHA, page_index=0, source_heavy_stroke_wall_bands=True,
    )
    assert off.wall_strip_count == on.wall_strip_count
    assert off.unresolved_gap_count == on.unresolved_gap_count


def test_dashed_green_title_and_dimension_layers_are_exclusions():
    assert classify_native_path_role(
        _stroke((0, 0), (80, 0), dashes="[3 2] 0"), 0,
    ) == ROLE_EXCLUSION
    assert classify_native_path_role(
        _stroke((0, 10), (80, 10), color=(0.1, 0.9, 0.1)), 1,
    ) == ROLE_EXCLUSION
    assert classify_native_path_role(
        _stroke((0, 20), (80, 20), layer="A-ANNO-DIMS"), 2,
    ) == ROLE_EXCLUSION
    title = _stroke((10, 700), (200, 700), layer="Title_Block")
    title["rect"] = fitz.Rect(10, 700, 200, 710)
    assert classify_native_path_role(
        title, 3, page_bounds=(0.0, 0.0, 400.0, 800.0), page_rotation=0,
    ) == ROLE_EXCLUSION


def test_diagonal_furniture_and_dimension_leaders_are_rejected_bridges():
    assert classify_native_path_role(
        _stroke((210, 130), (800, 490), width=0.2), 0,
    ) == ROLE_DIAGONAL_BRIDGE
    assert classify_native_path_role(
        _stroke((300, 200), (420, 340), layer="Dimension"), 1,
    ) == ROLE_EXCLUSION


def test_explicit_wall_layer_is_internal_until_outer_face_is_owned():
    row = strip(0, 0, 100, 2)[0]
    assert classify_native_path_role(row, 0) == ROLE_INTERNAL_WALL
    assert classify_native_path_role(
        row, 0, exterior_owner_indices=frozenset({0}),
    ) == ROLE_EXTERIOR_OUTER_FACE
    assert classify_native_path_role(
        row, 0, attached_indices=frozenset({0}),
    ) == ROLE_ATTACHED_STRUCTURE


def test_three_unwitnessed_collinear_gaps_are_not_invented_doors():
    rows = (
        strip(0, 0, 400, 2)
        + strip(0, 2, 2, 298)
        + strip(0, 298, 400, 300)
        + strip(398, 2, 400, 20)
        + strip(398, 50, 400, 70)
        + strip(398, 120, 400, 140)
        + strip(398, 242, 400, 298)
    )
    report = identify_source_wall_junctions_and_roles(
        rows, source_sha256=SHA, page_index=0,
    )
    assert report.measurement_authorized is False
    assert report.commercial_publishable is False
    assert report.invented_door_bridge_count >= 3
    assert all(span["can_issue_area"] is False for span in report.unresolved_open_spans)
    assert all(span["missing_jamb_opening_evidence"] for span in report.unresolved_open_spans)
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert result.closures == ()


def test_wide_unwitnessed_span_is_still_not_a_door_with_roles():
    rows = (
        strip(0, 0, 400, 2)
        + strip(0, 2, 2, 298)
        + strip(0, 298, 400, 300)
        + strip(398, 2, 400, 20)
        + strip(398, 242, 400, 298)
    )
    report = identify_source_wall_junctions_and_roles(
        rows, source_sha256=SHA, page_index=0,
    )
    widths = [
        span["gap_interval_pdf_pts"][1] - span["gap_interval_pdf_pts"][0]
        for span in report.unresolved_open_spans
    ]
    assert any(width == pytest.approx(222.0) for width in widths)
    assert all(span["opening_authenticated"] is False for span in report.unresolved_open_spans)


def test_raster_hull_is_not_a_wall_and_report_stays_abstained():
    trace = ExternalFootprintTrace(
        source_sha256=SHA, page_index=0, status="CANDIDATE",
        reason="test", polygon_pdf_pts=((100, 100), (400, 100), (400, 350), (100, 350)),
        bbox_pdf_pts=(100, 100, 400, 350), candidate_count=1,
    )
    report = identify_source_wall_junctions_and_roles(
        [], source_sha256=SHA, page_index=0, trace=trace,
    )
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.filled_strip_count == 0
    assert report.heavy_stroke_band_count == 0
    assert report.measurement_authorized is False


def test_heavy_stroke_closed_rectangle_has_no_invented_bridge():
    walls = [
        _stroke((100, 100), (400, 100)),
        _stroke((400, 100), (400, 350)),
        _stroke((400, 350), (100, 350)),
        _stroke((100, 350), (100, 100)),
    ]
    report = identify_source_wall_junctions_and_roles(
        walls, source_sha256=SHA, page_index=0,
    )
    assert report.heavy_stroke_band_count == 4
    assert report.invented_door_bridge_count == 0
    assert report.rejected_diagonal_bridge_count == 0
    assert report.to_dict()["can_issue_area"] is False
    assert report.to_dict()["measurement_authorized"] is False


# =====================================================================================================
# Title band on rotated sheets.
#
# ``row["rect"]`` is NATIVE page space (``page.get_drawings()``); ``page_bounds`` is the DISPLAY rect
# (``page.rect``). The band is the lowest 18 percent of what is DISPLAYED. On a /Rotate 90 sheet a native point
# (x, y) is displayed at (native_height - y, x): the displayed lowest edge of a native rect is its native x1 (not
# its y1) and the displayed height is the native width.
# =====================================================================================================
BAND = 0.82  # frozen on purpose: changing the module constant must fail these tests
UPRIGHT_BOUNDS = (0.0, 0.0, 400.0, 800.0)
ROTATED_NATIVE_SIZE = (600.0, 800.0)  # native width x height of the sheet shown at /Rotate 90
ROTATED_BOUNDS = (0.0, 0.0, 800.0, 600.0)  # its DISPLAY rect, page.rect
SHEETS = ((600.0, 800.0), (800.0, 600.0), (595.0, 842.0), (842.0, 595.0))
_LAYERS = ("", "A-WALL", WALL, "Title_Block", "A-ANNO-DIMS", "Furniture", "Site_Roof", "Walls", "text", "Dimension")
_PAINTS = (None, (0.0, 0.0, 0.0), (0.8, 0.1, 0.0), (0.1, 0.9, 0.1))
_DASHES = ("", "[]0", "[3 2] 0")
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CANDIDATE = EvidenceResolutionStatus.CANDIDATE


def _legacy_classify(
    row, path_index, *, exterior_owner_indices=frozenset(), attached_indices=frozenset(), page_bounds=None,
):
    """Frozen copy of ``classify_native_path_role`` before ``page_rotation`` existed (main ad191709a).

    On an upright page the rows and the bounds share one space, so this is the oracle for rotation 0 and, applied to
    a row mapped into display space, for every rotation. Its helpers are the module's own; only the title test and
    the order of the checks are frozen here.
    """
    if not isinstance(row, Mapping):
        return ROLE_UNKNOWN
    fill, stroke = row.get("fill"), row.get("color")
    if _owner_excluded_green_ink(fill) or _owner_excluded_green_ink(stroke):
        return ROLE_EXCLUSION
    if role_module._dashed(row):
        return ROLE_EXCLUSION
    tokens = role_module._layer_tokens(row)
    if tokens & role_module._EXCLUSION_LAYER_TOKENS or any(token.startswith("dim") for token in tokens):
        return ROLE_EXCLUSION
    if page_bounds is not None:
        try:
            rect = row.get("rect")
            y1 = float(rect.y1) if rect is not None else None
        except (TypeError, ValueError, AttributeError):
            y1 = None
        if y1 is not None:
            _, y0_page, _, y1_page = page_bounds
            height = y1_page - y0_page
            if height > 0 and y1 >= y0_page + 0.82 * height:
                return ROLE_EXCLUSION
    if role_module._is_diagonal_row(row):
        return ROLE_DIAGONAL_BRIDGE
    if path_index in exterior_owner_indices:
        return ROLE_EXTERIOR_OUTER_FACE
    if path_index in attached_indices:
        return ROLE_ATTACHED_STRUCTURE
    if is_explicit_wall_layer_name(str(row.get("layer") or "")):
        return ROLE_INTERNAL_WALL
    return ROLE_UNKNOWN


def _row(rect, *, layer="", fill=None, color=None, dashes="", items=None):
    box = fitz.Rect(*rect)
    return {
        "layer": layer, "fill": fill, "color": color, "dashes": dashes, "rect": box,
        "items": (("re", fitz.Rect(box), 1),) if items is None else items,
    }


def _role(row, *, bounds, rotation, index=0, owners=(), attached=()):
    return classify_native_path_role(
        row, index,
        exterior_owner_indices=frozenset(owners), attached_indices=frozenset(attached),
        page_bounds=bounds, page_rotation=rotation,
    )


def _random_rect(rng, width, height):
    x0 = rng.randrange(0, int(width) * 2) / 2.0
    y0 = rng.randrange(0, int(height) * 2) / 2.0
    return x0, y0, x0 + rng.randrange(0, 80) / 2.0, y0 + rng.randrange(0, 80) / 2.0


def _random_row(rng, width, height, *, neutral=False):
    """A random row. ``neutral`` keeps every typed negative except the band out of the way."""
    x0, y0, x1, y1 = _random_rect(rng, width, height)
    kind = rng.randrange(4)
    if kind == 0:
        items = (("l", fitz.Point(x0, y0), fitz.Point(x1, y0)),)
    elif kind == 1:
        items = (("l", fitz.Point(x0, y0), fitz.Point(x0 + 30.0, y0 + 30.0)),)
    elif kind == 2:
        items = (("re", fitz.Rect(x0, y0, x1, y1), 1),)
    else:
        items = ()
    if neutral:
        return _row((x0, y0, x1, y1), layer=rng.choice(("", WALL)), items=items)
    return _row(
        (x0, y0, x1, y1), layer=rng.choice(_LAYERS), fill=rng.choice(_PAINTS), color=rng.choice(_PAINTS),
        dashes=rng.choice(_DASHES), items=items,
    )


def _normalised(box):
    return fitz.Rect(min(box.x0, box.x1), min(box.y0, box.y1), max(box.x0, box.x1), max(box.y0, box.y1))


def _mapped(row, matrix):
    """The row with its rect and its line / rect items carried through ``matrix``."""
    out = dict(row)
    out["rect"] = _normalised(fitz.Rect(row["rect"]) * matrix)
    items = []
    for item in row.get("items") or ():
        if item and item[0] == "l":
            items.append(("l", fitz.Point(item[1]) * matrix, fitz.Point(item[2]) * matrix))
        elif item and item[0] == "re":
            items.append(("re", _normalised(fitz.Rect(item[1]) * matrix), *item[2:]))
        else:
            items.append(item)
    out["items"] = tuple(items)
    return out


@pytest.fixture
def make_page():
    documents = []

    def make(width, height, rotation=0):
        document = fitz.open()
        documents.append(document)
        page = document.new_page(width=width, height=height)
        if rotation:
            page.set_rotation(rotation)
        return page

    yield make
    for document in documents:
        document.close()


def _sheet_id(size):
    return f"{int(size[0])}x{int(size[1])}"


def test_upright_title_band_is_the_lowest_eighteen_percent_of_the_page():
    edge = BAND * 800.0
    kwargs = {"bounds": UPRIGHT_BOUNDS, "rotation": 0}
    assert _role(_row((10, 700, 200, 710)), **kwargs) == ROLE_EXCLUSION
    assert _role(_row((10, 100, 200, 110)), **kwargs) == ROLE_UNKNOWN
    assert _role(_row((10, 0, 200, edge)), **kwargs) == ROLE_EXCLUSION  # on the edge counts (>=)
    assert _role(_row((10, 0, 200, math.nextafter(edge, 0.0))), **kwargs) == ROLE_UNKNOWN
    assert _role(_row((10, 700, 200, 702), layer=WALL), **kwargs) == ROLE_EXCLUSION
    assert _role(_row((10, 100, 200, 102), layer=WALL), **kwargs) == ROLE_INTERNAL_WALL
    # lowest edge only: a row that starts above the band and ends inside it is excluded whole (unchanged semantics)
    assert _role(_row((10, 100, 200, 700)), **kwargs) == ROLE_EXCLUSION


def test_rotated_title_band_is_the_lowest_eighteen_percent_of_the_displayed_page():
    edge = BAND * 600.0  # displayed y is native x
    kwargs = {"bounds": ROTATED_BOUNDS, "rotation": 90}
    assert _role(_row((500, 100, 510, 110)), **kwargs) == ROLE_EXCLUSION
    assert _role(_row((100, 700, 110, 710)), **kwargs) == ROLE_UNKNOWN
    assert _role(_row((edge - 10.0, 100, edge, 110)), **kwargs) == ROLE_EXCLUSION
    assert _role(_row((edge - 10.0, 100, math.nextafter(edge, 0.0), 110)), **kwargs) == ROLE_UNKNOWN
    assert _role(_row((500, 100, 502, 700), layer=WALL), **kwargs) == ROLE_EXCLUSION
    assert _role(_row((100, 100, 102, 700), layer=WALL), **kwargs) == ROLE_INTERNAL_WALL
    assert _role(_row((100, 100, 500, 110)), **kwargs) == ROLE_EXCLUSION  # lowest displayed edge only


def test_a_native_bottom_row_is_not_in_the_title_band_of_a_rotated_sheet():
    """Native y near the native bottom is the DISPLAYED LEFT of a /Rotate 90 sheet: positive roles survive."""
    low = (50, 700, 60, 710)  # displayed x 90..100, y 50..60: the upper left of the page
    kwargs = {"bounds": ROTATED_BOUNDS, "rotation": 90}
    assert _role(_row(low, layer=WALL), **kwargs) == ROLE_INTERNAL_WALL
    assert _role(_row(low), owners=(0,), **kwargs) == ROLE_EXTERIOR_OUTER_FACE
    assert _role(_row(low), attached=(0,), **kwargs) == ROLE_ATTACHED_STRUCTURE
    # the frozen rule (native y1 against the display height) calls all three title block: the defect
    assert _legacy_classify(_row(low, layer=WALL), 0, page_bounds=ROTATED_BOUNDS) == ROLE_EXCLUSION
    assert _legacy_classify(
        _row(low), 0, exterior_owner_indices=frozenset({0}), page_bounds=ROTATED_BOUNDS,
    ) == ROLE_EXCLUSION


def test_a_displayed_bottom_row_is_title_block_whatever_a_wall_layer_or_an_exterior_owner_claims():
    band = (500, 100, 502, 400)  # displayed y 500..502 of 600: inside the band; native y1 400 is far from it
    kwargs = {"bounds": ROTATED_BOUNDS, "rotation": 90}
    assert _role(_row(band, layer=WALL), **kwargs) == ROLE_EXCLUSION
    assert _role(_row(band), owners=(0,), **kwargs) == ROLE_EXCLUSION
    assert _role(_row(band), attached=(0,), **kwargs) == ROLE_EXCLUSION
    assert _legacy_classify(_row(band, layer=WALL), 0, page_bounds=ROTATED_BOUNDS) == ROLE_INTERNAL_WALL  # missed


UNESTABLISHED = (None, 180, 270, 45, 450, -90, 91, True, False, "90", "0", 90.0, 0.0, float("nan"))


@pytest.mark.parametrize("rotation", UNESTABLISHED, ids=repr)
def test_an_unestablished_frame_demotes_wall_roles_and_keeps_band_independent_negatives(rotation):
    kwargs = {"bounds": ROTATED_BOUNDS, "rotation": rotation}
    inside, outside = (500, 100, 502, 400), (100, 100, 102, 400)
    for rect in (inside, outside):  # wherever the row sits, its band membership cannot be established
        assert _role(_row(rect, layer=WALL), **kwargs) == ROLE_UNKNOWN
        assert _role(_row(rect), owners=(0,), **kwargs) == ROLE_UNKNOWN
        assert _role(_row(rect), attached=(0,), **kwargs) == ROLE_UNKNOWN
        assert _role(_row(rect), **kwargs) == ROLE_UNKNOWN  # and a neutral row is not claimed as title block either
    assert _role(_row(outside, dashes="[3 2] 0"), **kwargs) == ROLE_EXCLUSION
    assert _role(_row(outside, color=(0.1, 0.9, 0.1)), **kwargs) == ROLE_EXCLUSION
    assert _role(_row(outside, layer="A-ANNO-DIMS"), **kwargs) == ROLE_EXCLUSION
    diagonal = _row(outside, items=(("l", fitz.Point(100, 100), fitz.Point(400, 400)),))
    assert _role(diagonal, **kwargs) == ROLE_DIAGONAL_BRIDGE
    # nothing to place: no bounds or no rect means no test, as before
    assert classify_native_path_role(_row(inside, layer=WALL), 0, page_rotation=rotation) == ROLE_INTERNAL_WALL
    unplaced = _row(inside, layer=WALL)
    del unplaced["rect"]
    assert _role(unplaced, **kwargs) == ROLE_INTERNAL_WALL
    assert _role("not a mapping", **kwargs) == ROLE_UNKNOWN


@pytest.mark.parametrize(
    "bounds",
    (
        (10.0, 0.0, 810.0, 600.0),  # does not start at the page origin
        (0.0, 5.0, 800.0, 605.0),
        (0.0, 0.0, 800.0, 0.0),  # zero height
        (0.0, 600.0, 800.0, 0.0),  # negative height
        (0.0, 0.0, 800.0, float("inf")),
        (0.0, 0.0, 800.0, float("nan")),
        (float("nan"), 0.0, 800.0, 600.0),
        (0.0, 0.0, float("nan"), 600.0),
        (2e-6, 0.0, 800.0, 600.0),  # just beyond the frame seam's 1e-6 pt tolerance
        (0.0, -2e-6, 800.0, 600.0),
    ),
    ids=repr,
)
def test_a_rotated_band_needs_finite_origin_anchored_bounds(bounds):
    row = _row((100, 100, 102, 400), layer=WALL)
    assert _role(row, bounds=bounds, rotation=90) == ROLE_UNKNOWN
    assert _role(_row((100, 100, 102, 400)), owners=(0,), bounds=bounds, rotation=90) == ROLE_UNKNOWN


def test_a_rotated_band_tolerates_sub_micro_point_origin_noise():
    """The frame seam's own tolerance (1e-6 pt): float noise at the page origin must not abstain."""
    noisy = (5e-7, -5e-7, 800.0, 600.0)
    assert _role(_row((100, 100, 102, 400), layer=WALL), bounds=noisy, rotation=90) == ROLE_INTERNAL_WALL
    assert _role(_row((500, 100, 502, 400), layer=WALL), bounds=noisy, rotation=90) == ROLE_EXCLUSION


def test_rotation_zero_keeps_the_legacy_handling_of_degenerate_bounds():
    """Recorded, not changed here: upright, a zero or negative height skips the test (the module's own behaviour)."""
    wall = _row((10, 700, 200, 702), layer=WALL)
    for bounds in ((0.0, 0.0, 400.0, 0.0), (0.0, 800.0, 400.0, 0.0)):
        assert _role(wall, bounds=bounds, rotation=0) == _legacy_classify(wall, 0, page_bounds=bounds) == ROLE_INTERNAL_WALL


def test_rotation_zero_is_identical_to_the_frozen_rule_on_arbitrary_rows():
    rng = random.Random(20261123)
    bounds_options = (
        UPRIGHT_BOUNDS, (10.0, 20.0, 410.0, 820.0), (0.0, 0.0, 400.0, 0.0), (0.0, 800.0, 400.0, 0.0), None,
    )
    odd_rects = (
        None, object(), SimpleNamespace(x1=1.0, y1="oops"), SimpleNamespace(y1=float("nan")),
        SimpleNamespace(y1=float("inf")), SimpleNamespace(y1=-5.0),
    )
    for index in range(4000):
        row = _random_row(rng, 400.0, 800.0)
        if index % 7 == 0:
            row["rect"] = rng.choice(odd_rects)
        owners = frozenset({index}) if rng.random() < 0.3 else frozenset()
        attached = frozenset({index}) if rng.random() < 0.3 else frozenset()
        bounds = rng.choice(bounds_options)
        expected = _legacy_classify(
            row, index, exterior_owner_indices=owners, attached_indices=attached, page_bounds=bounds,
        )
        got = classify_native_path_role(
            row, index, exterior_owner_indices=owners, attached_indices=attached,
            page_bounds=bounds, page_rotation=0,
        )
        assert got == expected, (index, bounds)
        if bounds is None:  # nothing to place: the rotation is irrelevant
            for rotation in UNESTABLISHED + (0, 90):
                assert classify_native_path_role(
                    row, index, exterior_owner_indices=owners, attached_indices=attached,
                    page_bounds=None, page_rotation=rotation,
                ) == expected


@pytest.mark.parametrize("native_size", SHEETS, ids=_sheet_id)
@pytest.mark.parametrize("rotation", (0, 90))
def test_a_page_classifies_like_the_same_drawing_on_an_upright_page(make_page, native_size, rotation):
    """PyMuPDF's own rotation matrix is the oracle for where a native row is displayed."""
    page = make_page(*native_size, rotation)
    assert effective_pdf_rotation(page) == rotation
    bounds = tuple(page.rect)
    rng = random.Random(4652 + rotation + int(native_size[0]))
    differing, roles = 0, set()
    for index in range(600):
        row = _random_row(rng, *native_size, neutral=True)
        owners = frozenset({index}) if rng.random() < 0.3 else frozenset()
        expected = _legacy_classify(
            _mapped(row, page.rotation_matrix), index, exterior_owner_indices=owners, page_bounds=bounds,
        )
        got = classify_native_path_role(
            row, index, exterior_owner_indices=owners, page_bounds=bounds, page_rotation=rotation,
        )
        assert got == expected, (rotation, native_size, index)
        roles.add(got)
        differing += _legacy_classify(row, index, exterior_owner_indices=owners, page_bounds=bounds) != got
    assert ROLE_EXCLUSION in roles and len(roles) > 1  # the sample really spans both sides of the band
    if rotation == 90:
        assert differing > 50  # the frozen rule applied to native rows is wrong on many of them
    else:
        assert differing == 0


@pytest.mark.parametrize("rotation", (180, 270))
def test_unsupported_page_rotations_abstain_instead_of_guessing(make_page, rotation):
    page = make_page(600.0, 800.0, rotation)
    assert effective_pdf_rotation(page) == rotation
    rng = random.Random(rotation)
    for index in range(200):
        row = _random_row(rng, 600.0, 800.0, neutral=True)
        got = classify_native_path_role(
            row, index, exterior_owner_indices=frozenset({index}), page_bounds=tuple(page.rect),
            page_rotation=effective_pdf_rotation(page),
        )
        assert got in (ROLE_UNKNOWN, ROLE_DIAGONAL_BRIDGE)


@pytest.mark.parametrize("native_size", ((600.0, 800.0), (800.0, 600.0)), ids=_sheet_id)
def test_one_displayed_drawing_has_the_same_roles_authored_upright_or_on_a_rotated_sheet(make_page, native_size):
    rotated = make_page(*native_size, 90)
    upright = make_page(native_size[1], native_size[0], 0)  # the upright sheet with the rotated sheet's displayed size
    assert tuple(rotated.rect) == tuple(upright.rect)
    rng = random.Random(90)
    seen = set()
    for index in range(500):
        shown = _random_row(rng, upright.rect.width, upright.rect.height, neutral=True)
        native = _mapped(shown, rotated.derotation_matrix)
        assert tuple(_normalised(fitz.Rect(native["rect"]) * rotated.rotation_matrix)) == pytest.approx(
            tuple(shown["rect"]), abs=1e-9,
        )  # the two matrices really are inverses
        owners = frozenset({index}) if index % 3 == 0 else frozenset()
        from_upright = classify_native_path_role(
            shown, index, exterior_owner_indices=owners, page_bounds=tuple(upright.rect),
            page_rotation=effective_pdf_rotation(upright),
        )
        from_rotated = classify_native_path_role(
            native, index, exterior_owner_indices=owners, page_bounds=tuple(rotated.rect),
            page_rotation=effective_pdf_rotation(rotated),
        )
        assert from_upright == from_rotated, index
        seen.add(from_upright)
    assert {ROLE_EXCLUSION, ROLE_EXTERIOR_OUTER_FACE} <= seen


def _frame(rotation):
    if rotation == 0:
        return UPRIGHT_BOUNDS, (400.0, 800.0)
    return ROTATED_BOUNDS, ROTATED_NATIVE_SIZE


def _displayed_edge(row, rotation):
    return row["rect"].y1 if rotation == 0 else row["rect"].x1


def _rows_clear_of_the_band(rng, rotation, count, margin):
    bounds, size = _frame(rotation)
    edge = BAND * (bounds[3] - bounds[1])
    rows = []
    while len(rows) < count:
        row = _random_row(rng, *size, neutral=True)
        if abs(_displayed_edge(row, rotation) - edge) >= margin:
            rows.append(row)
    return rows


@pytest.mark.parametrize("rotation", (0, 90))
@pytest.mark.parametrize("scale", (0.25, 2.0, 3.7))
def test_the_band_is_invariant_under_uniform_scale(rotation, scale):
    bounds, _ = _frame(rotation)
    scaled_bounds = tuple(value * scale for value in bounds)
    for index, row in enumerate(_rows_clear_of_the_band(random.Random(7), rotation, 300, margin=1.0)):
        owners = frozenset({index})
        before = classify_native_path_role(
            row, index, exterior_owner_indices=owners, page_bounds=bounds, page_rotation=rotation,
        )
        after = classify_native_path_role(
            _mapped(row, fitz.Matrix(scale, scale)), index, exterior_owner_indices=owners,
            page_bounds=scaled_bounds, page_rotation=rotation,
        )
        assert before == after


@pytest.mark.parametrize("rotation", (0, 90))
def test_the_band_ignores_translation_along_the_displayed_horizontal_axis(rotation):
    bounds, _ = _frame(rotation)
    for index, row in enumerate(_rows_clear_of_the_band(random.Random(11), rotation, 200, margin=1.0)):
        owners = frozenset({index})
        base = classify_native_path_role(
            row, index, exterior_owner_indices=owners, page_bounds=bounds, page_rotation=rotation,
        )
        for shift in (-137.5, 12.25, 900.0):
            # the displayed horizontal axis is native x upright and native y at /Rotate 90
            matrix = fitz.Matrix(1, 0, 0, 1, shift, 0) if rotation == 0 else fitz.Matrix(1, 0, 0, 1, 0, shift)
            moved = classify_native_path_role(
                _mapped(row, matrix), index, exterior_owner_indices=owners, page_bounds=bounds, page_rotation=rotation,
            )
            assert moved == base


@pytest.mark.parametrize("rotation", (0, 90))
def test_the_band_follows_translation_along_the_displayed_vertical_axis_only_across_the_edge(rotation):
    bounds, _ = _frame(rotation)
    edge = BAND * (bounds[3] - bounds[1])
    rng = random.Random(13)
    for index, row in enumerate(_rows_clear_of_the_band(rng, rotation, 200, margin=20.0)):
        base = classify_native_path_role(row, index, page_bounds=bounds, page_rotation=rotation)
        # the displayed vertical axis is native y upright and native x at /Rotate 90
        matrix = fitz.Matrix(1, 0, 0, 1, 0, 15) if rotation == 0 else fitz.Matrix(1, 0, 0, 1, 15, 0)
        assert classify_native_path_role(
            _mapped(row, matrix), index, page_bounds=bounds, page_rotation=rotation,
        ) == base  # stays on its side of the band
    # negative control: a row 10 pt above the band moved 20 pt down the displayed page crosses it
    probe = _row((edge - 40.0, 100, edge - 10.0, 110)) if rotation == 90 else _row((10, edge - 40.0, 200, edge - 10.0))
    crossing = fitz.Matrix(1, 0, 0, 1, 20, 0) if rotation == 90 else fitz.Matrix(1, 0, 0, 1, 0, 20)
    assert classify_native_path_role(probe, 0, page_bounds=bounds, page_rotation=rotation) == ROLE_UNKNOWN
    assert classify_native_path_role(
        _mapped(probe, crossing), 0, page_bounds=bounds, page_rotation=rotation,
    ) == ROLE_EXCLUSION


def _wall_row(x0, y0, x1, y1):
    row = strip(x0, y0, x1, y1)[0]
    row["rect"] = fitz.Rect(x0, y0, x1, y1)
    return row


ROOM_RECTS = ((100, 300, 400, 302), (100, 698, 400, 700), (100, 302, 102, 698), (398, 302, 400, 698))
TITLE_RECTS = ((540, 100, 542, 700), (520, 100, 590, 102))


def _rotated_room_rows():
    """A room (displayed upper left) and a title-block column (displayed bottom) on a 600 x 800 sheet at /Rotate 90."""
    return [_wall_row(*rect) for rect in ROOM_RECTS + TITLE_RECTS]


def _identify(rows, rotation, bounds=ROTATED_BOUNDS):
    return identify_source_wall_junctions_and_roles(
        rows, source_sha256=SHA, page_index=0, page_bounds=bounds, page_rotation=rotation,
    )


def _by_rect(report, rows):
    return {tuple(rows[record.path_index]["rect"]): record.role for record in report.path_roles}


def test_identify_places_the_title_band_in_the_displayed_frame_of_a_rotated_sheet():
    rows = _rotated_room_rows()
    report = _identify(rows, 90)
    roles = _by_rect(report, rows)
    assert [roles[rect] for rect in ROOM_RECTS] == [ROLE_INTERNAL_WALL] * 4
    assert [roles[rect] for rect in TITLE_RECTS] == [ROLE_EXCLUSION] * 2
    for record in report.path_roles:
        assert record.status is (CANDIDATE if record.role == ROLE_INTERNAL_WALL else ABSTAINED)
        assert record.topology_only and not record.physical_wall_authenticated and not record.can_issue_area
    legacy = {tuple(row["rect"]): _legacy_classify(row, i, page_bounds=ROTATED_BOUNDS) for i, row in enumerate(rows)}
    assert [legacy[rect] for rect in ROOM_RECTS] == [ROLE_INTERNAL_WALL] + [ROLE_EXCLUSION] * 3  # the defect
    assert legacy[TITLE_RECTS[1]] == ROLE_INTERNAL_WALL  # and a title row missed


@pytest.mark.parametrize("rotation", (None, 180, 270, True))
def test_identify_without_an_established_frame_abstains_on_every_wall_role(rotation):
    rows = _rotated_room_rows()
    report = _identify(rows, rotation)
    assert {record.role for record in report.path_roles} == {ROLE_UNKNOWN}
    assert all(record.status is ABSTAINED for record in report.path_roles)
    assert report.status is ABSTAINED


@pytest.mark.parametrize("rotation", (None, 0, 90, 180))
def test_the_report_stays_a_shadow_that_issues_nothing(rotation):
    report = _identify(_rotated_room_rows(), rotation)
    payload = report.to_dict()
    assert report.status is ABSTAINED
    assert report.measurement_authorized is False and report.commercial_publishable is False
    assert payload["measurement_authorized"] is False
    assert payload["commercial_publishable"] is False
    assert payload["can_issue_area"] is False
    assert all(
        record.topology_only and not record.physical_wall_authenticated and not record.can_issue_area
        for record in report.path_roles
    )


def test_identify_at_rotation_zero_equals_the_frozen_rule(monkeypatch):
    rows = [_wall_row(*rect) for rect in (
        (100, 100, 300, 102), (100, 400, 300, 402), (100, 102, 102, 400), (298, 102, 300, 400),
        (10, 700, 390, 703), (10, 0, 390, 2),
    )]
    for bounds in (UPRIGHT_BOUNDS, None):
        new = identify_source_wall_junctions_and_roles(
            rows, source_sha256=SHA, page_index=0, page_bounds=bounds, page_rotation=0,
        )
        with monkeypatch.context() as patched:
            patched.setattr(
                role_module, "classify_native_path_role",
                lambda row, index, **kw: _legacy_classify(
                    row, index, **{key: value for key, value in kw.items() if key != "page_rotation"},
                ),
            )
            old = identify_source_wall_junctions_and_roles(
                rows, source_sha256=SHA, page_index=0, page_bounds=bounds,
            )
        assert new.to_dict() == old.to_dict()
        assert [(r.path_index, r.role, r.status) for r in new.path_roles] == [
            (r.path_index, r.role, r.status) for r in old.path_roles
        ]
    assert any(record.role == ROLE_EXCLUSION for record in new.path_roles) is False  # bounds=None: no band at all


def test_roles_do_not_depend_on_row_order_or_on_unrelated_far_content():
    rows = _rotated_room_rows()
    base = _by_rect(_identify(rows, 90), rows)
    shuffled = list(rows)
    random.Random(3).shuffle(shuffled)
    assert _by_rect(_identify(shuffled, 90), shuffled) == base
    far = [_wall_row(5000, 5000, 5002, 5300), _wall_row(-5000, -5300, -4998, -5000), _wall_row(100, 9000, 102, 9100)]
    with_far = rows + far
    got = _by_rect(_identify(with_far, 90), with_far)
    assert {rect: role for rect, role in got.items() if rect in base} == base
    # the page frame is an input, never derived from the content: content beyond it does not move the band
    assert got[(5000, 5000, 5002, 5300)] == ROLE_EXCLUSION
    assert got[(-5000, -5300, -4998, -5000)] == ROLE_INTERNAL_WALL


def test_classification_does_not_mutate_its_inputs():
    rows = _rotated_room_rows()
    before = copy.deepcopy(rows)
    bounds = tuple(ROTATED_BOUNDS)
    for rotation in (None, 0, 90, 180):
        _identify(rows, rotation, bounds=bounds)
        for index, row in enumerate(rows):
            classify_native_path_role(
                row, index, exterior_owner_indices=frozenset({index}), page_bounds=bounds, page_rotation=rotation,
            )
    assert rows == before
    assert bounds == ROTATED_BOUNDS


_REPLAY_PROBE = """
import json
from tests.test_source_native_wall_role_and_junction_shadow import _identify, _rotated_room_rows
report = _identify(_rotated_room_rows(), 90)
print(json.dumps({
    "report": report.to_dict(),
    "roles": [[r.path_index, r.role, r.status.value] for r in report.path_roles],
}, sort_keys=True, default=str))
"""


def _replay_under_hash_seed(seed):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    done = subprocess.run(
        [sys.executable, "-c", _REPLAY_PROBE], cwd=ROOT, env=env, capture_output=True, text=True,
        timeout=180, check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_replay_is_deterministic_across_runs_and_hash_seeds():
    rows = _rotated_room_rows()
    first, second = _identify(rows, 90), _identify(rows, 90)
    assert first.to_dict() == second.to_dict()
    assert [(r.path_index, r.role) for r in first.path_roles] == [(r.path_index, r.role) for r in second.path_roles]
    assert _replay_under_hash_seed(0) == _replay_under_hash_seed(12345)


def test_only_the_diagnostic_tool_imports_the_role_module():
    """Shadow containment: no production module may consume these roles (they are diagnostic, not authority)."""
    name = "pb_source_native_wall_role_and_junction_shadow"
    importers = []
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if relative.parts[0] in {"tests", "benchmarks", "node_modules"} or any(p.startswith(".") for p in relative.parts):
            continue
        if path.name == f"{name}.py":
            continue
        text = path.read_text(encoding="utf-8-sig")
        if name not in text:
            continue
        for node in ast.walk(ast.parse(text, filename=str(path))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names = [node.value]
            if any(item == name or item.startswith(f"{name}.") for item in names):
                importers.append(relative.as_posix())
                break
    assert importers == ["tools/run_native_exterior_path_ownership.py"]


def test_the_tool_reads_the_rotation_from_the_production_page_frame(make_page):
    from tools.run_native_exterior_path_ownership import _page_rotation_for_roles

    assert _page_rotation_for_roles(make_page(600.0, 800.0, 0)) == 0
    assert _page_rotation_for_roles(make_page(600.0, 800.0, 90)) == 90
    assert _page_rotation_for_roles(make_page(600.0, 800.0, 180)) == 180  # reported as it is: the classifier abstains
    odd = make_page(600.0, 800.0, 0)
    odd.parent.xref_set_key(odd.xref, "Rotate", "45")
    assert _page_rotation_for_roles(odd) is None  # unresolved frame: fail closed, never guess
    assert _page_rotation_for_roles(SimpleNamespace()) is None


def _write_marks_pdf(path, rotation):
    """Three black marks drawn in NATIVE space on a 600 x 800 sheet, then the sheet is rotated."""
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    for rect in ((500, 100, 510, 400), (520, 100, 530, 400), (50, 700, 400, 710)):
        page.draw_rect(fitz.Rect(*rect), color=None, fill=(0, 0, 0))
    if rotation:
        page.set_rotation(rotation)
    document.save(path)
    document.close()


def _run_tool(tmp_path, monkeypatch, rotation):
    from tools import run_native_exterior_path_ownership as tool

    pdf = tmp_path / f"marks_{rotation}.pdf"
    _write_marks_pdf(pdf, rotation)
    out_dir = tmp_path / f"out_{rotation}"
    monkeypatch.setattr(sys, "argv", ["tool", "--pdf", str(pdf), "--page", "0", "--out-dir", str(out_dir)])
    assert tool.main() == 0
    return json.loads((out_dir / "page_1_native_exterior_owners.json").read_text(encoding="utf-8"))


def test_the_tool_labels_the_displayed_title_band_of_a_rotated_sheet(tmp_path, monkeypatch):
    payload = _run_tool(tmp_path, monkeypatch, 90)
    assert payload["title_band_page_rotation"] == 90
    # two marks sit in the displayed bottom band (native x >= 492); the third is the native bottom, displayed top left
    assert payload["wall_roles_and_junctions"]["role_counts"] == {ROLE_EXCLUSION: 2, ROLE_UNKNOWN: 1}
    assert payload["commercial_quantity_rows"] == 0


def test_the_tool_abstains_instead_of_guessing_the_band_on_an_unsupported_rotation(tmp_path, monkeypatch):
    payload = _run_tool(tmp_path, monkeypatch, 180)
    assert payload["title_band_page_rotation"] == 180
    assert payload["wall_roles_and_junctions"]["role_counts"] == {ROLE_UNKNOWN: 3}
    assert payload["commercial_quantity_rows"] == 0
