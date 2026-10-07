import json
from pathlib import Path
import fitz

import pb_schedule_opening_instance_binding_authority as sched
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_migration_contracts import EvidenceResolutionStatus

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
doc=fitz.open(SOURCE)
try:
    a610=[]
    for index in range(doc.page_count):
        text=" ".join((doc[index].get_text("text") or "").upper().split())
        if "WINDOW ELEVATIONS" in text and all(tag in text for tag in ("W01","W02","W05","W06")):
            a610.append(index)
    assert len(a610)==1, a610
    elevation_page_id=str(a610[0]+1)
finally:
    doc.close()

source=SourceVisibilityProducer(
    producer_method="diag-gpt2-maryborough-window-tag-binding-current-main",
    producer_version="1",
)
published=source.ingest_native_pdf_bytes(
    document_id="diag-gpt2-maryborough-window-tag-binding-current-main",
    source_bytes=SOURCE.read_bytes(),
    source_locator="memory://maryborough.pdf",
    page_ids=("7",elevation_page_id),
)
wall_opening=compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=("7",),
)
voids=compose_live_physical_opening_voids(
    source_visibility_producer=source,
    wall_opening_composition=wall_opening,
)

visibility=source.authority()
text_integrity=source.text_integrity_authority()
wanted={"W01","W02","W03","W04","W05","W06"}
tags=[]
for obs_id in published.text_observation_ids:
    resolved=text_integrity.resolve_text(ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=obs_id,
    ))
    if (
        resolved.status is not EvidenceResolutionStatus.CORROBORATED
        or resolved.trusted_text is None
        or resolved.receipt is None
        or str(resolved.receipt.page_id)!="7"
    ):
        continue
    normalized=sched.normalize_opening_tag(resolved.trusted_text)
    if normalized is None or normalized.tag not in wanted:
        continue
    bbox=sched._bbox_of_points(sched._geometry_points(tuple(float(v) for v in resolved.receipt.geometry)))
    tags.append({
        "tag":normalized.tag,
        "observation_id":obs_id,
        "bbox":None if bbox is None else list(bbox),
    })

physical=wall_opening.physical_opening_authority
semantic=wall_opening.semantic_enumeration_result.record
opening_rows=[]
containments={tag:[] for tag in sorted(wanted)}
if semantic is not None:
    for obs_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        existence=physical.prove_existence(selector)
        opening=existence.existence_record
        if opening is None or str(opening.page_id)!="7":
            continue
        records=[]
        for sid in opening.source_observation_ids:
            rr=visibility.resolve_visible(ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=sid,
            ))
            if rr.status is EvidenceResolutionStatus.CORROBORATED and rr.observation is not None:
                records.append(rr.observation)
        aperture=sched._opening_aperture(records)
        row={
            "opening_id":opening.record_id,
            "representative_observation_id":obs_id,
            "semantic_class":opening.semantic_class,
            "structural_pattern":opening.structural_pattern,
            "source_observation_count":len(opening.source_observation_ids),
            "aperture":None if aperture is None else {
                "axis":list(aperture.axis),
                "normal":list(aperture.normal),
                "along_min":aperture.along_min,
                "along_max":aperture.along_max,
                "normal_min":aperture.normal_min,
                "normal_max":aperture.normal_max,
            },
            "contained_tags":[],
        }
        if aperture is not None:
            for tagrow in tags:
                bbox=tuple(tagrow["bbox"]) if tagrow["bbox"] is not None else None
                if bbox is not None and sched._aperture_contains_bbox(aperture,bbox):
                    row["contained_tags"].append(tagrow["tag"])
                    containments[tagrow["tag"]].append(opening.record_id)
        opening_rows.append(row)

canonical=[
    {
        "canonical_opening_id":o.canonical_opening_id,
        "physical_opening_id":o.physical_opening_id,
        "type_mark":o.type_mark,
        "opening_kind":o.opening_kind,
        "tag_observation_id":o.tag_observation_id,
        "area_basis":o.area_basis,
        "area_m2":o.area_m2,
        "host_wall_id":o.host_wall_id,
        "structural_pattern":o.structural_pattern,
        "evidence_ids":list(o.evidence_ids),
    }
    for o in voids.canonical_openings
    if (o.type_mark or "").upper() in wanted or o.tag_observation_id
]
trace_rows=[
    {
        "opening_identity_id":t.opening_identity_id,
        "representative_observation_id":t.representative_observation_id,
        "schedule_status":getattr(t.schedule_binding_status,"value",str(t.schedule_binding_status)),
        "schedule_reasons":list(t.schedule_binding_reason_codes),
        "schedule_record_id":t.schedule_binding_record_id,
    }
    for t in voids.traces
]

print(json.dumps({
    "elevation_page_id":elevation_page_id,
    "tag_rows":tags,
    "tag_containments":containments,
    "physical_opening_count":len(opening_rows),
    "physical_openings":opening_rows,
    "canonical_marked_openings":canonical,
    "canonical_opening_count":len(voids.canonical_openings),
    "schedule_trace_reason_counts":{
        reason:sum(reason in row["schedule_reasons"] for row in trace_rows)
        for reason in sorted({r for row in trace_rows for r in row["schedule_reasons"]})
    },
    "traces":trace_rows,
},indent=2,sort_keys=True))
