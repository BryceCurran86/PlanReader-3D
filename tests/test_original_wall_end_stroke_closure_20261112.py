"""Original-app wall-end closers: source strokes that already meet two walls.

Ported from Next topology as default-off original producer evidence.
This is not a wall quantity, finished face, ceiling m2 or FIRM row.
The 80 PDF-point support span is a candidate heuristic, not scale-independent
physical wall identity. Green exclusion and wall-above-door stay on #4298.
"""
from __future__ import annotations

import math

import pytest

from pb_layered_wall_doorway_room_ring_shadow import (
    _WALL_END_SUPPORT_SPAN,
    _collect_dark_painted_source_wall_strips,
    _collect_wall_end_closing_strips,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32


def _line(x0, y0, x1, y1, color=None):
    import fitz
    return {
        "layer": "",
        "fill": None,
        "color": color,
        "rect": fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
        "items": [("l", fitz.Point(x0, y0), fitz.Point(x1, y1))],
    }


def _fill_rect(x0, y0, x1, y1, fill):
    import fitz
    return {
        "layer": "",
        "fill": fill,
        "color": None,
        "fill_opacity": 1.0,
        "rect": fitz.Rect(x0, y0, x1, y1),
        "items": [("re", fitz.Rect(x0, y0, x1, y1), 1)],
    }


def _u_room_open_south():
    dark = (0.195, 0.195, 0.195)
    return [
        _fill_rect(0, 20, 5, 120, dark),
        _fill_rect(200, 20, 205, 120, dark),
        _fill_rect(0, 115, 205, 120, dark),
    ]


def _scale_drawings(rows, factor: float):
    import fitz
    scaled = []
    for row in rows:
        items = []
        for item in row["items"]:
            if item[0] == "re":
                r = item[1]
                items.append(("re", fitz.Rect(r.x0 * factor, r.y0 * factor, r.x1 * factor, r.y1 * factor), *item[2:]))
            elif item[0] == "l":
                a, b = item[1], item[2]
                items.append(("l", fitz.Point(a.x * factor, a.y * factor), fitz.Point(b.x * factor, b.y * factor)))
            else:
                items.append(item)
        rect = row["rect"]
        scaled.append({
            **row,
            "rect": fitz.Rect(rect.x0 * factor, rect.y0 * factor, rect.x1 * factor, rect.y1 * factor),
            "items": items,
        })
    return scaled


def _rotate_xy_drawings(rows):
    import fitz
    rotated = []
    for row in rows:
        items = []
        for item in row["items"]:
            if item[0] == "re":
                r = item[1]
                items.append(("re", fitz.Rect(r.y0, r.x0, r.y1, r.x1), *item[2:]))
            elif item[0] == "l":
                a, b = item[1], item[2]
                items.append(("l", fitz.Point(a.y, a.x), fitz.Point(b.y, b.x)))
            else:
                items.append(item)
        rect = row["rect"]
        rotated.append({
            **row,
            "rect": fitz.Rect(rect.y0, rect.x0, rect.y1, rect.x1),
            "items": items,
        })
    return rotated


def _lookalike_grid(module: float):
    dark = (0.195, 0.195, 0.195)
    thick = 4.0
    rows = []
    for i in range(4):
        for j in range(3):
            x = i * module
            y0 = j * module
            rows.append(_fill_rect(x, y0, x + thick, y0 + module, dark))
            y = i * module
            x0 = j * module
            rows.append(_fill_rect(x0, y, x0 + module, y + thick, dark))
    for i in range(4):
        for j in range(3):
            x = i * module + thick / 2.0
            y0 = j * module
            y1 = (j + 1) * module
            rows.append(_line(x, y0, x, y1, color=(0.0, 0.0, 0.0)))
            y = i * module + thick / 2.0
            x0 = j * module
            x1 = (j + 1) * module
            rows.append(_line(x0, y, x1, y, color=(0.0, 0.0, 0.0)))
    return rows


def test_wall_end_closers_stay_off_without_dark_painted_opt_in():
    drawings = _u_room_open_south() + [_line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))]
    result = build_layered_wall_doorway_room_rings(drawings, source_sha256=SHA, page_index=0)
    assert result.rings == ()
    with pytest.raises(ValueError, match="requires dark_painted_wall_source"):
        build_layered_wall_doorway_room_rings(
            drawings, source_sha256=SHA, page_index=0, wall_end_stroke_closures=True,
        )


def test_wall_end_stroke_closes_only_when_both_native_ends_meet_major_walls():
    closer = _line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))
    drawings = _u_room_open_south() + [closer]
    supports = _collect_dark_painted_source_wall_strips(_u_room_open_south())
    assert len(_collect_wall_end_closing_strips(drawings, supports)) == 1
    prolonged = _u_room_open_south() + [_line(5, 20, 400, 20, color=(0.0, 0.0, 0.0))]
    assert _collect_wall_end_closing_strips(prolonged, supports) == []
    open_south = build_layered_wall_doorway_room_rings(
        _u_room_open_south(), source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    closed_south = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert not any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in open_south.rings)
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in closed_south.rings)
    assert all(not ring.takeoff_eligible for ring in closed_south.rings)
    assert all(not ring.physical_room_identity_issued for ring in closed_south.rings)
    assert all(not ring.metric_area_issued for ring in closed_south.rings)
    assert all(not ring.commercial_projection_allowed for ring in closed_south.rings)


def test_lookalike_grid_modules_are_not_major_wall_ends():
    module = _WALL_END_SUPPORT_SPAN - 9.0
    assert module == 71.0
    grid = _lookalike_grid(module)
    supports = _collect_dark_painted_source_wall_strips(grid)
    assert _collect_wall_end_closing_strips(grid, supports) == []


def test_wall_end_closer_survives_axis_swap_rotation():
    drawings = _rotate_xy_drawings(_u_room_open_south() + [_line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))])
    supports = _collect_dark_painted_source_wall_strips(_rotate_xy_drawings(_u_room_open_south()))
    assert len(_collect_wall_end_closing_strips(drawings, supports)) == 1
    result = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
    assert all(not ring.takeoff_eligible for ring in result.rings)


def test_wall_end_support_span_is_pdf_point_candidate_heuristic_only():
    closed = _u_room_open_south() + [_line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))]
    small = _scale_drawings(closed, 0.4)
    small_supports = _collect_dark_painted_source_wall_strips(_scale_drawings(_u_room_open_south(), 0.4))
    assert _collect_wall_end_closing_strips(small, small_supports) == []
    large = _scale_drawings(closed, 2.0)
    large_supports = _collect_dark_painted_source_wall_strips(_scale_drawings(_u_room_open_south(), 2.0))
    assert _collect_wall_end_closing_strips(large, large_supports)
    result = build_layered_wall_doorway_room_rings(
        large, source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
    assert all(not ring.takeoff_eligible for ring in result.rings)
    assert all(not ring.physical_room_identity_issued for ring in result.rings)
    assert all(not ring.metric_area_issued for ring in result.rings)


def test_invisible_and_invalid_stroke_opacity_cannot_close_a_room():
    supports = _collect_dark_painted_source_wall_strips(_u_room_open_south())
    opaque = _line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))
    opaque["stroke_opacity"] = 1.0
    assert len(_collect_wall_end_closing_strips(_u_room_open_south() + [opaque], supports)) == 1
    for opacity in (0.0, math.nan, False, True, "1", None):
        hidden = dict(opaque)
        hidden["stroke_opacity"] = opacity
        assert _collect_wall_end_closing_strips(_u_room_open_south() + [hidden], supports) == []
        result = build_layered_wall_doorway_room_rings(
            _u_room_open_south() + [hidden], source_sha256=SHA, page_index=0,
            dark_painted_wall_source=True, wall_end_stroke_closures=True,
        )
        assert not any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
    visible = build_layered_wall_doorway_room_rings(
        _u_room_open_south() + [opaque], source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in visible.rings)
    assert all(not ring.takeoff_eligible for ring in visible.rings)


def test_white_overpaint_and_excluding_clip_hide_a_wall_end_closer():
    import fitz

    supports = _collect_dark_painted_source_wall_strips(_u_room_open_south())
    closer = _line(5, 20, 200, 20, color=(0.0, 0.0, 0.0))
    closer["stroke_opacity"] = 1.0
    mask = _fill_rect(0, 15, 205, 25, (1.0, 1.0, 1.0))
    overpainted = _u_room_open_south() + [closer, mask]
    assert _collect_wall_end_closing_strips(overpainted, supports) == []
    result = build_layered_wall_doorway_room_rings(
        overpainted, source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert not any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
    clipped = dict(closer)
    clipped["scissor"] = fitz.Rect(0, 80, 50, 120)
    assert _collect_wall_end_closing_strips(_u_room_open_south() + [clipped], supports) == []
    inside = dict(closer)
    inside["scissor"] = fitz.Rect(0, 0, 220, 40)
    assert len(_collect_wall_end_closing_strips(_u_room_open_south() + [inside], supports)) == 1
    for scissor in ("not-a-rect", (math.nan, 0.0, 10.0, 10.0)):
        broken = dict(closer)
        broken["scissor"] = scissor
        assert _collect_wall_end_closing_strips(_u_room_open_south() + [broken], supports) == []


def test_green_aisle_ink_is_still_not_a_wall_end_support():
    green = (0.05, 0.55, 0.12)
    drawings = [
        _fill_rect(0, 20, 5, 120, green),
        _fill_rect(200, 20, 205, 120, green),
        _fill_rect(0, 115, 205, 120, green),
        _line(5, 20, 200, 20, color=(0.0, 0.0, 0.0)),
    ]
    result = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=SHA, page_index=0,
        dark_painted_wall_source=True, wall_end_stroke_closures=True,
    )
    assert not any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in result.rings)
