from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import fitz

import pb_opening_host_binding_authority as host
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def state(v):
    return str(getattr(v,"value",v))

def bbox_distance(a,b):
    ax0,ay0,ax1,ay1=a
    bx0,by0,bx1,by1=b
    dx=max(bx0-ax1,ax0-bx1,0.0)
    dy=max(by0-ay1,ay0-by1,0.0)
    return math.hypot(dx,dy)

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    with fitz.open(stream=data,filetype="pdf") as doc:
        indices=tuple(range(int(doc.page_count)))
    scope=source_floor_plan_topology_scope(PDF,indices)
    topology=tuple(scope.topology_page_indices() or ()) if scope else indices
    all_ids=tuple(str(i+1) for i in indices)
    topology_ids=tuple(str(i+1) for i in topology)
    evidence_ids=tuple(p for p in all_ids if p not in topology_ids)

    source=SourceVisibilityProducer(
        producer_method="diag_lot16_next_area_ready_host",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-next-area-ready-host",
        source_bytes=data,
        source_locator=str(PDF),
        page_ids=all_ids,
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

    targets={
        o.physical_opening_id:o
        for o in voids.canonical_openings
        if str(o.opening_kind or "").lower() in {"door","window"}
        and o.area_m2 is not None
        and not str(o.host_wall_id or "").strip()
    }
    semantic=wall.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic enumeration unavailable")
    physical=wall.physical_opening_authority
    visibility=source.authority()
    existence={}
    for observation_id in semantic.representative_observation_ids:
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        res=physical.prove_existence(selector)
        if res.status is EvidenceResolutionStatus.CORROBORATED and res.existence_record is not None:
            existence[res.existence_record.record_id]=res.existence_record

    rows=[]
    for pid,target in sorted(targets.items()):
        record=existence.get(pid)
        if record is None or not record.aperture_bbox_pt:
            continue
        page_id=str(record.page_id)
        wall_scope=wall.physical_wall_candidate_authority.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                page_id=page_id,
                decision_scope_id=f"wall-source:page-{page_id}",
            )
        )
        opening=host._opening_geometry(physical,record)
        supports=[]
        for support_id in record.source_observation_ids:
            sel=ObservationSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                observation_id=support_id,
            )
            rr=visibility.resolve_raster_opening_primitive(sel)
            obs=rr.observation
            supports.append({
                "observation_id":support_id,
                "status":state(rr.status),
                "kind":None if obs is None else obs.observation_kind,
                "source_primitive_ref":None if obs is None else obs.source_primitive_ref,
                "geometry":None if obs is None else list(obs.geometry),
                "derivation_parent_ids":[] if obs is None else list(obs.derivation_parent_ids),
            })

        nearby=[]
        aperture=tuple(float(v) for v in record.aperture_bbox_pt)
        for wr in wall_scope.records:
            pts=tuple((float(x),float(y)) for x,y in wr.wall_candidate.centerline_pts)
            if not pts:
                continue
            xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
            wb=(min(xs),min(ys),max(xs),max(ys))
            dist=bbox_distance(aperture,wb)
            if dist > 24.0:
                continue
            nearby.append({
                "wall_candidate_id":wr.wall_candidate_id,
                "candidate_identity_id":wr.physical_identity.candidate_identity_id,
                "identity_usable":wr.physical_identity.usable,
                "source_primitive_ids":list(wr.physical_identity.source_primitive_ids),
                "centerline_pts":[list(p) for p in pts],
                "reason_codes":list(wr.wall_candidate.reason_codes),
                "bbox_distance_pt":dist,
                "candidate_axis_data":(
                    None if opening is None
                    else host._candidate_axis_data(wr,opening)
                ),
                "equivalence_group":list(host._equivalence_group_for(
                    wall_scope.equivalence,wr.wall_candidate_id
                )) if wall_scope.equivalence is not None else [],
            })
        nearby.sort(key=lambda x:(x["bbox_distance_pt"],x["wall_candidate_id"]))
        rows.append({
            "physical_opening_id":pid,
            "opening_kind":target.opening_kind,
            "area_m2":target.area_m2,
            "area_basis":target.area_basis,
            "aperture_bbox_pt":list(aperture),
            "opening_geometry":None if opening is None else {
                "origin":opening.origin,
                "axis":opening.axis,
                "normal":opening.normal,
                "length":opening.length,
                "thickness":opening.thickness,
            },
            "g17_supports":supports,
            "nearby_w4_candidates":nearby,
        })
    print(json.dumps({
        "source_sha256":actual,
        "remaining_area_ready_unhosted_count":len(rows),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
