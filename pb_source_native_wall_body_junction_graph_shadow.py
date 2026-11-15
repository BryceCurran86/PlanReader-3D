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
from pb_source_native_exterior_endpoint_authority_shadow import (
    CONTACT_PT,
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
    geometry_kind: str
    role: str

    def to_dict(self) -> dict[str, object]:
        return {
            "native_path_ids": list(self.native_path_ids),
            "native_source_layers": list(self.native_source_layers),
            "viewport_id": self.viewport_id,
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
        geometry_kind=GEOMETRY_OBSERVED,
        role=role,
    )


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
) -> tuple[tuple[SourceWallBodyRecord, ...], tuple[SourceJunctionRecord, ...]]:
    """Typed bodies and junctions. Collinear gaps stay unsnapped."""
    bodies: list[SourceWallBodyRecord] = []
    index_for: list[str] = []
    for bar in bars:
        if getattr(bar, "polygon", None) is None or bar.polygon.is_empty:
            continue
        provenance = _provenance_for_bar(bar, drawings)
        bounds = tuple(round(float(v), 3) for v in bar.polygon.bounds)
        if provenance is None:
            bodies.append(SourceWallBodyRecord(
                body_id=_body_id((), bounds),
                provenance=SourcePathProvenance((), (), "", GEOMETRY_OBSERVED, "unknown"),
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
            if kind == JUNCTION_L and roles == (
                "exterior_outer_face_candidate",
                "exterior_outer_face_candidate",
            ):
                kind = JUNCTION_CORNER_RETURN
            junctions.append(SourceJunctionRecord(
                junction_kind=kind,
                left_body_id=index_for[i],
                right_body_id=index_for[j],
                left_path_ids=left_ids,
                right_path_ids=right_ids,
                separation_pdf_pts=separation,
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
            provenance_geometry_kind=GEOMETRY_OBSERVED,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason="multi_face_meeting_needs_source_owned_wall_body",
        ))
    return tuple(bodies), tuple(junctions)


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
) -> dict[str, object]:
    """P0–P2 shadow graph. Zero quantities; collinear gaps are not walls."""
    attempt = attempt_source_native_outer_wall_first(drawings)
    bodies, junctions = classify_source_wall_body_junctions(
        _unique_source_wall_bars(drawings), drawings,
    )
    inferred = sum(1 for item in junctions if item.provenance_geometry_kind == GEOMETRY_INFERRED)
    joined = sum(
        1
        for item in junctions
        if item.status is EvidenceResolutionStatus.CANDIDATE
        and item.junction_kind != JUNCTION_COLLINEAR_GAP
    )
    return {
        "exterior_preflight_status": attempt.status,
        "exterior_preflight_reason": attempt.reason,
        "body_count": len(bodies),
        "junction_count": len(junctions),
        "bodies": [item.to_dict() for item in bodies],
        "junctions": [item.to_dict() for item in junctions],
        "inferred_join_count": inferred,
        "joined_candidate_count": joined,
        "collinear_gap_unsnapped_count": sum(
            1 for item in junctions if item.junction_kind == JUNCTION_COLLINEAR_GAP
        ),
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "can_issue_area": False,
        "official_frozen120_score_change": 0,
    }
