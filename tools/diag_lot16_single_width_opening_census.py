from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import fitz

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionProducer,
)
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def state(value):
    return str(getattr(value, "value", value))


def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    with fitz.open(stream=payload,filetype="pdf") as doc:
        page_count=int(doc.page_count)
    all_indices=tuple(range(page_count))
    scope=source_floor_plan_topology_scope(PDF, all_indices)
    if scope is None:
        topology_indices=all_indices
        support_indices=()
    else:
        topology_indices=tuple(scope.topology_page_indices() or all_indices)
        support_indices=tuple(
            getattr(
                scope,
                "room_area_support_page_indices",
                getattr(scope, "evidence_page_indices", ()),
            ) or ()
        )
    execution_indices=tuple(sorted(set(topology_indices)|set(support_indices)))
    all_page_ids=tuple(str(i+1) for i in execution_indices)
    topology_page_ids=tuple(str(i+1) for i in topology_indices)
    evidence_page_ids=tuple(p for p in all_page_ids if p not in topology_page_ids)

    source_sha=actual
    document_id=f"live-source:{source_sha[:32]}"
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=all_page_ids,
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_page_ids,
        evidence_page_ids=evidence_page_ids,
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )

    physical=wall.physical_opening_authority
    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")

    representative_by_opening={}
    selector_by_opening={}
    existence_by_opening={}
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
            result.status is EvidenceResolutionStatus.CORROBORATED
            and record is not None
        ):
            representative_by_opening[record.record_id]=observation_id
            selector_by_opening[record.record_id]=selector
            existence_by_opening[record.record_id]=record

    label_producer=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    label_results={
        opening_id:label_producer.publish_scope(selector)
        for opening_id,selector in selector_by_opening.items()
    }

    canonical_by_id={o.physical_opening_id:o for o in voids.canonical_openings}
    binding_by_id={
        str(trace.opening_identity_id): trace
        for trace in wall.opening_bindings
        if str(getattr(trace,"opening_identity_id","") or "")
    }

    rows=[]
    all_label_counts=Counter()
    for opening_id,result in sorted(label_results.items()):
        evidence=getattr(result,"evidence",None)
        if evidence is None:
            continue
        values=tuple(float(v) for v in evidence.dimension_values_mm)
        all_label_counts[len(values)] += 1
        if len(values) != 1:
            continue
        opening=canonical_by_id.get(opening_id)
        trace=binding_by_id.get(opening_id)
        binding_status=state(getattr(trace,"status","")) if trace is not None else None
        host_wall_id=(
            str(getattr(opening,"host_wall_id","") or "")
            if opening is not None else ""
        )
        rows.append({
            "physical_opening_id":opening_id,
            "representative_observation_id":representative_by_opening.get(opening_id),
            "page_id":str(getattr(existence_by_opening[opening_id],"page_id","")),
            "structural_pattern":str(getattr(existence_by_opening[opening_id],"structural_pattern","")),
            "raw_text":evidence.raw_text,
            "dimension_values_mm":list(values),
            "semantic_kind":evidence.semantic_kind,
            "source_text_observation_ids":list(evidence.source_text_observation_ids),
            "label_status":state(result.status),
            "opening_kind":None if opening is None else opening.opening_kind,
            "type_mark":None if opening is None else opening.type_mark,
            "host_wall_id":host_wall_id or None,
            "host_binding_record_id":None if opening is None else opening.host_binding_record_id,
            "host_frame_record_id":None if opening is None else opening.host_frame_record_id,
            "binding_status":binding_status,
            "area_m2":None if opening is None else opening.area_m2,
            "area_basis":None if opening is None else opening.area_basis,
        })

    print(json.dumps({
        "source_sha256":actual,
        "topology_page_ids":topology_page_ids,
        "execution_page_ids":all_page_ids,
        "canonical_opening_count":len(voids.canonical_openings),
        "published_opening_area_count":sum(
            1 for o in voids.canonical_openings
            if o.area_m2 is not None and o.host_wall_id
        ),
        "label_dimension_count_by_axis_count":dict(sorted(all_label_counts.items())),
        "single_dimension_opening_count":len(rows),
        "single_dimension_hosted_count":sum(bool(r["host_wall_id"]) for r in rows),
        "single_dimension_kind_counts":dict(Counter(
            str(r["opening_kind"] or r["semantic_kind"] or "<none>")
            for r in rows
        ).most_common()),
        "single_dimension_value_counts_mm":dict(Counter(
            str(int(round(r["dimension_values_mm"][0])))
            for r in rows
        ).most_common()),
        "rows":rows,
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
