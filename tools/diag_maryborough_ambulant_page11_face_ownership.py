from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
from pb_source_room_label_authority import (
    SourceRoomLabelProducer,
    SourceRoomLabelSelector,
    _point_in_polygon,
)
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID="11"
TARGETS={"M-AMB","F-AMB"}

def norm(value):
    return " ".join(str(value or "").strip().upper().split())

def main():
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="gpt2-ambulant-page11-face-ownership-diag",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("snapshot unavailable")

    wall_auth=composition.physical_wall_candidate_authority
    wall_selector_kwargs=dict(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PAGE_ID,
        decision_scope_id=f"wall-source:page-{PAGE_ID}",
    )
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
    wall_scope=wall_auth.resolve_scope(PhysicalWallCandidateSelector(**wall_selector_kwargs))

    room_auth=build_source_room_face_authority(wall_auth)
    room_scope=room_auth.resolve_scope(SourceRoomFaceSelector(**wall_selector_kwargs))

    label_producer=SourceRoomLabelProducer.from_authorities(
        source,room_auth,page_ids=(PAGE_ID,)
    )
    label_scope=label_producer.authority().resolve_scope(
        SourceRoomLabelSelector(**wall_selector_kwargs)
    )

    integrity=source.text_integrity_authority()
    target_rows=[]
    for observation_id in current.text_observation_ids:
        result=integrity.resolve_text(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        receipt=result.receipt
        if receipt is None or str(receipt.page_id)!=PAGE_ID:
            continue
        raw=norm(receipt.raw_text)
        trusted=norm(result.trusted_text) if result.trusted_text is not None else ""
        if raw not in TARGETS and trusted not in TARGETS:
            continue
        geom=tuple(float(v) for v in receipt.geometry)
        center=None
        matches=[]
        if len(geom)==4:
            center=((geom[0]+geom[2])*0.5,(geom[1]+geom[3])*0.5)
            matches=[
                {
                    "face_id":str(record.face_id),
                    "record_id":str(record.record_id),
                    "area_page_pts2":float(record.area_page_pts2),
                    "bounding_wall_ids":list(record.bounding_wall_ids),
                }
                for record in room_scope.records
                if _point_in_polygon(center,record.polygon_pdf_pts)
            ]
        target_rows.append({
            "observation_id":observation_id,
            "raw_text":raw,
            "trusted_text":trusted or None,
            "status":getattr(result.status,"value",str(result.status)),
            "reason_codes":list(result.reason_codes),
            "geometry":list(geom),
            "center":list(center) if center else None,
            "face_match_count":len(matches),
            "face_matches":matches,
        })

    viewport_scopes=[]
    viewport_wall_producer=PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,page_ids=(PAGE_ID,)
    )
    viewport_wall_auth=viewport_wall_producer.authority()
    viewport_current=source.published_snapshot_for_revision(published.revision.revision_id)
    if viewport_current is not None:
        selectors=viewport_wall_auth.selectors_for_authenticated_viewports(
            document_id=viewport_current.revision.document_id,
            revision_id=viewport_current.revision.revision_id,
            source_sha256=viewport_current.revision.source_sha256,
            snapshot_id=viewport_current.snapshot.snapshot_id,
            page_id=PAGE_ID,
            view_type=DrawingViewType.FLOOR_PLAN.value,
        )
        viewport_room_auth=build_source_room_face_authority(viewport_wall_auth)
        try:
            viewport_label_auth=SourceRoomLabelProducer.from_authorities(
                source,viewport_room_auth,page_ids=(PAGE_ID,)
            ).authority()
        except Exception:
            viewport_label_auth=None
        for selector in selectors:
            vroom=viewport_room_auth.resolve_scope(SourceRoomFaceSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
            ))
            vlabel=None
            if viewport_label_auth is not None:
                vlabel=viewport_label_auth.resolve_scope(SourceRoomLabelSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                ))
            vtargets=[]
            for row in target_rows:
                if row["center"] is None:
                    continue
                point=tuple(row["center"])
                matches=[
                    {
                        "face_id":str(record.face_id),
                        "record_id":str(record.record_id),
                        "area_page_pts2":float(record.area_page_pts2),
                    }
                    for record in vroom.records
                    if _point_in_polygon(point,record.polygon_pdf_pts)
                ]
                vtargets.append({
                    "raw_text":row["raw_text"],
                    "trusted_text":row["trusted_text"],
                    "text_status":row["status"],
                    "text_reason_codes":row["reason_codes"],
                    "face_match_count":len(matches),
                    "face_matches":matches,
                })
            viewport_scopes.append({
                "decision_scope_id":selector.decision_scope_id,
                "room_status":getattr(vroom.status,"value",str(vroom.status)),
                "room_reason_codes":list(vroom.reason_codes),
                "room_face_count":len(vroom.records),
                "room_face_universe_complete":bool(vroom.face_universe_complete),
                "label_status":None if vlabel is None else getattr(vlabel.status,"value",str(vlabel.status)),
                "label_reason_codes":[] if vlabel is None else list(vlabel.reason_codes),
                "published_targets":[] if vlabel is None else [
                    {
                        "label":record.label,
                        "face_id":record.face_id,
                        "source_room_face_record_id":record.source_room_face_record_id,
                    }
                    for record in vlabel.records
                    if norm(record.label) in TARGETS
                ],
                "split_targets":[] if vlabel is None else [
                    {
                        "label":candidate.label,
                        "word_face_ids":list(candidate.word_face_ids),
                        "source_room_face_record_ids":list(candidate.source_room_face_record_ids),
                    }
                    for candidate in vlabel.split_face_candidates
                    if norm(candidate.label) in TARGETS
                ],
                "target_rows":vtargets,
            })

    print(json.dumps({
        "source_sha256":sha,
        "wall_scope_status":getattr(wall_scope.status,"value",str(wall_scope.status)),
        "wall_scope_reason_codes":list(wall_scope.reason_codes),
        "wall_count":len(wall_scope.records),
        "room_scope_status":getattr(room_scope.status,"value",str(room_scope.status)),
        "room_scope_reason_codes":list(room_scope.reason_codes),
        "room_face_universe_complete":bool(room_scope.face_universe_complete),
        "room_face_count":len(room_scope.records),
        "label_scope_status":getattr(label_scope.status,"value",str(label_scope.status)),
        "label_scope_reason_codes":list(label_scope.reason_codes),
        "published_targets":[
            {
                "label":record.label,
                "face_id":record.face_id,
                "source_room_face_record_id":record.source_room_face_record_id,
                "evidence_ids":list(record.evidence_ids),
            }
            for record in label_scope.records
            if norm(record.label) in TARGETS
        ],
        "split_targets":[
            {
                "label":candidate.label,
                "word_face_ids":list(candidate.word_face_ids),
                "source_room_face_record_ids":list(candidate.source_room_face_record_ids),
            }
            for candidate in label_scope.split_face_candidates
            if norm(candidate.label) in TARGETS
        ],
        "target_rows":target_rows,
        "viewport_scope_count":len(viewport_scopes),
        "viewport_scopes":viewport_scopes,
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
