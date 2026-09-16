"""Independent regressions for schedule-opening instance binding authority v2.

These attacks cover two authority propositions not exercised by the original
Route-B suite:

1. two distinct schedule rows remain two distinct rows even when their parsed
   dimensions are identical; exact governing-row identity cannot be selected by
   lexical/page ordering, and
2. plan tags must lie inside the actual jamb-bounded opening aperture, not merely
   inside the bounding box of the six G17 support segments.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_schedule_opening_instance_binding_authority import (
    BINDING_AMBIGUOUS_ROWS,
    BINDING_NO_CONTAINED_TAG,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SCOPE = "schedule-binding-v2-regression:page-1"


def _draw_opening(page: fitz.Page) -> None:
    # Two wall faces, interrupted from x=100..140, closed by two jambs.
    for first, second in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)


def _insert_schedule(page: fitz.Page, rows: tuple[tuple[str, str, str], ...]) -> None:
    y = 500.0
    for row in rows:
        for text, x in zip(row, (50.0, 150.0, 250.0)):
            page.insert_text(fitz.Point(x, y), text, color=(0, 0, 0))
        y += 30.0


def _ingest(payload: bytes, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="schedule-binding-v2-independent-regression",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published


def _opening_selector(producer: SourceVisibilityProducer, published) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(producer.authority())
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS:
            return selector
    raise AssertionError("fixture must prove one G17 opening")


def _bind(producer: SourceVisibilityProducer, selector: ObservationSelector):
    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(producer)
    return binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)


def test_distinct_identical_schedule_rows_do_not_mint_exact_row_identity() -> None:
    """Two different producer-owned rows are ambiguous even if values agree."""
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page)
    page.insert_text(fitz.Point(112.0, 106.0), "W1", color=(0, 0, 0))
    _insert_schedule(
        page,
        (
            ("MARK", "WIDTH", "HEIGHT"),
            ("W1", "900", "2100"),
            ("W1", "900", "2100"),
        ),
    )
    payload = doc.tobytes()
    doc.close()

    producer, published = _ingest(payload, "sched-identical-duplicate-rows")
    result = _bind(producer, _opening_selector(producer, published))

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes
    assert result.record is None


def test_tag_on_adjacent_wall_segment_is_not_inside_opening_aperture() -> None:
    """The six-segment support bbox is wider than the physical aperture.

    W1 at x=190 is on the right-hand wall continuation. It is inside the bbox
    of all six G17 support segments (x=20..220) but outside the real opening
    aperture (x=100..140), so it cannot establish per-instance tag binding.
    """
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page)
    page.insert_text(fitz.Point(190.0, 106.0), "W1", color=(0, 0, 0))
    _insert_schedule(page, (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    payload = doc.tobytes()
    doc.close()

    producer, published = _ingest(payload, "sched-adjacent-wall-tag")
    result = _bind(producer, _opening_selector(producer, published))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes
    assert result.record is None
