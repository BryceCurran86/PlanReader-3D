from __future__ import annotations

import fitz

from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_opening_count_quantity_publication import (
    publish_live_authenticated_opening_count_quantities,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
def _floor_plan_with_schedule_quantity(*, quantity: int | None) -> bytes:
    """One floor-plan opening plus a separately authenticated schedule page."""
    doc = fitz.open()
    try:
        plan = doc.new_page(width=760.0, height=650.0)
        plan.insert_text(fitz.Point(20.0, 24.0), "GROUND FLOOR PLAN")
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((145.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((145.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((145.0, 100.0), (145.0, 110.0)),
        ):
            plan.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        plan.insert_text(fitz.Point(112.0, 106.0), "W1")

        schedule = doc.new_page(width=760.0, height=650.0)
        schedule.insert_text(fitz.Point(20.0, 24.0), "WINDOW SCHEDULE")
        headings = ["MARK", "WIDTH", "HEIGHT"]
        values = ["W1", "900", "2100"]
        if quantity is not None:
            headings.append("QTY")
            values.append(str(int(quantity)))
        xs = (50.0, 180.0, 310.0, 440.0)
        for text, x in zip(headings, xs):
            schedule.insert_text(fitz.Point(x, 120.0), text)
        for text, x in zip(values, xs):
            schedule.insert_text(fitz.Point(x, 150.0), text)

        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _count_quantities(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="live-opening-count-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-opening-count",
        source_bytes=payload,
        source_locator="memory://live-opening-count.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    quantities = publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    return source, wall_opening, quantities


def test_explicit_schedule_quantity_reaches_generic_count_quantity() -> None:
    _source, wall_opening, quantities = _count_quantities(
        _floor_plan_with_schedule_quantity(quantity=1)
    )

    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.family == "opening_count"
    assert quantity.value == 1.0
    assert quantity.unit == "ea"
    assert len(quantity.input_entity_ids) == 1
    assert quantity.metadata["schedule_corroborated"] is True
    assert quantity.metadata["opening_mark"] == "W1"

    objects = tuple(
        trace
        for trace in wall_opening.opening_bindings
        if trace.opening_identity_id in quantity.input_entity_ids
    )
    assert len(objects) == 1


def test_explicit_schedule_quantity_closes_coverage_quantity_link() -> None:
    source, wall_opening, quantities = _count_quantities(
        _floor_plan_with_schedule_quantity(quantity=1)
    )
    assert quantities

    from pb_live_physical_opening_void_composition import (
        compose_live_physical_opening_voids,
    )

    composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    summaries, gaps = collect_live_canonical_coverage(
        objects=composition.canonical_openings,
        quantities=quantities,
        registry_run_scope="live-opening-count-regression",
    )
    assert all(
        "explicit_quantity_link_unavailable" not in tuple(reasons)
        for reasons in gaps.values()
    )
    records = [
        record
        for summary in summaries
        for record in summary.object_records
        if record.object_id in quantities[0].input_entity_ids
    ]
    assert len(records) == 1
    assert quantities[0].quantity_id in records[0].quantity_ids


def test_implicit_schedule_default_never_becomes_commercial_count() -> None:
    _source, _wall_opening, quantities = _count_quantities(
        _floor_plan_with_schedule_quantity(quantity=None)
    )
    assert quantities == ()
