from __future__ import annotations

import fitz

from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_FRAME_AREA_QUANTITY_AUTHORITY,
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _opening(page, x: float, y: float, *, gap: float = 40.0, run: float = 50.0, thick: float = 10.0) -> None:
    a, b = x + run, x + run + gap
    for yy in (y, y + thick):
        page.draw_line((x, yy), (a, yy), width=1)
        page.draw_line((b, yy), (b + run, yy), width=1)
    page.draw_line((a, y), (a, y + thick), width=1)
    page.draw_line((b, y), (b, y + thick), width=1)


def _frame_schedule_sheet(
    *,
    width_heading: str = "FRAME WIDTH",
    height_heading: str = "FRAME HEIGHT",
) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=760, height=380)

        # Two producer-discoverable viewports: the physical opening exists only
        # in the floor plan; its type/dimensions are authenticated separately by
        # the schedule. No physical scale or sill/head chain is supplied, so the
        # positive area must come from explicit frame dimensions rather than a
        # resolved 3-D void.
        page.draw_rect(fitz.Rect(20, 20, 320, 340), color=(0, 0, 0), width=1)
        page.draw_rect(fitz.Rect(360, 20, 740, 340), color=(0, 0, 0), width=1)
        page.insert_text((75, 320), "GROUND FLOOR PLAN", fontsize=11)
        page.insert_text((455, 320), "WINDOW SCHEDULE", fontsize=11)

        _opening(page, 60, 100)
        page.insert_text((118, 107), "W1", fontsize=8)

        xs = (390.0, 500.0, 625.0)
        for text, x in zip(("MARK", width_heading, height_heading), xs):
            page.insert_text((x, 145), text, fontsize=8)
        for text, x in zip(("W1", "900", "2100"), xs):
            page.insert_text((x, 170), text, fontsize=8)

        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _composition(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="live-opening-frame-area-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-opening-frame-area",
        source_bytes=payload,
        source_locator="memory://live-opening-frame-area.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    return compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )


def test_explicit_frame_dimensions_publish_gross_frame_opening_area() -> None:
    composition = _composition(_frame_schedule_sheet())

    assert len(composition.canonical_openings) == 1
    opening = composition.canonical_openings[0]
    assert opening.opening_kind == "window"
    assert opening.type_mark == "W1"
    assert opening.schedule_dimension_basis == "frame"
    assert opening.schedule_declared_width_mm == 900
    assert opening.schedule_declared_height_mm == 2100
    assert opening.area_basis == "schedule_frame_outer_dimensions"
    assert opening.area_m2 == 1.89
    assert opening.schedule_binding_record_id
    assert opening.schedule_binding_record_id in opening.evidence_ids

    quantities = publish_live_opening_area_quantities(composition)
    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.value == 1.89
    assert quantity.unit == "m2"
    assert quantity.authority == LIVE_OPENING_FRAME_AREA_QUANTITY_AUTHORITY
    assert quantity.metadata["area_basis"] == "schedule_frame_outer_dimensions"
    assert quantity.metadata["schedule_dimension_basis"] == "frame"
    assert quantity.input_entity_ids == (opening.canonical_opening_id,)


def test_generic_width_height_schedule_does_not_become_gross_frame_area() -> None:
    composition = _composition(
        _frame_schedule_sheet(
            width_heading="WIDTH",
            height_heading="HEIGHT",
        )
    )

    assert len(composition.canonical_openings) == 1
    opening = composition.canonical_openings[0]
    assert opening.schedule_dimension_basis in {None, ""}
    quantities = publish_live_opening_area_quantities(composition)
    assert all(
        quantity.metadata.get("area_basis") != "schedule_frame_outer_dimensions"
        for quantity in quantities
    )
