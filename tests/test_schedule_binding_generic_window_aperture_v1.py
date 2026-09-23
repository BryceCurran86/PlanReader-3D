from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_GEOMETRY_UNAVAILABLE,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _opening_selector(source: SourceVisibilityProducer, published, expected_pattern: str):
    physical = PhysicalOpeningAuthority(source.authority())
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
            and result.existence_record.structural_pattern == expected_pattern
        ):
            return selector
    raise AssertionError(f"fixture must prove {expected_pattern}")


def _insert_schedule(page: fitz.Page, mark: str) -> None:
    y = 220.0
    for row in (("MARK", "WIDTH", "HEIGHT"), (mark, "900", "2100")):
        for text, x in zip(row, (50.0, 150.0, 250.0)):
            page.insert_text(fitz.Point(x, y), text, color=(0, 0, 0))
        y += 30.0


def test_gap_window_jamb_pair_has_source_backed_aperture_for_schedule_binding() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=350)
    page.insert_text(fitz.Point(30, 30), "GROUND FLOOR PLAN", color=(0, 0, 0))
    for first, second in (
        ((20.0, 100.0), (250.0, 100.0)),
        ((290.0, 100.0), (650.0, 100.0)),
        ((250.0, 100.0), (250.0, 140.0)),
        ((290.0, 100.0), (290.0, 140.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(262.0, 122.0), "W1", color=(0, 0, 0))
    _insert_schedule(page, "W1")
    payload = doc.tobytes()
    doc.close()

    source = SourceVisibilityProducer(
        producer_method="window-gap-aperture-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="window-gap-aperture",
        source_bytes=payload,
        source_locator="memory://window-gap-aperture.pdf",
    )
    selector = _opening_selector(
        source,
        published,
        GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    )

    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    result = binder.publish_scope(
        opening_selector=selector,
        decision_scope_id="window-gap-aperture:scope",
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.tag_mark == "W1"
    assert result.record.schedule_row_width_mm == 900
    assert result.record.schedule_row_height_mm == 2100


def test_gap_door_single_jamb_does_not_invent_opposite_aperture_depth() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=350)
    page.insert_text(fitz.Point(30, 30), "GROUND FLOOR PLAN", color=(0, 0, 0))
    for first, second in (
        ((20.0, 100.0), (250.0, 100.0)),
        ((310.0, 100.0), (650.0, 100.0)),
        ((250.0, 100.0), (250.0, 140.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(270.0, 122.0), "D1", color=(0, 0, 0))
    _insert_schedule(page, "D1")
    payload = doc.tobytes()
    doc.close()

    source = SourceVisibilityProducer(
        producer_method="door-gap-aperture-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="door-gap-aperture",
        source_bytes=payload,
        source_locator="memory://door-gap-aperture.pdf",
    )
    selector = _opening_selector(
        source,
        published,
        GAP_CORROBORATED_DOOR_JAMB_LEAF,
    )

    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    result = binder.publish_scope(
        opening_selector=selector,
        decision_scope_id="door-gap-aperture:scope",
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert BINDING_GEOMETRY_UNAVAILABLE in result.reason_codes
