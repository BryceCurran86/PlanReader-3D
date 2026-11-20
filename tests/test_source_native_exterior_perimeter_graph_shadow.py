"""Synthetic perimeter-graph: dark-ink ownership + real joints vs near-misses."""
from __future__ import annotations

import fitz

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_exterior_endpoint_authority_shadow import (
    CONTACT_PT,
    REASON_NEAR_MISS,
)
from pb_source_native_exterior_perimeter_graph_shadow import (
    build_source_native_exterior_perimeter_graph,
    export_exterior_face_evidence_packet,
    select_outermost_vertical_face_edge_index,
)


def _trace(points, *, sha="ab" * 32):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return ExternalFootprintTrace(
        source_sha256=sha,
        page_index=0,
        status="CANDIDATE",
        reason="test_morphological_contour",
        polygon_pdf_pts=tuple(points),
        bbox_pdf_pts=(min(xs), min(ys), max(xs), max(ys)),
        candidate_count=1,
        commercial_publishable=False,
        measurement_authorized=False,
    )


def _stroke(a, b, *, dashes="", width=0.5, layer="WallExternal", color=(0.0, 0.0, 0.0), fill=None):
    row = {
        "layer": layer,
        "fill": fill,
        "color": color,
        "width": width,
        "dashes": dashes,
        "items": [("l", fitz.Point(*a), fitz.Point(*b))],
    }
    if fill is not None:
        row["type"] = "fs"
    else:
        row["type"] = "s"
    return row


def _painted(a, b, *, layer="WallExternal"):
    # Painted exterior layer required for contact_candidate junction.
    x0, y0 = a
    x1, y1 = b
    return {
        "layer": layer,
        "fill": (0.0, 0.0, 0.0),
        "color": (0.0, 0.0, 0.0),
        "width": 0.5,
        "dashes": "",
        "type": "fs",
        "items": [("l", fitz.Point(*a), fitz.Point(*b))],
        "rect": (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
    }


def test_closed_dark_rectangle_owns_edges_and_reports_corner_joints():
    drawings = [
        _painted((200.0, 130.0), (200.0, 490.0)),
        _painted((200.0, 130.0), (800.0, 130.0)),
        _painted((800.0, 130.0), (800.0, 490.0)),
        _painted((200.0, 490.0), (800.0, 490.0)),
    ]
    graph = build_source_native_exterior_perimeter_graph(
        drawings,
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    assert len(graph.edges) == 4
    assert graph.owned_edge_count == 4
    assert len(graph.corners) == 4
    assert all(c.separation_pdf_pts is not None for c in graph.corners)
    assert graph.physical_wall_authenticated is False
    assert graph.commercial_publishable is False


def test_near_miss_corner_is_not_a_physical_join():
    # Right vertical stops 0.4 pt short of the SE corner — classic near-miss.
    gap = 0.4
    assert gap > CONTACT_PT
    drawings = [
        _painted((200.0, 130.0), (200.0, 490.0)),
        _painted((200.0, 130.0), (800.0, 130.0)),
        _painted((800.0, 130.0), (800.0, 490.0 - gap)),
        _painted((200.0, 490.0), (800.0, 490.0)),
    ]
    graph = build_source_native_exterior_perimeter_graph(
        drawings,
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    se = next(c for c in graph.corners if c.tip_pdf_pts == (800.0, 490.0))
    assert se.joint_kind == "near_miss"
    assert se.status is EvidenceResolutionStatus.ABSTAINED
    assert se.reason == REASON_NEAR_MISS
    assert se.physical_join_authenticated is False
    assert graph.closed_candidate is False


def test_stroke_only_contact_is_not_labeled_distance_near_miss():
    # Tips coincide, but strokes are not painted WallExternal fills — still not
    # a physical join, and must not be conflated with a geometric near-miss.
    drawings = [
        _stroke((200.0, 130.0), (200.0, 490.0), layer="WallExternal"),
        _stroke((200.0, 130.0), (800.0, 130.0), layer="WallExternal"),
        _stroke((800.0, 130.0), (800.0, 490.0), layer="WallExternal"),
        _stroke((200.0, 490.0), (800.0, 490.0), layer="WallExternal"),
    ]
    graph = build_source_native_exterior_perimeter_graph(
        drawings,
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    assert graph.near_miss_corner_count == 0
    assert all(
        c.joint_kind == "representation_contact_unauthenticated"
        for c in graph.corners
    )
    assert all(c.status is EvidenceResolutionStatus.ABSTAINED for c in graph.corners)
    assert graph.closed_candidate is False


def test_pale_decoration_does_not_steal_dark_outer_owner():
    drawings = [
        _stroke((200.0, 130.0), (200.0, 490.0)),
        _stroke((200.0, 130.0), (800.0, 130.0)),
        _stroke((800.0, 130.0), (800.0, 490.0)),
        _stroke((200.0, 490.0), (800.0, 490.0)),
        # Pale mid-grey guide just outside the east face.
        _stroke(
            (802.0, 130.0), (802.0, 490.0),
            color=(0.7, 0.7, 0.7), layer="Guide_Annotation",
        ),
    ]
    graph = build_source_native_exterior_perimeter_graph(
        drawings,
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    east = next(e for e in graph.edges if e.start_pdf_pts[0] == 800.0 and e.end_pdf_pts[0] == 800.0)
    assert east.status is EvidenceResolutionStatus.CANDIDATE
    assert east.native_path_indices == (2,)


def test_outermost_vertical_face_selector_and_handoff_packet():
    drawings = [
        _stroke((200.0, 130.0), (200.0, 490.0)),
        _stroke((200.0, 130.0), (800.0, 130.0)),
        _stroke((800.0, 130.0), (800.0, 490.0)),
        _stroke((200.0, 490.0), (800.0, 490.0)),
    ]
    graph = build_source_native_exterior_perimeter_graph(
        drawings,
        _trace(((200.0, 130.0), (800.0, 130.0), (800.0, 490.0), (200.0, 490.0))),
    )
    east_index = select_outermost_vertical_face_edge_index(graph.edges, prefer_max_x=True)
    assert east_index == 1  # contour order: N, E, S, W starting at NW going east first? 
    # points: (200,130)->(800,130)=edge0 north; (800,130)->(800,490)=edge1 east
    assert east_index == 1
    packet = export_exterior_face_evidence_packet(graph, edge_index=east_index)
    assert packet["edge_index"] == 1
    assert packet["native_path_indices"] == [2]
    assert packet["physical_wall_authenticated"] is False
    assert packet["can_issue_area"] is False
    assert "GPT1" in packet["consumer_note"]
