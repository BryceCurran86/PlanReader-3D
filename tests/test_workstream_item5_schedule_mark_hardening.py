"""Red-team tests for shared schedule-mark semantics after merged #383."""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_schedule_opening_instance_binding_authority import BINDING_AMBIGUOUS_ROWS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _bind,
    _draw_opening,
    _ingest,
    _insert_schedule_table,
    _opening_selector,
)


def _tag_pdf_multiple_openings(
    *,
    marks: list[str],
    schedule_rows: tuple[tuple[str, ...], ...],
    extra_pages: list[tuple[tuple[str, ...], ...]] | None = None,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)

    y = 50.0
    for mark in marks:
        _draw_opening(
            page,
            x0=20.0,
            gap0=100.0,
            gap1=140.0,
            x1=220.0,
            y0=y,
            y1=y + 10.0,
        )
        page.insert_text(fitz.Point(112, y + 6.0), mark, color=(0, 0, 0))
        y += 30.0

    if schedule_rows:
        _insert_schedule_table(page, schedule_rows, y0=y + 50.0)

    if extra_pages:
        for rows in extra_pages:
            extra = doc.new_page(width=700, height=800)
            _insert_schedule_table(extra, rows, y0=50.0)

    payload = doc.tobytes()
    doc.close()
    return payload


def _physical_selectors(published, visibility) -> dict[str, ObservationSelector]:
    physical = PhysicalOpeningAuthority(visibility)
    selectors: dict[str, ObservationSelector] = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS and result.existence_record:
            selectors[result.existence_record.record_id] = selector
    return selectors


def test_five_w1_instances_bind_separately_without_conflict() -> None:
    payload = _tag_pdf_multiple_openings(
        marks=["W1"] * 5,
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "multi-w1")
    selectors = _physical_selectors(published, src.authority())

    assert len(selectors) == 5
    record_ids: set[str] = set()
    for selector in selectors.values():
        result = _bind(src, selector)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.record is not None
        assert result.record.schedule_row_width_mm == 900
        record_ids.add(result.record.opening_record_id)
    assert len(record_ids) == 5


def test_twenty_d1_instances_bind_separately_without_conflict() -> None:
    payload = _tag_pdf_multiple_openings(
        marks=["D1"] * 20,
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("D1", "820", "2040")),
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "multi-d1")
    selectors = _physical_selectors(published, src.authority())

    assert len(selectors) == 20
    opening_ids: set[str] = set()
    for selector in selectors.values():
        result = _bind(src, selector)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.record is not None
        opening_ids.add(result.record.opening_record_id)
    assert len(opening_ids) == 20


def test_identical_schedule_tables_on_separate_sheets_is_ambiguous() -> None:
    payload = _tag_pdf_multiple_openings(
        marks=["W1"],
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
        extra_pages=[
            (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"))
        ],
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "multi-page-schedule")
    result = _bind(src, _opening_selector(published, src.authority()))

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


def test_mixed_door_and_window_marks_bind_by_exact_contained_mark() -> None:
    payload = _tag_pdf_multiple_openings(
        marks=["W1", "D1"],
        schedule_rows=(
            ("MARK", "WIDTH", "HEIGHT"),
            ("D1", "820", "2040"),
            ("W1", "900", "2100"),
        ),
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "mixed-marks")
    selectors = _physical_selectors(published, src.authority())

    records = []
    for selector in selectors.values():
        result = _bind(src, selector)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.record is not None
        records.append(result.record)

    by_mark = {record.tag_mark: record for record in records}
    assert by_mark["W1"].schedule_row_width_mm == 900
    assert by_mark["W1"].schedule_row_height_mm == 2100
    assert by_mark["D1"].schedule_row_width_mm == 820
    assert by_mark["D1"].schedule_row_height_mm == 2040


def test_duplicate_mark_different_attributes_is_ambiguous() -> None:
    payload = _tag_pdf_multiple_openings(
        marks=["W1"],
        schedule_rows=(
            ("MARK", "WIDTH", "HEIGHT", "FIRE"),
            ("W1", "900", "2100", "60"),
            ("W1", "900", "2100", "-"),
        ),
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "ambiguous-attributes")
    result = _bind(src, _opening_selector(published, src.authority()))

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


def test_adding_conflicting_same_mark_row_only_weakens_authority() -> None:
    unique_payload = _tag_pdf_multiple_openings(
        marks=["W1"],
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
    )
    unique_src = SourceVisibilityProducer(
        producer_method="test", producer_version="1.0"
    )
    unique_published = _ingest(unique_src, unique_payload, "unique-row")
    unique_result = _bind(
        unique_src,
        _opening_selector(unique_published, unique_src.authority()),
    )
    assert unique_result.status is EvidenceResolutionStatus.CORROBORATED

    conflicting_payload = _tag_pdf_multiple_openings(
        marks=["W1"],
        schedule_rows=(
            ("MARK", "WIDTH", "HEIGHT"),
            ("W1", "900", "2100"),
            ("W1", "900", "2000"),
        ),
    )
    conflicting_src = SourceVisibilityProducer(
        producer_method="test", producer_version="1.0"
    )
    conflicting_published = _ingest(
        conflicting_src, conflicting_payload, "conflicting-row"
    )
    conflicting_result = _bind(
        conflicting_src,
        _opening_selector(conflicting_published, conflicting_src.authority()),
    )
    assert conflicting_result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in conflicting_result.reason_codes


def test_headless_schedule_continuation_across_pages_abstains() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=50.0,
        y1=60.0,
    )
    page.insert_text(fitz.Point(112, 56.0), "W3", color=(0, 0, 0))
    _insert_schedule_table(
        page,
        (
            ("MARK", "WIDTH", "HEIGHT"),
            ("W1", "900", "2100"),
            ("W2", "1200", "2100"),
        ),
        y0=100.0,
    )

    continuation = doc.new_page(width=700, height=800)
    _insert_schedule_table(
        continuation,
        (("W3", "1800", "2100"), ("W4", "2400", "2100")),
        y0=50.0,
    )

    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "headless-continuation")
    result = _bind(src, _opening_selector(published, src.authority()))

    # Column alignment and row spacing alone cannot prove that page 2 continues
    # page 1's schedule. A producer-owned continuation proposition would be needed.
    assert result.status is EvidenceResolutionStatus.ABSTAINED


def test_headless_page_rejects_masquerading_note() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=50.0,
        y1=60.0,
    )
    page.insert_text(fitz.Point(112, 56.0), "W1", color=(0, 0, 0))
    page.insert_text(fitz.Point(50, 400), "W1", color=(0, 0, 0))
    page.insert_text(fitz.Point(150, 400), "900", color=(0, 0, 0))
    page.insert_text(fitz.Point(250, 400), "2100", color=(0, 0, 0))

    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "note-masquerading")
    result = _bind(src, _opening_selector(published, src.authority()))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
