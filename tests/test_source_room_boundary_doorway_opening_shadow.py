"""Tests for producer-owned source room boundary doorway opening shadow authority (Items 11 & 13)."""

from __future__ import annotations

import copy
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_boundary_doorway_opening_shadow import (
    COMPETING_OPENING_CHORD_OWNERSHIP,
    INVALID_ROOM_POLYGON,
    NO_WALL_EDGES_PRESENT,
    ROOM_BOUNDARY_DEFECT_REMAINS,
    SOURCE_LINEAGE_MISMATCH,
    SOURCE_ROOM_BOUNDARY_DOORWAY_CANDIDATE,
    SOURCE_ROOM_BOUNDARY_DOORWAY_RESOLVED,
    SourceRoomBoundaryDoorwayRecord,
    SourceRoomBoundaryDoorwayResult,
    SourceRoomDoorwayOpeningSelector,
    SourceRoomOpeningCandidate,
    SourceRoomWallEdge,
    evaluate_source_room_boundary_doorway_shadow,
)

VALID_SHA = "a" * 64


def _selector(
    room_id: str = "ROOM_LAUNDRY",
    room_label: str = "LAUNDRY",
    source_sha256: str = VALID_SHA,
) -> SourceRoomDoorwayOpeningSelector:
    return SourceRoomDoorwayOpeningSelector(
        document_id="doc_maryborough",
        revision_id="rev_01",
        source_sha256=source_sha256,
        snapshot_id="snap_01",
        page_id="page_07",
        room_id=room_id,
        room_label=room_label,
    )


def test_positive_room_boundary_with_doorway_opening():
    """Rectangular room: 3 solid walls, 1 wall with a doorway opening gap."""
    # Room polygon: (100, 100) -> (200, 100) -> (200, 200) -> (100, 200)
    polygon = [
        (100.0, 100.0),
        (200.0, 100.0),
        (200.0, 200.0),
        (150.0, 200.0),
        (120.0, 200.0),
        (100.0, 200.0),
    ]
    # Edge 1: (100, 100) -> (200, 100) (top wall)
    # Edge 2: (200, 100) -> (200, 200) (right wall)
    # Edge 3: (200, 200) -> (150, 200) (bottom wall right jamb)
    # Edge 4: (150, 200) -> (120, 200) (doorway opening D10)
    # Edge 5: (120, 200) -> (100, 200) (bottom wall left jamb)
    # Edge 6: (100, 200) -> (100, 100) (left wall)

    walls = [
        SourceRoomWallEdge("W_TOP", (100.0, 100.0), (200.0, 100.0)),
        SourceRoomWallEdge("W_RIGHT", (200.0, 100.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_BOT_R", (150.0, 200.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_BOT_L", (100.0, 200.0), (120.0, 200.0)),
        SourceRoomWallEdge("W_LEFT", (100.0, 200.0), (100.0, 100.0)),
    ]

    openings = [
        SourceRoomOpeningCandidate("DOOR_D10", (120.0, 200.0), (150.0, 200.0), "doorway")
    ]

    sel = _selector("ROOM_LAUNDRY", "LAUNDRY")
    result = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=walls,
        opening_candidates=openings,
    )

    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert SOURCE_ROOM_BOUNDARY_DOORWAY_RESOLVED in result.reason_codes
    assert SOURCE_ROOM_BOUNDARY_DOORWAY_CANDIDATE in result.reason_codes
    assert result.unowned_edge_count == 0

    record = result.record
    assert isinstance(record, SourceRoomBoundaryDoorwayRecord)
    assert record.wall_edge_count == 5
    assert record.opening_edge_count == 1
    assert "DOOR_D10" in record.bounding_opening_ids
    assert "W_TOP" in record.bounding_wall_ids
    assert "W_LEFT" in record.bounding_wall_ids
    assert record.partition_invented is False
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False
    assert record.diagnostic_only is True


def test_negative_room_boundary_unaccounted_defect():
    """Unaccounted wall gap without an authentic opening candidate fails closed."""
    polygon = [
        (100.0, 100.0),
        (200.0, 100.0),
        (200.0, 200.0),
        (100.0, 200.0),
    ]
    # Bottom edge (200, 200) -> (100, 200) has NO wall and NO opening
    walls = [
        SourceRoomWallEdge("W_TOP", (100.0, 100.0), (200.0, 100.0)),
        SourceRoomWallEdge("W_RIGHT", (200.0, 100.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_LEFT", (100.0, 200.0), (100.0, 100.0)),
    ]
    openings = []

    sel = _selector("ROOM_PWD", "PWD")
    result = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=walls,
        opening_candidates=openings,
    )

    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert ROOM_BOUNDARY_DEFECT_REMAINS in result.reason_codes
    assert result.record is None
    assert result.unowned_edge_count == 1


def test_negative_misaligned_opening_chord():
    """Opening candidate offset beyond snap tolerance fails closed."""
    polygon = [
        (100.0, 100.0),
        (200.0, 100.0),
        (200.0, 200.0),
        (100.0, 200.0),
    ]
    walls = [
        SourceRoomWallEdge("W_TOP", (100.0, 100.0), (200.0, 100.0)),
        SourceRoomWallEdge("W_RIGHT", (200.0, 100.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_LEFT", (100.0, 200.0), (100.0, 100.0)),
    ]
    # Opening chord offset by 5 pt (exceeds default 2.5 pt snap tolerance)
    openings = [
        SourceRoomOpeningCandidate("DOOR_D13", (100.0, 205.0), (200.0, 205.0), "doorway")
    ]

    sel = _selector("ROOM_PWD", "PWD")
    result = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=walls,
        opening_candidates=openings,
    )

    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert ROOM_BOUNDARY_DEFECT_REMAINS in result.reason_codes
    assert result.record is None


def test_conflict_competing_opening_candidates():
    """Multiple distinct opening candidates claiming the same edge fails closed."""
    polygon = [
        (100.0, 100.0),
        (200.0, 100.0),
        (200.0, 200.0),
        (100.0, 200.0),
    ]
    walls = [
        SourceRoomWallEdge("W_TOP", (100.0, 100.0), (200.0, 100.0)),
        SourceRoomWallEdge("W_RIGHT", (200.0, 100.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_LEFT", (100.0, 200.0), (100.0, 100.0)),
    ]
    # Two competing openings claiming the bottom edge
    openings = [
        SourceRoomOpeningCandidate("DOOR_D11", (100.0, 200.0), (200.0, 200.0)),
        SourceRoomOpeningCandidate("DOOR_D12", (100.0, 200.0), (200.0, 200.0)),
    ]

    sel = _selector("ROOM_AMB", "M-AMB")
    result = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=walls,
        opening_candidates=openings,
    )

    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert COMPETING_OPENING_CHORD_OWNERSHIP in result.reason_codes
    assert result.record is None


def test_negative_invalid_polygon():
    """Degenerate or collinear points fail closed."""
    sel = _selector()
    walls = [SourceRoomWallEdge("W1", (0.0, 0.0), (10.0, 0.0))]

    # Less than 3 points
    res1 = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=[(0.0, 0.0), (10.0, 0.0)],
        wall_edges=walls,
        opening_candidates=[],
    )
    assert res1.status == EvidenceResolutionStatus.ABSTAINED
    assert INVALID_ROOM_POLYGON in res1.reason_codes

    # Collinear points (zero area)
    res2 = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)],
        wall_edges=walls,
        opening_candidates=[],
    )
    assert res2.status == EvidenceResolutionStatus.ABSTAINED
    assert INVALID_ROOM_POLYGON in res2.reason_codes


def test_negative_no_wall_edges_present():
    """A polygon formed 100% of openings without any wall edge fails closed."""
    polygon = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, 100.0),
        (0.0, 100.0),
    ]
    openings = [
        SourceRoomOpeningCandidate("D1", (0.0, 0.0), (100.0, 0.0)),
        SourceRoomOpeningCandidate("D2", (100.0, 0.0), (100.0, 100.0)),
        SourceRoomOpeningCandidate("D3", (100.0, 100.0), (0.0, 100.0)),
        SourceRoomOpeningCandidate("D4", (0.0, 100.0), (0.0, 0.0)),
    ]
    sel = _selector("ROOM_VIRTUAL", "GHOST")
    res = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=[],
        opening_candidates=openings,
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert NO_WALL_EDGES_PRESENT in res.reason_codes


def test_negative_lineage_mismatch():
    """Invalid SHA-256 or selector fields fail closed."""
    with pytest.raises(ValueError):
        _selector(source_sha256="not_a_sha")

    # Non-selector object
    res = evaluate_source_room_boundary_doorway_shadow(
        None,  # type: ignore
        polygon_pdf_pts=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        wall_edges=[],
        opening_candidates=[],
    )
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_LINEAGE_MISMATCH in res.reason_codes


def test_metamorphic_translation_invariance():
    """Translating the entire room, walls, and opening by (+50, -30) yields identical candidate validity."""
    polygon = [
        (100.0, 100.0),
        (200.0, 100.0),
        (200.0, 200.0),
        (100.0, 200.0),
    ]
    walls = [
        SourceRoomWallEdge("W_TOP", (100.0, 100.0), (200.0, 100.0)),
        SourceRoomWallEdge("W_RIGHT", (200.0, 100.0), (200.0, 200.0)),
        SourceRoomWallEdge("W_LEFT", (100.0, 200.0), (100.0, 100.0)),
    ]
    openings = [
        SourceRoomOpeningCandidate("DOOR_D07", (100.0, 200.0), (200.0, 200.0))
    ]

    sel = _selector("ROOM_OFFICE", "OFFICE")
    res1 = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=walls,
        opening_candidates=openings,
    )
    assert res1.status == EvidenceResolutionStatus.CANDIDATE

    # Shift by dx=50, dy=-30
    dx, dy = 50.0, -30.0
    poly_shifted = [(x + dx, y + dy) for x, y in polygon]
    walls_shifted = [
        SourceRoomWallEdge(
            w.wall_id,
            (w.start_pt[0] + dx, w.start_pt[1] + dy),
            (w.end_pt[0] + dx, w.end_pt[1] + dy),
        )
        for w in walls
    ]
    openings_shifted = [
        SourceRoomOpeningCandidate(
            o.opening_id,
            (o.start_pt[0] + dx, o.start_pt[1] + dy),
            (o.end_pt[0] + dx, o.end_pt[1] + dy),
        )
        for o in openings
    ]

    res2 = evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=poly_shifted,
        wall_edges=walls_shifted,
        opening_candidates=openings_shifted,
    )
    assert res2.status == EvidenceResolutionStatus.CANDIDATE
    assert res1.record.area_sq_pt == res2.record.area_sq_pt
    assert res1.record.wall_edge_count == res2.record.wall_edge_count
    assert res1.record.opening_edge_count == res2.record.opening_edge_count


def test_no_input_mutation():
    """Verify input collections and objects are never mutated."""
    polygon = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    walls = [
        SourceRoomWallEdge("W1", (0.0, 0.0), (10.0, 0.0)),
        SourceRoomWallEdge("W2", (10.0, 0.0), (10.0, 10.0)),
        SourceRoomWallEdge("W3", (0.0, 10.0), (0.0, 0.0)),
    ]
    openings = [SourceRoomOpeningCandidate("O1", (0.0, 10.0), (10.0, 10.0))]

    poly_copy = copy.deepcopy(polygon)
    walls_copy = copy.deepcopy(walls)
    openings_copy = copy.deepcopy(openings)

    sel = _selector()
    evaluate_source_room_boundary_doorway_shadow(
        sel,
        polygon_pdf_pts=polygon,
        wall_edges=walls,
        opening_candidates=openings,
    )

    assert polygon == poly_copy
    assert walls == walls_copy
    assert openings == openings_copy
