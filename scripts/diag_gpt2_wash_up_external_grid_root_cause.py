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

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGET="WASH UP"

def norm(v): return " ".join(str(v or "").strip().upper().split())

source=SourceVisibilityProducer(
    producer_method="diag-gpt2-wash-up-external-grid-root-cause",
    producer_version="1",
)
published=source.ingest_native_pdf_bytes(
    document_id="diag-gpt2-wash-up-external-grid-root-cause",
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
current=source.published_snapshot_for_revision(published.revision.revision_id)
assert current is not None

wall_producer=PhysicalWallCandidateProducer.from_authenticated_viewports(
    source,page_ids=("7",)
)
wall_auth=wall_producer.authority()
selectors=wall_auth.selectors_for_authenticated_viewports(
    document_id=current.revision.document_id,
    revision_id=current.revision.revision_id,
    source_sha256=current.revision.source_sha256,
    snapshot_id=current.snapshot.snapshot_id,
    page_id="7",
    view_type=DrawingViewType.FLOOR_PLAN.value,
)
assert len(selectors)==1, len(selectors)
selector=selectors[0]
wall_scope=wall_auth.resolve_scope(selector)
room_auth=build_source_room_face_authority(wall_auth)
room_scope=room_auth.resolve_scope(SourceRoomFaceSelector(
    document_id=selector.document_id,
    revision_id=selector.revision_id,
    source_sha256=selector.source_sha256,
    snapshot_id=selector.snapshot_id,
    page_id=selector.page_id,
    decision_scope_id=selector.decision_scope_id,
))
label_scope=SourceRoomLabelProducer.from_authorities(
    source,room_auth,page_ids=("7",)
).authority().resolve_scope(SourceRoomLabelSelector(
    document_id=selector.document_id,
    revision_id=selector.revision_id,
    source_sha256=selector.source_sha256,
    snapshot_id=selector.snapshot_id,
    page_id=selector.page_id,
    decision_scope_id=selector.decision_scope_id,
))
candidates=[c for c in label_scope.split_face_candidates if norm(c.label)==TARGET]
assert len(candidates)==1, len(candidates)
candidate=candidates[0]

fully,_=comp._fully_grid_opposed_wall_evidence(wall_scope)
component=comp._grid_connected_component(
    tuple(str(v) for v in candidate.word_face_ids),
    room_scope=room_scope,
    fully_grid_wall_ids=fully,
)
assert component is not None
room_by_face={str(r.face_id):r for r in room_scope.records}
edge_owners=comp._local_edge_owners(room_scope)
counts={}
for face_id in component:
    for wall_id,edge in tuple(room_by_face[face_id].boundary_wall_edges or ()):
        key=(str(wall_id),comp._edge_key(edge))
        counts[key]=counts.get(key,0)+1

external_grid=[]
invalid_internal=[]
component_set=set(component)
for key,count in counts.items():
    wall_id,edge=key
    owners=edge_owners.get(key,())
    if count==1 and wall_id in fully:
        external_grid.append((wall_id,edge,owners))
    if count==2 and (
        wall_id not in fully
        or len(owners)!=2
        or not set(owners).issubset(component_set)
    ):
        invalid_internal.append((wall_id,edge,owners,wall_id in fully))

abstentions=[]
for a in tuple(room_scope.abstained_faces or ()):
    try: poly=Polygon(a.polygon_pdf_pts)
    except Exception: continue
    if poly.is_empty: continue
    abstentions.append((a,poly))

external_rows=[]
for wall_id,edge,owners in external_grid:
    line=LineString((edge[0],edge[1]))
    touching=[]
    for a,poly in abstentions:
        hit=line.intersection(poly.boundary)
        if hit.is_empty or float(getattr(hit,"length",0.0))<=1e-9:
            continue
        touching.append({
            "face_id":a.face_id,
            "reason":a.reason,
            "area_page_pts2":a.area_page_pts2,
            "intersection_length":float(hit.length),
            "bounding_wall_ids":list(a.bounding_wall_ids),
        })
    external_rows.append({
        "wall_id":wall_id,
        "edge":[list(edge[0]),list(edge[1])],
        "published_global_owners":list(owners),
        "touching_abstained_faces":touching,
    })

wall_by_id={str(r.wall_candidate_id):r for r in wall_scope.records}
internal_rows=[]
for wall_id,edge,owners,is_grid in invalid_internal:
    rec=wall_by_id.get(wall_id)
    internal_rows.append({
        "wall_id":wall_id,
        "edge":[list(edge[0]),list(edge[1])],
        "published_global_owners":list(owners),
        "grid":is_grid,
        "candidate_identity_id":None if rec is None else rec.physical_identity.candidate_identity_id,
        "source_primitive_ids":[] if rec is None else list(rec.physical_identity.source_primitive_ids),
        "centerline_pts":[] if rec is None else [list(p) for p in rec.wall_candidate.centerline_pts],
        "edge_ids":[] if rec is None else list(rec.physical_identity.edge_ids),
    })

print(json.dumps({
    "component_count":len(component),
    "seed_face_ids":list(candidate.word_face_ids),
    "external_grid_edge_count":len(external_rows),
    "external_grid_edges":external_rows,
    "invalid_internal_edge_count":len(internal_rows),
    "invalid_internal_edges":internal_rows,
    "room_abstention_reason_counts":{
        reason:sum(1 for a in room_scope.abstained_faces if a.reason==reason)
        for reason in sorted({a.reason for a in room_scope.abstained_faces})
    },
},indent=2,sort_keys=True))
