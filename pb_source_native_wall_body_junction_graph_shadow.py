"""Shadow: source-owned wall-body / junction graph with typed provenance.

Cursor P0–P2 on GPT1's research→repo handoff. Reuses the #4347 native bars
and endpoint identity receipts. Does not snap collinear gaps, does not copy
a second heavy-stroke collector, and does not promote an exterior footprint.
Observed source ink stays observed; inferred joins are never emitted as
physical walls.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Point
from shapely.ops import nearest_points

from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _collect_strips,
    _source_wall_ink_candidate_drawings,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
from pb_next_wall_ring_preview import (
    _collect_cavity_multi_face_strips,
    _collect_monotonic_source_stroke_pairs,
    _collect_source_heavy_stroke_strips,
    _collect_source_wide_face_pairs,
)
from pb_new_wall_graph_diagnostic import inspect_native_wall_graph
from pb_source_native_exterior_endpoint_authority_shadow import (
    CONTACT_PT,
    REASON_COMPETING,
    ROLE_DIAGONAL_BRIDGE,
    ROLE_EXCLUSION,
    ROLE_EXTERIOR_OUTER_FACE,
    ROLE_UNKNOWN,
    authenticate_external_wall_junction,
    classify_source_native_path_role,
)

GEOMETRY_OBSERVED = "observed_source_ink"
GEOMETRY_INFERRED = "inferred_not_source_ink"

JUNCTION_L = "l_corner"
JUNCTION_T = "t_junction"
JUNCTION_CROSS = "cross_junction"
JUNCTION_MULTI = "multi_face_meeting"
JUNCTION_COLLINEAR_GAP = "collinear_gap_unsnapped"
JUNCTION_CORNER_RETURN = "corner_return"

REASON_MISSING_PROVENANCE = "source_path_provenance_missing"
REASON_INFERRED_JOIN_FORBIDDEN = "inferred_collinear_join_not_source_ink"
REASON_NON_STRUCTURAL = "visual_crossing_without_structural_native_witness"
REASON_UNCLOSED_EXTERIOR = "unclosed_exterior_endpoint_no_unique_jamb"
REASON_DUPLICATE_PATH_OWNER = "duplicate_native_path_owner"
REASON_LAYER_NOT_PHYSICAL = "exterior_layer_name_is_not_physical_wall"
REASON_WINDOW_NO_UNIQUE_JAMB = "window_gap_missing_unique_hosted_jamb_pair"
JUNCTION_WINDOW_CONTINUITY = "window_aperture_continuity"


def _path_ids(bar: Any) -> tuple[int, ...]:
    return tuple(sorted({int(v) for v in bar.native_path_indices()}))


def _layers_for(drawings: Sequence[Mapping[str, Any] | object], paths: Sequence[int]) -> tuple[str, ...]:
    out = []
    for index in paths:
        if 0 <= index < len(drawings) and isinstance(drawings[index], Mapping):
            layer = str(drawings[index].get("layer") or "").strip()
            if layer:
                out.append(layer)
    return tuple(out)


def _axis(bar: Any) -> str:
    x0, y0, x1, y1 = (float(v) for v in bar.polygon.bounds)
    if (x1 - x0) > (y1 - y0) + CONTACT_PT:
        return "h"
    if (y1 - y0) > (x1 - x0) + CONTACT_PT:
        return "v"
    return "unknown"


def _tips(bar: Any) -> tuple[tuple[float, float], tuple[float, float]]:
    x0, y0, x1, y1 = (float(v) for v in bar.polygon.bounds)
    if _axis(bar) == "h":
        return (x0, (y0 + y1) / 2.0), (x1, (y0 + y1) / 2.0)
    if _axis(bar) == "v":
        return ((x0 + x1) / 2.0, y0), ((x0 + x1) / 2.0, y1)
    return (x0, y0), (x1, y1)


def _tip_hits(tip: tuple[float, float], bar: Any) -> bool:
    return float(Point(tip).distance(bar.polygon)) <= CONTACT_PT


def _thickness(bar: Any) -> float:
    x0, y0, x1, y1 = (float(v) for v in bar.polygon.bounds)
    return min(x1 - x0, y1 - y0)


def _tip_hits_interior(tip: tuple[float, float], bar: Any) -> bool:
    if not _tip_hits(tip, bar):
        return False
    corner_pt = max(_thickness(bar), 4 * CONTACT_PT) + CONTACT_PT
    return min(float(Point(tip).distance(Point(other))) for other in _tips(bar)) > corner_pt


@dataclass(frozen=True)
class SourcePathProvenance:
    native_path_ids: tuple[int, ...]
    native_source_layers: tuple[str, ...]
    viewport_id: str
    page_index: int
    geometry_kind: str
    role: str

    def to_dict(self) -> dict[str, object]:
        return {
            "native_path_ids": list(self.native_path_ids),
            "native_source_layers": list(self.native_source_layers),
            "viewport_id": self.viewport_id,
            "page_index": self.page_index,
            "geometry_kind": self.geometry_kind,
            "role": self.role,
        }


@dataclass(frozen=True)
class SourceWallBodyRecord:
    body_id: str
    provenance: SourcePathProvenance
    bounds_pdf_pts: tuple[float, float, float, float]
    long_axis: str
    status: EvidenceResolutionStatus
    reason: str
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "body_id": self.body_id,
            "provenance": self.provenance.to_dict(),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "long_axis": self.long_axis,
            "status": self.status.value,
            "reason": self.reason,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class SourceJunctionRecord:
    junction_kind: str
    left_body_id: str
    right_body_id: str
    left_path_ids: tuple[int, ...]
    right_path_ids: tuple[int, ...]
    separation_pdf_pts: float
    contact_pdf_pts: tuple[float, float]
    page_index: int
    provenance_geometry_kind: str
    status: EvidenceResolutionStatus
    reason: str
    physical_join_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "junction_kind": self.junction_kind,
            "left_body_id": self.left_body_id,
            "right_body_id": self.right_body_id,
            "left_path_ids": list(self.left_path_ids),
            "right_path_ids": list(self.right_path_ids),
            "separation_pdf_pts": self.separation_pdf_pts,
            "contact_pdf_pts": list(self.contact_pdf_pts),
            "page_index": self.page_index,
            "provenance_geometry_kind": self.provenance_geometry_kind,
            "status": self.status.value,
            "reason": self.reason,
            "physical_join_authenticated": False,
            "measurement_authorized": False,
        }


def _body_id(paths: Sequence[int], bounds: Sequence[float]) -> str:
    return "body:" + ",".join(str(v) for v in paths) + ":" + ",".join(
        f"{float(v):.3f}" for v in bounds
    )


def _provenance_for_bar(
    bar: Any,
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_index: int = -1,
) -> SourcePathProvenance | None:
    paths = _path_ids(bar)
    if not paths:
        return None
    layers = _layers_for(drawings, paths)
    role = ROLE_UNKNOWN
    if 0 <= paths[0] < len(drawings):
        role = classify_source_native_path_role(drawings[paths[0]])
    viewport = ""
    row = drawings[paths[0]] if 0 <= paths[0] < len(drawings) else None
    if isinstance(row, Mapping):
        viewport = str(row.get("viewport_id") or row.get("source_viewport_id") or "").strip()
    return SourcePathProvenance(
        native_path_ids=paths,
        native_source_layers=layers,
        viewport_id=viewport,
        page_index=page_index,
        geometry_kind=GEOMETRY_OBSERVED,
        role=role,
    )


def _contact_point(left: Any, right: Any) -> tuple[float, float]:
    a, b = nearest_points(left.polygon, right.polygon)
    return (round((a.x + b.x) / 2.0, 3), round((a.y + b.y) / 2.0, 3))


def _classify_pair(left: Any, right: Any) -> str | None:
    distance = float(left.polygon.distance(right.polygon))
    left_axis, right_axis = _axis(left), _axis(right)
    if distance > CONTACT_PT:
        if left_axis == right_axis != "unknown" and 0.03 < distance <= 2.5:
            return JUNCTION_COLLINEAR_GAP
        return None
    left_tip_hits = any(_tip_hits(tip, right) for tip in _tips(left))
    right_tip_hits = any(_tip_hits(tip, left) for tip in _tips(right))
    left_into = any(_tip_hits_interior(tip, right) for tip in _tips(left))
    right_into = any(_tip_hits_interior(tip, left) for tip in _tips(right))
    overlap = left.polygon.intersection(right.polygon)
    overlap_area = float(overlap.area) if overlap is not None and not overlap.is_empty else 0.0
    if overlap_area > CONTACT_PT and left_axis != right_axis:
        return JUNCTION_CROSS
    if left_into != right_into:
        return JUNCTION_T
    if (left_tip_hits or right_tip_hits) and left_axis != right_axis:
        return JUNCTION_L
    return None


def classify_source_wall_body_junctions(
    bars: Sequence[Any],
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_index: int = -1,
) -> tuple[tuple[SourceWallBodyRecord, ...], tuple[SourceJunctionRecord, ...]]:
    """Typed bodies and junctions. Collinear gaps stay unsnapped."""
    bodies: list[SourceWallBodyRecord] = []
    index_for: list[str] = []
    for bar in bars:
        if getattr(bar, "polygon", None) is None or bar.polygon.is_empty:
            continue
        provenance = _provenance_for_bar(bar, drawings, page_index=page_index)
        bounds = tuple(round(float(v), 3) for v in bar.polygon.bounds)
        if provenance is None:
            bodies.append(SourceWallBodyRecord(
                body_id=_body_id((), bounds),
                provenance=SourcePathProvenance(
                    (), (), "", page_index, GEOMETRY_OBSERVED, "unknown",
                ),
                bounds_pdf_pts=bounds,
                long_axis=_axis(bar),
                status=EvidenceResolutionStatus.ABSTAINED,
                reason=REASON_MISSING_PROVENANCE,
            ))
            index_for.append(bodies[-1].body_id)
            continue
        bodies.append(SourceWallBodyRecord(
            body_id=_body_id(provenance.native_path_ids, bounds),
            provenance=provenance,
            bounds_pdf_pts=bounds,
            long_axis=_axis(bar),
            status=EvidenceResolutionStatus.CANDIDATE,
            reason="source_wall_body_observed_not_physical_authority",
        ))
        index_for.append(bodies[-1].body_id)
    owner_counts: dict[int, int] = {}
    for body in bodies:
        for path in body.provenance.native_path_ids:
            owner_counts[path] = owner_counts.get(path, 0) + 1
    bodies = [
        body
        if not any(owner_counts.get(path, 0) > 1 for path in body.provenance.native_path_ids)
        else SourceWallBodyRecord(
            body_id=body.body_id,
            provenance=body.provenance,
            bounds_pdf_pts=body.bounds_pdf_pts,
            long_axis=body.long_axis,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_DUPLICATE_PATH_OWNER,
        )
        for body in bodies
    ]
    valid = [bar for bar in bars if getattr(bar, "polygon", None) is not None and not bar.polygon.is_empty]
    contacts: dict[int, set[int]] = {i: set() for i in range(len(valid))}
    junctions: list[SourceJunctionRecord] = []
    for i, left in enumerate(valid):
        for j in range(i + 1, len(valid)):
            right = valid[j]
            kind = _classify_pair(left, right)
            if kind is None:
                continue
            left_ids, right_ids = _path_ids(left), _path_ids(right)
            separation = round(float(left.polygon.distance(right.polygon)), 4)
            status, reason = authenticate_external_wall_junction(
                native_path_ids=left_ids,
                nearby_native_path_ids=right_ids,
                separation_pdf_pts=separation,
                drawings=drawings,
            )
            if kind == JUNCTION_COLLINEAR_GAP:
                status = EvidenceResolutionStatus.ABSTAINED
                reason = REASON_INFERRED_JOIN_FORBIDDEN
            roles = (
                bodies[i].provenance.role,
                bodies[j].provenance.role,
            )
            if any(role in {ROLE_EXCLUSION, ROLE_DIAGONAL_BRIDGE} for role in roles):
                status = EvidenceResolutionStatus.ABSTAINED
                if reason != REASON_COMPETING:
                    reason = REASON_NON_STRUCTURAL
            if kind == JUNCTION_L and roles == (
                ROLE_EXTERIOR_OUTER_FACE,
                ROLE_EXTERIOR_OUTER_FACE,
            ):
                kind = JUNCTION_CORNER_RETURN
            junctions.append(SourceJunctionRecord(
                junction_kind=kind,
                left_body_id=index_for[i],
                right_body_id=index_for[j],
                left_path_ids=left_ids,
                right_path_ids=right_ids,
                separation_pdf_pts=separation,
                contact_pdf_pts=_contact_point(left, right),
                page_index=page_index,
                provenance_geometry_kind=GEOMETRY_OBSERVED,
                status=status,
                reason=reason,
            ))
            if separation <= CONTACT_PT:
                contacts[i].add(j)
                contacts[j].add(i)
    seen_multi: set[tuple[int, ...]] = set()
    for index, neighbours in contacts.items():
        if len(neighbours) < 2:
            continue
        members = tuple(sorted((index, *neighbours)))
        if members in seen_multi:
            continue
        seen_multi.add(members)
        junctions.append(SourceJunctionRecord(
            junction_kind=JUNCTION_MULTI,
            left_body_id=index_for[members[0]],
            right_body_id=index_for[members[1]],
            left_path_ids=_path_ids(valid[members[0]]),
            right_path_ids=_path_ids(valid[members[1]]),
            separation_pdf_pts=0.0,
            contact_pdf_pts=_contact_point(valid[members[0]], valid[members[1]]),
            page_index=page_index,
            provenance_geometry_kind=GEOMETRY_OBSERVED,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason="multi_face_meeting_needs_source_owned_wall_body",
        ))
    return tuple(bodies), tuple(junctions)


def _open_endpoint_receipts(bars: Sequence[Any]) -> tuple[dict[str, object], ...]:
    opens: list[dict[str, object]] = []
    valid = [bar for bar in bars if getattr(bar, "polygon", None) is not None and not bar.polygon.is_empty]
    for i, bar in enumerate(valid):
        for tip in _tips(bar):
            if any(j != i and _tip_hits(tip, valid[j]) for j in range(len(valid))):
                continue
            nearest_sep = None
            nearby: tuple[int, ...] = ()
            for j, other in enumerate(valid):
                if j == i:
                    continue
                sep = float(Point(tip).distance(other.polygon))
                if nearest_sep is None or sep < nearest_sep:
                    nearest_sep = sep
                    nearby = _path_ids(other)
            opens.append({
                "tip_pdf_pts": [round(float(tip[0]), 3), round(float(tip[1]), 3)],
                "native_path_ids": list(_path_ids(bar)),
                "nearby_native_path_ids": list(nearby),
                "separation_pdf_pts": None if nearest_sep is None else round(float(nearest_sep), 4),
                "status": EvidenceResolutionStatus.ABSTAINED.value,
                "reason": REASON_UNCLOSED_EXTERIOR,
                "physical_join_authenticated": False,
                "measurement_authorized": False,
                "snap_join_applied": False,
            })
    opens.sort(key=lambda row: (
        float("inf") if row["separation_pdf_pts"] is None else float(row["separation_pdf_pts"]),
        row["native_path_ids"],
        row["nearby_native_path_ids"],
        row["tip_pdf_pts"],
    ))
    return tuple(opens)


def authenticate_window_continuity_topology(
    *,
    left_host_path_ids: Sequence[int],
    right_host_path_ids: Sequence[int],
    left_jamb_path_ids: Sequence[int],
    right_jamb_path_ids: Sequence[int],
    sill_or_floor_path_ids: Sequence[int],
    drawings: Sequence[Mapping[str, Any] | object],
) -> tuple[EvidenceResolutionStatus, str]:
    """Topology-only window continuity. Never a wall and never a quantity."""
    hosts = (tuple(left_host_path_ids), tuple(right_host_path_ids))
    jambs = (tuple(left_jamb_path_ids), tuple(right_jamb_path_ids))
    sill = tuple(sill_or_floor_path_ids)
    owned = (*hosts[0], *hosts[1], *jambs[0], *jambs[1], *sill)
    if (
        not hosts[0] or not hosts[1] or not jambs[0] or not jambs[1] or not sill
        or len(set(owned)) != len(owned)
        or not set(hosts[0]).isdisjoint(set(hosts[1]))
        or not set(jambs[0]).isdisjoint(set(jambs[1]))
    ):
        return EvidenceResolutionStatus.ABSTAINED, REASON_WINDOW_NO_UNIQUE_JAMB
    status, reason = authenticate_external_wall_junction(
        native_path_ids=hosts[0],
        nearby_native_path_ids=hosts[1],
        separation_pdf_pts=CONTACT_PT,
        drawings=drawings,
    )
    if status is EvidenceResolutionStatus.ABSTAINED and reason in {
        REASON_COMPETING,
        "native_source_path_owner_missing",
        "foreign_view_path_index_collision",
        "native_path_owners_not_disjoint",
    }:
        return status, reason
    for path in owned:
        if not (0 <= path < len(drawings)) or not isinstance(drawings[path], Mapping):
            return EvidenceResolutionStatus.ABSTAINED, REASON_WINDOW_NO_UNIQUE_JAMB
    return EvidenceResolutionStatus.CANDIDATE, "window_continuity_topology_only_not_wall"


def classify_window_continuity_edges(
    junctions: Sequence[SourceJunctionRecord],
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_index: int = -1,
    opening_witnesses: Sequence[Mapping[str, Any]] = (),
    open_endpoints: Sequence[Mapping[str, Any]] = (),
) -> tuple[SourceJunctionRecord, ...]:
    """Window gaps stay topology-only. Length, ASW text, and nearest snap are not hosts."""
    by_hosts = {
        (tuple(row.get("left_host_path_ids") or ()), tuple(row.get("right_host_path_ids") or ())): row
        for row in opening_witnesses
        if isinstance(row, Mapping)
    }

    def _edge(left_ids, right_ids, sep, contact, left_body="", right_body=""):
        key = (tuple(left_ids), tuple(right_ids))
        mirror = (tuple(right_ids), tuple(left_ids))
        witness = by_hosts.get(key) or by_hosts.get(mirror) or {}
        status, reason = authenticate_window_continuity_topology(
            left_host_path_ids=witness.get("left_host_path_ids") or (),
            right_host_path_ids=witness.get("right_host_path_ids") or (),
            left_jamb_path_ids=witness.get("left_jamb_path_ids") or (),
            right_jamb_path_ids=witness.get("right_jamb_path_ids") or (),
            sill_or_floor_path_ids=witness.get("sill_or_floor_path_ids") or (),
            drawings=drawings,
        )
        return SourceJunctionRecord(
            junction_kind=JUNCTION_WINDOW_CONTINUITY,
            left_body_id=left_body,
            right_body_id=right_body,
            left_path_ids=tuple(left_ids),
            right_path_ids=tuple(right_ids),
            separation_pdf_pts=float(sep),
            contact_pdf_pts=tuple(contact),
            page_index=page_index,
            provenance_geometry_kind=GEOMETRY_INFERRED,
            status=status,
            reason=reason if status is EvidenceResolutionStatus.ABSTAINED else (
                "window_continuity_topology_only_not_wall"
            ),
        )

    out: list[SourceJunctionRecord] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for item in junctions:
        if item.junction_kind != JUNCTION_COLLINEAR_GAP:
            continue
        pair = tuple(sorted((item.left_path_ids, item.right_path_ids)))
        if pair in seen:
            continue
        seen.add(pair)
        out.append(_edge(
            item.left_path_ids, item.right_path_ids, item.separation_pdf_pts,
            item.contact_pdf_pts, item.left_body_id, item.right_body_id,
        ))
    for row in open_endpoints:
        if not isinstance(row, Mapping):
            continue
        left_ids = tuple(int(v) for v in (row.get("native_path_ids") or ()))
        right_ids = tuple(int(v) for v in (row.get("nearby_native_path_ids") or ()))
        sep = row.get("separation_pdf_pts")
        if not left_ids or not right_ids or sep is None or float(sep) <= CONTACT_PT:
            continue
        pair = tuple(sorted((left_ids, right_ids)))
        if pair in seen:
            continue
        seen.add(pair)
        tip = tuple(float(v) for v in (row.get("tip_pdf_pts") or (0.0, 0.0)))
        if len(tip) != 2:
            tip = (0.0, 0.0)
        out.append(_edge(left_ids, right_ids, sep, tip))
    return tuple(out)


def audit_source_native_exterior_cycle(
    bars: Sequence[Any],
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_index: int = -1,
    opening_chassis_witness: bool = False,
    bodies: Sequence[SourceWallBodyRecord] | None = None,
) -> dict[str, object]:
    """Unique-or-abstain outer cycle. Layer names are not physical walls."""
    if bodies is None:
        bodies, _junctions = classify_source_wall_body_junctions(
            bars, drawings, page_index=page_index,
        )
    opens = _open_endpoint_receipts(bars)
    graph = inspect_native_wall_graph(bars, source_drawings=drawings)
    exterior_bodies = tuple(
        body for body in bodies if body.provenance.role == ROLE_EXTERIOR_OUTER_FACE
    )
    first = opens[0] if opens else None
    closed = (
        not opens
        and len(exterior_bodies) >= 3
        and all(body.status is not EvidenceResolutionStatus.ABSTAINED for body in exterior_bodies)
        and opening_chassis_witness is False
        and graph.second_stage_join_applied is False
    )
    return {
        "status": (
            EvidenceResolutionStatus.CANDIDATE.value
            if closed else EvidenceResolutionStatus.ABSTAINED.value
        ),
        "reason": (
            "source_exterior_cycle_candidate_not_physical_authority"
            if closed else (
                first["reason"] if first else REASON_UNCLOSED_EXTERIOR
            )
        ),
        "first_unclosed_endpoint": first,
        "open_endpoint_count": len(opens),
        "open_endpoints": list(opens),
        "component_count": graph.component_count,
        "second_stage_join_applied": graph.second_stage_join_applied,
        "exterior_layer_body_count": len(exterior_bodies),
        "exterior_layer_is_not_physical_wall": True,
        "candidate_outer_cycle_count": 1 if closed else 0,
        "path_id_sequence": [
            list(body.provenance.native_path_ids) for body in exterior_bodies
        ],
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "layer_name_physical_promotion": False,
        "snap_join_applied": False,
    }


def _unique_source_wall_bars(drawings: Sequence[Mapping[str, Any] | object]) -> list[Any]:
    wall_ink = _source_wall_ink_candidate_drawings(drawings)[0]
    named, _other = _collect_strips(wall_ink)
    bars = (
        list(named)
        + list(_collect_dark_painted_source_wall_strips(wall_ink))
        + list(_collect_monotonic_source_stroke_pairs(wall_ink))
        + list(_collect_source_heavy_stroke_strips(wall_ink))
        + list(_collect_cavity_multi_face_strips(wall_ink))
        + list(_collect_source_wide_face_pairs(wall_ink))
    )
    unique = {}
    for bar in bars:
        if getattr(bar, "polygon", None) is None or bar.polygon.is_empty:
            continue
        key = (int(bar.path_index), *(round(float(v), 4) for v in bar.polygon.bounds))
        unique[key] = bar
    return list(unique.values())


def build_source_native_wall_body_junction_graph(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_index: int = -1,
) -> dict[str, object]:
    """P0–P2 shadow graph. Zero quantities; collinear gaps are not walls."""
    attempt = attempt_source_native_outer_wall_first(drawings)
    bars = _unique_source_wall_bars(drawings)
    bodies, junctions = classify_source_wall_body_junctions(
        bars, drawings, page_index=page_index,
    )
    cycle = audit_source_native_exterior_cycle(
        bars, drawings, page_index=page_index, bodies=bodies,
    )
    window_edges = classify_window_continuity_edges(
        junctions,
        drawings,
        page_index=page_index,
        open_endpoints=cycle.get("open_endpoints") or (),
    )
    inferred = sum(1 for item in junctions if item.provenance_geometry_kind == GEOMETRY_INFERRED)
    joined = sum(
        1
        for item in junctions
        if item.status is EvidenceResolutionStatus.CANDIDATE
        and item.junction_kind != JUNCTION_COLLINEAR_GAP
    )
    refused = sum(1 for item in junctions if item.status is EvidenceResolutionStatus.ABSTAINED)
    return {
        "page_index": page_index,
        "exterior_preflight_status": attempt.status,
        "exterior_preflight_reason": attempt.reason,
        "component_count": cycle["component_count"],
        "body_count": len(bodies),
        "junction_count": len(junctions),
        "bodies": [item.to_dict() for item in bodies],
        "junctions": [item.to_dict() for item in junctions],
        "inferred_join_count": inferred,
        "joined_candidate_count": joined,
        "refused_join_count": refused,
        "collinear_gap_unsnapped_count": sum(
            1 for item in junctions if item.junction_kind == JUNCTION_COLLINEAR_GAP
        ),
        "window_continuity_edges": [item.to_dict() for item in window_edges],
        "window_continuity_candidate_count": sum(
            1 for item in window_edges if item.status is EvidenceResolutionStatus.CANDIDATE
        ),
        "window_continuity_abstain_count": sum(
            1 for item in window_edges if item.status is EvidenceResolutionStatus.ABSTAINED
        ),
        "exterior_cycle": cycle,
        "first_unclosed_endpoint": cycle["first_unclosed_endpoint"],
        "open_endpoint_count": cycle["open_endpoint_count"],
        "candidate_outer_cycle_count": cycle["candidate_outer_cycle_count"],
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "can_issue_area": False,
        "official_frozen120_score_change": 0,
        "snap_join_applied": False,
        "layer_name_physical_promotion": False,
    }
