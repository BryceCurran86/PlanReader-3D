from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
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
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual != SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    topology,support,_page_count=_source_page_scopes(PDF)
    execution=tuple(sorted(set(topology)|set(support))) or topology
    page_ids=tuple(str(i+1) for i in execution)
    topology_ids=tuple(str(i+1) for i in topology)
    evidence_ids=tuple(p for p in page_ids if p not in topology_ids)

    document_id=f"live-source:{actual[:32]}"
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
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
    dim=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    visibility=source.authority()
    physical=wall.physical_opening_authority
    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")

    selector_by_physical={}
    existence_by_physical={}
    for observation_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result=physical.prove_existence(selector)
        if result.status is EvidenceResolutionStatus.CORROBORATED and result.existence_record is not None:
            pid=result.existence_record.record_id
            selector_by_physical[pid]=selector
            existence_by_physical[pid]=result.existence_record

    rows=[]
    for opening in sorted(voids.canonical_openings,key=lambda x:x.physical_opening_id):
        if opening.area_m2 is None:
            continue
        selector=selector_by_physical.get(opening.physical_opening_id)
        existence=existence_by_physical.get(opening.physical_opening_id)
        if selector is None or existence is None:
            continue
        d=dim.publish_scope(selector)
        text_rows=[]
        if d.evidence is not None:
            for observation_id in d.evidence.source_text_observation_ids:
                res=visibility.resolve_visible(ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                ))
                obs=res.observation
                text_rows.append({
                    "observation_id":observation_id,
                    "status":state(res.status),
                    "raw_text":None if obs is None else obs.raw_text,
                    "geometry":None if obs is None else list(obs.geometry),
                    "source_primitive_ref":None if obs is None else obs.source_primitive_ref,
                })
        rows.append({
            "physical_opening_id":opening.physical_opening_id,
            "opening_kind":opening.opening_kind,
            "structural_pattern":opening.structural_pattern,
            "area_m2":opening.area_m2,
            "area_basis":opening.area_basis,
            "aperture_bbox_pt":list(existence.aperture_bbox_pt) if existence.aperture_bbox_pt else None,
            "dimension_status":state(d.status),
            "dimension_reason_codes":list(d.reason_codes),
            "dimension_raw_text":None if d.evidence is None else d.evidence.raw_text,
            "dimension_record_id":None if d.evidence is None else d.evidence.record_id,
            "dimension_source_text":text_rows,
            "host_wall_id":opening.host_wall_id,
            "host_binding_record_id":opening.host_binding_record_id,
        })
    print(json.dumps({
        "source_sha256":actual,
        "document_id":document_id,
        "revision_id":published.revision.revision_id,
        "topology_page_ids":list(topology_ids),
        "evidence_page_ids":list(evidence_ids),
        "area_opening_count":len(rows),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
