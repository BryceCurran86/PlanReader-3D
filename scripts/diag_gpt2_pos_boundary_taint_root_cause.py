from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import LineString, Polygon

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
import pb_source_composite_room_face_authority as comp
import pb_source_room_face_authority as rooms
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
from pb_source_room_label_authority import SourceRoomLabelProducer, SourceRoomLabelSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGET = "POS COUNTER"


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


source = SourceVisibilityProducer(
    producer_method="diag-gpt2-pos-boundary-taint-root-cause",
    producer_version="1",
)
published = source.ingest_native_pdf_bytes(
    document_id="diag-gpt2-pos-boundary-taint-root-cause",
    source_bytes=SOURCE.read_bytes(),
    source_locator="memory://maryborough.pdf",
    page_ids=("7",),
)
compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=("7",),
    evidence_page_ids=(),
)
current = source.published_snapshot_for_revision(published.revision.revision_id)
assert current is not None

wall_producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
    source,
    page_ids=("7",),
)
wall_auth = wall_producer.authority()
selectors = wall_auth.selectors_for_authenticated_viewports(
    document_id=current.revision.document_id,
    revision_id=current.revision.revision_id,
    source_sha256=current.revision.source_sha256,
    snapshot_id=current.snapshot.snapshot_id,
    page_id="7",
    view_type=DrawingViewType.FLOOR_PLAN.value,
)
assert len(selectors) == 1, len(selectors)
selector = selectors[0]
wall_scope = wall_auth.resolve_scope(selector)

room_auth = build_source_room_face_authority(wall_auth)
room_selector = SourceRoomFaceSelector(
    document_id=selector.document_id,
    revision_id=selector.revision_id,
    source_sha256=selector.source_sha256,
    snapshot_id=selector.snapshot_id,
    page_id=selector.page_id,
    decision_scope_id=selector.decision_scope_id,
)
room_scope = room_auth.resolve_scope(room_selector)
label_scope = SourceRoomLabelProducer.from_authorities(
    source,
    room_auth,
    page_ids=("7",),
).authority().resolve_scope(
    SourceRoomLabelSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
    )
)
candidates = [c for c in label_scope.split_face_candidates if norm(c.label) == TARGET]
assert len(candidates) == 1, len(candidates)
candidate = candidates[0]

fully, _ = comp._fully_grid_opposed_wall_evidence(wall_scope)
component = comp._grid_connected_component(
    tuple(str(v) for v in candidate.word_face_ids),
    room_scope=room_scope,
    fully_grid_wall_ids=fully,
)
assert component is not None
room_by_face = {str(r.face_id): r for r in room_scope.records}
edge_counts: dict[tuple[str, object], int] = {}
for face_id in component:
    record = room_by_face[face_id]
    for wall_id, edge in tuple(record.boundary_wall_edges or ()):
        key = (str(wall_id), comp._edge_key(edge))
        edge_counts[key] = edge_counts.get(key, 0) + 1
exposed = [
    (wall_id, edge)
    for (wall_id, edge), count in edge_counts.items()
    if count == 1 and wall_id in fully
]

boundary_abstentions = [
    a
    for a in room_scope.abstained_faces
    if a.reason == rooms.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED
]
touching: dict[str, dict] = {}
for wall_id, edge in exposed:
    line = LineString((edge[0], edge[1]))
    for abstained in boundary_abstentions:
        poly = Polygon(abstained.polygon_pdf_pts)
        hit = line.intersection(poly.boundary)
        if hit.is_empty or float(getattr(hit, "length", 0.0)) <= 1e-9:
            continue
        row = touching.setdefault(
            str(abstained.face_id),
            {"abstention": abstained, "edge_hits": []},
        )
        row["edge_hits"].append(
            {
                "wall_id": wall_id,
                "edge": [list(edge[0]), list(edge[1])],
                "intersection_length": float(hit.length),
            }
        )

evaluation = wall_scope.boundary_evaluation
assert evaluation is not None
tainted_ids = {str(v) for v in evaluation.boundary_tainted_wall_candidate_ids}
taint_reasons = {
    str(wall_id): list(reasons)
    for wall_id, reasons in evaluation.boundary_taint_reason_codes
}
wall_by_id = {str(r.wall_candidate_id): r for r in wall_scope.records}
ownership_by_face = {
    str(f.face_id): f for f in room_scope.ownership_evaluation.unresolved_faces
}

face_rows = []
for face_id, row in sorted(touching.items()):
    abstained = row["abstention"]
    polygon = abstained.polygon_pdf_pts
    face_tainted_walls = sorted(set(abstained.bounding_wall_ids) & tainted_ids)
    excluded_touching = []
    for primitive in evaluation.excluded_boundary_primitives:
        if rooms._excluded_primitive_touches_face(primitive, polygon):
            excluded_touching.append(
                {
                    "category": primitive.category,
                    "source_observation_id": primitive.source_observation_id,
                    "geometry": [primitive.x1, primitive.y1, primitive.x2, primitive.y2],
                }
            )
    ownership = ownership_by_face.get(face_id)
    wall_rows = []
    for wall_id in face_tainted_walls:
        record = wall_by_id.get(wall_id)
        wall_rows.append(
            {
                "wall_id": wall_id,
                "taint_reasons": taint_reasons.get(wall_id, []),
                "centerline_pts": []
                if record is None
                else [list(p) for p in record.wall_candidate.centerline_pts],
                "source_primitive_ids": []
                if record is None
                else list(record.physical_identity.source_primitive_ids),
            }
        )
    face_rows.append(
        {
            "face_id": face_id,
            "area_page_pts2": abstained.area_page_pts2,
            "edge_hit_count": len(row["edge_hits"]),
            "edge_hits": row["edge_hits"],
            "ownership_shadow_unresolved": ownership is not None,
            "ownership_reason_codes": []
            if ownership is None
            else list(ownership.reason_codes),
            "ownership_competing_wall_ids": []
            if ownership is None
            else list(ownership.competing_wall_ids),
            "boundary_tainted_wall_count": len(face_tainted_walls),
            "boundary_tainted_walls": wall_rows,
            "excluded_boundary_primitive_touch_count": len(excluded_touching),
            "excluded_boundary_primitives_touching": excluded_touching,
            "polygon_pdf_pts": [list(p) for p in polygon],
        }
    )

print(
    json.dumps(
        {
            "wall_scope_complete": wall_scope.scope_complete,
            "wall_scope_reasons": list(wall_scope.reason_codes),
            "boundary_evaluation_status": evaluation.status,
            "boundary_tainted_wall_count": len(tainted_ids),
            "excluded_boundary_primitive_count": len(
                evaluation.excluded_boundary_primitives
            ),
            "room_reason_codes": list(room_scope.reason_codes),
            "room_ownership_unresolved_face_count": len(
                room_scope.ownership_evaluation.unresolved_faces
            ),
            "pos_component_count": len(component),
            "pos_exposed_grid_edge_count": len(exposed),
            "touching_boundary_abstention_count": len(face_rows),
            "faces": face_rows,
        },
        indent=2,
        sort_keys=True,
    )
)
