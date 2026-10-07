from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_visibility_authority import SourceVisibilityProducer

PROJECT="au_qld_lot16_power"
PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
OLD=Path("artifacts/old-authoritative/family_runs/opening_area.sealed.json")
OUT=Path("artifacts/gpt3-lot16-regression")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _state(value) -> str:
    return str(getattr(value,"value",value))


def main() -> None:
    old=json.loads(OLD.read_text(encoding="utf-8"))
    prior_rows=[
        q for q in old.get("quantities",())
        if not q.get("abstained",False)
    ]
    prior_by_physical={}
    for q in prior_rows:
        refs=[str(x) for x in (q.get("object_identity_refs") or ()) if str(x)]
        if len(refs)!=1:
            raise SystemExit(f"prior quantity lacks exactly one physical identity: {q.get('quantity_id')}")
        prior_by_physical[refs[0]]=q

    source_bytes=PDF.read_bytes()
    sha=hashlib.sha256(source_bytes).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    doc=fitz.open(stream=source_bytes,filetype="pdf")
    try:
        page_count=int(doc.page_count)
    finally:
        doc.close()
    all_indices=tuple(range(page_count))
    scope=source_floor_plan_topology_scope(PDF,all_indices)
    topology_indices=(
        tuple(scope.topology_page_indices() or ())
        if scope is not None else all_indices
    )
    topology_page_ids=tuple(str(i+1) for i in topology_indices)
    all_page_ids=tuple(str(i+1) for i in all_indices)
    evidence_page_ids=tuple(p for p in all_page_ids if p not in topology_page_ids)

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_sealed_identity_regression",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=all_page_ids,
    )
    wall_opening=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_page_ids,
        evidence_page_ids=evidence_page_ids,
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    area_quantities=publish_live_opening_area_quantities(voids)

    semantic=wall_opening.semantic_enumeration_result.record
    semantic_ids=set(() if semantic is None else semantic.physical_opening_record_ids)
    binding_by_identity={
        str(t.opening_identity_id):t
        for t in wall_opening.opening_bindings
        if t.opening_identity_id
    }
    frame_by_identity={
        str(t.opening_identity_id):t
        for t in wall_opening.host_frames
        if t.opening_identity_id
    }
    canonical_by_identity={
        str(o.physical_opening_id):o
        for o in voids.canonical_openings
    }
    quantity_by_identity={}
    for q in area_quantities:
        for identity in q.input_entity_ids:
            quantity_by_identity.setdefault(str(identity),[]).append(q)

    rows=[]
    for physical_id,old_q in sorted(prior_by_physical.items()):
        binding=binding_by_identity.get(physical_id)
        frame=frame_by_identity.get(physical_id)
        canonical=canonical_by_identity.get(physical_id)
        current_q=quantity_by_identity.get(physical_id,[])
        if physical_id not in semantic_ids:
            first_failure="SEMANTIC_ENUMERATION"
        elif binding is None or getattr(binding,"record_id",None) is None:
            first_failure="HOST_BINDING"
        elif canonical is None:
            first_failure="CANONICALISATION"
        elif not current_q:
            first_failure="QUANTITY"
        else:
            first_failure="PRESERVED"

        rows.append({
            "prior_quantity_id":old_q.get("quantity_id"),
            "prior_value":old_q.get("value"),
            "physical_opening_id":physical_id,
            "first_failure_stage":first_failure,
            "semantic_present":physical_id in semantic_ids,
            "binding_present":binding is not None,
            "binding_status":None if binding is None else _state(binding.status),
            "binding_record_id":None if binding is None else binding.record_id,
            "binding_host_wall_id":None if binding is None else binding.host_wall_id,
            "binding_reason_codes":[] if binding is None else list(binding.reason_codes),
            "frame_present":frame is not None,
            "frame_status":None if frame is None else _state(frame.status),
            "frame_record_id":None if frame is None else frame.record_id,
            "frame_reason_codes":[] if frame is None else list(frame.reason_codes),
            "canonical_present":canonical is not None,
            "canonical_kind":None if canonical is None else canonical.opening_kind,
            "canonical_area_m2":None if canonical is None else canonical.area_m2,
            "canonical_area_basis":None if canonical is None else canonical.area_basis,
            "canonical_figured_area_record_id":None if canonical is None else canonical.figured_area_record_id,
            "current_area_quantity_count":len(current_q),
            "current_area_quantity_ids":[q.quantity_id for q in current_q],
        })

    preserved=sum(r["first_failure_stage"]=="PRESERVED" for r in rows)
    lost=[r for r in rows if r["first_failure_stage"]!="PRESERVED"]
    payload={
        "source_sha256":sha,
        "topology_page_ids":topology_page_ids,
        "prior_sealed_identity_count":len(rows),
        "preserved_identity_count":preserved,
        "lost_identity_count":len(lost),
        "semantic_physical_opening_count":0 if semantic is None else len(semantic.physical_opening_record_ids),
        "opening_binding_count":len(wall_opening.opening_bindings),
        "host_bound_count":sum(1 for x in wall_opening.opening_bindings if x.record_id and x.host_wall_id),
        "canonical_opening_count":len(voids.canonical_openings),
        "opening_area_quantity_count":len(area_quantities),
        "rows":rows,
        "lost_rows":lost,
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"sealed-identity-regression.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(payload,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
