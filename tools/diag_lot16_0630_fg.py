from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionProducer,
    _gap_span_for_opening,
    _label_matches_gap,
    _trusted_text_lines,
    parse_opening_label_dimensions,
)
from pb_opening_label_semantic_authority import (
    OpeningLabelSemanticProducer,
    _trusted_native_lines,
)
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def status(value):
    return str(getattr(value, "value", value))

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    assert actual == SHA
    source=SourceVisibilityProducer(producer_method="diag_lot16_0630_fg",producer_version="1")
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-0630-fg",
        source_bytes=data,
        source_locator=str(PDF),
        page_ids=tuple(str(i+1) for i in range(13)),
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
        evidence_page_ids=tuple(str(i) for i in range(1,14) if i != 3),
    )
    physical=wall.physical_opening_authority
    dim=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    sem=OpeningLabelSemanticProducer.from_source_visibility_producer(source)
    rows=[]
    for observation_id in wall.semantic_enumeration_result.record.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        result=physical.prove_existence(selector)
        opening=result.existence_record
        if result.status is not EvidenceResolutionStatus.CORROBORATED or opening is None:
            continue
        gap=_gap_span_for_opening(source,opening)
        trusted=_trusted_text_lines(source,opening)
        texts=[line.text for line in trusted if gap is not None and _label_matches_gap(line,gap)]
        if not any("0630" in t or "FG" in t.upper() for t in texts):
            continue
        s=sem.publish_scope(selector)
        d=dim.publish_scope(selector)
        rows.append({
            "opening_id":opening.record_id,
            "pattern":opening.structural_pattern,
            "bbox":opening.aperture_bbox_pt,
            "owned_dimension_lines":[
                {
                    "text":line.text,
                    "ids":list(line.observation_ids),
                    "parsed":None if parse_opening_label_dimensions(line.text) is None else {
                        "raw_text":parse_opening_label_dimensions(line.text).raw_text,
                        "tokens":list(parse_opening_label_dimensions(line.text).dimension_tokens),
                        "suffix":parse_opening_label_dimensions(line.text).suffix_text,
                    }
                }
                for line in trusted
                if gap is not None and _label_matches_gap(line,gap)
            ],
            "native_lines":[
                {
                    "text":line.text,
                    "ids":list(line.observation_ids),
                    "match":False if gap is None else _label_matches_gap(line,gap),
                }
                for _b,_l,line in _trusted_native_lines(source,opening)
            ],
            "semantic":{
                "status":status(s.status),
                "reasons":list(s.reason_codes),
                "kind":None if s.evidence is None else s.evidence.semantic_kind,
                "source_ids":[] if s.evidence is None else list(s.evidence.source_text_observation_ids),
                "raw_texts":[] if s.evidence is None else list(s.evidence.raw_texts),
            },
            "dimension":{
                "status":status(d.status),
                "reasons":list(d.reason_codes),
                "raw_text":None if d.evidence is None else d.evidence.raw_text,
                "values":[] if d.evidence is None else list(d.evidence.dimension_values_mm),
                "area":None if d.evidence is None else d.evidence.area_m2,
                "source_ids":[] if d.evidence is None else list(d.evidence.source_text_observation_ids),
            }
        })
    print(json.dumps({"source_sha256":actual,"rows":rows},indent=2,sort_keys=True))

if __name__ == "__main__":
    main()
