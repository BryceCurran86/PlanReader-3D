from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import fitz

from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def rect_for_geometry(g):
    if len(g)!=4:
        return None
    x0,y0,x1,y1=(float(v) for v in g)
    return (min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))

def rect_distance(a,b):
    dx=max(0.0,max(a[0],b[0])-min(a[2],b[2]))
    dy=max(0.0,max(a[1],b[1])-min(a[3],b[3]))
    return math.hypot(dx,dy)

def main():
    data=PDF.read_bytes()
    sha=hashlib.sha256(data).hexdigest()
    if sha!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")
    with fitz.open(stream=data,filetype="pdf") as doc:
        indices=tuple(range(int(doc.page_count)))
    scope=source_floor_plan_topology_scope(PDF,indices)
    topology=tuple(scope.topology_page_indices() or ()) if scope else indices
    topology_ids=tuple(str(i+1) for i in topology)
    all_ids=tuple(str(i+1) for i in indices)
    support=tuple(p for p in all_ids if p not in topology_ids)
    source=SourceVisibilityProducer(
        producer_method="diag_lot16_area_ready_source_evidence",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-area-ready-source-evidence",
        source_bytes=data,
        source_locator=str(PDF),
        page_ids=all_ids,
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_ids,
        evidence_page_ids=support,
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None
    ready=[
        x for x in voids.canonical_openings
        if str(x.opening_kind or "").strip().lower() in {"door","window"}
        and x.area_m2 is not None
        and not str(x.host_wall_id or "").strip()
    ]
    physical=wall.physical_opening_authority
    semantic=wall.semantic_enumeration_result.record
    assert semantic is not None
    existence={}
    for observation_id in semantic.representative_observation_ids:
        r=physical.prove_existence(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        if r.existence_record is not None:
            existence[r.existence_record.record_id]=r.existence_record

    visibility=source.authority()
    observations=[]
    for oid in current.visible_observation_ids:
        rr=visibility.resolve_visible(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=oid,
        ))
        if rr.observation is not None:
            observations.append(rr.observation)

    rows=[]
    for target in sorted(ready,key=lambda x:x.physical_opening_id):
        ex=existence.get(target.physical_opening_id)
        if ex is None or ex.aperture_bbox_pt is None:
            continue
        aperture=tuple(float(v) for v in ex.aperture_bbox_pt)
        nearby=[]
        for obs in observations:
            if str(obs.page_id)!=str(ex.page_id):
                continue
            box=rect_for_geometry(obs.geometry)
            if box is None:
                continue
            d=rect_distance(aperture,box)
            if d>12.0:
                continue
            nearby.append({
                "distance_pt":d,
                "observation_id":obs.observation_id,
                "kind":obs.observation_kind,
                "origin_kind":obs.origin_kind,
                "primitive_ref":obs.source_primitive_ref,
                "geometry":list(obs.geometry),
                "derivation_parent_ids":list(obs.derivation_parent_ids),
                "producer_method":obs.producer_method,
                "producer_version":obs.producer_version,
            })
        nearby.sort(key=lambda x:(x["distance_pt"],x["kind"],x["observation_id"]))
        rows.append({
            "physical_opening_id":target.physical_opening_id,
            "opening_kind":target.opening_kind,
            "area_m2":target.area_m2,
            "structural_pattern":target.structural_pattern,
            "aperture_bbox_pt":list(aperture),
            "nearby_observation_count":len(nearby),
            "nearby_observations":nearby[:120],
        })
    print(json.dumps({
        "source_sha256":sha,
        "topology_page_ids":list(topology_ids),
        "area_ready_unhosted_count":len(ready),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
