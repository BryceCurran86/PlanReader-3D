"""A08/A09 tests: Multi-page schedule extraction and canonical tag-to-schedule association with ambiguity guards."""
from __future__ import annotations

import fitz

from pb_opening_evidence_v170 import DIMENSION_BASIS_ROUGH_OPENING, OpeningEvidence
from pb_opening_schedule_v171 import (
    ScheduleEntry,
    enrich_opening_evidence,
    parse_schedule_pages,
)


def _schedule_doc() -> fitz.Document:
    doc = fitz.open()
    # Page 1: standard door schedule
    p1 = doc.new_page(width=842.0, height=595.0)
    p1.insert_text((40, 60), "MARK", fontsize=10)
    p1.insert_text((160, 60), "WIDTH", fontsize=10)
    p1.insert_text((280, 60), "HEIGHT", fontsize=10)
    p1.insert_text((40, 90), "D1", fontsize=10)
    p1.insert_text((160, 90), "820", fontsize=10)
    p1.insert_text((280, 90), "2040", fontsize=10)
    # Page 2: continuation schedule
    p2 = doc.new_page(width=842.0, height=595.0)
    p2.insert_text((40, 60), "MARK", fontsize=10)
    p2.insert_text((160, 60), "WIDTH", fontsize=10)
    p2.insert_text((280, 60), "HEIGHT", fontsize=10)
    p2.insert_text((40, 90), "W7", fontsize=10)
    p2.insert_text((160, 90), "1800", fontsize=10)
    p2.insert_text((280, 90), "1200", fontsize=10)
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def test_parse_schedule_pages_deterministic_multipage_order_and_provenance() -> None:
    doc = _schedule_doc()
    try:
        # Pass pages out of order; output must be deterministically ordered by page_no
        entries = parse_schedule_pages([(2, doc[1]), (1, doc[0])])
        by_mark = {e.type_mark: e for e in entries}
        assert "D1" in by_mark and by_mark["D1"].page_no == 1
        assert (by_mark["D1"].width_mm, by_mark["D1"].height_mm) == (820, 2040)
        assert "W7" in by_mark and by_mark["W7"].page_no == 2
        assert (by_mark["W7"].width_mm, by_mark["W7"].height_mm) == (1800, 1200)
    finally:
        doc.close()


def test_enrich_opening_evidence_matches_canonical_marks_and_rejects_unlabeled() -> None:
    inst_door = OpeningEvidence(
        type_mark="D01",
        wall_ref="W1",
        extraction_method="vector_plan",
    )
    inst_unlabeled = OpeningEvidence(
        type_mark="",
        wall_ref="W2",
        extraction_method="vector_plan",
    )
    sched = [
        ScheduleEntry(
            type_mark="D1",
            width_mm=820,
            height_mm=2040,
            dimension_basis=DIMENSION_BASIS_ROUGH_OPENING,
            page_no=1,
            parse_source="header_separate",
        )
    ]
    out = enrich_opening_evidence([inst_door, inst_unlabeled], sched)
    assert out[0].type_mark == "D01"
    assert out[0].width_m == 0.82
    assert out[0].height_m == 2.04
    assert out[1].type_mark == ""
    assert out[1].width_m is None


def test_enrich_opening_evidence_abstains_on_cross_page_canonical_duplicate_conflict() -> None:
    inst = OpeningEvidence(
        type_mark="D01",
        wall_ref="W1",
        extraction_method="vector_plan",
    )
    conflicting = [
        ScheduleEntry(
            type_mark="D01",
            width_mm=820,
            height_mm=2040,
            dimension_basis=DIMENSION_BASIS_ROUGH_OPENING,
            page_no=1,
            parse_source="header_separate",
        ),
        ScheduleEntry(
            type_mark="D1",
            width_mm=920,
            height_mm=2040,
            dimension_basis=DIMENSION_BASIS_ROUGH_OPENING,
            page_no=2,
            parse_source="header_separate",
        ),
    ]
    out = enrich_opening_evidence([inst], conflicting)
    assert out[0].width_m is None
    assert out[0].height_m is None
    assert any(obs.get("status") == "ambiguous" for obs in out[0].source_observations)


def test_enrich_opening_evidence_picks_highest_provenance_for_agreeing_canonical_duplicates() -> None:
    inst = OpeningEvidence(
        type_mark="W07",
        wall_ref="W3",
        extraction_method="vector_plan",
    )
    agreeing = [
        ScheduleEntry(
            type_mark="W7",
            width_mm=1800,
            height_mm=1200,
            dimension_basis=DIMENSION_BASIS_ROUGH_OPENING,
            page_no=1,
            parse_source="heuristic",
        ),
        ScheduleEntry(
            type_mark="W07",
            width_mm=1800,
            height_mm=1200,
            dimension_basis=DIMENSION_BASIS_ROUGH_OPENING,
            page_no=2,
            parse_source="header_separate",
        ),
    ]
    out = enrich_opening_evidence([inst], agreeing)
    assert out[0].width_m == 1.8
    assert out[0].height_m == 1.2
    assert out[0].dimension_confidence == 0.8
