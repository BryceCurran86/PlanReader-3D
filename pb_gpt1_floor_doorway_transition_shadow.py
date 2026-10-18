"""Source-neutral doorway floor-boundary corroboration, SHADOW ONLY.

Does not close room rings, create door frames, infer floor finishes, compute m²,
change original polygons, or grant any customer/benchmark quantity authority.
A typed structural door and source-owned host frame must BOTH support an already
shared edge of TWO original canonical floor-face candidates.

A threshold across an aperture is *not* a wall. If different finishes are
separately authenticated later, the finish change happens at the real doorway.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_opening_host_frame_authority import OpeningHostFrameResult
from pb_opening_kind_authority import OpeningKindResolution, resolve_opening_kind
from pb_physical_opening_authority import PhysicalOpeningExistenceRecord
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

_SCHEMA = "gpt1.floor_doorway_transition_shadow.v1"
_EPS_PT = 1e-4  # Original PDF float representation only. NOT 2.5pt snap.
Point = tuple[float, float]


@dataclass(frozen=True)
class FloorDoorwayTransitionShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    opening_identity_id: str | None = None
    source_floor_ids: tuple[str, ...] = ()
    threshold_pdf_pts: tuple[Point, Point] | None = None
    candidate_id: str | None = None
    diagnostic_only: bool = True
    finish_transition_authorized: bool = False
    commercial_projection_allowed: bool = False
    schema_version: str = _SCHEMA


def _blocked(reason: str, *, conflict: bool = False) -> FloorDoorwayTransitionShadow:
    return FloorDoorwayTransitionShadow(
        status=(EvidenceResolutionStatus.CONFLICT if conflict else EvidenceResolutionStatus.ABSTAINED),
        reason_codes=(reason,),
    )


def _point(p: object) -> Point | None:
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        return None
    if any(type(v) not in (float, int) for v in p):
        return None
    q = (float(p[0]), float(p[1]))
    return q if all(math.isfinite(v) for v in q) else None


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _dot(a: Point, b: Point) -> float:
    return a[0]*b[0] + a[1]*b[1]


def _cross(a: Point, b: Point) -> float:
    return a[0]*b[1] - a[1]*b[0]


def _polygon(floor: LiveCanonicalFloorSurfaceObject) -> tuple[Point, ...] | None:
    raw = floor.polygon_pdf_pts
    if not isinstance(raw, (tuple, list)):
        return None
    pts = tuple(_point(p) for p in raw)
    if any(p is None for p in pts):
        return None
    if len(pts) > 3 and math.dist(pts[0], pts[-1]) <= _EPS_PT:
        pts = pts[:-1]
    if len(pts) < 3 or len(set(pts)) != len(pts):
        return None
    area = sum(_cross(a,b) for a,b in zip(pts, pts[1:]+pts[:1]))/2
    if not math.isfinite(area) or abs(area) <= _EPS_PT:
        return None
    # Reject self-crossing or overlapping source boundaries; do not repair.
    edges = list(zip(pts, pts[1:]+pts[:1]))
    for i, (a,b) in enumerate(edges):
        if math.dist(a,b) <= _EPS_PT:
            return None
        for j,(c,d) in enumerate(edges):
            if j <= i or (j-i in (1, len(edges)-1)):
                continue
            r,s=_sub(b,a),_sub(d,c)
            denom=_cross(r,s)
            if abs(denom) <= _EPS_PT:
                if abs(_cross(_sub(c,a),r)) <= _EPS_PT:
                    t=(_dot(_sub(c,a),r)/_dot(r,r),_dot(_sub(d,a),r)/_dot(r,r))
                    if min(max(t),1.0)-max(min(t),0.0)>_EPS_PT:
                        return None
                continue
            t=_cross(_sub(c,a),s)/denom
            u=_cross(_sub(c,a),r)/denom
            if _EPS_PT < t < 1-_EPS_PT and _EPS_PT < u < 1-_EPS_PT:
                return None
    return pts


def _covers_on_boundary(
    polygon: tuple[Point, ...], origin: Point, axis: Point, u0: float, u1: float,
) -> bool:
    spans=[]
    # The original wall/room edge may consist of many collinear subedges.
    for a,b in zip(polygon, polygon[1:]+polygon[:1]):
        aa,bb=_sub(a,origin),_sub(b,origin)
        if abs(_cross(axis,aa))>_EPS_PT or abs(_cross(axis,bb))>_EPS_PT:
            continue
        lo,hi=sorted((_dot(axis,aa),_dot(axis,bb)))
        if hi >= u0-_EPS_PT and lo <= u1+_EPS_PT:
            spans.append((lo,hi))
    spans.sort()
    end=u0
    for lo,hi in spans:
        if lo > end+_EPS_PT:
            return False
        end=max(end,hi)
        if end >= u1-_EPS_PT:
            return True
    return False


def diagnose_floor_doorway_transition_shadow(
    first: LiveCanonicalFloorSurfaceObject,
    second: LiveCanonicalFloorSurfaceObject,
    *,
    opening: PhysicalOpeningExistenceRecord,
    host_frame: OpeningHostFrameResult,
    kind: OpeningKindResolution,
) -> FloorDoorwayTransitionShadow:
    """Corroborate possible doorway threshold, never material or metric m²."""
    if type(first) is not LiveCanonicalFloorSurfaceObject or type(second) is not LiveCanonicalFloorSurfaceObject:
        return _blocked("canonical_floor_source_type_unavailable")
    if first.canonical_floor_id == second.canonical_floor_id:
        return _blocked("duplicate_canonical_floor_identity", conflict=True)
    pair=tuple(sorted((first.canonical_floor_id,second.canonical_floor_id)))
    if any(type(x) is not str or not x or x!=x.strip() for x in pair):
        return _blocked("canonical_floor_identity_malformed")
    lineage=("document_id","revision_id","source_sha256","snapshot_id","page_id")
    if any(not getattr(first,k,None) or getattr(first,k)!=getattr(second,k) for k in lineage):
        return _blocked("original_floor_source_lineage_mismatch", conflict=True)
    if any(
        not f.geometry_complete or not f.physical_floor_surface_identity_resolved
        or not f.source_room_face_record_id or not f.evidence_ids
        or len(set(f.evidence_ids)) != len(f.evidence_ids)
        for f in (first,second)
    ):
        return _blocked("original_room_floor_source_face_unproven")
    if type(opening) is not PhysicalOpeningExistenceRecord:
        return _blocked("typed_original_physical_opening_unavailable")
    if any(getattr(opening,k)!=getattr(first,k) for k in lineage):
        return _blocked("original_opening_source_lineage_mismatch", conflict=True)
    if opening.status is not EvidenceResolutionStatus.CORROBORATED or opening.blocking_reasons:
        return _blocked("original_physical_opening_unproven")
    # Never borrow a typed door determination belonging to another opening.
    original_kind=resolve_opening_kind(structural_pattern=opening.structural_pattern)
    if (
        type(kind) is not OpeningKindResolution
        or kind.status is not EvidenceResolutionStatus.CORROBORATED
        or kind.structural_kind != "door" or kind.opening_kind != "door"
        or original_kind.status is not EvidenceResolutionStatus.CORROBORATED
        or original_kind.structural_kind != kind.structural_kind
        or str(opening.semantic_class).strip().lower() not in ("door", "opening")
    ):
        return _blocked("structural_door_kind_unverified")
    if type(host_frame) is not OpeningHostFrameResult or host_frame.status is not EvidenceResolutionStatus.CORROBORATED or host_frame.evidence is None:
        return _blocked("source_opening_host_frame_unverified")
    frame=host_frame.evidence
    if any(getattr(frame.selector,k)!=getattr(first,k) for k in lineage):
        return _blocked("source_opening_frame_lineage_mismatch", conflict=True)
    if (frame.opening_identity_id != frame.selector.opening_identity_id
        or not frame.record_id or not frame.host_binding_record_id
        or not frame.host_wall_id or not frame.source_observation_ids
        or not opening.source_observation_ids
        or any(type(v) is not str or not v or v != v.strip()
               for v in (*frame.source_observation_ids, *opening.source_observation_ids))
        or len(set(frame.source_observation_ids)) != len(frame.source_observation_ids)
        or len(set(opening.source_observation_ids)) != len(opening.source_observation_ids)
        or not set(frame.source_observation_ids).intersection(opening.source_observation_ids)):
        return _blocked("source_opening_frame_physical_identity_unbound")
    if any(frame.host_wall_id not in floor.bounding_wall_ids for floor in (first,second)):
        return _blocked("source_floor_boundary_host_wall_unbound")
    origin=_point(frame.origin_pt);axis=_point(frame.axis_unit);normal=_point(frame.normal_unit)
    if origin is None or axis is None or normal is None:
        return _blocked("source_opening_frame_axes_invalid")
    if (abs(_dot(axis,axis)-1)>1e-4 or abs(_dot(normal,normal)-1)>1e-4
        or abs(_dot(axis,normal))>1e-4):
        return _blocked("source_opening_frame_axes_invalid")
    u0,u1=frame.u0_pt,frame.u1_pt
    if (any(type(x) not in (int,float) or not math.isfinite(x) for x in (u0,u1,frame.wall_thickness_pt))
        or u0 >= u1 or frame.wall_thickness_pt<=0):
        return _blocked("source_opening_frame_span_invalid")
    if (frame.whole_wall_length_pt is not None
        and (type(frame.whole_wall_length_pt) not in (int,float)
             or not math.isfinite(frame.whole_wall_length_pt)
             or u0 < -_EPS_PT or u1 > frame.whole_wall_length_pt+_EPS_PT)):
        return _blocked("source_opening_frame_span_outside_wall")
    polygons=tuple(_polygon(f) for f in (first,second))
    if any(poly is None for poly in polygons):
        return _blocked("source_floor_polygon_not_simple")
    if not all(_covers_on_boundary(poly,origin,axis,u0,u1) for poly in polygons):
        return _blocked("original_doorway_threshold_not_on_both_floor_edges")
    # Shared line must SEPARATE rooms; not run through either room interior.
    signs=[]
    for poly in polygons:
        vals=[_cross(axis,_sub(p,origin)) for p in poly]
        pos=any(v>_EPS_PT for v in vals)
        neg=any(v<-_EPS_PT for v in vals)
        if pos==neg:
            return _blocked("doorway_not_separating_distinct_room_interiors",conflict=pos)
        signs.append(1 if pos else -1)
    if signs[0]==signs[1]:
        return _blocked("doorway_rooms_occupy_same_side",conflict=True)
    endpoints=((origin[0]+axis[0]*u0, origin[1]+axis[1]*u0),
               (origin[0]+axis[0]*u1, origin[1]+axis[1]*u1))
    rid=stable_contract_id("gpt1_floor_doorway_shadow",{
        "source_sha256":first.source_sha256,
        "revision_id":first.revision_id,
        "floors":pair,
        "opening_identity_id":frame.opening_identity_id,
        "frame_record_id":frame.record_id,
    },digest_chars=24)
    return FloorDoorwayTransitionShadow(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("original_doorway_shared_source_floor_edge_candidate",
                      "finished_wall_face_and_material_transition_not_authenticated"),
        opening_identity_id=frame.opening_identity_id,
        source_floor_ids=pair,threshold_pdf_pts=endpoints,candidate_id=rid,
    )
