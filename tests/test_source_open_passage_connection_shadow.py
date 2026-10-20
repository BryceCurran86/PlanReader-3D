"""Tests for pb_source_open_passage_connection_shadow.py (Items 12 & 20).

Proves producer-owned open passage and connected space shadow authority:
- Positive proof of physical transition stroke between differing finishes.
- Positive proof of contiguous finish flow between shared-finish spaces.
- Fails closed on unpartitioned finish conflicts without artificial wall invention.
- Vetoes open passage when obstructed by a physical wall candidate.
- Metamorphic translation invariance and no-mutation checks.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_open_passage_connection_shadow import (
    INVALID_PASSAGE_GEOMETRY,
    OPEN_PASSAGE_OBSTRUCTED_BY_WALL,
    PASSAGE_ENDPOINTS_UNALIGNED_WITH_WALLS,
    SOURCE_OPEN_PASSAGE_RESOLVED,
    TRANSITION_CONTIGUOUS_FLOW,
    TRANSITION_PHYSICAL_STROKE,
    UNPARTITIONED_FINISH_CONFLICT,
    SourceOpenPassageSelector,
    SourcePassageWallEdge,
    evaluate_source_open_passage_connection_shadow,
)

SAMPLE_SHA = "b" * 64


def _make_selector(
    *,
    document_id: str = "doc_test_mary",
    revision_id: str = "rev_test_mary",
    source_sha256: str = SAMPLE_SHA,
    snapshot_id: str = "snap_test_mary",
    page_id: str = "7",
    primary_room_id: str = "room_food_prep",
    connected_room_id: str = "room_wash_up",
) -> SourceOpenPassageSelector:
    return SourceOpenPassageSelector(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        primary_room_id=primary_room_id,
        connected_room_id=connected_room_id,
    )


def _make_adjoining_walls():
    """Create walls with an opening from (100.0, 50.0) to (100.0, 110.0)."""
    # Primary room walls: top wall stub terminates at (100, 50); bottom wall stub begins at (100, 110)
    primary_edges = (
        SourcePassageWallEdge(
            wall_id="w_top_stub", start_pt=(100.0, 0.0), end_pt=(100.0, 50.0)
        ),
        SourcePassageWallEdge(
            wall_id="w_bot_stub", start_pt=(100.0, 110.0), end_pt=(100.0, 200.0)
        ),
        SourcePassageWallEdge(
            wall_id="w_left", start_pt=(0.0, 0.0), end_pt=(0.0, 200.0)
        ),
    )
    connected_edges = (
        SourcePassageWallEdge(
            wall_id="w_conn_top", start_pt=(100.0, 0.0), end_pt=(200.0, 0.0)
        ),
        SourcePassageWallEdge(
            wall_id="w_conn_bot", start_pt=(100.0, 200.0), end_pt=(200.0, 200.0)
        ),
        SourcePassageWallEdge(
            wall_id="w_conn_right", start_pt=(200.0, 0.0), end_pt=(200.0, 200.0)
        ),
    )
    passage = ((100.0, 50.0), (100.0, 110.0))
    return primary_edges, connected_edges, passage


def test_positive_physical_transition_stroke():
    """Adjoining rooms with differing finishes and an authentic threshold transition mark."""
    selector = _make_selector()
    p_edges, c_edges, passage = _make_adjoining_walls()
    trans_stroke = ((100.0, 50.0), (100.0, 110.0))

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=passage,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
        transition_mark_geometry=trans_stroke,
        primary_finish_code="FT2",
        connected_finish_code="CPT1",
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_OPEN_PASSAGE_RESOLVED in result.reason_codes
    assert result.record is not None
    rec = result.record
    assert rec.transition_type == TRANSITION_PHYSICAL_STROKE
    assert rec.clear_width_pt == pytest.approx(60.0)
    assert rec.partition_invented is False
    assert rec.primary_finish_code == "FT2"
    assert rec.connected_finish_code == "CPT1"
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False


def test_positive_contiguous_finish_flow():
    """Adjoining rooms sharing identical finish code (e.g. FT3 in Food Prep and Wash Up)."""
    selector = _make_selector()
    p_edges, c_edges, passage = _make_adjoining_walls()

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=passage,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
        transition_mark_geometry=None,
        primary_finish_code="FT3",
        connected_finish_code="FT3",
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_OPEN_PASSAGE_RESOLVED in result.reason_codes
    assert result.record is not None
    rec = result.record
    assert rec.transition_type == TRANSITION_CONTIGUOUS_FLOW
    assert rec.clear_width_pt == pytest.approx(60.0)
    assert rec.partition_invented is False


def test_unpartitioned_finish_conflict():
    """Differing finishes without a threshold mark fail closed rather than inventing a line."""
    selector = _make_selector()
    p_edges, c_edges, passage = _make_adjoining_walls()

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=passage,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
        transition_mark_geometry=None,
        primary_finish_code="FT3",
        connected_finish_code="VINYL",
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert UNPARTITIONED_FINISH_CONFLICT in result.reason_codes
    assert result.record is None


def test_passage_obstructed_by_wall_candidate():
    """Passage candidate fails when an existing wall stands across the opening."""
    selector = _make_selector()
    p_edges, c_edges, passage = _make_adjoining_walls()
    obstructing_wall = SimpleNamespace(endpoints_pt=((100.0, 50.0), (100.0, 110.0)))

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=passage,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
        primary_finish_code="FT3",
        connected_finish_code="FT3",
        existing_wall_candidates=(obstructing_wall,),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPEN_PASSAGE_OBSTRUCTED_BY_WALL in result.reason_codes
    assert result.record is None


def test_passage_endpoints_unaligned():
    """Passage endpoints not matching wall terminations fail closed."""
    selector = _make_selector()
    p_edges, c_edges, _ = _make_adjoining_walls()
    unaligned_passage = (
        (150.0, 50.0),
        (150.0, 110.0),
    )  # shifted in x away from wall stubs

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=unaligned_passage,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
        primary_finish_code="FT3",
        connected_finish_code="FT3",
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PASSAGE_ENDPOINTS_UNALIGNED_WITH_WALLS in result.reason_codes
    assert result.record is None


def test_invalid_passage_geometry():
    """Zero-width passage fails closed."""
    selector = _make_selector()
    p_edges, c_edges, _ = _make_adjoining_walls()
    zero_width = ((100.0, 50.0), (100.0, 50.0))

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=zero_width,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert INVALID_PASSAGE_GEOMETRY in result.reason_codes


def test_invalid_selector_fails():
    """Selector with identical room IDs or bad SHA raises ValueError."""
    with pytest.raises(ValueError, match="distinct"):
        _make_selector(primary_room_id="room_1", connected_room_id="room_1")
    with pytest.raises(ValueError, match="source_sha256"):
        _make_selector(source_sha256="not_valid_sha")


def test_metamorphic_translation_invariance():
    """Translating the passage and wall coordinates preserves resolution and clear width."""
    selector = _make_selector()
    p_edges, c_edges, passage = _make_adjoining_walls()
    dx, dy = 250.0, 400.0

    t_p_edges = [
        SourcePassageWallEdge(
            wall_id=e.wall_id,
            start_pt=(e.start_pt[0] + dx, e.start_pt[1] + dy),
            end_pt=(e.end_pt[0] + dx, e.end_pt[1] + dy),
        )
        for e in p_edges
    ]
    t_c_edges = [
        SourcePassageWallEdge(
            wall_id=e.wall_id,
            start_pt=(e.start_pt[0] + dx, e.start_pt[1] + dy),
            end_pt=(e.end_pt[0] + dx, e.end_pt[1] + dy),
        )
        for e in c_edges
    ]
    t_passage = (
        (passage[0][0] + dx, passage[0][1] + dy),
        (passage[1][0] + dx, passage[1][1] + dy),
    )

    result = evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=t_passage,
        primary_wall_edges=t_p_edges,
        connected_wall_edges=t_c_edges,
        primary_finish_code="FT3",
        connected_finish_code="FT3",
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.record is not None
    assert result.record.clear_width_pt == pytest.approx(60.0)


def test_input_no_mutation():
    """Verify evaluator does not mutate caller data structures."""
    selector = _make_selector()
    p_edges, c_edges, passage = _make_adjoining_walls()

    orig_p = copy.deepcopy(p_edges)
    orig_c = copy.deepcopy(c_edges)
    orig_pass = copy.deepcopy(passage)

    evaluate_source_open_passage_connection_shadow(
        selector,
        passage_endpoints=passage,
        primary_wall_edges=p_edges,
        connected_wall_edges=c_edges,
        primary_finish_code="FT3",
        connected_finish_code="FT3",
    )

    assert p_edges == orig_p
    assert c_edges == orig_c
    assert passage == orig_pass
