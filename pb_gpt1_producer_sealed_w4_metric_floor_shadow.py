"""Producer-sealed W4 source room-face to GPT1 figured metric ring bridge.

Only the *existing* W4 SourceRoomFaceAuthority can authenticate the physical
wall-owned room boundary. Caller-authored flags, two-sheet alignments, source
label matches or page-coordinate sketches cannot stand in for the authority.

The W4 scope is obtained from the producer-minted room composition runtime
binding, then resolved again via its SourceRoomFaceSelector. This remains a
read-only CANDIDATE handoff and does not assign measured area/finish authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition, LiveCanonicalRoomObject,
)
from pb_live_canonical_floor_surface import (
    LiveCanonicalFloorSurfaceComposition, LiveCanonicalFloorSurfaceObject,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector, SourceRoomFaceRecord,
)
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class SourceSealedW4MetricFloorShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    physical_room_id: str
    canonical_room_id: str
    canonical_floor_id: str
    source_room_face_record_id: str
    original_source_face_boundary_wall_ids: tuple[str, ...]
    original_published_boundary_subedges: tuple[tuple[str, tuple[tuple[float,float],tuple[float,float]]], ...]
    source_sha256: str
    revision_id: str
    snapshot_id: str
    decision_scope_id: str
    page_id: str
    viewport_id: str | None
    independent_candidate_metric_area_m2: float | None
    diagnostic_only: bool = True
    figured_source_side_to_w4_wall_id: tuple[tuple[str, str], ...] = ()
    candidate_wall_length_m_by_w4_id: tuple[tuple[str, float], ...] = ()


def _cycle(value: object) -> tuple[tuple[float, float], ...] | None:
    if type(value) not in (list, tuple) or len(value) < 3:
        return None
    result = []
    for raw in value:
        if type(raw) not in (list, tuple) or len(raw) != 2:
            return None
        if any(type(n) not in (int,float) for n in raw):
            return None
        try:
            point = tuple(round(float(n),6) for n in raw)
        except (TypeError,ValueError,OverflowError):
            return None
        if not all(math.isfinite(n) for n in point):
            return None
        result.append(point)
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    if len(result) < 3 or len(set(result)) != len(result):
        return None
    return min(
        variant
        for i in range(len(result))
        for variant in (
            tuple(result[(i+j)%len(result)] for j in range(len(result))),
            tuple(result[(i-j)%len(result)] for j in range(len(result))),
        )
    )


def _edge(a, b):
    return (a,b) if a <= b else (b,a)


def bind_producer_sealed_w4_metric_floor_shadow(
    rooms: LiveCanonicalRoomComposition,
    floors: LiveCanonicalFloorSurfaceComposition,
    metric_room: FiguredPolygonMetricShadow,
    *,
    physical_room_id: str,
) -> SourceSealedW4MetricFloorShadow:
    """Re-read original producer W4 scope and fail on any duplicated owner."""
    def block(reason):
        return SourceSealedW4MetricFloorShadow(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(reason,),
            physical_room_id=str(physical_room_id),
            canonical_room_id="",canonical_floor_id="",
            source_room_face_record_id="",
            original_source_face_boundary_wall_ids=(),
            original_published_boundary_subedges=(),
            source_sha256="",revision_id="",snapshot_id="",
            decision_scope_id="",page_id="",viewport_id=None,
            independent_candidate_metric_area_m2=None,
        )
    if (
        type(rooms) is not LiveCanonicalRoomComposition
        or type(floors) is not LiveCanonicalFloorSurfaceComposition
        or type(metric_room) is not FiguredPolygonMetricShadow
        or metric_room.status is not EvidenceResolutionStatus.CANDIDATE
        or metric_room.diagnostic_only is not True
        or type(metric_room.candidate_area_m2) is not float
        or not math.isfinite(metric_room.candidate_area_m2)
        or metric_room.candidate_area_m2 <= 0
        or type(metric_room.source_figure_ids) is not tuple
        or len(metric_room.source_figure_ids) < 2
        or len(set(metric_room.source_figure_ids)) != len(metric_room.source_figure_ids)
        or any(type(v) is not str or not v or v != v.strip()
               for v in metric_room.source_figure_ids)
        or type(physical_room_id) is not str or not physical_room_id
        or physical_room_id != physical_room_id.strip()
    ):
        return block("original_w4_room_metric_input_untrusted")

    owning_rooms = [item for item in rooms.rooms if
        type(item) is LiveCanonicalRoomObject
        and item.physical_room_id == physical_room_id
    ]
    if len(owning_rooms) != 1:
        return block("original_w4_physical_room_not_unique")
    room = owning_rooms[0]
    binding = rooms.room_face_authority_binding_for(room)
    if binding is None:
        return block("original_w4_producer_sealed_room_face_authority_missing")
    # Never reuse a scope selected only by page title or nearest room label.
    selector = SourceRoomFaceSelector(
        document_id=room.document_id,revision_id=room.revision_id,
        source_sha256=room.source_sha256,snapshot_id=room.snapshot_id,
        page_id=room.page_id,decision_scope_id=room.decision_scope_id,
    )
    source_scope = binding.authority.resolve_scope(selector)
    if (
        source_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not source_scope.scope_complete
        or (source_scope.document_id,source_scope.revision_id,
            source_scope.source_sha256,source_scope.snapshot_id,
            source_scope.page_id,source_scope.decision_scope_id)
        != (room.document_id,room.revision_id,room.source_sha256,
            room.snapshot_id,room.page_id,room.decision_scope_id)
    ):
        return block("original_w4_published_room_face_scope_unavailable")
    original_records = [
        record for record in source_scope.records
        if type(record) is SourceRoomFaceRecord
        and record.record_id == room.source_room_face_record_id
    ]
    if len(original_records) != 1:
        return block("original_w4_source_room_face_record_not_unique")
    original = original_records[0]
    if (
        (original.document_id,original.revision_id,original.source_sha256,
         original.snapshot_id,original.page_id,original.decision_scope_id)
        != (room.document_id,room.revision_id,room.source_sha256,
            room.snapshot_id,room.page_id,room.decision_scope_id)
        or type(room.geometry_complete) is not bool or not room.geometry_complete
        or not room.source_room_face_record_id
        or room.evidence_ids != (original.record_id,)
        or metric_room.physical_room_id != room.physical_room_id
        or (metric_room.source_sha256,metric_room.revision_id,
            metric_room.page_id)
        != (room.source_sha256,room.revision_id,room.page_id)
    ):
        return block("original_w4_source_room_face_lineage_conflict")
    from shapely.geometry import Polygon
    try:
        metric_shape = Polygon(metric_room.metric_vertices_mm)
        if (
            not metric_shape.is_valid or metric_shape.area <= 0
            or not math.isclose(
                metric_shape.area / 1_000_000.0,
                metric_room.candidate_area_m2, rel_tol=1e-9, abs_tol=1e-9,
            )
        ):
            return block("original_w4_independent_metric_ring_area_conflict")
    except (TypeError,ValueError,OverflowError):
        return block("original_w4_independent_metric_ring_area_conflict")
    if (
        type(metric_room.source_side_ids) is not tuple
        or len(metric_room.source_side_ids) != len(metric_room.source_vertices_pdf_pts)
        or len(set(metric_room.source_side_ids)) != len(metric_room.source_side_ids)
        or any(type(v) is not str or not v or v != v.strip()
               for v in metric_room.source_side_ids)
        or type(metric_room.source_segment_ids) is not tuple
        or len(metric_room.source_segment_ids) < len(metric_room.source_side_ids)
        or len(set(metric_room.source_segment_ids)) != len(metric_room.source_segment_ids)
    ):
        return block("original_w4_independent_metric_source_side_identity_conflict")
    # The figured room solver carries one metric vertex for each original
    # source wall vertex. An equal-area but geometrically reshaped polygon
    # cannot borrow W4 ownership: each oriented edge must remain on its exact
    # source direction (including the same winding and vertex order).
    original_vertices = metric_room.source_vertices_pdf_pts
    metric_vertices = metric_room.metric_vertices_mm
    if len(original_vertices) != len(metric_vertices):
        return block("original_w4_figured_side_correspondence_unavailable")
    for i in range(len(original_vertices)):
        a = original_vertices[i]
        b = original_vertices[(i+1) % len(original_vertices)]
        u = metric_vertices[i]
        v = metric_vertices[(i+1) % len(metric_vertices)]
        try:
            sx,sy = float(b[0])-float(a[0]), float(b[1])-float(a[1])
            mx,my = float(v[0])-float(u[0]), float(v[1])-float(u[1])
            source_len,metric_len = math.hypot(sx,sy),math.hypot(mx,my)
            aligned = (
                math.isfinite(source_len) and source_len > 0
                and math.isfinite(metric_len) and metric_len > 0
                and sx*mx + sy*my > 0
                and abs(sx*my-sy*mx) <= 1e-8*source_len*metric_len
            )
        except (TypeError,ValueError,OverflowError,IndexError):
            aligned = False
        if not aligned:
            return block("original_w4_figured_metric_side_direction_conflict")
    source_polygon = _cycle(original.polygon_pdf_pts)
    if (
        source_polygon is None
        or source_polygon != _cycle(room.polygon_pdf_pts)
        or source_polygon != _cycle(metric_room.source_vertices_pdf_pts)
        or type(original.area_page_pts2) not in (int,float)
        or type(room.area_page_pts2) not in (int,float)
        or not math.isfinite(float(original.area_page_pts2))
        or not math.isclose(float(original.area_page_pts2),
                            float(room.area_page_pts2),rel_tol=0,abs_tol=1e-6)
    ):
        return block("original_w4_source_room_face_geometry_conflict")
    if (
        not original.bounding_wall_ids
        or len(set(original.bounding_wall_ids)) != len(original.bounding_wall_ids)
        or set(original.bounding_wall_ids)!=set(room.bounding_wall_ids)
        or not original.boundary_wall_edges
    ):
        return block("original_w4_source_wall_ownership_unavailable")
    points=tuple(tuple(round(float(n),6) for n in raw)
                 for raw in original.polygon_pdf_pts)
    if points[-1]==points[0]:
        points=points[:-1]
    actual_edges = {_edge(points[i],points[(i+1)%len(points)])
                    for i in range(len(points))}
    seen_edges=set()
    retained=[]
    for wall_id,raw_edge in original.boundary_wall_edges:
        if (
            type(wall_id) is not str or not wall_id
            or wall_id not in original.bounding_wall_ids
            or type(raw_edge) not in (tuple,list) or len(raw_edge)!=2
        ):
            return block("original_w4_source_wall_subedge_untrusted")
        try:
            endpoints=tuple(tuple(round(float(n),6) for n in v)
                            for v in raw_edge)
        except (TypeError,ValueError,OverflowError):
            return block("original_w4_source_wall_subedge_untrusted")
        if any(len(v)!=2 or not all(math.isfinite(n) for n in v)
               for v in endpoints):
            return block("original_w4_source_wall_subedge_untrusted")
        edge=_edge(*endpoints)
        if edge not in actual_edges or edge in seen_edges:
            return block("original_w4_source_wall_subedge_competing")
        seen_edges.add(edge)
        retained.append((wall_id,edge))
    if seen_edges != actual_edges:
        return block("original_w4_source_wall_subedge_incomplete")
    # This is the first real producer-backed connection from figured metric
    # perimeter sides to exact W4 physical walls. Match the original source
    # edge itself; never assign a room side to a nearest/parallel candidate.
    owner_by_edge = {edge: wall_id for wall_id, edge in retained}
    figured_w4_sides = []
    wall_metric_mm: dict[str, list[float]] = {}
    for index, side_id in enumerate(metric_room.source_side_ids):
        start = tuple(round(float(n),6) for n in original_vertices[index])
        finish = tuple(round(float(n),6) for n in original_vertices[
            (index + 1) % len(original_vertices)
        ])
        physical_wall = owner_by_edge.get(_edge(start, finish))
        if physical_wall is None:
            return block("original_w4_figured_source_side_owner_unavailable")
        metric_first = tuple(float(n) for n in metric_vertices[index])
        metric_last = tuple(float(n) for n in metric_vertices[
            (index + 1) % len(metric_vertices)
        ])
        length_mm = math.dist(metric_first, metric_last)
        if not math.isfinite(length_mm) or length_mm <= 0:
            return block("original_w4_figured_source_side_length_unavailable")
        figured_w4_sides.append((side_id, physical_wall))
        wall_metric_mm.setdefault(physical_wall, []).append(length_mm)
    if set(wall_metric_mm) != set(original.bounding_wall_ids):
        return block("original_w4_figured_wall_member_universe_incomplete")
    candidate_wall_lengths = tuple(
        (wall_id, math.fsum(lengths) / 1000.)
        for wall_id, lengths in sorted(wall_metric_mm.items())
    )
    matches=[
        floor for floor in floors.floors
        if type(floor) is LiveCanonicalFloorSurfaceObject
        and floor.source_room_face_record_id==original.record_id
    ]
    if len(matches)!=1:
        return block("original_w4_canonical_floor_not_unique")
    floor=matches[0]
    if (
        (floor.document_id,floor.revision_id,floor.source_sha256,
         floor.snapshot_id,floor.page_id)
        != (room.document_id,room.revision_id,room.source_sha256,
            room.snapshot_id,room.page_id)
        or floor.room_entity_id!=room.canonical_room_id
        or floor.viewport_id!=room.viewport_id
        or not floor.geometry_complete
        or not floor.physical_floor_surface_identity_resolved
        or floor.physical_floor_surface_id!=floor.canonical_floor_id
        or _cycle(floor.polygon_pdf_pts)!=source_polygon
    ):
        return block("original_w4_canonical_floor_lineage_conflict")
    return SourceSealedW4MetricFloorShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("producer_sealed_original_w4_face_metric_shadow_only",),
        room.physical_room_id,room.canonical_room_id,
        floor.canonical_floor_id,original.record_id,
        tuple(sorted(original.bounding_wall_ids)),
        tuple(sorted(retained)),room.source_sha256,room.revision_id,
        room.snapshot_id,room.decision_scope_id,room.page_id,
        room.viewport_id,metric_room.candidate_area_m2,
        figured_source_side_to_w4_wall_id=tuple(figured_w4_sides),
        candidate_wall_length_m_by_w4_id=candidate_wall_lengths,
    )
