from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_composite_room_face_authority import _fully_grid_opposed_wall_evidence
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
from pb_source_room_label_authority import SourceRoomLabelProducer, SourceRoomLabelSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID="7"
TARGETS={"TRUCK DRIVER LOUNGE","DRY STORE","WASH UP"}

def norm(v):
    return " ".join(str(v or "").strip().upper().split())

def shortest_paths(graph,start,goal,allowed):
    q=deque([[start]])
    best=None
    out=[]
    while q:
        path=q.popleft()
        if best is not None and len(path)>best:
            continue
        node=path[-1]
        if node==goal:
            best=len(path)
            out.append(path)
            continue
        for nxt in sorted(graph.get(node,())):
            if nxt not in allowed or nxt in path:
                continue
            q.append(path+[nxt])
    return out

def main():
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="diag-gpt2-truck-driver-grid-path",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None

    wall_prod=PhysicalWallCandidateProducer.from_authenticated_viewports(source,page_ids=(PAGE_ID,))
    wall_auth=wall_prod.authority()
    selectors=wall_auth.selectors_for_authenticated_viewports(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PAGE_ID,
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    assert len(selectors)==1
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
    label_prod=SourceRoomLabelProducer.from_authorities(source,room_auth,page_ids=(PAGE_ID,))
    label_scope=label_prod.authority().resolve_scope(SourceRoomLabelSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
    ))

    fully_grid,_evidence=_fully_grid_opposed_wall_evidence(wall_scope)
    room_by_face={str(r.face_id):r for r in room_scope.records}
    faces_by_wall=defaultdict(list)
    for record in room_scope.records:
        for wall_id in record.bounding_wall_ids:
            faces_by_wall[str(wall_id)].append(str(record.face_id))

    graph=defaultdict(set)
    edge_walls=defaultdict(set)
    for wall_id,faces in faces_by_wall.items():
        if wall_id not in fully_grid:
            continue
        unique=sorted(set(faces))
        for i,left in enumerate(unique):
            for right in unique[i+1:]:
                graph[left].add(right)
                graph[right].add(left)
                edge_walls[tuple(sorted((left,right)))].add(wall_id)

    rows=[]
    for candidate in label_scope.split_face_candidates:
        label=norm(candidate.label)
        if label not in TARGETS:
            continue
        bbox=box(*candidate.source_bbox)
        allowed={
            face_id
            for face_id,record in room_by_face.items()
            if Polygon(record.polygon_pdf_pts).intersects(bbox)
        }
        word_faces=list(candidate.word_face_ids)
        transitions=[]
        used_faces=[]
        eligible=True
        for left,right in zip(word_faces,word_faces[1:]):
            if left==right:
                paths=[[left]]
            else:
                paths=shortest_paths(graph,left,right,allowed)
            if len(paths)!=1:
                eligible=False
            chosen=paths[0] if len(paths)==1 else None
            if chosen:
                for face_id in chosen:
                    if face_id not in used_faces:
                        used_faces.append(face_id)
            transitions.append({
                "left_face_id":left,
                "right_face_id":right,
                "shortest_path_count":len(paths),
                "shortest_paths":paths,
                "chosen_path":chosen,
                "path_separator_wall_ids":(
                    [
                        sorted(edge_walls[tuple(sorted((a,b)))])
                        for a,b in zip(chosen,chosen[1:])
                    ]
                    if chosen else []
                ),
            })

        union=None
        if eligible and used_faces:
            polys=[Polygon(room_by_face[f].polygon_pdf_pts) for f in used_faces]
            merged=unary_union(polys)
            union={
                "geom_type":merged.geom_type,
                "is_valid":bool(merged.is_valid),
                "is_empty":bool(merged.is_empty),
                "area_page_pts2":float(merged.area),
                "hole_count":(
                    len(tuple(merged.interiors))
                    if merged.geom_type=="Polygon" else None
                ),
                "face_ids":used_faces,
            }
            eligible=(
                merged.geom_type=="Polygon"
                and merged.is_valid
                and not merged.is_empty
                and len(tuple(merged.interiors))==0
            )

        rows.append({
            "label":label,
            "candidate_record_id":candidate.record_id,
            "source_bbox":list(candidate.source_bbox),
            "word_face_ids":word_faces,
            "allowed_face_count":len(allowed),
            "allowed_face_ids":sorted(allowed),
            "transitions":transitions,
            "union":union,
            "eligible":eligible,
        })

    print(json.dumps({
        "source_sha256":sha,
        "fully_grid_wall_count":len(fully_grid),
        "room_face_count":len(room_scope.records),
        "rows":rows,
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
