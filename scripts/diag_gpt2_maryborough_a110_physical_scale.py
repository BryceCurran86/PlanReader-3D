from __future__ import annotations

import json
from pathlib import Path

from pb_drawing_evidence_binding import DrawingViewType
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")

source=SourceVisibilityProducer(
    producer_method="diag-gpt2-maryborough-a110-physical-scale",
    producer_version="1",
)
published=source.ingest_native_pdf_bytes(
    document_id="diag-gpt2-maryborough-a110-physical-scale",
    source_bytes=SOURCE.read_bytes(),
    source_locator="memory://maryborough.pdf",
    page_ids=("7",),
)

# Materialize the same authenticated floor-plan viewport universe used by live
# room-area composition, then refresh producer snapshot lineage.
wall_producer=PhysicalWallCandidateProducer.from_authenticated_viewports(
    source,page_ids=("7",)
)
wall_auth=wall_producer.authority()
current=source.published_snapshot_for_revision(published.revision.revision_id)
assert current is not None
selectors=wall_auth.selectors_for_authenticated_viewports(
    document_id=current.revision.document_id,
    revision_id=current.revision.revision_id,
    source_sha256=current.revision.source_sha256,
    snapshot_id=current.snapshot.snapshot_id,
    page_id="7",
    view_type=DrawingViewType.FLOOR_PLAN.value,
)

scale=PhysicalScaleProducer.from_source_visibility_producer(source)
page_result=scale.publish_scope(PhysicalScaleSelector(
    document_id=current.revision.document_id,
    revision_id=current.revision.revision_id,
    source_sha256=current.revision.source_sha256,
    snapshot_id=current.snapshot.snapshot_id,
    page_id="7",
    viewport_id=None,
))

viewport_rows=[]
for selector in selectors:
    wall_scope=wall_auth.resolve_scope(selector)
    viewport_id=getattr(wall_scope,"viewport_id",None)
    if not viewport_id:
        continue
    result=scale.publish_scope(PhysicalScaleSelector(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id="7",
        viewport_id=str(viewport_id),
    ))
    evidence=result.evidence
    viewport_rows.append({
        "viewport_id":str(viewport_id),
        "viewport_bbox":list(getattr(wall_scope,"viewport_bbox",()) or ()),
        "wall_scope_status":getattr(wall_scope.status,"value",str(wall_scope.status)),
        "wall_scope_complete":bool(wall_scope.scope_complete),
        "scale_status":getattr(result.status,"value",str(result.status)),
        "scale_reason_codes":list(result.reason_codes),
        "scale_evidence":None if evidence is None else {
            "record_id":evidence.record_id,
            "source_kind":evidence.source_kind,
            "source_span_pt":evidence.source_span_pt,
            "physical_span_mm":evidence.physical_span_mm,
            "points_per_mm":evidence.points_per_mm,
            "mm_per_point":evidence.mm_per_point,
            "source_segment_observation_ids":list(evidence.source_segment_observation_ids),
            "source_text_observation_ids":list(evidence.source_text_observation_ids),
        },
    })

print(json.dumps({
    "page_scale_status":getattr(page_result.status,"value",str(page_result.status)),
    "page_scale_reason_codes":list(page_result.reason_codes),
    "page_scale_evidence":None if page_result.evidence is None else page_result.evidence.record_id,
    "authenticated_floor_plan_viewport_count":len(selectors),
    "viewports":viewport_rows,
},indent=2,sort_keys=True))
