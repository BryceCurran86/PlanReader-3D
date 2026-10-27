"""Tests for producer-owned source full-plan recovery engine shadow authority (Workstream C, Items 27 & 30)."""

from __future__ import annotations

import copy
from dataclasses import replace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_finish_occurrence_ownership_shadow import SourceFloorFinishMark
from pb_source_full_plan_recovery_engine_shadow import (
    EMPTY_PAGE_PAYLOADS,
    PAGE_COMPLEXITY_BLOCKED,
    PAGE_QUARANTINED_SAFELY,
    SOURCE_FULL_PLAN_ENGINE_ABSTAINED,
    SOURCE_FULL_PLAN_ENGINE_CANDIDATE,
    SOURCE_FULL_PLAN_ENGINE_RESOLVED,
    SOURCE_FULL_PLAN_PARTIAL_RECOVERY,
    SOURCE_LINEAGE_MISMATCH,
    SourceFullPlanEngineRecord,
    SourceFullPlanEngineResult,
    SourceFullPlanEngineSelector,
    SourcePageExecutionVerdict,
    SourcePageInputPayload,
    execute_source_full_plan_recovery_engine_shadow,
)
from pb_source_room_boundary_doorway_opening_shadow import (
    SourceRoomOpeningCandidate,
    SourceRoomWallEdge,
)

VALID_SHA = "e" * 64


def _selector() -> SourceFullPlanEngineSelector:
    return SourceFullPlanEngineSelector(
        document_id="doc_q5446_multi",
        revision_id="rev_01",
        source_sha256=VALID_SHA,
        snapshot_id="snap_01",
    )


def _healthy_page(page_id: str = "page_01") -> SourcePageInputPayload:
    # A simple rectangular room: 3 walls, 1 doorway opening
    poly = (
        (100.0, 100.0),
        (200.0, 100.0),
        (200.0, 200.0),
        (100.0, 200.0),
    )
    walls = (
        SourceRoomWallEdge("W_TOP", (100.0, 100.0), (200.0, 100.0)),
        SourceRoomWallEdge("W_RIGHT", (200.0, 100.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_LEFT", (100.0, 200.0), (100.0, 100.0)),
    )
    openings = (
        SourceRoomOpeningCandidate("DOOR_01", (100.0, 200.0), (200.0, 200.0)),
    )
    finish = (
        SourceFloorFinishMark("OCC_FT2", page_id, "FT2", (150.0, 150.0)),
    )
    return SourcePageInputPayload(
        page_id=page_id,
        page_type="floor_plan",
        room_polygon_candidates=(("ROOM_A", poly),),
        wall_edges=walls,
        opening_candidates=openings,
        finish_mark_candidates=finish,
    )


def test_positive_multi_page_full_recovery():
    """Two healthy floor plan pages both successfully evaluated."""
    page1 = _healthy_page("page_01")
    page2 = _healthy_page("page_02")
    sel = _selector()

    res = execute_source_full_plan_recovery_engine_shadow(sel, pages=[page1, page2])

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_FULL_PLAN_ENGINE_RESOLVED in res.reason_codes
    assert SOURCE_FULL_PLAN_ENGINE_CANDIDATE in res.reason_codes

    record = res.record
    assert isinstance(record, SourceFullPlanEngineRecord)
    assert record.total_pages_evaluated == 2
    assert record.successful_pages_count == 2
    assert record.quarantined_pages_count == 0
    assert record.total_rooms_recovered == 2
    assert record.total_finish_zones_recovered == 2
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False
    assert record.diagnostic_only is True


def test_positive_partial_pipeline_failure_isolation():
    """Page 1 healthy + Page 2 blocked by complexity: healthy page succeeds, blocked page quarantined."""
    page1 = _healthy_page("page_01")
    page2_blocked = SourcePageInputPayload(
        page_id="page_02_elevation",
        page_type="elevation",
        is_blocked=True,
        block_reason=PAGE_COMPLEXITY_BLOCKED,
    )
    sel = _selector()

    res = execute_source_full_plan_recovery_engine_shadow(sel, pages=[page1, page2_blocked])

    # Overall document succeeds with partial recovery!
    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_FULL_PLAN_ENGINE_RESOLVED in res.reason_codes
    assert SOURCE_FULL_PLAN_PARTIAL_RECOVERY in res.reason_codes

    record = res.record
    assert record.total_pages_evaluated == 2
    assert record.successful_pages_count == 1
    assert record.quarantined_pages_count == 1
    assert record.total_rooms_recovered == 1
    assert record.total_finish_zones_recovered == 1

    # Check page verdicts
    v1 = next(v for v in record.page_verdicts if v.page_id == "page_01")
    v2 = next(v for v in record.page_verdicts if v.page_id == "page_02_elevation")

    assert v1.status == EvidenceResolutionStatus.CANDIDATE
    assert v1.is_quarantined is False
    assert v1.recovered_room_ids == ("ROOM_A",)

    assert v2.status == EvidenceResolutionStatus.ABSTAINED
    assert v2.is_quarantined is True
    assert PAGE_COMPLEXITY_BLOCKED in v2.reason_codes
    assert PAGE_QUARANTINED_SAFELY in v2.reason_codes


def test_negative_all_pages_failing():
    """When all pages are blocked or fail closed, engine reports ABSTAINED."""
    p1 = SourcePageInputPayload("p1", is_blocked=True, block_reason="scale_unavailable")
    p2 = SourcePageInputPayload("p2", is_blocked=True, block_reason="complexity_exceeded")
    sel = _selector()

    res = execute_source_full_plan_recovery_engine_shadow(sel, pages=[p1, p2])

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_FULL_PLAN_ENGINE_ABSTAINED in res.reason_codes
    assert res.record.successful_pages_count == 0
    assert res.record.quarantined_pages_count == 2


def test_negative_empty_page_payloads():
    """Empty pages list fails closed."""
    sel = _selector()
    res = execute_source_full_plan_recovery_engine_shadow(sel, pages=[])
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert EMPTY_PAGE_PAYLOADS in res.reason_codes


def test_negative_lineage_mismatch():
    """Invalid selector fails closed."""
    with pytest.raises(ValueError):
        SourceFullPlanEngineSelector("doc", "rev", "short_sha", "snap")

    res = execute_source_full_plan_recovery_engine_shadow(
        None,  # type: ignore
        pages=[_healthy_page()],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_LINEAGE_MISMATCH in res.reason_codes


def test_metamorphic_page_order_invariance():
    """Permuting the page order preserves overall recovered room and finish totals."""
    p1 = _healthy_page("p1")
    p2 = _healthy_page("p2")
    sel = _selector()

    res1 = execute_source_full_plan_recovery_engine_shadow(sel, pages=[p1, p2])
    res2 = execute_source_full_plan_recovery_engine_shadow(sel, pages=[p2, p1])

    assert res1.status == res2.status
    assert res1.record.total_rooms_recovered == res2.record.total_rooms_recovered
    assert res1.record.total_finish_zones_recovered == res2.record.total_finish_zones_recovered
    assert res1.record.successful_pages_count == res2.record.successful_pages_count


def test_input_no_mutation():
    """Verify input collections and objects are never mutated."""
    p1 = _healthy_page("p1")
    pages = [p1]
    pages_copy = copy.deepcopy(pages)
    sel = _selector()

    execute_source_full_plan_recovery_engine_shadow(sel, pages=pages)
    assert pages == pages_copy

def test_foreign_page_finish_not_recovered_by_full_plan_shadow_engine():
    page = _healthy_page("page_07")
    foreign = SourceFloorFinishMark(
        "OCC_FOREIGN_FT3","page_11","FT3",(150.,150.)
    )
    blocked = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=[replace(page,finish_mark_candidates=(foreign,))],
    )
    control = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=[page],
    )
    assert blocked.record.total_rooms_recovered == 1
    assert blocked.record.total_finish_zones_recovered == 0
    assert blocked.record.page_verdicts[0].recovered_finish_ids == ()
    assert control.record.total_finish_zones_recovered == 1
    assert control.record.page_verdicts[0].recovered_finish_ids == ("OCC_FT2",)
    assert blocked.record.takeoff_eligible is False
    assert blocked.record.commercial_projection_allowed is False
