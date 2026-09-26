"""Regression tests for pb_wall_fill_internal_partition_evidence.

Uses the real Lamu Ishakani ECD classrooms source drawing (benchmarks/
sources/lamu-ishakani-ecd-classrooms-boq.pdf, page index 40) as the
positive-evidence fixture, plus synthetic fixtures for the two false
positives this module's own development caught: a page-border/title-block
frame line masquerading as a wall-like fill, and an internal partition's
own top/bottom endpoints (which legitimately reach the envelope's y-extent,
since it spans between opposite perimeter walls by definition) being
mistaken for perimeter evidence by a boundary-proximity check that didn't
account for the fill's own orientation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from pb_wall_fill_internal_partition_evidence import (
    _is_wall_like_fill,
    resolve_dpc_all_walls_geometry,
    resolve_internal_partition_length_m,
)

_LAMU_PDF = (
    Path(__file__).resolve().parent.parent
    / "benchmarks"
    / "sources"
    / "lamu-ishakani-ecd-classrooms-boq.pdf"
)
_LAMU_FLOOR_PLAN_PAGE_INDEX = 40


def _load_lamu_page():
    if not _LAMU_PDF.exists():
        pytest.skip(f"benchmark source fixture not present: {_LAMU_PDF}")
    doc = fitz.open(str(_LAMU_PDF))
    return doc, doc[_LAMU_FLOOR_PLAN_PAGE_INDEX]


def test_real_lamu_drawing_finds_the_confirmed_internal_partition() -> None:
    doc, page = _load_lamu_page()
    try:
        drawings = page.get_drawings()
        result = resolve_internal_partition_length_m(
            drawings, length_m=16.0, width_m=8.2, page=page
        )
    finally:
        doc.close()

    assert result.status == "found"
    # This module derives length purely from wall-fill pixel geometry and
    # the already-resolved envelope scale -- it does not read or bind to
    # any figured dimension text. The range below is independently derived
    # from that geometry, then separately cross-validated (in this test,
    # not in production logic) against the drawing's own "6100" figured
    # dimension for the same real-world span, which happens to confirm it.
    assert 5.8 <= result.total_length_m <= 6.4
    # Independently confirms a physically plausible masonry thickness
    # (drawing's own dimension chain brackets show 200mm).
    assert result.wall_thickness_m is not None
    assert 0.17 <= result.wall_thickness_m <= 0.23


def _make_fill(x0, y0, x1, y1, fill=(0.0, 0.0, 0.0)):
    return {"type": "f", "fill": fill, "rect": fitz.Rect(x0, y0, x1, y1)}


class _FakePageRect:
    def __init__(self, width, height):
        self.width = width
        self.height = height


def test_page_border_frame_line_is_excluded_as_wall_like() -> None:
    """Regression: a title-block/page-border line is also thin, long, and
    solid-black-filled, but spans nearly the entire sheet -- must not be
    mistaken for a wall."""
    page_rect = _FakePageRect(842.0, 1191.0)
    border = _make_fill(4.5, 10.5, 828.8, 18.6)  # ~824pt long on an 842pt-wide page
    assert not _is_wall_like_fill(border, page_rect)

    real_wall = _make_fill(200.5, 115.8, 206.1, 202.2)  # ~86pt on the same page
    assert _is_wall_like_fill(real_wall, page_rect)


def test_internal_partition_endpoints_near_envelope_edge_are_not_perimeter() -> None:
    """Regression: a vertical internal partition's own top/bottom endpoints
    legitimately reach the derived envelope's min_y/max_y (it spans between
    the two horizontal perimeter walls by definition) -- an orientation-
    unaware boundary check wrongly excluded it as 'perimeter' during this
    module's own development. Only left/right proximity should matter for
    a vertical fill.
    """
    west_wall = _make_fill(100.0, 100.0, 105.6, 300.0)   # vertical, at the left edge
    east_wall = _make_fill(500.0, 100.0, 505.6, 300.0)   # vertical, at the right edge
    top_wall = _make_fill(100.0, 100.0, 500.0, 105.6)    # horizontal, at the top edge
    partition = _make_fill(300.0, 100.0, 305.6, 300.0)   # vertical, dead centre

    drawings = [west_wall, east_wall, top_wall, partition]
    # 400x200pt bbox at an arbitrary consistent scale.
    result = resolve_internal_partition_length_m(
        drawings, length_m=400.0 / 40.0, width_m=200.0 / 40.0, page=None
    )
    assert result.status == "found"
    assert result.total_length_m == pytest.approx(200.0 / 40.0, abs=0.1)


def test_furniture_style_stroke_only_shapes_are_never_wall_like() -> None:
    """A stroke-only rectangle (no fill) -- the desk/furniture convention on
    the real Lamu drawing -- must never be treated as a wall candidate,
    regardless of its aspect ratio."""
    desk = {"type": "s", "fill": None, "rect": fitz.Rect(200.0, 100.0, 260.0, 106.0)}
    assert not _is_wall_like_fill(desk, None)


def test_implausible_wall_thickness_abstains() -> None:
    """If the derived scale would imply a wall thickness far outside any
    real masonry range, the result must be distrusted rather than used."""
    # Walls genuinely 400pt apart, but caller supplies a real dimension
    # (4000m) that would make every fill's ~6pt thickness imply ~6mm --
    # not a real wall.
    west_wall = _make_fill(100.0, 100.0, 106.0, 300.0)
    east_wall = _make_fill(500.0, 100.0, 506.0, 300.0)
    result = resolve_internal_partition_length_m(
        [west_wall, east_wall], length_m=4000.0, width_m=2000.0, page=None
    )
    assert result.status == "abstained"
    assert "wall thickness" in result.reason


def _compound_geometry_fixture(
    *,
    full_transverse: bool,
    longitudinal_start_m: float = 0.0,
    longitudinal_end_m: float = 16.0,
):
    """Source wall fills for span-authority adversarial tests."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    length_m, width_m = 16.0, 8.2
    thickness = 4.0
    x1 = x0 + length_m * scale
    y1 = y0 + width_m * scale
    classroom_depth_m = 6.1
    classroom_y = y0 + classroom_depth_m * scale
    mid_x = x0 + (length_m * scale) / 2.0

    drawings = [
        _make_fill(x0, y0, x1, y0 + thickness),
        _make_fill(x0, y0, x0 + thickness, y1),
        _make_fill(x1 - thickness, y0, x1, y1),
    ]
    trans_end = y1 if full_transverse else classroom_y
    drawings.append(
        _make_fill(
            mid_x - thickness / 2.0,
            y0,
            mid_x + thickness / 2.0,
            trans_end,
        )
    )

    lx0 = x0 + longitudinal_start_m * scale
    lx1 = x0 + longitudinal_end_m * scale
    if lx1 > lx0:
        drawings.append(
            _make_fill(
                lx0,
                classroom_y - thickness,
                lx1,
                classroom_y,
            )
        )
    return drawings, length_m, width_m


def test_dpc_all_walls_short_longitudinal_run_is_not_upgraded_to_building_length() -> None:
    drawings, length_m, width_m = _compound_geometry_fixture(
        full_transverse=False,
        longitudinal_start_m=4.0,
        longitudinal_end_m=12.0,
    )
    result = resolve_dpc_all_walls_geometry(
        drawings,
        length_m=length_m,
        width_m=width_m,
        page=None,
        page_text="GROUND FLOOR PLAN VERANDAH DPC under all walls",
    )
    assert result.status == "found"
    assert len(result.longitudinal_runs) == 1
    assert result.longitudinal_runs[0].grid_length_m == pytest.approx(8.0, abs=0.1)
    assert result.longitudinal_runs[0].grid_length_m < length_m


def test_dpc_all_walls_transverse_run_stopping_before_verandah_is_not_upgraded() -> None:
    drawings, length_m, width_m = _compound_geometry_fixture(
        full_transverse=False,
        longitudinal_start_m=0.0,
        longitudinal_end_m=16.0,
    )
    result = resolve_dpc_all_walls_geometry(
        drawings,
        length_m=length_m,
        width_m=width_m,
        page=None,
        page_text="GROUND FLOOR PLAN VERANDAH DPC under all walls",
    )
    assert result.status == "found"
    assert len(result.transverse_runs) == 1
    assert result.transverse_runs[0].grid_length_m == pytest.approx(6.1, abs=0.1)
    assert result.transverse_runs[0].grid_length_m < width_m


def test_dpc_all_walls_full_source_spans_publish_full_runs_without_dimension_substitution() -> None:
    drawings, length_m, width_m = _compound_geometry_fixture(
        full_transverse=True,
        longitudinal_start_m=0.0,
        longitudinal_end_m=16.0,
    )
    result = resolve_dpc_all_walls_geometry(
        drawings,
        length_m=length_m,
        width_m=width_m,
        page=None,
        page_text="GROUND FLOOR PLAN VERANDAH DPC under all walls",
    )
    assert result.status == "found"
    assert len(result.transverse_runs) == 1
    assert len(result.longitudinal_runs) == 1
    assert result.transverse_runs[0].grid_length_m == pytest.approx(8.2, abs=0.1)
    assert result.longitudinal_runs[0].grid_length_m == pytest.approx(16.0, abs=0.1)
    assert result.total_internal_length_m == pytest.approx(24.2, abs=0.1)
