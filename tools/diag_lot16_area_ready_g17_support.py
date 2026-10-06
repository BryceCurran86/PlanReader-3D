from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def state(v):
    return str(getattr(v,"value",v))

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    with fitz.open(stream=data,filetype="pdf") as doc:
        indices=tuple(range(int(doc.page_count)))
    scope=source_floor_plan_topology_scope(PDF,indices)
    topology=tuple(scope.topology_page_indices() or ()) if scope else indices
    all_page_ids=tuple(str(i+1) for i in indices)
    topology_page_ids=tuple(str(i+1) for i in topology)
    evidence_page_ids=tuple(p for p in all_page_ids if p not in topology_page_ids)

    source=SourceVisibilityProducer(
        producer_method="diag_lot16_area_ready_g17_support",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-area-ready-g17-support",
        source_bytes=data,
        source_locator=str(PDF),
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
    ready={
        o.physical_opening_id:o
        for o in voids.canonical_openings
        if str(o.opening_kind or "").lower() in {"door","window"}
        and o.area_m2 is not None
        and not str(o.host_wall_id or "").strip()
    }
    visibility=source.authority()
    physical=wall.physical_opening_authority
    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")
    existence={}
    for oid in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        res=physical.prove_existence(selector)
        if res.status is EvidenceResolutionStatus.CORROBORATED and res.existence_record is not None:
            existence[res.existence_record.record_id]=res.existence_record

    rows=[]
    for opening_id,target in sorted(ready.items()):
        record=existence.get(opening_id)
        if record is None:
            continue
        supports=[]
        for support_id in record.source_observation_ids:
            res=visibility.resolve_raster_opening_primitive(ObservationSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                observation_id=support_id,
            ))
            obs=res.observation
            supports.append({
                "observation_id":support_id,
                "status":state(res.status),
                "reason_codes":list(res.reason_codes),
                "kind":None if obs is None else obs.observation_kind,
                "source_primitive_ref":None if obs is None else obs.source_primitive_ref,
                "geometry":None if obs is None else list(obs.geometry),
                "derivation_parent_ids":[] if obs is None else list(obs.derivation_parent_ids),
                "source_partition_id":None if obs is None else obs.source_partition_id,
            })
        rows.append({
            "physical_opening_id":opening_id,
            "kind":target.opening_kind,
            "area_m2":target.area_m2,
            "area_basis":target.area_basis,
            "aperture_bbox_pt":record.aperture_bbox_pt,
            "source_lineage_root_ids":list(record.source_lineage_root_ids),
            "supports":supports,
        })
    print(json.dumps({
        "source_sha256":actual,
        "area_ready_unhosted_count":len(rows),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
