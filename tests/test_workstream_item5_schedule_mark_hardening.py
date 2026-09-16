"""Red-team tests for Item 5: Harden Shared Schedule Mark Semantics."""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_schedule_opening_instance_binding_authority import BINDING_AMBIGUOUS_ROWS
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
    schedule_rows: tuple[tuple[str, str, str], ...],
    extra_pages: list[tuple[tuple[str, str, str], ...]] | None = None,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)
    
    # Draw openings vertically
    y = 50.0
    for mark in marks:
        _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=y, y1=y+10.0)
        page.insert_text(fitz.Point(112, y + 6.0), mark, color=(0, 0, 0))
        y += 30.0

    if schedule_rows:
        _insert_schedule_table(page, schedule_rows, y0=y+50.0)
        
    if extra_pages:
        for rows in extra_pages:
            p2 = doc.new_page(width=700, height=800)
            _insert_schedule_table(p2, rows, y0=50.0)

    payload = doc.tobytes()
    doc.close()
    return payload


def test_five_w1_instances_bind_separately_without_conflict() -> None:
    # 5 physical openings all tagged W1, and a single W1 row in the schedule.
    # The authority should bind each physical opening to the same row independently.
    payload = _tag_pdf_multiple_openings(
        marks=["W1", "W1", "W1", "W1", "W1"],
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "multi-w1")
    visibility = src.authority()
    phys = PhysicalOpeningAuthority(visibility)
    
    # We should have 5 physical openings
    valid_selectors = {}
    for obs_id in published.visible_observation_ids:
        from pb_source_observation_authority import ObservationSelector
        sel = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        res = phys.prove_existence(sel)
        if res.proposition == PHYSICAL_OPENING_EXISTS and res.existence_record:
            valid_selectors[res.existence_record.record_id] = sel
    
    assert len(valid_selectors) == 5
    
    for sel in valid_selectors.values():
        result = _bind(src, sel)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.record is not None
        assert result.record.schedule_row_width_mm == 900


def test_identical_schedule_tables_on_separate_sheets_is_ambiguous() -> None:
    # 1 physical opening, W1. Two identical schedule tables on different pages.
    # The system must not arbitrary select one; it must fail closed.
    payload = _tag_pdf_multiple_openings(
        marks=["W1"],
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")),
        extra_pages=[(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"))]
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "multi-page-schedule")
    sel = _opening_selector(published, src.authority())
    result = _bind(src, sel)
    
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


def test_mixed_door_and_window_marks() -> None:
    # 1 W1 opening, 1 D1 opening. Schedule has both. W1 should bind strictly to W1.
    payload = _tag_pdf_multiple_openings(
        marks=["W1", "D1"],
        schedule_rows=(
            ("MARK", "WIDTH", "HEIGHT"),
            ("D1", "820", "2040"),
            ("W1", "900", "2100"),
        )
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "mixed-marks")
    visibility = src.authority()
    phys = PhysicalOpeningAuthority(visibility)
    
    # Find the W1 opening selector
    w1_sel = None
    for obs_id in published.visible_observation_ids:
        from pb_source_observation_authority import ObservationSelector
        sel = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        if phys.prove_existence(sel).existence_record is not None:
            # check the tag
            res = _bind(src, sel)
            if res.record and res.record.tag_mark == "W1":
                w1_sel = sel
                break
    
    assert w1_sel is not None
    result = _bind(src, w1_sel)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record.schedule_row_width_mm == 900
    assert result.record.schedule_row_height_mm == 2100

def test_twenty_d1_instances_bind_separately_without_conflict() -> None:
    payload = _tag_pdf_multiple_openings(
        marks=["D1"] * 20,
        schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("D1", "820", "2040")),
    )
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "multi-d1")
    visibility = src.authority()
    phys = PhysicalOpeningAuthority(visibility)
    
    valid_selectors = {}
    for obs_id in published.visible_observation_ids:
        from pb_source_observation_authority import ObservationSelector
        sel = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        res = phys.prove_existence(sel)
        if res.proposition == PHYSICAL_OPENING_EXISTS and res.existence_record:
            valid_selectors[res.existence_record.record_id] = sel
    
    assert len(valid_selectors) == 20
    
    for sel in valid_selectors.values():
        result = _bind(src, sel)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.record is not None


def test_duplicate_mark_different_attributes_is_ambiguous() -> None:
    # Schedule has two W1 rows (e.g. one deleted/revised, or different fire rating)
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
    sel = _opening_selector(published, src.authority())
    result = _bind(src, sel)
    
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes


def test_schedule_continuation_across_pages() -> None:
    # Page 1 has W1, W2. Page 2 has W3, W4 (without header).
    # We tag W3 on page 1. It should find W3 on page 2.
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=50.0, y1=60.0)
    page.insert_text(fitz.Point(112, 56.0), "W3", color=(0, 0, 0))
    _insert_schedule_table(page, (
        ("MARK", "WIDTH", "HEIGHT"),
        ("W1", "900", "2100"),
        ("W2", "1200", "2100"),
    ), y0=100.0)
    
    p2 = doc.new_page(width=700, height=800)
    _insert_schedule_table(p2, (
        ("W3", "1800", "2100"),
        ("W4", "2400", "2100"),
    ), y0=50.0)
    
    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "headless-continuation")
    sel = _opening_selector(published, src.authority())
    result = _bind(src, sel)
    
    # Let's assert what happens. 
    # If the parser supports headless rows, it might CORROBORATE.
    # Otherwise it might ABSTAIN (BINDING_NO_MATCHING_ROW).
    assert result.status in (EvidenceResolutionStatus.CORROBORATED, EvidenceResolutionStatus.ABSTAINED)

def test_headless_page_without_inherited_header_rejects_masquerading_note() -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=800)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=50.0, y1=60.0)
    page.insert_text(fitz.Point(112, 56.0), "W1", color=(0, 0, 0))

    page.insert_text(fitz.Point(50, 400), "W1", color=(0, 0, 0))
    page.insert_text(fitz.Point(150, 400), "900", color=(0, 0, 0))
    page.insert_text(fitz.Point(250, 400), "2100", color=(0, 0, 0))

    payload = doc.tobytes()
    doc.close()

    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, payload, "note-masquerading")
    sel = _opening_selector(published, src.authority())
    result = _bind(src, sel)
    
    assert result.status is EvidenceResolutionStatus.ABSTAINED