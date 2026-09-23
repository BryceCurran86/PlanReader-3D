"""Fail-closed live ceiling-lining resolver tests."""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_live_ceiling_lining_integration import (
    LIVE_CEILING_LINING_FINISH_INCOMPLETE,
    LIVE_CEILING_LINING_NO_FLOOR_PLAN,
    LIVE_CEILING_LINING_RESOLVED,
    LIVE_CEILING_LINING_SCALE_UNAVAILABLE,
    LIVE_CEILING_LINING_SCOPE_NOT_UNIQUE,
    resolve_live_ceiling_lining,
)


def _draw_room_frame(page, *, x0=40.0, y0=40.0, x1=320.0, y1=160.0) -> None:
    shape = page.new_shape()
    shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y0))
    shape.draw_line(fitz.Point(x1, y0), fitz.Point(x1, y1))
    shape.draw_line(fitz.Point(x1, y1), fitz.Point(x0, y1))
    shape.draw_line(fitz.Point(x0, y1), fitz.Point(x0, y0))
    shape.finish(width=1.0)
    shape.commit()


def _write_single_plan(
    path: Path,
    *,
    include_title: bool = True,
    include_scale_bar: bool = True,
    include_right_finish: bool = True,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=420.0, height=240.0)

    _draw_room_frame(page)
    page.draw_line(
        fitz.Point(180.0, 40.0),
        fitz.Point(180.0, 160.0),
        color=(0, 0, 0),
        width=1.0,
    )

    if include_title:
        page.insert_text(
            fitz.Point(120.0, 58.0),
            "GROUND FLOOR PLAN",
            fontsize=8.0,
            color=(0, 0, 0),
        )

    page.insert_text(
        fitz.Point(58.0, 98.0),
        "CEILING FINISH: BOARD",
        fontsize=6.0,
        color=(0, 0, 0),
    )
    if include_right_finish:
        page.insert_text(
            fitz.Point(190.0, 98.0),
            "CEILING FINISH: BOARD",
            fontsize=6.0,
            color=(0, 0, 0),
        )

    page.insert_text(
        fitz.Point(205.0, 72.0),
        "SCALE 1:100",
        fontsize=6.0,
        color=(0, 0, 0),
    )

    if include_scale_bar:
        span = POINTS_PER_METRE_AT_1_1 / 100.0
        x0, x1, y = 70.0, 70.0 + span, 132.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 6.0), fitz.Point(x0, y + 6.0))
        shape.draw_line(fitz.Point(x1, y - 6.0), fitz.Point(x1, y + 6.0))
        shape.finish(width=0.8)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 1.0, y + 15.0), "0", fontsize=6.0)
        page.insert_text(fitz.Point(x1 - 3.0, y + 15.0), "1m", fontsize=6.0)

    doc.save(path)
    doc.close()


def _write_two_floor_plans(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=520.0, height=260.0)

    for x0, x1, title in (
        (30.0, 240.0, "GROUND FLOOR PLAN"),
        (280.0, 490.0, "FIRST FLOOR PLAN"),
    ):
        y0, y1 = 40.0, 180.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y0))
        shape.draw_line(fitz.Point(x1, y0), fitz.Point(x1, y1))
        shape.draw_line(fitz.Point(x1, y1), fitz.Point(x0, y1))
        shape.draw_line(fitz.Point(x0, y1), fitz.Point(x0, y0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text(
            fitz.Point(x0 + 45.0, 60.0),
            title,
            fontsize=8.0,
            color=(0, 0, 0),
        )

    doc.save(path)
    doc.close()


def test_complete_single_floor_plan_resolves_live_ceiling_quantity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "single-complete-plan.pdf"
    _write_single_plan(path)

    result = resolve_live_ceiling_lining(path)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_CEILING_LINING_RESOLVED,)
    assert result.quantity_m2 is not None
    assert result.quantity_m2 > 0.0
    assert result.finish_descriptor
    assert result.source_page == 1
    assert result.viewport_id
    assert result.viewport_bbox is not None
    assert len(result.room_entity_ids) == 2
    assert len(result.room_area_quantity_ids) == 2
    assert len(result.ceiling_quantity_ids) == 2
    assert result.physical_scale_record_id


def test_ratio_text_without_graphic_bar_remains_blocked(tmp_path: Path) -> None:
    path = tmp_path / "ratio-only-plan.pdf"
    _write_single_plan(path, include_scale_bar=False)

    result = resolve_live_ceiling_lining(path)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CEILING_LINING_SCALE_UNAVAILABLE,)
    assert result.quantity_m2 is None


def test_partial_room_finish_coverage_never_becomes_total(tmp_path: Path) -> None:
    path = tmp_path / "partial-finish-plan.pdf"
    _write_single_plan(path, include_right_finish=False)

    result = resolve_live_ceiling_lining(path)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CEILING_LINING_FINISH_INCOMPLETE,)
    assert result.quantity_m2 is None


def test_missing_floor_plan_title_cannot_mint_viewport_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "untitled-plan.pdf"
    _write_single_plan(path, include_title=False)

    result = resolve_live_ceiling_lining(path)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CEILING_LINING_NO_FLOOR_PLAN,)
    assert result.quantity_m2 is None


def test_multiple_floor_plans_are_not_summed_without_identity_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-floor-plans.pdf"
    _write_two_floor_plans(path)

    result = resolve_live_ceiling_lining(path)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CEILING_LINING_SCOPE_NOT_UNIQUE,)
    assert result.quantity_m2 is None
