from __future__ import annotations

import json
import math
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
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.run_source_closed_project_handoff import _source_page_scopes


PROJECT="au_qld_lot16_power"
PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
PROJECT_DIR=Path("benchmarks/frozen_holdout/full_plan_v2/projects")/PROJECT
SEALED=Path("artifacts/gpt3-lot16-exact")/f"{PROJECT}.json"
OUT=Path("artifacts/gpt3-lot16-exact")
BBOX_TOL_PT=0.75


def bbox_from_observation(obs):
    geometry=tuple(float(v) for v in (getattr(obs,"geometry",()) or ()))
    if len(geometry)==4:
        x0,y0,x1,y1=geometry
        return (min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
    if len(geometry)>=4 and len(geometry)%2==0:
        xs=geometry[0::2]
        ys=geometry[1::2]
        return (min(xs),min(ys),max(xs),max(ys))
    return None


def union_bbox(boxes):
    xs0=[b[0] for b in boxes]; ys0=[b[1] for b in boxes]
    xs1=[b[2] for b in boxes]; ys1=[b[3] for b in boxes]
    return (min(xs0),min(ys0),max(xs1),max(ys1))


def bbox_delta(a,b):
    return max(abs(float(x)-float(y)) for x,y in zip(a,b))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sealed=json.loads(SEALED.read_text(encoding="utf-8"))
    sealed_opening_refs={
        tuple(row.get("object_identity_refs") or ()):row
        for row in sealed.get("quantities",())
        if row.get("family")=="opening_area"
        and not row.get("abstained",False)
    }

    takeoff=json.loads((PROJECT_DIR/"reference_takeoff.json").read_text(encoding="utf-8"))
    item_by_object_ref={}
    for item in takeoff.get("items",()):
        if not item.get("denominator_eligible",False):
            continue
        for ref in item.get("expected_object_refs",()):
            item_by_object_ref[str(ref)]=str(item["item_id"])

    truth=json.loads((PROJECT_DIR/"reference_truth_draft.json").read_text(encoding="utf-8"))
    frozen=[]
    for row in truth.get("verified_physical_candidates",()):
        attrs=row.get("attributes") or {}
        bbox=attrs.get("source_bbox_pdf_pt")
        object_ref=str(row.get("object_ref") or "")
        if not object_ref or not isinstance(bbox,list) or len(bbox)!=4:
            continue
        if object_ref not in item_by_object_ref:
            continue
        frozen.append({
            "object_ref":object_ref,
            "benchmark_item_id":item_by_object_ref[object_ref],
            "bbox":tuple(float(v) for v in bbox),
        })

    payload=PDF.read_bytes()
    source_sha=sealed["source_sha256s"][0]
    topology,support,page_count=_source_page_scopes(PDF)
    # Exact parity with family_group="all" handoff after #1732:
    # decode the full source universe while restricting topology minting.
    execution=tuple(range(page_count))
    page_ids=tuple(str(i+1) for i in execution)
    topology_ids=tuple(str(i+1) for i in topology)
    evidence_ids=tuple(p for p in page_ids if p not in topology_ids)

    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{source_sha[:32]}",
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
    canonical={o.physical_opening_id:o for o in voids.canonical_openings}
    current=source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    if current is None:
        raise SystemExit("current source snapshot unavailable after opening composition")

    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")
    physical=wall.physical_opening_authority
    selectors={}
    for observation_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result=physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.existence_record is not None
        ):
            selectors[result.existence_record.record_id]=selector

    visibility=source.authority()
    labels=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    production=[]
    for refs,row in sealed_opening_refs.items():
        if len(refs)!=1:
            continue
        pid=str(refs[0])
        selector=selectors.get(pid)
        if selector is None or pid not in canonical:
            continue
        result=labels.publish_scope(selector)
        evidence=result.evidence
        if evidence is None:
            continue
        boxes=[]
        for observation_id in evidence.source_text_observation_ids:
            resolved=visibility.resolve_visible(ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            ))
            if resolved.observation is None:
                continue
            box=bbox_from_observation(resolved.observation)
            if box is not None:
                boxes.append(box)
        if not boxes:
            continue
        production.append({
            "physical_opening_id":pid,
            "quantity_id":row["quantity_id"],
            "family":row["family"],
            "bbox":union_bbox(boxes),
        })

    bindings=[]
    audit=[]
    used_items=set()
    for prod in production:
        matches=[
            cand for cand in frozen
            if bbox_delta(prod["bbox"],cand["bbox"]) <= BBOX_TOL_PT
        ]
        status="UNMATCHED"
        if len(matches)==1 and matches[0]["benchmark_item_id"] not in used_items:
            match=matches[0]
            used_items.add(match["benchmark_item_id"])
            bindings.append({
                "benchmark_item_id":match["benchmark_item_id"],
                "production_object_identity_refs":[prod["physical_opening_id"]],
                "production_family":"opening_area",
            })
            status="BOUND"
        elif len(matches)>1:
            status="AMBIGUOUS"
        audit.append({
            **prod,
            "status":status,
            "matches":[
                {
                    "benchmark_item_id":m["benchmark_item_id"],
                    "object_ref":m["object_ref"],
                    "frozen_bbox":list(m["bbox"]),
                    "max_bbox_delta_pt":bbox_delta(prod["bbox"],m["bbox"]),
                }
                for m in matches
            ],
        })

    identity_map={
        "schema_version":"1.0.0",
        "project_id":PROJECT,
        "source_sha256s":sealed["source_sha256s"],
        "bindings":bindings,
    }
    (OUT/"lot16.identity-map.json").write_text(
        json.dumps(identity_map,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    (OUT/"lot16.identity-audit.json").write_text(
        json.dumps({
            "bbox_tolerance_pt":BBOX_TOL_PT,
            "sealed_opening_quantity_count":len(sealed_opening_refs),
            "production_bbox_count":len(production),
            "frozen_bbox_candidate_count":len(frozen),
            "binding_count":len(bindings),
            "audit":audit,
        },indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "sealed_opening_quantity_count":len(sealed_opening_refs),
        "production_bbox_count":len(production),
        "binding_count":len(bindings),
        "audit":audit,
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
