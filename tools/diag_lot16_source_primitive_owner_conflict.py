from __future__ import annotations

import hashlib
import json
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

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    with fitz.open(stream=data,filetype="pdf") as doc:
        indices=tuple(range(int(doc.page_count)))
    scope=source_floor_plan_topology_scope(PDF,indices)
    topology=tuple(scope.topology_page_indices() or ()) if scope else indices
    topology_ids=tuple(str(i+1) for i in topology)
    all_ids=tuple(str(i+1) for i in indices)
    support_ids=tuple(x for x in all_ids if x not in topology_ids)

    source=SourceVisibilityProducer(
        producer_method="diag_lot16_source_primitive_owner_conflict",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-source-primitive-owner-conflict",
        source_bytes=data,
        source_locator=str(PDF),
        page_ids=all_ids,
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_ids,
        evidence_page_ids=support_ids,
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None

    remaining=[
        o for o in voids.canonical_openings
        if str(o.opening_kind or "").lower() in {"door","window"}
        and o.area_m2 is not None
        and not str(o.host_wall_id or "").strip()
    ]
    semantic=wall.semantic_enumeration_result.record
    assert semantic is not None
    physical=wall.physical_opening_authority
    existence={}
    for observation_id in semantic.representative_observation_ids:
        res=physical.prove_existence(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        if res.status is EvidenceResolutionStatus.CORROBORATED and res.existence_record is not None:
            existence[res.existence_record.record_id]=res.existence_record

    rows=[]
    for target in sorted(remaining,key=lambda x:x.physical_opening_id):
        opening=existence.get(target.physical_opening_id)
        if opening is None:
            continue
        page_id=str(opening.page_id)
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
        geometry=host._opening_geometry(physical,opening)
        if geometry is None or wall_scope.equivalence is None:
            continue
        lines=host._authenticated_raster_source_lines(
            physical, opening, wall_scope.source_observation_ids
        )
        edge_tol=max(0.5,min(2.0,geometry.length*0.02))
        candidate_rows=[]
        primitive_to_owners={}
        for record in wall_scope.records:
            identity=record.physical_identity
            if not identity.usable or not identity.candidate_identity_id:
                continue
            qualifying=[]
            for primitive_id in identity.source_primitive_ids:
                line=lines.get(str(primitive_id))
                if line is None:
                    continue
                data=host._source_line_axis_data(line,geometry)
                if data is None:
                    continue
                along_min,along_max,offset=data
                if (
                    along_min >= -edge_tol
                    or along_max <= geometry.length + edge_tol
                    or abs(offset) > host._RASTER_WHOLE_WALL_CENTER_TOL_PT + host._COORD_TOL
                ):
                    continue
                qualifying.append({
                    "primitive_id":str(primitive_id),
                    "line":list(line),
                    "along_min":along_min,
                    "along_max":along_max,
                    "offset":offset,
                })
                primitive_to_owners.setdefault(str(primitive_id),[]).append(record.wall_candidate_id)
            if qualifying:
                candidate_rows.append({
                    "wall_candidate_id":record.wall_candidate_id,
                    "candidate_identity_id":identity.candidate_identity_id,
                    "all_source_primitive_ids":list(identity.source_primitive_ids),
                    "qualifying_primitives":qualifying,
                    "centerline_pts":[list(p) for p in record.wall_candidate.centerline_pts],
                    "reason_codes":list(record.wall_candidate.reason_codes),
                    "equivalence_group":list(host._equivalence_group_for(
                        wall_scope.equivalence,record.wall_candidate_id
                    )),
                })
        pair_lookup=host._pair_lookup(wall_scope.equivalence)
        pair_rows=[]
        ids=[r["wall_candidate_id"] for r in candidate_rows]
        for i,left in enumerate(ids):
            for right in ids[i+1:]:
                pair_rows.append({
                    "left":left,
                    "right":right,
                    "classification":None if pair_lookup.get(tuple(sorted((left,right)))) is None else pair_lookup[tuple(sorted((left,right)))].value,
                    "shared_qualifying_primitives":sorted(
                        set(next(r["qualifying_primitives"] for r in candidate_rows if r["wall_candidate_id"]==left)[k]["primitive_id"] for k in range(len(next(r["qualifying_primitives"] for r in candidate_rows if r["wall_candidate_id"]==left))))
                        & set(next(r["qualifying_primitives"] for r in candidate_rows if r["wall_candidate_id"]==right)[k]["primitive_id"] for k in range(len(next(r["qualifying_primitives"] for r in candidate_rows if r["wall_candidate_id"]==right))))
                    )
                })
        resolution=host._resolve_raster_source_primitive_host_from_lines(
            wall_scope.records,geometry,wall_scope.equivalence,lines
        )
        rows.append({
            "physical_opening_id":target.physical_opening_id,
            "opening_kind":target.opening_kind,
            "area_m2":target.area_m2,
            "aperture_bbox_pt":opening.aperture_bbox_pt,
            "opening_geometry":{
                "origin":geometry.origin,
                "axis":geometry.axis,
                "normal":geometry.normal,
                "length":geometry.length,
                "thickness":geometry.thickness,
            },
            "resolver_status":state(resolution.status),
            "resolver_reason_codes":list(resolution.reason_codes),
            "resolver_band_count":len(resolution.bands),
            "qualifying_candidate_count":len(candidate_rows),
            "qualifying_candidates":candidate_rows,
            "primitive_to_owners":primitive_to_owners,
            "pair_relations":pair_rows,
        })
    print(json.dumps({
        "source_sha256":actual,
        "remaining_area_ready_unhosted_count":len(rows),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
