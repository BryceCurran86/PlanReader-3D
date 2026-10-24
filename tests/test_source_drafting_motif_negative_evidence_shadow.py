"""Tests for producer-owned source drafting motif negative evidence shadow authority (Items 5 & 28)."""

from __future__ import annotations

import copy
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_drafting_motif_negative_evidence_shadow import (
    EMPTY_CANDIDATE_SEGMENTS,
    SOURCE_DRAFTING_MOTIF_CANDIDATE,
    SOURCE_DRAFTING_MOTIF_RESOLVED,
    SOURCE_LINEAGE_MISMATCH,
    SUBTYPE_DIMENSION_TICK,
    SUBTYPE_FURNITURE_FIXTURE,
    SUBTYPE_GRID_LINE,
    SUBTYPE_HATCH_STROKE,
    SUBTYPE_STRUCTURAL_WALL_RUN,
    SUBTYPE_UNPROVEN_DRAFTING_INK,
    SourceDraftingMotifRecord,
    SourceDraftingMotifResult,
    SourceDraftingMotifSelector,
    SourceDraftingSegment,
    evaluate_source_drafting_motif_negative_evidence_shadow,
)

VALID_SHA = "c" * 64


def _selector(page_id: str = "page_03") -> SourceDraftingMotifSelector:
    return SourceDraftingMotifSelector(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256=VALID_SHA,
        snapshot_id="snap_01",
        page_id=page_id,
    )


def test_positive_dimension_tick_identification():
    """Short 4.5 pt segments angled at 45 degrees are classified as dimension ticks."""
    ticks = [
        SourceDraftingSegment("TICK_1", (100.0, 100.0), (103.18, 103.18)),  # len 4.5 pt, 45 deg
        SourceDraftingSegment("TICK_2", (200.0, 100.0), (203.18, 103.18)),
    ]
    sel = _selector()
    res = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=ticks)

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_DRAFTING_MOTIF_RESOLVED in res.reason_codes
    record = res.record
    assert isinstance(record, SourceDraftingMotifRecord)
    assert record.dimension_tick_count == 2
    assert record.verdicts[0].subtype == SUBTYPE_DIMENSION_TICK
    assert record.verdicts[1].subtype == SUBTYPE_DIMENSION_TICK


def test_positive_grid_line_identification():
    """Long thin stroke (500 pt, width 0.2 pt) without partner is classified as grid line."""
    grid = [
        SourceDraftingSegment("GRID_A", (50.0, 300.0), (550.0, 300.0), stroke_width=0.2),
    ]
    sel = _selector()
    res = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=grid)

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    record = res.record
    assert record.grid_line_count == 1
    assert record.verdicts[0].subtype == SUBTYPE_GRID_LINE


def test_positive_hatch_stroke_array_identification():
    """Array of 5 parallel strokes with 3 pt spacing is classified as hatch strokes."""
    hatch = [
        SourceDraftingSegment(f"HATCH_{i}", (10.0 + 3.0 * i, 10.0), (30.0 + 3.0 * i, 30.0))
        for i in range(5)
    ]
    sel = _selector()
    res = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=hatch)

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    record = res.record
    assert record.hatch_stroke_count == 5
    assert all(v.subtype == SUBTYPE_HATCH_STROKE for v in record.verdicts)


def test_positive_furniture_fixture_closed_loop():
    """Small closed rectangle representing a sink/symbol is classified as furniture/fixture."""
    fixture_segs = [
        SourceDraftingSegment("FIX_1", (50.0, 50.0), (70.0, 50.0), path_id="PATH_SINK"),
        SourceDraftingSegment("FIX_2", (70.0, 50.0), (70.0, 65.0), path_id="PATH_SINK"),
        SourceDraftingSegment("FIX_3", (70.0, 65.0), (50.0, 65.0), path_id="PATH_SINK"),
        SourceDraftingSegment("FIX_4", (50.0, 65.0), (50.0, 50.0), path_id="PATH_SINK"),
    ]
    sel = _selector()
    res = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=fixture_segs)

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    record = res.record
    assert record.furniture_fixture_count == 4
    assert all(v.subtype == SUBTYPE_FURNITURE_FIXTURE for v in record.verdicts)


def test_protection_genuine_paired_wall_faces():
    """Segments participating in verified wall faces are strictly protected from negative classification."""
    wall_segs = [
        SourceDraftingSegment("WALL_FACE_1", (100.0, 100.0), (300.0, 100.0), stroke_width=1.2),
        SourceDraftingSegment("WALL_FACE_2", (100.0, 110.0), (300.0, 110.0), stroke_width=1.2),
    ]
    sel = _selector()
    res = evaluate_source_drafting_motif_negative_evidence_shadow(
        sel,
        candidate_segments=wall_segs,
        known_wall_primitive_ids=["WALL_FACE_1", "WALL_FACE_2"],
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    record = res.record
    assert record.structural_wall_run_count == 2
    assert record.dimension_tick_count == 0
    assert record.grid_line_count == 0
    assert all(v.subtype == SUBTYPE_STRUCTURAL_WALL_RUN for v in record.verdicts)


def test_negative_empty_segments():
    """Empty candidate segments list fails closed."""
    sel = _selector()
    res = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=[])
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert EMPTY_CANDIDATE_SEGMENTS in res.reason_codes


def test_negative_lineage_mismatch():
    """Invalid selector or SHA-256 fails closed."""
    with pytest.raises(ValueError):
        SourceDraftingMotifSelector("d", "r", "not_sha", "s", "p")

    seg = SourceDraftingSegment("S1", (0.0, 0.0), (10.0, 10.0))
    res = evaluate_source_drafting_motif_negative_evidence_shadow(
        None,  # type: ignore
        candidate_segments=[seg],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_LINEAGE_MISMATCH in res.reason_codes


def test_metamorphic_translation_invariance():
    """Translating linework preserves motif classifications and counts."""
    ticks = [
        SourceDraftingSegment("TICK_1", (100.0, 100.0), (103.18, 103.18)),
        SourceDraftingSegment("TICK_2", (200.0, 100.0), (203.18, 103.18)),
    ]
    sel = _selector()
    res1 = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=ticks)
    assert res1.status == EvidenceResolutionStatus.CANDIDATE

    # Shift by dx=120, dy=-75
    dx, dy = 120.0, -75.0
    ticks_shifted = [
        SourceDraftingSegment(
            t.primitive_id,
            (t.start_pt[0] + dx, t.start_pt[1] + dy),
            (t.end_pt[0] + dx, t.end_pt[1] + dy),
        )
        for t in ticks
    ]
    res2 = evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=ticks_shifted)
    assert res2.status == EvidenceResolutionStatus.CANDIDATE
    assert res1.record.dimension_tick_count == res2.record.dimension_tick_count


def test_input_no_mutation():
    """Verify input collections and objects are never mutated."""
    ticks = [
        SourceDraftingSegment("TICK_1", (100.0, 100.0), (103.18, 103.18)),
    ]
    ticks_copy = copy.deepcopy(ticks)
    sel = _selector()
    evaluate_source_drafting_motif_negative_evidence_shadow(sel, candidate_segments=ticks)
    assert ticks == ticks_copy
