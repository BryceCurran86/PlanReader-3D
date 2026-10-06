from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

import pb_opening_label_dimension_authority as labels
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    with fitz.open(stream=data,filetype="pdf") as doc:
        page_count=int(doc.page_count)
    indices=tuple(range(page_count))
    scope=source_floor_plan_topology_scope(PDF,indices)
    topology=tuple(scope.topology_page_indices() or indices) if scope else indices
    support=tuple(getattr(scope,"room_area_support_page_indices",()) or ()) if scope else ()
    execution=tuple(sorted(set(topology)|set(support)))
    page_ids=tuple(str(i+1) for i in execution)
    topology_ids=tuple(str(i+1) for i in topology)
    evidence_ids=tuple(p for p in page_ids if p not in topology_ids)

    source_sha=actual
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{source_sha[:32]}",
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
    physical=wall.physical_opening_authority
    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")

    openings={}
    selectors={}
    for obs_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        result=physical.prove_existence(selector)
        record=result.existence_record
        if result.status is EvidenceResolutionStatus.CORROBORATED and record is not None:
            openings[record.record_id]=record
            selectors[record.record_id]=selector

    producer=labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    sample=next(iter(openings.values()))
    trusted=producer._trusted_text_lines_for_opening(sample)
    trusted_870=[]
    for line in trusted:
        parsed=labels.parse_opening_label_dimensions(line.text)
        if parsed is None:
            continue
        if tuple(parsed.dimension_values_mm)==(870.0,):
            trusted_870.append({
                "text":line.text,
                "bbox":list(line.bbox),
                "observation_ids":list(line.observation_ids),
            })

    matched=[]
    gap_unavailable=0
    for opening_id,opening in openings.items():
        gap=labels._gap_span_for_opening(source,opening)
        if gap is None:
            gap_unavailable+=1
            continue
        rows=[]
        for line in trusted:
            parsed=labels.parse_opening_label_dimensions(line.text)
            if parsed is None or tuple(parsed.dimension_values_mm)!=(870.0,):
                continue
            if labels._label_matches_gap(line,gap):
                rows.append({
                    "text":line.text,
                    "bbox":list(line.bbox),
                    "observation_ids":list(line.observation_ids),
                })
        if rows:
            result=producer.publish_scope(selectors[opening_id])
            matched.append({
                "opening_id":opening_id,
                "page_id":opening.page_id,
                "structural_pattern":opening.structural_pattern,
                "aperture_bbox_pt":list(opening.aperture_bbox_pt) if opening.aperture_bbox_pt else None,
                "matching_870_lines":rows,
                "published_status":str(getattr(result.status,"value",result.status)),
                "published_reason_codes":list(result.reason_codes),
                "published_evidence":None if result.evidence is None else {
                    "raw_text":result.evidence.raw_text,
                    "dimension_values_mm":list(result.evidence.dimension_values_mm),
                    "semantic_kind":result.evidence.semantic_kind,
                },
            })

    print(json.dumps({
        "source_sha256":actual,
        "physical_opening_count":len(openings),
        "trusted_text_line_count":len(trusted),
        "trusted_870_line_count":len(trusted_870),
        "trusted_870_lines":trusted_870,
        "gap_unavailable_opening_count":gap_unavailable,
        "opening_match_count":len(matched),
        "matches":matched,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
