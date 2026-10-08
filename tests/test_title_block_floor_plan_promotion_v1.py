from __future__ import annotations

from typing import Iterable, Optional, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
)

W0, H0 = 1190.0, 842.0
DEFAULT_LABELS = ("DRAWING TITLE", "DRAWING NO", "SCALE", "DRAWN BY", "DATE")
PLAN = (120.0, 120.0, 760.0, 560.0)


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _plan(page: fitz.Page, box: Sequence[float]) -> None:
    x0, y0, x1, y1 = box
    xm, ym = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for a, b in (
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
        ((x0, ym), (x1, ym)),
        ((xm, y0), (xm, y1)),
    ):
        page.draw_line(a, b, width=0.6)


def _title_block(
    page: fitz.Page,
    *,
    value: str = "FLOOR PLAN",
    labels: Sequence[str] = DEFAULT_LABELS,
    frame: bool = True,
) -> None:
    x, y = W0 - 390.0, H0 - 122.0
    if frame:
        page.draw_rect(
            fitz.Rect(x - 20.0, y - 14.0, W0 - 30.0, H0 - 30.0),
            width=0.5,
        )
    for index, label in enumerate(labels):
        page.insert_text((x + index * 60.0, y), label, fontsize=7.0)
    page.insert_text((x, y + 13.0), value, fontsize=10.0)


def _sheet(
    *,
    value: str = "FLOOR PLAN",
    labels: Sequence[str] = DEFAULT_LABELS,
    plans: Iterable[Sequence[float]] = (PLAN,),
    texts: Iterable[tuple[str, tuple[float, float]]] = (),
    title_block: bool = True,
) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=W0, height=H0)
    page.draw_rect(fitz.Rect(20.0, 20.0, W0 - 20.0, H0 - 20.0), width=0.5)
    if title_block:
        _title_block(page, value=value, labels=labels)
    for box in plans:
        _plan(page, box)
    for text, at in texts:
        page.insert_text(at, text, fontsize=10.0)
    return _reopen(doc)


def _floor_rows(doc: fitz.Document):
    return [
        row
        for row in segment_page_viewports(doc[0], page_number=3)
        if row.view_type == DrawingViewType.FLOOR_PLAN.value
    ]


def test_title_block_only_single_floor_plan_is_promoted_by_f07() -> None:
    doc = _sheet()
    try:
        rows = _floor_rows(doc)
        assert len(rows) == 1
        row = rows[0]
        assert row.status == ViewportSegmentationStatus.DERIVED.value
        assert row.bounding_box is not None
        assert is_segment_page_viewports_product(row) is True
        assert is_authoritative_derived_viewport(row) is True
        assert row.provenance["partition_mode"] == "title_block_single_view_floor_plan"
        assert row.provenance["page_title_authority_owned"] is True
        assert row.provenance["single_view_validated"] is True
    finally:
        doc.close()


def test_title_block_single_floor_plan_can_coexist_with_unbounded_legend() -> None:
    doc = _sheet(texts=(("LEGEND", (40.0, 300.0)),))
    try:
        rows = segment_page_viewports(doc[0], page_number=3)
        floor = [
            row for row in rows
            if row.view_type == DrawingViewType.FLOOR_PLAN.value
        ]
        assert len(floor) == 1
        assert is_authoritative_derived_viewport(floor[0]) is True
        assert any(
            row.view_type == DrawingViewType.LEGEND.value
            for row in rows
        )
    finally:
        doc.close()


def test_non_floor_plan_title_block_cannot_promote_floor_plan() -> None:
    doc = _sheet(value="ROOF PLAN")
    try:
        assert _floor_rows(doc) == []
    finally:
        doc.close()


def test_two_separated_drawing_regions_remain_fail_closed() -> None:
    doc = _sheet(
        plans=(
            (80.0, 120.0, 380.0, 520.0),
            (640.0, 120.0, 940.0, 520.0),
        )
    )
    try:
        assert _floor_rows(doc) == []
    finally:
        doc.close()


def test_weak_title_block_without_explicit_title_field_cannot_promote() -> None:
    doc = _sheet(value="1:100", labels=("SCALE", "DATE"))
    try:
        assert _floor_rows(doc) == []
    finally:
        doc.close()
