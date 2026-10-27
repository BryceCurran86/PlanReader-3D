"""Tests for producer-owned source full-plan recovery engine shadow authority (Workstream C, Items 27 & 30)."""

from __future__ import annotations

import copy
from dataclasses import replace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_finish_occurrence_ownership_shadow import SourceFloorFinishMark
from pb_source_full_plan_recovery_engine_shadow import (
    DUPLICATE_SOURCE_PAGE_ID,
    DUPLICATE_SOURCE_ROOM_ID,
    UNSUPPORTED_SOURCE_PAGE_TYPE,
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


def test_same_room_competing_finish_codes_abstain_through_real_engine():
    """FT2/FT3 rivalry must not disappear at the recovery-engine call site."""
    page = _healthy_page("page_11")
    ft3 = SourceFloorFinishMark("OCC_FT3", "page_11", "FT3", (160., 160.))
    original = page.finish_mark_candidates[0]
    for marks in ((original, ft3), (ft3, original)):
        source_page = replace(page, finish_mark_candidates=marks)
        before = copy.deepcopy(source_page)
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=(source_page,)
        )
        verdict = result.record.page_verdicts[0]
        assert verdict.recovered_room_ids == ("ROOM_A",)
        assert verdict.recovered_finish_ids == ()
        assert result.record.total_finish_zones_recovered == 0
        assert result.record.total_rooms_recovered == 1
        assert result.record.takeoff_eligible is False
        assert result.record.commercial_projection_allowed is False
        assert source_page == before


def test_same_room_duplicate_finish_marks_abstain_through_real_engine():
    """Two separately addressed FT2 marks are not one authenticated zone."""
    page = _healthy_page("page_11")
    duplicate = SourceFloorFinishMark("OCC_FT2_OTHER", "page_11", "FT2", (160., 160.))
    for marks in (
        page.finish_mark_candidates + (duplicate,),
        (duplicate,) + page.finish_mark_candidates,
    ):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=(replace(page, finish_mark_candidates=marks),)
        )
        assert result.record.total_finish_zones_recovered == 0
        assert result.record.page_verdicts[0].recovered_finish_ids == ()


def test_outside_room_rival_does_not_poison_local_finish():
    """A same-page mark outside the room is not a same-room competitor."""
    page = _healthy_page("page_11")
    outside = SourceFloorFinishMark("OCC_OUTSIDE", "page_11", "FT3", (250., 250.))
    result = execute_source_full_plan_recovery_engine_shadow(
        _selector(),
        pages=(replace(page, finish_mark_candidates=(outside,) + page.finish_mark_candidates),),
    )
    assert result.record.page_verdicts[0].recovered_finish_ids == ("OCC_FT2",)
    assert result.record.total_finish_zones_recovered == 1
    assert result.record.takeoff_eligible is False
    assert result.record.commercial_projection_allowed is False


def test_one_finish_occurrence_cannot_own_two_overlapping_room_candidates():
    """Ambiguous overlapping room ownership must not double-count a mark."""
    page = _healthy_page("page_11")
    _, polygon = page.room_polygon_candidates[0]
    rooms = (("ROOM_A", polygon), ("ROOM_B", polygon))
    for ordered_rooms in (rooms, rooms[::-1]):
        source_page = replace(page, room_polygon_candidates=ordered_rooms)
        before = copy.deepcopy(source_page)
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=(source_page,)
        )
        verdict = result.record.page_verdicts[0]
        assert verdict.recovered_room_ids == ("ROOM_A", "ROOM_B")
        assert verdict.recovered_finish_ids == ()
        assert result.record.total_rooms_recovered == 2
        assert result.record.total_finish_zones_recovered == 0
        assert result.record.takeoff_eligible is False
        assert result.record.commercial_projection_allowed is False
        assert source_page == before


def test_reused_finish_occurrence_id_cannot_create_multiple_zones():
    """Two source marks with the same ID cannot evade the rival-mark veto."""
    page = _healthy_page("page_11")
    original = page.finish_mark_candidates[0]
    repeated_id = replace(original, mark_center_pt=(160.0, 160.0))
    for marks in ((original, repeated_id), (repeated_id, original)):
        source_page = replace(page, finish_mark_candidates=marks)
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=(source_page,)
        )
        assert result.record.page_verdicts[0].recovered_room_ids == ("ROOM_A",)
        assert result.record.page_verdicts[0].recovered_finish_ids == ()
        assert result.record.total_finish_zones_recovered == 0
        assert result.record.commercial_projection_allowed is False


def test_unrelated_room_candidate_preserves_single_finish_owner():
    """A distant, nonrecovered room does not poison the valid local candidate."""
    page = _healthy_page("page_11")
    _, polygon = page.room_polygon_candidates[0]
    distant = tuple((x + 400.0, y + 400.0) for x, y in polygon)
    for rooms in (
        (("ROOM_A", polygon), ("ROOM_DISTANT", distant)),
        (("ROOM_DISTANT", distant), ("ROOM_A", polygon)),
    ):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(),
            pages=(replace(page, room_polygon_candidates=rooms),),
        )
        assert result.record.page_verdicts[0].recovered_room_ids == ("ROOM_A",)
        assert result.record.page_verdicts[0].recovered_finish_ids == ("OCC_FT2",)
        assert result.record.total_finish_zones_recovered == 1
        assert result.record.takeoff_eligible is False
        assert result.record.commercial_projection_allowed is False


def test_duplicate_page_scope_quarantines_all_collisions_and_preserves_sibling():
    """A repeated PDF page cannot multiply diagnostic rooms or finish zones."""
    duplicate = _healthy_page("page_11")
    sibling = _healthy_page("page_09")
    baseline = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(sibling,)
    )
    ids = set()
    for pages in (
        (duplicate, sibling, duplicate),
        (sibling, duplicate, duplicate),
        (duplicate, duplicate, sibling),
    ):
        before = copy.deepcopy(pages)
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=pages
        )
        record = result.record
        ids.add(record.record_id)
        assert record.total_pages_evaluated == 3
        assert record.successful_pages_count == 1
        assert record.quarantined_pages_count == 2
        assert record.total_rooms_recovered == 1
        assert record.total_finish_zones_recovered == 1
        assert record.reason_codes == (
            SOURCE_FULL_PLAN_ENGINE_RESOLVED,
            SOURCE_FULL_PLAN_PARTIAL_RECOVERY,
            SOURCE_FULL_PLAN_ENGINE_CANDIDATE,
        )
        duplicate_verdicts = [
            v for v in record.page_verdicts if v.page_id == "page_11"
        ]
        assert len(duplicate_verdicts) == 2
        assert all(v.status == EvidenceResolutionStatus.ABSTAINED for v in duplicate_verdicts)
        assert all(v.reason_codes == (
            DUPLICATE_SOURCE_PAGE_ID, PAGE_QUARANTINED_SAFELY
        ) for v in duplicate_verdicts)
        assert all(v.recovered_room_ids == () and v.recovered_finish_ids == ()
                   for v in duplicate_verdicts)
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False
        assert pages == before
    assert len(ids) == 1
    assert baseline.record.total_rooms_recovered == 1
    assert baseline.record.total_finish_zones_recovered == 1


def test_duplicate_page_scope_abstains_even_if_one_copy_is_blocked():
    page = _healthy_page("page_11")
    blocked = SourcePageInputPayload(
        page_id="page_11", is_blocked=True, block_reason=PAGE_COMPLEXITY_BLOCKED
    )
    for pages in ((page, blocked), (blocked, page)):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=pages
        )
        assert result.status == EvidenceResolutionStatus.ABSTAINED
        assert result.record.successful_pages_count == 0
        assert result.record.quarantined_pages_count == 2
        assert result.record.total_rooms_recovered == 0
        assert result.record.total_finish_zones_recovered == 0
        assert all(DUPLICATE_SOURCE_PAGE_ID in v.reason_codes
                   for v in result.record.page_verdicts)


def test_shadow_receipt_id_binds_page_room_finish_membership_not_just_counts():
    """Equal aggregate counts with different source scopes cannot share an ID."""
    original = _healthy_page("page_11")
    other_page = _healthy_page("page_09")
    _, poly = original.room_polygon_candidates[0]
    other_room = replace(
        original, room_polygon_candidates=(("ROOM_B", poly),)
    )
    a = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(original,)
    ).record
    b = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(other_page,)
    ).record
    c = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(other_room,)
    ).record
    assert (a.total_rooms_recovered, a.total_finish_zones_recovered) == (1, 1)
    assert (b.total_rooms_recovered, b.total_finish_zones_recovered) == (1, 1)
    assert (c.total_rooms_recovered, c.total_finish_zones_recovered) == (1, 1)
    assert len({a.record_id, b.record_id, c.record_id}) == 3
    first = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(original, other_page)
    ).record
    reversed_order = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(other_page, original)
    ).record
    assert first.record_id == reversed_order.record_id
    assert first.takeoff_eligible is False
    assert first.commercial_projection_allowed is False


def test_non_floor_plan_sheet_lookalikes_are_quarantined_before_recovery():
    """A room-like shape on RCP/elevation/finish sheets is not a floor-plan room."""
    floor = _healthy_page("page_07")
    for page_type in ("elevation", "reflected_ceiling_plan", "floor_finish_plan"):
        lookalike = replace(_healthy_page("page_09"), page_type=page_type)
        receipt_ids = set()
        for pages in ((floor, lookalike), (lookalike, floor)):
            before = copy.deepcopy(pages)
            result = execute_source_full_plan_recovery_engine_shadow(
                _selector(), pages=pages
            )
            record = result.record
            receipt_ids.add(record.record_id)
            assert record.successful_pages_count == 1
            assert record.quarantined_pages_count == 1
            assert record.total_rooms_recovered == 1
            assert record.total_finish_zones_recovered == 1
            assert result.status == EvidenceResolutionStatus.CANDIDATE
            assert SOURCE_FULL_PLAN_PARTIAL_RECOVERY in record.reason_codes
            blocked = next(v for v in record.page_verdicts if v.page_id == "page_09")
            assert blocked.page_type == page_type
            assert blocked.status == EvidenceResolutionStatus.ABSTAINED
            assert blocked.reason_codes == (
                UNSUPPORTED_SOURCE_PAGE_TYPE, PAGE_QUARANTINED_SAFELY
            )
            assert blocked.recovered_room_ids == ()
            assert blocked.recovered_finish_ids == ()
            assert blocked.is_quarantined is True
            assert record.takeoff_eligible is False
            assert record.commercial_projection_allowed is False
            assert pages == before
        assert len(receipt_ids) == 1


def test_unblocked_non_floor_plan_alone_never_recovers_room_or_finish():
    for page_type in ("elevation", "reflected_ceiling_plan", "floor_finish_plan"):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(),
            pages=(replace(_healthy_page("page_09"), page_type=page_type),),
        )
        assert result.status == EvidenceResolutionStatus.ABSTAINED
        assert result.record.total_rooms_recovered == 0
        assert result.record.total_finish_zones_recovered == 0
        assert result.record.quarantined_pages_count == 1
        assert result.record.page_verdicts[0].reason_codes == (
            UNSUPPORTED_SOURCE_PAGE_TYPE, PAGE_QUARANTINED_SAFELY
        )


def test_source_page_type_must_be_explicit_nonempty_string():
    for invalid in ("", "  ", None, 42):
        with pytest.raises(ValueError, match="page_type"):
            SourcePageInputPayload(page_id="page_09", page_type=invalid)


def test_duplicate_room_id_quarantines_page_without_poisoning_healthy_sibling():
    """Repeated physical room identity is not two diagnostic rooms or finish owners."""
    duplicate = _healthy_page("page_11")
    room = duplicate.room_polygon_candidates[0]
    collision = replace(duplicate, room_polygon_candidates=(room, room))
    healthy = _healthy_page("page_07")
    baseline = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(healthy,)
    )
    ids = set()
    for pages in ((collision, healthy), (healthy, collision)):
        before = copy.deepcopy(pages)
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=pages
        )
        record = result.record
        ids.add(record.record_id)
        assert record.status == EvidenceResolutionStatus.CANDIDATE
        assert SOURCE_FULL_PLAN_PARTIAL_RECOVERY in record.reason_codes
        assert record.total_pages_evaluated == 2
        assert record.successful_pages_count == 1
        assert record.quarantined_pages_count == 1
        assert record.total_rooms_recovered == baseline.record.total_rooms_recovered == 1
        assert record.total_finish_zones_recovered == baseline.record.total_finish_zones_recovered == 1
        verdict = next(v for v in record.page_verdicts if v.page_id == "page_11")
        assert verdict.status == EvidenceResolutionStatus.ABSTAINED
        assert verdict.reason_codes == (DUPLICATE_SOURCE_ROOM_ID, PAGE_QUARANTINED_SAFELY)
        assert verdict.recovered_room_ids == ()
        assert verdict.recovered_finish_ids == ()
        assert verdict.is_quarantined is True
        assert record.commercial_projection_allowed is False
        assert record.takeoff_eligible is False
        assert record.diagnostic_only is True
        assert pages == before
    assert len(ids) == 1


def test_conflicting_duplicate_room_polygons_also_quarantine_source_page():
    """Distinct geometries cannot silently reuse one physical room ID."""
    original = _healthy_page("page_11")
    room_id, polygon = original.room_polygon_candidates[0]
    displaced = tuple((x + 400.0, y + 400.0) for x, y in polygon)
    for rooms in (
        ((room_id, polygon), (room_id, displaced)),
        ((room_id, displaced), (room_id, polygon)),
    ):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=(replace(original, room_polygon_candidates=rooms),)
        )
        record = result.record
        assert result.status == EvidenceResolutionStatus.ABSTAINED
        assert record.quarantined_pages_count == 1
        assert record.total_rooms_recovered == 0
        assert record.total_finish_zones_recovered == 0
        assert record.page_verdicts[0].reason_codes == (
            DUPLICATE_SOURCE_ROOM_ID, PAGE_QUARANTINED_SAFELY
        )
        assert record.takeoff_eligible is False


def test_room_identity_is_scoped_to_source_page_not_entire_document():
    """Identical room IDs on independently identified pages are not a collision."""
    first = _healthy_page("page_07")
    second = _healthy_page("page_11")
    result = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(first, second)
    )
    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert result.record.quarantined_pages_count == 0
    assert result.record.total_rooms_recovered == 2
    assert result.record.total_finish_zones_recovered == 2
    assert result.record.takeoff_eligible is False


def test_blocked_page_reason_precedes_duplicate_room_diagnostic():
    """Existing explicit source block cannot be overwritten by downstream room logic."""
    original = _healthy_page("page_11")
    room = original.room_polygon_candidates[0]
    page = replace(
        original, room_polygon_candidates=(room, room),
        is_blocked=True, block_reason="source_complexity_exceeded"
    )
    result = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(page,)
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.record.page_verdicts[0].reason_codes == (
        "source_complexity_exceeded", PAGE_QUARANTINED_SAFELY
    )
    assert result.record.total_rooms_recovered == 0
    assert result.record.total_finish_zones_recovered == 0


def test_unclosed_overlapping_room_still_vetoes_finish_owner():
    """A failed wall closure is not evidence that a competing room does not exist."""
    original = _healthy_page("page_11")
    room_id, polygon = original.room_polygon_candidates[0]
    rival_polygon = tuple((x + 20.0, y + 20.0) for x, y in polygon)
    rival = ("ROOM_UNCLOSED", rival_polygon)
    # Rival geometry contains the FT2 mark, but its shifted edges do not
    # match the original source walls/opening; boundary closure must abstain.
    rival_only = execute_source_full_plan_recovery_engine_shadow(
        _selector(),
        pages=(replace(original, room_polygon_candidates=(rival,)),),
    )
    assert rival_only.record.total_rooms_recovered == 0
    assert rival_only.record.total_finish_zones_recovered == 0

    baseline = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(original,)
    )
    assert baseline.record.page_verdicts[0].recovered_finish_ids == ("OCC_FT2",)
    ids = set()
    for rooms in (
        ((room_id, polygon), rival),
        (rival, (room_id, polygon)),
    ):
        page = replace(original, room_polygon_candidates=rooms)
        before = copy.deepcopy(page)
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=(page,)
        )
        verdict = result.record.page_verdicts[0]
        ids.add(result.record.record_id)
        assert verdict.recovered_room_ids == ("ROOM_A",)
        assert verdict.recovered_finish_ids == ()
        assert result.record.total_rooms_recovered == 1
        assert result.record.total_finish_zones_recovered == 0
        assert result.record.takeoff_eligible is False
        assert result.record.commercial_projection_allowed is False
        assert result.record.diagnostic_only is True
        assert page == before
    assert len(ids) == 1


def test_unclosed_distant_room_does_not_veto_unique_finish_owner():
    """Only a spatially plausible rival can withhold a diagnostic finish."""
    original = _healthy_page("page_11")
    room_id, polygon = original.room_polygon_candidates[0]
    distant = ("ROOM_UNCLOSED", tuple((x + 400.0, y + 400.0) for x, y in polygon))
    for rooms in (((room_id, polygon), distant), (distant, (room_id, polygon))):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(),
            pages=(replace(original, room_polygon_candidates=rooms),),
        )
        verdict = result.record.page_verdicts[0]
        assert verdict.recovered_room_ids == ("ROOM_A",)
        assert verdict.recovered_finish_ids == ("OCC_FT2",)
        assert result.record.total_finish_zones_recovered == 1
        assert result.record.commercial_projection_allowed is False


@pytest.mark.parametrize(
    "bad_field,bad_value",
    [
        ("room_polygon_candidates", (("", ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))),)),
        ("room_polygon_candidates", (("ROOM_BAD", ((0.0, 0.0), (float("nan"), 0.0), (0.0, 1.0))),)),
        ("wall_edges", ("not-a-wall-edge",)),
        ("opening_candidates", ("not-an-opening",)),
        ("finish_mark_candidates", ("not-a-mark",)),
    ],
)
def test_malformed_source_candidates_quarantine_only_their_page(bad_field, bad_value):
    """Five malformed original candidate universes never mint partial recovery."""
    malformed = replace(_healthy_page("bad_page"), **{bad_field: bad_value})
    good = _healthy_page("good_page")
    result = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(malformed, good)
    )
    assert result.record is not None
    assert result.record.quarantined_pages_count == 1
    assert result.record.successful_pages_count == 1
    assert result.record.total_rooms_recovered == 1
    assert result.record.total_finish_zones_recovered == 1
    assert result.record.page_verdicts[0].reason_codes == (
        SOURCE_LINEAGE_MISMATCH, PAGE_QUARANTINED_SAFELY
    )
    assert result.record.page_verdicts[0].recovered_finish_ids == ()
    assert result.record.page_verdicts[1].recovered_finish_ids == ("OCC_FT2",)
    assert result.record.takeoff_eligible is False
    assert result.record.commercial_projection_allowed is False


def test_untyped_page_input_abstains_without_partial_source_recovery():
    result = execute_source_full_plan_recovery_engine_shadow(
        _selector(), pages=(_healthy_page("good_page"), object())
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (SOURCE_LINEAGE_MISMATCH,)
    assert result.record is None


@pytest.mark.parametrize("invalid_reason", (None, 123, object()))
def test_blocked_page_invalid_reason_preserves_healthy_sibling(invalid_reason):
    """Bad caller-owned reason cannot crash or poison a distinct source page."""
    blocked = replace(
        _healthy_page("blocked_source_page"),
        is_blocked=True,
        block_reason=invalid_reason,
    )
    healthy = _healthy_page("healthy_source_page")
    for pages in ((blocked, healthy), (healthy, blocked)):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=pages,
        )
        assert result.record is not None
        assert result.record.successful_pages_count == 1
        assert result.record.quarantined_pages_count == 1
        assert result.record.total_finish_zones_recovered == 1
        quarantined = [v for v in result.record.page_verdicts if v.is_quarantined]
        assert len(quarantined) == 1
        assert quarantined[0].reason_codes == (
            PAGE_COMPLEXITY_BLOCKED, PAGE_QUARANTINED_SAFELY
        )
        assert result.record.takeoff_eligible is False
        assert result.record.commercial_projection_allowed is False


def test_omitted_source_page_type_never_claims_floor_plan_authority():
    """A source sheet with look-alike rooms/marks must not default to floor plan."""
    healthy = _healthy_page("actual_floor")
    lookalike = replace(
        _healthy_page("unverified_sheet"),
        page_type=SourcePageInputPayload(page_id="placeholder").page_type,
    )
    assert lookalike.page_type == "unverified"
    ids = set()
    for pages in ((lookalike, healthy), (healthy, lookalike)):
        result = execute_source_full_plan_recovery_engine_shadow(
            _selector(), pages=pages,
        )
        assert result.record is not None
        ids.add(result.record.record_id)
        assert result.record.total_rooms_recovered == 1
        assert result.record.total_finish_zones_recovered == 1
        assert result.record.successful_pages_count == 1
        assert result.record.quarantined_pages_count == 1
        quarantined = next(v for v in result.record.page_verdicts if v.page_id == "unverified_sheet")
        assert quarantined.reason_codes == (
            UNSUPPORTED_SOURCE_PAGE_TYPE, PAGE_QUARANTINED_SAFELY
        )
        assert quarantined.recovered_room_ids == ()
        assert quarantined.recovered_finish_ids == ()
        assert result.record.takeoff_eligible is False
        assert result.record.commercial_projection_allowed is False
    assert len(ids) == 1
