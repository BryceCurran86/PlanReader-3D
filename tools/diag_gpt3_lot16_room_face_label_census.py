from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import fitz

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_room_face_takeoff import extract_planar_faces
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    _canonical_polygon,
    _point_in_or_on_polygon,
    _wall_edges,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import _normalized_room_line
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"
PAGE_INDEX=2

def center(bbox):
    x0,y0,x1,y1=(float(v) for v in bbox)
    return ((x0+x1)/2.0,(y0+y1)/2.0)

def contains(point, polygon):
    return bool(_point_in_or_on_polygon(point, tuple(tuple(float(v) for v in p) for p in polygon)))

def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_room_face_label_census",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-room-face-label-census",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=tuple(str(i) for i in range(1,14)),
    )
    wall_opening=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise SystemExit("current snapshot unavailable")

    wall_selector=PhysicalWallCandidateSelector(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PAGE_ID,
        decision_scope_id=f"wall-source:page-{PAGE_ID}",
    )
    wall_scope=wall_opening.physical_wall_candidate_authority.resolve_scope(wall_selector)

    face_authority=build_source_room_face_authority(
        wall_opening.physical_wall_candidate_authority
    )
    face_selector=SourceRoomFaceSelector(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PAGE_ID,
        decision_scope_id=f"wall-source:page-{PAGE_ID}",
    )
    face_scope=face_authority.resolve_scope(face_selector)

    raw_segments=[]
    for record in tuple(wall_scope.records or ()):
        for edge in _wall_edges(record):
            raw_segments.append((edge[0],edge[1]))
    raw_faces=tuple(
        polygon
        for face in extract_planar_faces(raw_segments,min_area=1e-6)
        for polygon in (_canonical_polygon(face),)
        if polygon
    )
    published_faces=tuple(face_scope.records or ())
    abstained_faces=tuple(face_scope.abstained_faces or ())

    doc=fitz.open(stream=payload,filetype="pdf")
    try:
        page=doc[PAGE_INDEX]
        labels=[]
        for block in page.get_text("dict").get("blocks") or ():
            for line in block.get("lines") or ():
                spans=line.get("spans") or ()
                text=" ".join(
                    str(span.get("text") or "").strip()
                    for span in spans
                    if str(span.get("text") or "").strip()
                ).strip()
                normalized=_normalized_room_line(text)
                if normalized is None:
                    continue
                bbox=tuple(float(x) for x in line.get("bbox",(0,0,0,0)))
                pt=center(bbox)
                raw_matches=[
                    idx for idx,poly in enumerate(raw_faces)
                    if contains(pt,poly)
                ]
                pub_matches=[
                    row.record_id for row in published_faces
                    if contains(pt,row.polygon_pdf_pts)
                ]
                abst_matches=[
                    {
                        "face_id":row.face_id,
                        "reason":row.reason,
                        "area_page_pts2":row.area_page_pts2,
                    }
                    for row in abstained_faces
                    if contains(pt,row.polygon_pdf_pts)
                ]
                if len(pub_matches)==1:
                    state="PUBLISHED_FACE"
                elif pub_matches:
                    state="MULTIPLE_PUBLISHED_FACES"
                elif abst_matches:
                    state="ABSTAINED_FACE"
                elif raw_matches:
                    state="RAW_FACE_NOT_PUBLISHED_OR_ABSTAINED"
                else:
                    state="NO_RAW_FACE"
                labels.append({
                    "text":text,
                    "normalized":normalized,
                    "bbox":list(bbox),
                    "center":list(pt),
                    "state":state,
                    "raw_face_count":len(raw_matches),
                    "raw_face_indexes":raw_matches,
                    "published_face_ids":pub_matches,
                    "abstained_faces":abst_matches,
                })
    finally:
        doc.close()

    state_counts=Counter(row["state"] for row in labels)
    abstain_reason_counts=Counter(
        item["reason"]
        for row in labels
        for item in row["abstained_faces"]
    )
    payload_out={
        "source_sha256":actual,
        "current_snapshot_id":current.snapshot.snapshot_id,
        "wall_scope_status":wall_scope.status.value,
        "wall_scope_complete":bool(wall_scope.scope_complete),
        "wall_scope_reason_codes":list(wall_scope.reason_codes),
        "wall_candidate_count":len(wall_scope.records),
        "raw_planar_face_count":len(raw_faces),
        "face_scope_status":face_scope.status.value,
        "face_scope_complete":bool(face_scope.scope_complete),
        "face_universe_complete":bool(face_scope.face_universe_complete),
        "face_scope_reason_codes":list(face_scope.reason_codes),
        "published_face_count":len(published_faces),
        "abstained_face_count":len(abstained_faces),
        "ownership_evaluation":{
            "status":face_scope.ownership_evaluation.status,
            "reason_code":face_scope.ownership_evaluation.reason_code,
            "face_count":face_scope.ownership_evaluation.face_count,
            "owned_face_count":len(face_scope.ownership_evaluation.owned_face_ids),
            "unresolved_face_count":len(face_scope.ownership_evaluation.unresolved_faces),
            "degenerate_owned_face_count":len(face_scope.ownership_evaluation.degenerate_owned_face_ids),
            "competing_edge_count":face_scope.ownership_evaluation.competing_edge_count,
            "unowned_edge_count":face_scope.ownership_evaluation.unowned_edge_count,
        },
        "room_label_candidate_count":len(labels),
        "label_state_counts":dict(state_counts),
        "label_abstain_reason_counts":dict(abstain_reason_counts),
        "labels":labels,
    }
    print(json.dumps(payload_out,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
