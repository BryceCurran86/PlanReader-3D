from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
from pb_source_room_label_authority import SourceRoomLabelProducer, SourceRoomLabelSelector, _point_in_polygon
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation_authority import DrawingViewType

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGES=("7","11")
TARGETS={"M-AMB","F-AMB"}

def norm(v):
    return " ".join(str(v or "").strip().upper().split())

def main():
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-amb-room-label",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=PAGES,
    )
    compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=PAGES,
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None
    text_auth=source.text_integrity_authority()
    vp=PhysicalWallCandidateProducer.from_authenticated_viewports(source,page_ids=PAGES)
    wall_auth=vp.authority()
    room_auth=build_source_room_face_authority(wall_auth)
    label_prod=SourceRoomLabelProducer.from_authorities(source,room_auth,page_ids=PAGES)
    label_auth=label_prod.authority()

    out={}
    for page_id in PAGES:
        selectors=wall_auth.selectors_for_authenticated_viewports(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=page_id,
            view_type=DrawingViewType.FLOOR_PLAN.value,
        )
        if not selectors:
            out[page_id]={"wall_selector_count":0}
            continue
        selector=selectors[0]
        wall_scope=wall_auth.resolve_scope(selector)
        room_scope=room_auth.resolve_scope(SourceRoomFaceSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        ))
        label_scope=label_auth.resolve_scope(SourceRoomLabelSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        ))
        rows=[]
        for observation_id in current.text_observation_ids:
            native=text_auth.resolve_text(ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            ))
            receipt=native.receipt
            if receipt is None or str(receipt.page_id)!=page_id:
                continue
            raw=norm(receipt.raw_text)
            if raw not in TARGETS:
                continue
            geometry=tuple(float(v) for v in receipt.geometry)
            center=None
            matches=[]
            if len(geometry)==4:
                center=((geometry[0]+geometry[2])*0.5,(geometry[1]+geometry[3])*0.5)
                matches=[
                    {
                        "face_id":record.face_id,
                        "record_id":record.record_id,
                        "area_page_pts2":record.area_page_pts2,
                    }
                    for record in room_scope.records
                    if _point_in_polygon(center,record.polygon_pdf_pts)
                ]
            rows.append({
                "raw_text":receipt.raw_text,
                "observation_id":observation_id,
                "native_status":getattr(native.status,"value",str(native.status)),
                "native_reason_codes":list(native.reason_codes),
                "receipt_id":receipt.receipt_id,
                "geometry":list(geometry),
                "center":list(center) if center else None,
                "face_matches":matches,
            })

        out[page_id]={
            "decision_scope_id":selector.decision_scope_id,
            "wall_scope_status":getattr(wall_scope.status,"value",str(wall_scope.status)),
            "room_scope_status":getattr(room_scope.status,"value",str(room_scope.status)),
            "room_face_count":len(room_scope.records),
            "label_scope_status":getattr(label_scope.status,"value",str(label_scope.status)),
            "label_scope_reason_codes":list(label_scope.reason_codes),
            "published_labels":[
                {
                    "label":record.label,
                    "face_id":record.face_id,
                    "source_room_face_record_id":record.source_room_face_record_id,
                    "evidence_ids":list(record.evidence_ids),
                }
                for record in label_scope.records
                if norm(record.label) in TARGETS
            ],
            "split_candidates":[
                {
                    "label":candidate.label,
                    "word_face_ids":list(candidate.word_face_ids),
                    "source_room_face_record_ids":list(candidate.source_room_face_record_ids),
                }
                for candidate in label_scope.split_face_candidates
                if norm(candidate.label) in TARGETS
            ],
            "native_target_rows":rows,
        }
    print(json.dumps({
        "source_sha256":sha,
        "pages":out,
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
