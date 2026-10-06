from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import fitz

import pb_opening_host_binding_authority as host
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def state(value):
    return str(getattr(value, "value", value))

def center(points):
    xs=[float(p[0]) for p in points]
    ys=[float(p[1]) for p in points]
    return (sum(xs)/len(xs),sum(ys)/len(ys))

def dist(a,b):
    return math.hypot(float(a[0])-float(b[0]),float(a[1])-float(b[1]))

def main():
    source_bytes=PDF.read_bytes()
    source_sha=hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    with fitz.open(stream=source_bytes,filetype="pdf") as doc:
        indices=tuple(range(int(doc.page_count)))
    scope=source_floor_plan_topology_scope(PDF,indices)
    topology_indices=tuple(scope.topology_page_indices() or ()) if scope else indices
    topology_page_ids=tuple(str(i+1) for i in topology_indices)
    all_page_ids=tuple(str(i+1) for i in indices)
    evidence_page_ids=tuple(p for p in all_page_ids if p not in topology_page_ids)

    source=SourceVisibilityProducer(
        producer_method="diag_lot16_area_ready_wall_candidates",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-area-ready-wall-candidates",
        source_bytes=source_bytes,
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
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None

    ready=[
        opening for opening in voids.canonical_openings
        if str(opening.opening_kind or "").strip().lower() in {"door","window"}
        and opening.area_m2 is not None
        and not str(opening.host_wall_id or "").strip()
    ]
    semantic=wall.semantic_enumeration_result.record
    assert semantic is not None
    physical=wall.physical_opening_authority
    existence_by_id={}
    for observation_id in semantic.representative_observation_ids:
        result=physical.prove_existence(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        if result.existence_record is not None:
            existence_by_id[result.existence_record.record_id]=result.existence_record

    rows=[]
    for target in sorted(ready,key=lambda x:x.physical_opening_id):
        existence=existence_by_id.get(target.physical_opening_id)
        if existence is None:
            continue
        page_id=str(existence.page_id)
        wall_scope=wall.physical_wall_candidate_authority.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                page_id=page_id,
                decision_scope_id=f"wall-source:page-{page_id}",
            )
        )
        geometry=host._opening_geometry(physical,existence)
        if geometry is None:
            continue
        opening_center=(
            geometry.origin[0] + geometry.axis[0]*geometry.length/2.0,
            geometry.origin[1] + geometry.axis[1]*geometry.length/2.0,
        )
        candidates=[]
        for record in wall_scope.records:
            wc=record.wall_candidate
            pts=tuple((float(x),float(y)) for x,y in wc.centerline_pts)
            c=center(pts)
            axis_data=host._candidate_axis_data(record,geometry)
            candidates.append({
                "wall_candidate_id":record.wall_candidate_id,
                "representation":wc.representation,
                "status":state(wc.status),
                "reason_codes":list(wc.reason_codes),
                "centerline_pts":[list(p) for p in pts],
                "center_distance_pt":dist(c,opening_center),
                "candidate_axis_data":None if axis_data is None else {
                    "along_min":axis_data[0],
                    "along_max":axis_data[1],
                    "offset":axis_data[2],
                },
                "identity_usable":bool(record.physical_identity.usable),
                "candidate_identity_id":record.physical_identity.candidate_identity_id,
                "source_primitive_ids":list(record.physical_identity.source_primitive_ids),
                "face_a_segment_ids":list(wc.face_a_segment_ids),
                "face_b_segment_ids":[] if wc.face_b_segment_ids is None else list(wc.face_b_segment_ids),
            })
        candidates.sort(key=lambda x:(x["center_distance_pt"],x["wall_candidate_id"]))
        rows.append({
            "physical_opening_id":target.physical_opening_id,
            "opening_kind":target.opening_kind,
            "area_m2":target.area_m2,
            "area_basis":target.area_basis,
            "structural_pattern":target.structural_pattern,
            "aperture_bbox_pt":existence.aperture_bbox_pt,
            "opening_geometry":{
                "origin":geometry.origin,
                "axis":geometry.axis,
                "normal":geometry.normal,
                "length":geometry.length,
                "thickness":geometry.thickness,
                "center":opening_center,
            },
            "wall_scope_record_count":len(wall_scope.records),
            "nearby_candidates":candidates[:30],
            "parallel_candidates":[c for c in candidates if c["candidate_axis_data"] is not None][:30],
        })
    print(json.dumps({
        "source_sha256":source_sha,
        "topology_page_ids":list(topology_page_ids),
        "area_ready_unhosted_count":len(ready),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
