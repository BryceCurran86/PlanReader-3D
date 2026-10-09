from __future__ import annotations

from pathlib import Path

import fitz

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
import pb_live_physical_net_wall_integration as integration
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1


def _pdf_bytes(*, include_scale_bar: bool) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=460.0, height=320.0)
        page.draw_rect(
            fitz.Rect(30.0, 25.0, 370.0, 230.0),
            color=(0, 0, 0),
            width=1.0,
        )
        page.insert_text(
            fitz.Point(120.0, 48.0),
            "GROUND FLOOR PLAN",
            fontsize=8.0,
            color=(0, 0, 0),
        )

        for first, second in (
            ((70.0, 70.0), (330.0, 70.0)),
            ((330.0, 70.0), (330.0, 175.0)),
            ((330.0, 175.0), (70.0, 175.0)),
            ((70.0, 175.0), (70.0, 70.0)),
            ((200.0, 70.0), (200.0, 175.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )

        page.insert_text(
            fitz.Point(92.0, 122.0),
            "CEILING FINISH: CHIPBOARD",
            fontsize=7.0,
            color=(0, 0, 0),
        )

        if include_scale_bar:
            span = POINTS_PER_METRE_AT_1_1 / 100.0
            x0, x1, y = 95.0, 95.0 + span, 205.0
            shape = page.new_shape()
            shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
            shape.draw_line(fitz.Point(x0, y - 6.0), fitz.Point(x0, y + 6.0))
            shape.draw_line(fitz.Point(x1, y - 6.0), fitz.Point(x1, y + 6.0))
            shape.finish(width=1.0)
            shape.commit()
            page.insert_text(fitz.Point(x0 - 2.0, y + 18.0), "0", fontsize=7.0)
            page.insert_text(fitz.Point(x1 - 4.0, y + 18.0), "1m", fontsize=7.0)

        # Ratio text exists in both fixtures. It keeps drawing classification
        # positive, but it must never mint FIRM scale by itself.
        page.insert_text(
            fitz.Point(390.0, 285.0),
            "SCALE 1:100",
            fontsize=7.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _write(tmp_path: Path, *, include_scale_bar: bool) -> Path:
    path = tmp_path / (
        "room-scale-bar.pdf" if include_scale_bar else "room-title-scale-only.pdf"
    )
    path.write_bytes(_pdf_bytes(include_scale_bar=include_scale_bar))
    return path


def test_native_graphic_scale_bar_produces_firm_live_room_and_floor_areas(tmp_path) -> None:
    claim = collect_live_physical_net_wall_claim(
        _write(tmp_path, include_scale_bar=True),
        pages=(0,),
    )

    firm = [
        quantity
        for quantity in claim.room_area_quantity_evidence
        if (
            not quantity.abstained
            and quantity.status == AuthorityStatus.FIRM.value
        )
    ]
    assert firm
    assert all(
        quantity.authority == MeasurementAuthorityType.PDF_SCALED.value
        for quantity in firm
    )
    assert all(
        quantity.value is not None and float(quantity.value) > 0.0
        for quantity in firm
    )

    firm_ids = {quantity.quantity_id for quantity in firm}
    enriched = [
        floor
        for floor in claim.canonical_floors
        if floor.metric_area_quantity_id in firm_ids
    ]
    assert enriched
    assert all(floor.metric_area_m2 is not None for floor in enriched)
    assert all(
        floor.metric_area_authority == MeasurementAuthorityType.PDF_SCALED.value
        for floor in enriched
    )


def test_title_block_ratio_without_graphic_scale_bar_never_mints_metric_room_area(tmp_path) -> None:
    claim = collect_live_physical_net_wall_claim(
        _write(tmp_path, include_scale_bar=False),
        pages=(0,),
    )

    assert not any(
        not quantity.abstained
        and quantity.status == AuthorityStatus.FIRM.value
        and quantity.authority == MeasurementAuthorityType.PDF_SCALED.value
        for quantity in claim.room_area_quantity_evidence
    )
    assert all(
        floor.metric_area_quantity_id is None
        and floor.metric_area_m2 is None
        for floor in claim.canonical_floors
    )


def test_authenticated_viewport_owner_is_resolved_once_per_room_scope(
    tmp_path, monkeypatch
) -> None:
    original = integration._unique_authenticated_containing_floor_plan_viewport
    calls: list[tuple[str, str]] = []

    def counted(*, source, scope_rooms, page_id, snapshot_id):
        calls.append((page_id, snapshot_id))
        return original(
            source=source,
            scope_rooms=scope_rooms,
            page_id=page_id,
            snapshot_id=snapshot_id,
        )

    monkeypatch.setattr(
        integration,
        "_unique_authenticated_containing_floor_plan_viewport",
        counted,
    )
    claim = collect_live_physical_net_wall_claim(
        _write(tmp_path, include_scale_bar=True),
        pages=(0,),
    )
    assert claim.canonical_rooms
    # Repeated scale fallbacks may recheck the same ownership decision; the
    # authenticated lookup must never be rebuilt twice for one room scope.
    assert len(calls) == len(set(calls))
