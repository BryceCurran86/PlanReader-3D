"""Tests for producer-owned source wall junction continuity and through-wall ownership shadow authority (Workstream A, Items 2 & 4)."""

from __future__ import annotations

import copy
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wall_junction_continuity_shadow import (
    ABUTTING_STEM_WALL_TERMINATES,
    COLLINEAR_THROUGH_CONTINUATION_RESOLVED,
    CONTINUOUS_THROUGH_WALL_RESOLVED,
    CORNER_WALL_BEND_RESOLVED,
    EMPTY_INCIDENT_EDGES,
    JUNCTION_CONTINUITY_AMBIGUOUS,
    JUNCTION_ENDPOINT_UNALIGNED,
    JUNCTION_TYPE_COLLINEAR,
    JUNCTION_TYPE_L_CORNER,
    JUNCTION_TYPE_T_JUNCTION,
    JUNCTION_TYPE_X_CROSSING,
    SOURCE_LINEAGE_MISMATCH,
    SOURCE_WALL_JUNCTION_CONTINUITY_CANDIDATE,
    SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED,
    TWO_WAY_THROUGH_CROSSING_RESOLVED,
    SourceIncidentWallEdge,
    SourceWallJunctionContinuityRecord,
    SourceWallJunctionContinuityResult,
    SourceWallJunctionContinuitySelector,
    evaluate_source_wall_junction_continuity_shadow,
)

VALID_SHA = "d" * 64


def _selector(junction_id: str = "JUNC_01") -> SourceWallJunctionContinuitySelector:
    return SourceWallJunctionContinuitySelector(
        document_id="doc_maryborough",
        revision_id="rev_01",
        source_sha256=VALID_SHA,
        snapshot_id="snap_01",
        page_id="page_07",
        junction_id=junction_id,
    )


def test_positive_t_junction_continuity_and_abutting_stem():
    """T-junction: through-wall (E_LEFT, E_RIGHT) is continuous, while E_STEM terminates."""
    # Junction at (100, 100)
    # Horizontal through-wall: (0, 100) -> (100, 100) -> (200, 100)
    # Vertical abutting stem: (100, 100) -> (100, 180)
    edges = [
        SourceIncidentWallEdge("E_LEFT", (0.0, 100.0), (100.0, 100.0), parent_wall_id="WALL_THROUGH"),
        SourceIncidentWallEdge("E_RIGHT", (100.0, 100.0), (200.0, 100.0), parent_wall_id="WALL_THROUGH"),
        SourceIncidentWallEdge("E_STEM", (100.0, 100.0), (100.0, 180.0), parent_wall_id="WALL_PARTITION"),
    ]

    sel = _selector("JUNC_T_01")
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED in res.reason_codes
    assert CONTINUOUS_THROUGH_WALL_RESOLVED in res.reason_codes
    assert ABUTTING_STEM_WALL_TERMINATES in res.reason_codes

    record = res.record
    assert isinstance(record, SourceWallJunctionContinuityRecord)
    assert record.junction_type == JUNCTION_TYPE_T_JUNCTION
    assert set(record.through_wall_edge_ids) == {"E_LEFT", "E_RIGHT"}
    assert record.abutting_wall_edge_ids == ("E_STEM",)
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False
    assert record.diagnostic_only is True


def test_positive_l_corner_wall_bend():
    """L-corner: two non-collinear perpendicular edges establish a corner bend."""
    edges = [
        SourceIncidentWallEdge("E_HORIZ", (50.0, 100.0), (100.0, 100.0)),
        SourceIncidentWallEdge("E_VERT", (100.0, 100.0), (100.0, 160.0)),
    ]
    sel = _selector("JUNC_CORNER_01")
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert CORNER_WALL_BEND_RESOLVED in res.reason_codes
    record = res.record
    assert record.junction_type == JUNCTION_TYPE_L_CORNER
    assert set(record.through_wall_edge_ids) == {"E_HORIZ", "E_VERT"}
    assert record.abutting_wall_edge_ids == ()


def test_positive_collinear_through_continuation():
    """Collinear degree-2 continuation: straight continuous wall."""
    edges = [
        SourceIncidentWallEdge("E1", (0.0, 50.0), (50.0, 50.0)),
        SourceIncidentWallEdge("E2", (50.0, 50.0), (120.0, 50.0)),
    ]
    sel = _selector("JUNC_CONT_01")
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(50.0, 50.0),
        incident_edges=edges,
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert COLLINEAR_THROUGH_CONTINUATION_RESOLVED in res.reason_codes
    assert res.record.junction_type == JUNCTION_TYPE_COLLINEAR
    assert set(res.record.through_wall_edge_ids) == {"E1", "E2"}


def test_positive_x_crossing():
    """X-crossing: four orthogonal edges forming two through-pairs."""
    edges = [
        SourceIncidentWallEdge("E_LEFT", (0.0, 100.0), (100.0, 100.0)),
        SourceIncidentWallEdge("E_RIGHT", (100.0, 100.0), (200.0, 100.0)),
        SourceIncidentWallEdge("E_TOP", (100.0, 0.0), (100.0, 100.0)),
        SourceIncidentWallEdge("E_BOT", (100.0, 100.0), (100.0, 200.0)),
    ]
    sel = _selector("JUNC_X_01")
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert TWO_WAY_THROUGH_CROSSING_RESOLVED in res.reason_codes
    assert res.record.junction_type == JUNCTION_TYPE_X_CROSSING
    assert len(res.record.through_wall_edge_ids) == 4


def test_negative_endpoint_unaligned_beyond_snap_tolerance():
    """An edge with endpoint offset by 5 pt (> 2.5 pt snap tolerance) fails closed."""
    edges = [
        SourceIncidentWallEdge("E1", (0.0, 100.0), (100.0, 100.0)),
        SourceIncidentWallEdge("E2", (105.0, 100.0), (200.0, 100.0)),  # 5 pt offset from (100, 100)
    ]
    sel = _selector()
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert JUNCTION_ENDPOINT_UNALIGNED in res.reason_codes
    assert res.record is None


def test_negative_ambiguous_3_way_star():
    """Three edges meeting at 120 degrees without any collinear pair fails closed."""
    edges = [
        SourceIncidentWallEdge("E1", (100.0, 100.0), (200.0, 100.0)),  # 0 deg
        SourceIncidentWallEdge("E2", (100.0, 100.0), (50.0, 186.6)),   # 120 deg
        SourceIncidentWallEdge("E3", (100.0, 100.0), (50.0, 13.4)),    # 240 deg
    ]
    sel = _selector("JUNC_STAR")
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert JUNCTION_CONTINUITY_AMBIGUOUS in res.reason_codes
    assert res.record is None


def test_negative_empty_incident_edges():
    """Empty incident edges list fails closed."""
    sel = _selector()
    res = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=[],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert EMPTY_INCIDENT_EDGES in res.reason_codes


def test_negative_lineage_mismatch():
    """Invalid selector fails closed."""
    with pytest.raises(ValueError):
        SourceWallJunctionContinuitySelector("d", "r", "not_sha", "s", "p", "j")

    edge = SourceIncidentWallEdge("E1", (0.0, 0.0), (10.0, 0.0))
    res = evaluate_source_wall_junction_continuity_shadow(
        None,  # type: ignore
        junction_pt=(0.0, 0.0),
        incident_edges=[edge],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_LINEAGE_MISMATCH in res.reason_codes


def test_metamorphic_translation_invariance():
    """Translating the junction point and all incident edges preserves junction classification."""
    edges = [
        SourceIncidentWallEdge("E_LEFT", (0.0, 100.0), (100.0, 100.0)),
        SourceIncidentWallEdge("E_RIGHT", (100.0, 100.0), (200.0, 100.0)),
        SourceIncidentWallEdge("E_STEM", (100.0, 100.0), (100.0, 180.0)),
    ]
    sel = _selector("JUNC_T")
    res1 = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )
    assert res1.status == EvidenceResolutionStatus.CANDIDATE

    # Shift by dx=85.0, dy=-45.0
    dx, dy = 85.0, -45.0
    edges_shifted = [
        SourceIncidentWallEdge(
            e.edge_id,
            (e.start_pt[0] + dx, e.start_pt[1] + dy),
            (e.end_pt[0] + dx, e.end_pt[1] + dy),
        )
        for e in edges
    ]
    res2 = evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0 + dx, 100.0 + dy),
        incident_edges=edges_shifted,
    )
    assert res2.status == EvidenceResolutionStatus.CANDIDATE
    assert res1.record.junction_type == res2.record.junction_type
    assert res1.record.through_wall_edge_ids == res2.record.through_wall_edge_ids
    assert res1.record.abutting_wall_edge_ids == res2.record.abutting_wall_edge_ids


def test_input_no_mutation():
    """Verify input collections and objects are never mutated."""
    edges = [
        SourceIncidentWallEdge("E_LEFT", (0.0, 100.0), (100.0, 100.0)),
        SourceIncidentWallEdge("E_RIGHT", (100.0, 100.0), (200.0, 100.0)),
    ]
    edges_copy = copy.deepcopy(edges)
    sel = _selector()
    evaluate_source_wall_junction_continuity_shadow(
        sel,
        junction_pt=(100.0, 100.0),
        incident_edges=edges,
    )
    assert edges == edges_copy
