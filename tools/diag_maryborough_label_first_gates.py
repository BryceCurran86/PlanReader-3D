from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

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
from pb_source_composite_room_face_authority import compose_grid_separated_room_faces
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "7"
TARGETS = (
    "POS COUNTER",
    "FOOD SERVICE",
    "WASH UP",
    "TRUCK DRIVER LOUNGE",
    "M-AMB",
    "F-AMB",
    "DRY STORE",
)


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    payload=SOURCE.read_bytes()
    sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="gpt2-maryborough-label-first-gates",
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
    if current is None:
        raise RuntimeError("published snapshot unavailable")

    wall_producer=PhysicalWallCandidateProducer.from_authenticated_viewports(
        source,page_ids=(PAGE_ID,)
    )
    wall_auth=wall_producer.authority()
    selectors=wall_auth.selectors_for_authenticated_viewports(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PAGE_ID,
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    if len(selectors)!=1:
        raise RuntimeError(f"expected one A110 selector, got {len(selectors)}")
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
    room_by_face={str(r.face_id):r for r in room_scope.records}

    label_auth=SourceRoomLabelProducer.from_authorities(
        source,room_auth,page_ids=(PAGE_ID,)
    ).authority()
    label_scope=label_auth.resolve_scope(SourceRoomLabelSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
    ))
    composite=compose_grid_separated_room_faces(
        wall_scope=wall_scope,
        room_scope=room_scope,
        label_scope=label_scope,
    )

    # Resolve every native word once and regroup by producer-owned block/line.
    text_auth=source.text_integrity_authority()
    lines=defaultdict(list)
    for oid in current.text_observation_ids:
        result=text_auth.resolve_text(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=oid,
        ))
        receipt=result.receipt
        if receipt is None or str(receipt.page_id)!=PAGE_ID:
            continue
        key=(int(receipt.block_no),int(receipt.line_no))
        geom=tuple(float(v) for v in (receipt.geometry or ()))
        face_ids=[]
        if len(geom)==4:
            x0,y0,x1,y1=geom
            center=((x0+x1)*0.5,(y0+y1)*0.5)
            face_ids=[
                str(rec.face_id)
                for rec in room_scope.records
                if _point_in_polygon(center,rec.polygon_pdf_pts)
            ]
        lines[key].append({
            "observation_id":oid,
            "word_no":int(receipt.word_no),
            "raw_text":str(receipt.raw_text),
            "trusted_text":result.trusted_text,
            "status":getattr(result.status,"value",str(result.status)),
            "reason_codes":list(result.reason_codes),
            "geometry":list(geom),
            "face_ids":face_ids,
        })

    target_line_rows={target:[] for target in TARGETS}
    for (block_no,line_no),words in sorted(lines.items()):
        ordered=sorted(words,key=lambda row:row["word_no"])
        raw_line=norm(" ".join(row["raw_text"] for row in ordered))
        if raw_line not in TARGETS:
            continue
        target_line_rows[raw_line].append({
            "block_no":block_no,
            "line_no":line_no,
            "raw_line":raw_line,
            "words":ordered,
        })

    label_records=defaultdict(list)
    for record in label_scope.records:
        label=norm(record.label)
        if label in TARGETS:
            label_records[label].append({
                "record_id":record.record_id,
                "face_id":str(record.face_id),
                "source_room_face_record_id":str(record.source_room_face_record_id),
            })

    split_records=defaultdict(list)
    for record in label_scope.split_face_candidates:
        label=norm(record.label)
        if label in TARGETS:
            split_records[label].append({
                "record_id":record.record_id,
                "word_face_ids":[str(x) for x in record.word_face_ids],
                "source_room_face_record_ids":[str(x) for x in record.source_room_face_record_ids],
            })

    composite_records=defaultdict(list)
    for record in composite.records:
        label=norm(record.label)
        if label in TARGETS:
            composite_records[label].append({
                "record_id":record.record_id,
                "constituent_face_ids":[str(x) for x in record.constituent_face_ids],
                "separator_wall_ids":[str(x) for x in record.separator_wall_ids],
                "bounding_wall_ids":[str(x) for x in record.bounding_wall_ids],
            })

    targets={}
    unresolved_composite=set(str(x) for x in composite.unresolved_label_candidate_ids)
    for target in TARGETS:
        rows=target_line_rows[target]
        first_failure=None
        if not rows:
            first_failure="native_exact_line_unavailable"
        elif any(
            any(word["status"]!="corroborated" for word in row["words"])
            for row in rows
        ):
            first_failure="text_integrity"
        elif any(
            any(len(word["face_ids"])!=1 for word in row["words"])
            for row in rows
        ):
            first_failure="source_face_ownership"
        elif label_records[target]:
            first_failure=None
        elif not split_records[target]:
            first_failure="room_label_binding"
        elif composite_records[target]:
            first_failure=None
        else:
            ids={row["record_id"] for row in split_records[target]}
            if ids & unresolved_composite:
                first_failure="composite_room_geometry_or_separator_authority"
            else:
                first_failure="composite_room_authority"

        targets[target]={
            "first_failure":first_failure,
            "native_lines":rows,
            "label_records":label_records[target],
            "split_face_candidates":split_records[target],
            "composite_records":composite_records[target],
        }

    print(json.dumps({
        "source_sha256":sha,
        "wall_scope_status":getattr(wall_scope.status,"value",str(wall_scope.status)),
        "wall_scope_complete":bool(wall_scope.scope_complete),
        "room_scope_status":getattr(room_scope.status,"value",str(room_scope.status)),
        "room_scope_complete":bool(room_scope.scope_complete),
        "label_scope_status":getattr(label_scope.status,"value",str(label_scope.status)),
        "label_scope_reason_codes":list(label_scope.reason_codes),
        "composite_status":getattr(composite.status,"value",str(composite.status)),
        "composite_reason_codes":list(composite.reason_codes),
        "targets":targets,
    },indent=2,sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
