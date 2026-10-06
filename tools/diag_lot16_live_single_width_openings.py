from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.run_source_closed_project_handoff import _source_page_scopes

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def state(v):
    return str(getattr(v,"value",v))

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    topology,support,_page_count=_source_page_scopes(PDF)
    execution=tuple(sorted(set(topology)|set(support))) or topology
    page_ids=tuple(str(i+1) for i in execution)
    topology_ids=tuple(str(i+1) for i in topology)
    evidence_ids=tuple(p for p in page_ids if p not in topology_ids)

    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    document_id=f"live-source:{actual[:32]}"
    published=source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=data,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=page_ids,
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_ids,
        evidence_page_ids=evidence_ids,
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )
    canonical_by_physical={
        o.physical_opening_id:o for o in voids.canonical_openings
    }

    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")
    physical=wall.physical_opening_authority
    label=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    visibility=source.authority()

    rows=[]
    all_corrob=0
    for observation_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result=physical.prove_existence(selector)
        record=result.existence_record
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or record is None
        ):
            continue
        dim=label.publish_scope(selector)
        if dim.status is not EvidenceResolutionStatus.CORROBORATED or dim.evidence is None:
            continue
        all_corrob+=1
        evidence=dim.evidence
        if len(tuple(evidence.dimension_values_mm)) != 1:
            continue
        opening=canonical_by_physical.get(record.record_id)
        text_rows=[]
        for oid in evidence.source_text_observation_ids:
            res=visibility.resolve_visible(ObservationSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                observation_id=oid,
            ))
            obs=res.observation
            text_rows.append({
                "observation_id":oid,
                "status":state(res.status),
                "raw_text":None if obs is None else obs.raw_text,
                "geometry":None if obs is None else list(obs.geometry),
                "source_primitive_ref":None if obs is None else obs.source_primitive_ref,
            })
        rows.append({
            "physical_opening_id":record.record_id,
            "page_id":record.page_id,
            "structural_pattern":record.structural_pattern,
            "aperture_bbox_pt":list(record.aperture_bbox_pt) if record.aperture_bbox_pt else None,
            "raw_text":evidence.raw_text,
            "dimension_values_mm":list(evidence.dimension_values_mm),
            "semantic_kind":evidence.semantic_kind,
            "label_evidence_id":evidence.evidence_id,
            "source_text":text_rows,
            "canonical_present":opening is not None,
            "opening_kind":None if opening is None else opening.opening_kind,
            "host_wall_id":None if opening is None else opening.host_wall_id,
            "host_binding_record_id":None if opening is None else opening.host_binding_record_id,
            "host_frame_record_id":None if opening is None else opening.host_frame_record_id,
            "area_m2":None if opening is None else opening.area_m2,
            "area_basis":None if opening is None else opening.area_basis,
            "geometry_complete":False if opening is None else bool(opening.geometry_complete),
        })
    print(json.dumps({
        "source_sha256":actual,
        "document_id":document_id,
        "topology_page_ids":list(topology_ids),
        "evidence_page_ids":list(evidence_ids),
        "all_correlated_label_dimension_count":all_corrob,
        "single_dimension_opening_count":len(rows),
        "single_dimension_values_mm":sorted({v for row in rows for v in row["dimension_values_mm"]}),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
