"""F.23 secondary-footprint orthogonal-depth attacks (gold-free).

Depth must be perpendicular to the verandah adjoining edge:
  top/bottom → vertical figured dimension with vector anchors
  left/right → horizontal figured dimension with vector anchors

Wall-thickness marks parallel to the edge must never become width.
No benchmark project quantities, IDs, or expected BOQ values.
"""
from __future__ import annotations

import fitz
import pytest

from pb_secondary_footprint_evidence import resolve_secondary_footprint_width_m


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


_EDGE_FRACTIONS = {
    "top": (0.5, 0.08),
    "bottom": (0.5, 0.92),
    "left": (0.12, 0.45),
    "right": (0.88, 0.55),
    "center": (0.5, 0.5),
}


def _draw_vertical_depth(
    page: fitz.Page,
    *,
    x: float,
    y0: float,
    y1: float,
    text: str,
    fontsize: float,
) -> None:
    page.draw_line((x, y0), (x, y1))
    page.draw_line((x - 18, y0), (x + 18, y0))
    page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=fontsize, rotate=90)


def _draw_horizontal_depth(
    page: fitz.Page,
    *,
    y: float,
    x0: float,
    x1: float,
    text: str,
    fontsize: float,
) -> None:
    page.draw_line((x0, y), (x1, y))
    page.draw_line((x0, y - 18), (x0, y + 18))
    page.draw_line((x1, y - 18), (x1, y + 18))
    page.insert_text(((x0 + x1) / 2.0 - 12, y - 4), text, fontsize=fontsize)


def _build_plan_with_orthogonal_depth(
    *,
    edge: str = "bottom",
    depth_text: str = "1800",
    label_text: str = "VERANDAH",
    dx: float = 0.0,
    dy: float = 0.0,
    scale: float = 1.0,
    page_w: float = 640.0,
    page_h: float = 460.0,
    include_depth: bool = True,
    parallel_thickness_text: str | None = None,
    second_depth_text: str | None = None,
    depth_offset_along: float = 0.0,
    second_label: bool = False,
    omit_witnesses: bool = False,
    omit_frame: bool = False,
    add_elevation_trap: bool = False,
) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=page_w * scale if scale != 1.0 else page_w, height=page_h if scale == 1.0 else page_h * scale)
    # Keep geometry simple: apply dx/dy/scale on frame coordinates.
    fs = 10.0 * scale
    fx0, fy0 = 30.0 * scale + dx, 30.0 * scale + dy
    fx1, fy1 = fx0 + 280.0 * scale, fy0 + 280.0 * scale
    if not omit_frame:
        page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))

    width = fx1 - fx0
    height = fy1 - fy0
    page.insert_text((fx0 + 0.10 * width, fy0 + 0.50 * height), "150 5,700 150", fontsize=fs)
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0 * scale), "GROUND FLOOR PLAN", fontsize=fs)

    x_frac, y_frac = _EDGE_FRACTIONS[edge]
    label_width = fitz.get_text_length(label_text, fontsize=fs)
    label_x = fx0 + x_frac * width - label_width / 2.0 + depth_offset_along * scale
    label_y = fy0 + y_frac * height
    page.insert_text((label_x, label_y), label_text, fontsize=fs)
    if second_label:
        page.insert_text((fx0 + 0.5 * width, fy0 + 0.5 * height + 12.0 * scale), label_text, fontsize=fs)

    label_cx = label_x + label_width / 2.0
    label_cy = label_y - fs * 0.35

    if include_depth and edge in ("top", "bottom"):
        # Depth axis is vertical; place slightly inward from the label.
        span = 36.0 * scale
        if edge == "bottom":
            y1 = label_cy - 4.0 * scale
            y0 = y1 - span
        else:
            y0 = label_cy + 4.0 * scale
            y1 = y0 + span
        x = label_cx
        if omit_witnesses:
            page.draw_line((x, y0), (x, y1))
            page.insert_text((x + 5, (y0 + y1) / 2.0), depth_text, fontsize=fs, rotate=90)
        else:
            _draw_vertical_depth(page, x=x, y0=y0, y1=y1, text=depth_text, fontsize=fs)
        if second_depth_text is not None:
            _draw_vertical_depth(
                page,
                x=x + 55.0 * scale,
                y0=y0,
                y1=y1,
                text=second_depth_text,
                fontsize=fs,
            )
        if parallel_thickness_text is not None:
            # Parallel to bottom/top edge = horizontal dim (must NOT win).
            ty = label_cy - 2.0 * scale if edge == "bottom" else label_cy + 2.0 * scale
            page.draw_line((label_cx - 20 * scale, ty), (label_cx + 20 * scale, ty))
            page.draw_line((label_cx - 20 * scale, ty - 10), (label_cx - 20 * scale, ty + 10))
            page.draw_line((label_cx + 20 * scale, ty - 10), (label_cx + 20 * scale, ty + 10))
            page.insert_text((label_cx - 10 * scale, ty - 3), parallel_thickness_text, fontsize=fs)

    if include_depth and edge in ("left", "right"):
        span = 36.0 * scale
        if edge == "left":
            x0 = label_cx + 4.0 * scale
            x1 = x0 + span
        else:
            x1 = label_cx - 4.0 * scale
            x0 = x1 - span
        y = label_cy
        if omit_witnesses:
            page.draw_line((x0, y), (x1, y))
            page.insert_text(((x0 + x1) / 2.0 - 10, y - 4), depth_text, fontsize=fs)
        else:
            _draw_horizontal_depth(page, y=y, x0=x0, x1=x1, text=depth_text, fontsize=fs)
        if second_depth_text is not None:
            _draw_horizontal_depth(
                page,
                y=y + 40.0 * scale,
                x0=x0,
                x1=x1,
                text=second_depth_text,
                fontsize=fs,
            )
        if parallel_thickness_text is not None:
            # Parallel to left/right edge = vertical dim (must NOT win).
            tx = label_cx + 2.0 * scale if edge == "left" else label_cx - 2.0 * scale
            page.draw_line((tx, label_cy - 20 * scale), (tx, label_cy + 20 * scale))
            page.draw_line((tx - 10, label_cy - 20 * scale), (tx + 10, label_cy - 20 * scale))
            page.draw_line((tx - 10, label_cy + 20 * scale), (tx + 10, label_cy + 20 * scale))
            page.insert_text((tx + 4, label_cy), parallel_thickness_text, fontsize=fs, rotate=90)

    if add_elevation_trap:
        ex0 = fx1 + 40.0 * scale
        page.draw_rect(fitz.Rect(ex0, fy0, ex0 + 200 * scale, fy1))
        page.insert_text((ex0 + 20 * scale, fy1 - 8 * scale), "WEST ELEVATION", fontsize=fs)
        page.insert_text((ex0 + 40 * scale, label_y), "VERANDAH", fontsize=fs)
        _draw_vertical_depth(
            page,
            x=ex0 + 90 * scale,
            y0=label_cy - 40 * scale,
            y1=label_cy - 4 * scale,
            text="9999",
            fontsize=fs,
        )

    return _reopen(doc)


def _resolve(doc: fitz.Document):
    result = resolve_secondary_footprint_width_m(doc[0], page_num=1)
    doc.close()
    return result


@pytest.mark.parametrize("edge", ["top", "bottom", "left", "right"])
def test_all_four_edges_resolve_orthogonal_depth(edge: str):
    result = _resolve(_build_plan_with_orthogonal_depth(edge=edge, depth_text="2400"))
    assert result is not None
    assert result.edge == edge
    assert result.width_m == pytest.approx(2.4)
    assert result.depth_orientation == ("vertical" if edge in ("top", "bottom") else "horizontal")


def test_bottom_edge_requires_vertical_depth_not_horizontal_chain():
    result = _resolve(_build_plan_with_orthogonal_depth(edge="bottom", depth_text="1800"))
    assert result is not None
    assert result.width_m == pytest.approx(1.8)
    assert result.depth_orientation == "vertical"


def test_parallel_200mm_thickness_trap_never_becomes_width():
    # Closer parallel thickness mark + farther true orthogonal depth.
    result = _resolve(
        _build_plan_with_orthogonal_depth(
            edge="bottom",
            depth_text="1800",
            parallel_thickness_text="200",
            depth_offset_along=40.0,  # shift depth slightly; thickness stays at label
        )
    )
    assert result is not None
    assert result.width_m == pytest.approx(1.8)
    assert result.width_m != pytest.approx(0.2)


def test_wrong_orientation_only_returns_none():
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    frame = fitz.Rect(30, 30, 310, 310)
    page.draw_rect(frame)
    page.insert_text((50, 170), "150 5,700 150", fontsize=10)
    page.insert_text((50, 302), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((150, 295), "VERANDAH", fontsize=10)
    # Only a horizontal (parallel) figure near bottom edge.
    page.draw_line((140, 280), (200, 280))
    page.draw_line((140, 270), (140, 290))
    page.draw_line((200, 270), (200, 290))
    page.insert_text((155, 276), "1800", fontsize=10)
    doc = _reopen(doc)
    assert _resolve(doc) is None


def test_unrelated_nearby_dimension_ignored_without_orthogonal_anchor():
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    frame = fitz.Rect(30, 30, 310, 310)
    page.draw_rect(frame)
    page.insert_text((50, 60), "5500", fontsize=10)
    page.insert_text((50, 302), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((150, 295), "VERANDAH", fontsize=10)
    doc = _reopen(doc)
    assert _resolve(doc) is None


def test_true_depth_farther_than_thickness_mark_still_wins():
    result = _resolve(
        _build_plan_with_orthogonal_depth(
            edge="bottom",
            depth_text="2100",
            parallel_thickness_text="200",
            depth_offset_along=70.0,
        )
    )
    assert result is not None
    assert result.width_m == pytest.approx(2.1)


def test_missing_witness_anchor_support_fails_closed():
    # Dimension line without witnesses → not an accepted binding for depth.
    result = _resolve(
        _build_plan_with_orthogonal_depth(edge="bottom", depth_text="1800", omit_witnesses=True)
    )
    assert result is None


def test_conflicting_orthogonal_depths_fail_closed():
    result = _resolve(
        _build_plan_with_orthogonal_depth(
            edge="bottom",
            depth_text="1800",
            second_depth_text="2100",
        )
    )
    assert result is None


def test_input_order_invariance_of_identical_depths():
    a = _resolve(_build_plan_with_orthogonal_depth(edge="left", depth_text="1500"))
    b = _resolve(_build_plan_with_orthogonal_depth(edge="left", depth_text="1500"))
    assert a is not None and b is not None
    assert a.width_m == b.width_m == pytest.approx(1.5)


def test_translation_invariance():
    base = _resolve(_build_plan_with_orthogonal_depth(edge="bottom", depth_text="1800"))
    shifted = _resolve(
        _build_plan_with_orthogonal_depth(edge="bottom", depth_text="1800", dx=120.0, dy=-18.0)
    )
    assert base is not None and shifted is not None
    assert shifted.width_m == pytest.approx(base.width_m)
    assert shifted.edge == base.edge


def test_scale_invariance_of_printed_depth_value():
    base = _resolve(_build_plan_with_orthogonal_depth(edge="right", depth_text="1800", scale=1.0))
    scaled = _resolve(
        _build_plan_with_orthogonal_depth(
            edge="right",
            depth_text="1800",
            scale=1.6,
            page_w=900.0,
            page_h=700.0,
        )
    )
    assert base is not None and scaled is not None
    assert scaled.width_m == pytest.approx(base.width_m)


def test_adding_parallel_trap_cannot_strengthen_or_change_depth():
    clean = _resolve(_build_plan_with_orthogonal_depth(edge="bottom", depth_text="1800"))
    trapped = _resolve(
        _build_plan_with_orthogonal_depth(
            edge="bottom",
            depth_text="1800",
            parallel_thickness_text="200",
        )
    )
    assert clean is not None and trapped is not None
    assert trapped.width_m == pytest.approx(clean.width_m)


def test_removing_depth_evidence_cannot_strengthen():
    with_depth = _resolve(_build_plan_with_orthogonal_depth(edge="bottom", depth_text="1800"))
    without = _resolve(_build_plan_with_orthogonal_depth(edge="bottom", include_depth=False))
    assert with_depth is not None
    assert without is None


def test_raster_only_page_fails_closed():
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    # Image-only page: no native labels or figured dimensions.
    page.insert_image(fitz.Rect(20, 20, 380, 380), stream=_tiny_png_bytes())
    doc = _reopen(doc)
    assert _resolve(doc) is None


def _tiny_png_bytes() -> bytes:
    # 1x1 PNG
    import base64

    return base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_interior_label_fails_closed():
    assert _resolve(_build_plan_with_orthogonal_depth(edge="center", depth_text="1800")) is None


def test_two_labels_fail_closed():
    assert _resolve(_build_plan_with_orthogonal_depth(edge="bottom", second_label=True)) is None


def test_elevation_trap_does_not_override_plan_depth():
    result = _resolve(
        _build_plan_with_orthogonal_depth(
            edge="bottom",
            depth_text="1800",
            add_elevation_trap=True,
            page_w=900.0,
        )
    )
    assert result is not None
    assert result.width_m == pytest.approx(1.8)


def test_no_label_returns_none():
    assert _resolve(_build_plan_with_orthogonal_depth(edge="bottom", label_text="STORE")) is None


def test_legacy_inline_verandah_width_path_still_wired_in_extractor():
    """Extractor still has the page-wide regex fallback; F.23 is additive."""
    import inspect
    import pb_planreader_pdf_extractor as mod

    src = inspect.getsource(mod.GenericPlanReaderExtractor.extract_from_pdf)
    assert "wide\\s*veranda" in src or "wide\\s*veranda" in src.replace("\\\\", "\\")
    assert "resolve_secondary_footprint_width_m" in src
