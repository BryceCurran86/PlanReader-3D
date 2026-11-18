"""Shadow: converge exterior edge ownership with corner endpoint witnesses.

Reusable original-native perimeter graph for footprint-first contours.
Consumes ``own_exterior_contour_native_paths`` and
``authenticate_external_wall_junction``. Prefer true dark wall ink over
nearby decorations (already filtered by edge ownership). Real joints require
representation contact; near-miss separations never mint walls or quantities.

Does not issue FIRM areas, mutate customer rows, or use project/benchmark
names as prediction inputs. Face handoff packets are selected by geometry
(edge index or outermost vertical face), not by house name.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_exterior_edge_path_ownership import (
    ExteriorEdgeNativeOwnership,
    own_exterior_contour_native_paths,
)
from pb_source_native_exterior_endpoint_authority_shadow import (
    CONTACT_PT,
    REASON_MISSING_NATIVE_PATH_OWNER,
    REASON_NEAR_MISS,
    authenticate_external_wall_junction,
)

_AXIS_PT = 2.0


def _xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def _segment_endpoints(
    drawings: Sequence[Mapping[str, Any] | object],
    path_index: int,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if not (0 <= path_index < len(drawings)):
        return None
    row = drawings[path_index]
    if not isinstance(row, Mapping):
        return None
    for item in row.get("items") or ():
        if not item or item[0] != "l" or len(item) < 3:
            continue
        return _xy(item[1]), _xy(item[2])
    return None


def _nearest_tip_to_corner(
    drawings: Sequence[Mapping[str, Any] | object],
    path_indices: Sequence[int],
    corner: tuple[float, float],
) -> tuple[int, ...] | None:
    """Unique path whose tip is nearest the corner; ties / empties abstain."""
    if not path_indices:
        return None
    scored: list[tuple[float, int]] = []
    for index in path_indices:
        ends = _segment_endpoints(drawings, int(index))
        if ends is None:
            continue
        dist = min(
            math.hypot(ends[0][0] - corner[0], ends[0][1] - corner[1]),
            math.hypot(ends[1][0] - corner[0], ends[1][1] - corner[1]),
        )
        if math.isfinite(dist):
            scored.append((round(dist, 4), int(index)))
    if not scored:
        return None
    best = min(dist for dist, _index in scored)
    cluster = tuple(sorted({index for dist, index in scored if dist == best}))
    return cluster if len(cluster) == 1 else None


def _tip_separation_pt(
    drawings: Sequence[Mapping[str, Any] | object],
    left_ids: Sequence[int],
    right_ids: Sequence[int],
    corner: tuple[float, float],
) -> float | None:
    left_ends = []
    right_ends = []
    for index in left_ids:
        ends = _segment_endpoints(drawings, int(index))
        if ends is not None:
            left_ends.extend(ends)
    for index in right_ids:
        ends = _segment_endpoints(drawings, int(index))
        if ends is not None:
            right_ends.extend(ends)
    if not left_ends or not right_ends:
        return None
    # Prefer tips nearest the contour corner on each side.
    left_tip = min(
        left_ends,
        key=lambda p: math.hypot(p[0] - corner[0], p[1] - corner[1]),
    )
    right_tip = min(
        right_ends,
        key=lambda p: math.hypot(p[0] - corner[0], p[1] - corner[1]),
    )
    return math.hypot(left_tip[0] - right_tip[0], left_tip[1] - right_tip[1])


@dataclass(frozen=True)
class ExteriorPerimeterCornerWitness:
    corner_index: int
    tip_pdf_pts: tuple[float, float]
    incoming_edge_index: int
    outgoing_edge_index: int
    incoming_path_ids: tuple[int, ...]
    outgoing_path_ids: tuple[int, ...]
    separation_pdf_pts: float | None
    status: EvidenceResolutionStatus
    reason: str
    joint_kind: str  # "contact_candidate" | "near_miss" | "unwitnessed"
    physical_join_authenticated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "corner_index": self.corner_index,
            "tip_pdf_pts": list(self.tip_pdf_pts),
            "incoming_edge_index": self.incoming_edge_index,
            "outgoing_edge_index": self.outgoing_edge_index,
            "incoming_path_ids": list(self.incoming_path_ids),
            "outgoing_path_ids": list(self.outgoing_path_ids),
            "separation_pdf_pts": self.separation_pdf_pts,
            "status": self.status.value,
            "reason": self.reason,
            "joint_kind": self.joint_kind,
            "physical_join_authenticated": False,
            "can_issue_area": False,
            "commercial_publishable": False,
        }


@dataclass(frozen=True)
class ExteriorPerimeterGraphShadow:
    source_sha256: str
    page_index: int
    edges: tuple[ExteriorEdgeNativeOwnership, ...]
    corners: tuple[ExteriorPerimeterCornerWitness, ...]
    owned_edge_count: int
    contact_corner_count: int
    near_miss_corner_count: int
    unwitnessed_corner_count: int
    closed_candidate: bool
    topology_only: bool = True
    physical_wall_authenticated: bool = False
    commercial_publishable: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "page_index": self.page_index,
            "edges": [edge.to_dict() for edge in self.edges],
            "corners": [corner.to_dict() for corner in self.corners],
            "owned_edge_count": self.owned_edge_count,
            "contact_corner_count": self.contact_corner_count,
            "near_miss_corner_count": self.near_miss_corner_count,
            "representation_contact_unauthenticated_count": sum(
                1
                for c in self.corners
                if c.joint_kind == "representation_contact_unauthenticated"
            ),
            "unwitnessed_corner_count": self.unwitnessed_corner_count,
            "closed_candidate": self.closed_candidate,
            "topology_only": True,
            "physical_wall_authenticated": False,
            "commercial_publishable": False,
            "measurement_authorized": False,
            "can_issue_area": False,
            "official_frozen120_score_change": 0,
        }


def _corner_witness(
    *,
    corner_index: int,
    corner: tuple[float, float],
    incoming: ExteriorEdgeNativeOwnership,
    outgoing: ExteriorEdgeNativeOwnership,
    drawings: Sequence[Mapping[str, Any] | object],
) -> ExteriorPerimeterCornerWitness:
    incoming_tip = _nearest_tip_to_corner(
        drawings, incoming.native_path_indices, corner,
    )
    outgoing_tip = _nearest_tip_to_corner(
        drawings, outgoing.native_path_indices, corner,
    )
    if incoming_tip is None or outgoing_tip is None:
        return ExteriorPerimeterCornerWitness(
            corner_index=corner_index,
            tip_pdf_pts=corner,
            incoming_edge_index=incoming.edge_index,
            outgoing_edge_index=outgoing.edge_index,
            incoming_path_ids=tuple(incoming.native_path_indices),
            outgoing_path_ids=tuple(outgoing.native_path_indices),
            separation_pdf_pts=None,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_MISSING_NATIVE_PATH_OWNER,
            joint_kind="unwitnessed",
        )
    separation = _tip_separation_pt(drawings, incoming_tip, outgoing_tip, corner)
    if separation is None:
        return ExteriorPerimeterCornerWitness(
            corner_index=corner_index,
            tip_pdf_pts=corner,
            incoming_edge_index=incoming.edge_index,
            outgoing_edge_index=outgoing.edge_index,
            incoming_path_ids=incoming_tip,
            outgoing_path_ids=outgoing_tip,
            separation_pdf_pts=None,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_MISSING_NATIVE_PATH_OWNER,
            joint_kind="unwitnessed",
        )
    status, reason = authenticate_external_wall_junction(
        native_path_ids=incoming_tip,
        nearby_native_path_ids=outgoing_tip,
        separation_pdf_pts=float(separation),
        drawings=drawings,
    )
    # Distance near-misses are not the same as representation contact that still
    # lacks painted exterior-layer proof. Keep them distinct for GPT1 handoff.
    if math.isfinite(separation) and separation > CONTACT_PT:
        joint_kind = "near_miss"
    elif status is EvidenceResolutionStatus.CANDIDATE:
        joint_kind = "contact_candidate"
    elif math.isfinite(separation) and separation <= CONTACT_PT:
        joint_kind = "representation_contact_unauthenticated"
    else:
        joint_kind = "unwitnessed"
    return ExteriorPerimeterCornerWitness(
        corner_index=corner_index,
        tip_pdf_pts=corner,
        incoming_edge_index=incoming.edge_index,
        outgoing_edge_index=outgoing.edge_index,
        incoming_path_ids=incoming_tip,
        outgoing_path_ids=outgoing_tip,
        separation_pdf_pts=round(float(separation), 4),
        status=status,
        reason=reason,
        joint_kind=joint_kind,
    )


def build_source_native_exterior_perimeter_graph(
    drawings: Sequence[Mapping[str, Any] | object],
    trace: ExternalFootprintTrace,
    *,
    closures: Sequence[Any] = (),
) -> ExteriorPerimeterGraphShadow:
    """Bind contour edges and authenticate corner joints, or ABSTAIN."""
    edges = own_exterior_contour_native_paths(drawings, trace, closures=closures)
    corners: list[ExteriorPerimeterCornerWitness] = []
    if edges:
        for index, incoming in enumerate(edges):
            outgoing = edges[(index + 1) % len(edges)]
            # Contour corner is the shared vertex: end of incoming == start of outgoing.
            corner = incoming.end_pdf_pts
            corners.append(
                _corner_witness(
                    corner_index=index,
                    corner=corner,
                    incoming=incoming,
                    outgoing=outgoing,
                    drawings=drawings,
                )
            )
    owned = sum(
        1
        for edge in edges
        if edge.status is EvidenceResolutionStatus.CANDIDATE and edge.native_path_indices
    )
    contact = sum(1 for c in corners if c.joint_kind == "contact_candidate")
    near_miss = sum(1 for c in corners if c.joint_kind == "near_miss")
    unauth_contact = sum(
        1 for c in corners if c.joint_kind == "representation_contact_unauthenticated"
    )
    unwitnessed = sum(1 for c in corners if c.joint_kind == "unwitnessed")
    closed_candidate = (
        len(edges) >= 4
        and owned == len(edges)
        and contact == len(corners)
        and near_miss == 0
        and unauth_contact == 0
        and unwitnessed == 0
    )
    return ExteriorPerimeterGraphShadow(
        source_sha256=str(trace.source_sha256 or ""),
        page_index=int(trace.page_index),
        edges=edges,
        corners=tuple(corners),
        owned_edge_count=owned,
        contact_corner_count=contact,
        near_miss_corner_count=near_miss,
        unwitnessed_corner_count=unwitnessed,
        closed_candidate=closed_candidate,
    )


def select_outermost_vertical_face_edge_index(
    edges: Sequence[ExteriorEdgeNativeOwnership],
    *,
    prefer_max_x: bool = True,
) -> int | None:
    """Geometric face selector — no project name. Ties abstain."""
    vertical: list[tuple[float, int]] = []
    for edge in edges:
        start, end = edge.start_pdf_pts, edge.end_pdf_pts
        if abs(start[0] - end[0]) > _AXIS_PT:
            continue
        if abs(start[1] - end[1]) <= NOISE_PT:
            continue
        if edge.status is not EvidenceResolutionStatus.CANDIDATE:
            continue
        if not edge.native_path_indices:
            continue
        vertical.append((round((start[0] + end[0]) / 2.0, 4), int(edge.edge_index)))
    if not vertical:
        return None
    target = max(x for x, _i in vertical) if prefer_max_x else min(x for x, _i in vertical)
    cluster = [i for x, i in vertical if x == target]
    return cluster[0] if len(cluster) == 1 else None


def export_exterior_face_evidence_packet(
    graph: ExteriorPerimeterGraphShadow,
    *,
    edge_index: int,
) -> dict[str, Any]:
    """Shadow handoff for a single owned face. Never FIRM / customer."""
    edge = next((e for e in graph.edges if e.edge_index == int(edge_index)), None)
    if edge is None:
        return {
            "status": EvidenceResolutionStatus.ABSTAINED.value,
            "reason": "exterior_face_edge_index_missing",
            "edge_index": int(edge_index),
            "physical_wall_authenticated": False,
            "can_issue_area": False,
            "commercial_publishable": False,
        }
    start_corner = next(
        (c for c in graph.corners if c.outgoing_edge_index == edge.edge_index),
        None,
    )
    end_corner = next(
        (c for c in graph.corners if c.incoming_edge_index == edge.edge_index),
        None,
    )
    return {
        "status": edge.status.value,
        "reason": edge.reason,
        "classification": edge.classification,
        "edge_index": edge.edge_index,
        "start_pdf_pts": list(edge.start_pdf_pts),
        "end_pdf_pts": list(edge.end_pdf_pts),
        "native_path_indices": list(edge.native_path_indices),
        "unique_owner_overlap_fraction": edge.unique_owner_overlap_fraction,
        "chain_start_shortfall_pt": edge.chain_start_shortfall_pt,
        "chain_end_shortfall_pt": edge.chain_end_shortfall_pt,
        "start_corner": None if start_corner is None else start_corner.to_dict(),
        "end_corner": None if end_corner is None else end_corner.to_dict(),
        "source_sha256": graph.source_sha256,
        "page_index": graph.page_index,
        "topology_only": True,
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "can_issue_area": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
        "consumer_note": (
            "GPT1 may consume this face as source-owned exterior ink evidence. "
            "It is not physical-wall or area authority."
        ),
    }
