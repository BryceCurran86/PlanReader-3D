from __future__ import annotations

import fitz
import pytest

from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_FRAME_SCHEDULE_AREA_QUANTITY_AUTHORITY,
)
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)


def _frame_schedule_pdf(*, explicit_frame_basis: bool) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=760.0, height=650.0)
        page.insert_text(fitz.Point(20.0, 24.0), "FLOOR PLAN")

        # One generic jamb-bounded two-face interruption. This proves opening
        # existence only; W1 + its authenticated schedule row supplies kind.
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((145.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((145.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((145.0, 100.0), (145.0, 110.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)

        page.insert_text(fitz.Point(112.0, 65.0), "900")
        page.insert_text(fitz.Point(112.0, 106.0), "W1")

        headings = (
            "MARK",
            "FRAMEWIDTH" if explicit_frame_basis else "WIDTH",
            "FRAMEHEIGHT" if explicit_frame_basis else "HEIGHT",
        )
        values = ("W1", "1200", "1800")
        xs = (50.0, 170.0, 380.0)
        for text, x in zip(headings, xs):
            page.insert_text(fitz.Point(x, 500.0), text)
        for text, x in zip(values, xs):
            page.insert_text(fitz.Point(x, 530.0), text)

        # Deliberately no vertical-placement or scale authority. Therefore a
        # sealed physical void cannot rescue the test. Only explicit FRAME
        # semantics may publish the 1200 x 1800 gross frame area.
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_explicit_frame_schedule_dimensions_publish_gross_frame_area(
    tmp_path,
) -> None:
    path = tmp_path / "frame-schedule.pdf"
    path.write_bytes(_frame_schedule_pdf(explicit_frame_basis=True))

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert len(claim.canonical_openings) == 1
    opening = claim.canonical_openings[0]
    assert opening.opening_kind == "window"
    assert opening.type_mark == "W1"
    assert opening.schedule_row_dimension_basis == "frame"
    assert opening.schedule_declared_width_mm == 1200
    assert opening.schedule_declared_height_mm == 1800
    assert opening.geometry_complete is False
    assert opening.area_basis == "authenticated_frame_schedule"
    assert opening.area_m2 == pytest.approx(2.16)

    assert len(claim.opening_quantity_evidence) == 1
    quantity = claim.opening_quantity_evidence[0]
    assert quantity.value == pytest.approx(2.16)
    assert quantity.unit == "m2"
    assert quantity.input_entity_ids == (opening.canonical_opening_id,)
    assert quantity.authority == LIVE_OPENING_FRAME_SCHEDULE_AREA_QUANTITY_AUTHORITY
    assert quantity.metadata["area_basis"] == "authenticated_frame_schedule"
    assert quantity.metadata["schedule_row_dimension_basis"] == "frame"
    assert quantity.metadata["measurement_record_id"] == opening.schedule_binding_record_id


def test_generic_width_height_schedule_does_not_mint_frame_area(
    tmp_path,
) -> None:
    path = tmp_path / "generic-dimensions.pdf"
    path.write_bytes(_frame_schedule_pdf(explicit_frame_basis=False))

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert claim.canonical_openings
    opening = claim.canonical_openings[0]
    assert opening.schedule_declared_width_mm == 1200
    assert opening.schedule_declared_height_mm == 1800
    assert opening.schedule_row_dimension_basis == ""
    assert opening.geometry_complete is False
    assert opening.area_basis != "authenticated_frame_schedule"
    assert claim.opening_quantity_evidence == ()
