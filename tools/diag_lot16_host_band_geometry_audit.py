from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def state(value):
    return str(getattr(value,"value",value))


def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_lot16_host_band_geometry_audit",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-host-band-geometry-audit",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise SystemExit("current snapshot unavailable")

    wall_scope=composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=f"wall-source:page-{PAGE_ID}",
        )
    )
    if wall_scope.equivalence is None:
        raise SystemExit("wall equivalence unavailable")

    physical=composition.physical_opening_authority
    semantic=composition.semantic_enumeration_result.record
    rows=[]
    if semantic is not None:
        for observation_id in semantic.representative_observation_ids:
            selector=ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
            existence=physical.prove_existence(selector)
            opening=existence.existence_record
            if opening is None:
                rows.append({
                    "observation_id":observation_id,
                    "existence_status":state(existence.status),
                    "existence_reason_codes":list(existence.reason_codes),
                    "opening_id":None,
                })
                continue

            geometry=host._opening_geometry(physical,opening)
            trace=next(
                (x for x in composition.opening_bindings
                 if x.opening_identity_id==opening.record_id),
                None,
            )
            row={
                "observation_id":observation_id,
                "opening_id":opening.record_id,
                "pattern":opening.structural_pattern,
                "binding_status":None if trace is None else state(trace.status),
                "binding_reason_codes":[] if trace is None else list(trace.reason_codes),
                "host_wall_id":None if trace is None else trace.host_wall_id,
                "geometry_available":geometry is not None,
            }
            if geometry is None:
                rows.append(row)
                continue

            edge_tol=max(0.5,min(2.0,geometry.length*0.02))
            axis_tol=max(0.5,geometry.thickness*0.05)
            thickness_tol=max(0.75,geometry.thickness*0.15)
            proximity_limit=max(24.0,geometry.thickness*3.0)

            axis_rows=[]
            left=[]
            right=[]
            spanning=[]
            for record in wall_scope.records:
                data=host._candidate_axis_data(record,geometry)
                if data is None:
                    continue
                along_min,along_max,offset=data
                item={
                    "wall_candidate_id":record.wall_candidate_id,
                    "along_min":along_min,
                    "along_max":along_max,
                    "offset":offset,
                    "identity_usable":bool(record.physical_identity.usable),
                    "candidate_identity_id":record.physical_identity.candidate_identity_id,
                }
                axis_rows.append(item)
                if along_min < -edge_tol and abs(along_max) <= edge_tol:
                    left.append(item)
                if along_max > geometry.length + edge_tol and abs(along_min-geometry.length) <= edge_tol:
                    right.append(item)
                if along_min < -edge_tol and along_max > geometry.length + edge_tol:
                    spanning.append(item)

            generic_lineage=host._resolve_generic_gap_lineage_host(
                physical,opening,wall_scope.records,wall_scope.equivalence
            )
            direct=host._resolve_host_bands(
                wall_scope.records,geometry,wall_scope.equivalence
            )
            raster_whole=host._resolve_raster_whole_wall_host(
                wall_scope.records,geometry,wall_scope.equivalence
            )
            raster_split=host._resolve_raster_split_centerline_host(
                wall_scope.records,geometry,wall_scope.equivalence
            )

            row.update({
                "geometry":{
                    "origin":list(geometry.origin),
                    "axis":list(geometry.axis),
                    "normal":list(geometry.normal),
                    "length":geometry.length,
                    "thickness":geometry.thickness,
                },
                "thresholds":{
                    "edge_tol":edge_tol,
                    "axis_tol":axis_tol,
                    "thickness_tol":thickness_tol,
                    "proximity_limit":proximity_limit,
                },
                "axis_compatible_count":len(axis_rows),
                "left_edge_candidate_count":len(left),
                "right_edge_candidate_count":len(right),
                "spanning_candidate_count":len(spanning),
                "axis_offsets":sorted(round(float(x["offset"]),6) for x in axis_rows),
                "left_offsets":sorted(round(float(x["offset"]),6) for x in left),
                "right_offsets":sorted(round(float(x["offset"]),6) for x in right),
                "spanning_offsets":sorted(round(float(x["offset"]),6) for x in spanning),
                "generic_lineage":{
                    "available":generic_lineage is not None,
                    "status":None if generic_lineage is None else state(generic_lineage.status),
                    "band_count":0 if generic_lineage is None else len(generic_lineage.bands),
                    "reason_codes":[] if generic_lineage is None else list(generic_lineage.reason_codes),
                },
                "direct_host_bands":{
                    "status":state(direct.status),
                    "band_count":len(direct.bands),
                    "reason_codes":list(direct.reason_codes),
                },
                "raster_whole_wall":{
                    "status":state(raster_whole.status),
                    "band_count":len(raster_whole.bands),
                    "reason_codes":list(raster_whole.reason_codes),
                },
                "raster_split_centerline":{
                    "status":state(raster_split.status),
                    "band_count":len(raster_split.bands),
                    "reason_codes":list(raster_split.reason_codes),
                },
                "left_candidates":left[:12],
                "right_candidates":right[:12],
                "spanning_candidates":spanning[:12],
            })
            rows.append(row)

    unresolved=[r for r in rows if not r.get("host_wall_id")]
    summary={
        "opening_count":len(rows),
        "host_bound_count":sum(bool(r.get("host_wall_id")) for r in rows),
        "unbound_count":len(unresolved),
        "unbound_patterns":dict(Counter(str(r.get("pattern")) for r in unresolved)),
        "unbound_binding_reasons":dict(Counter(
            reason
            for r in unresolved
            for reason in r.get("binding_reason_codes",[])
        )),
        "unbound_geometry_available":sum(bool(r.get("geometry_available")) for r in unresolved),
        "unbound_axis_compatible_zero":sum(
            int(r.get("axis_compatible_count",0)==0) for r in unresolved if r.get("geometry_available")
        ),
        "unbound_left_zero":sum(
            int(r.get("left_edge_candidate_count",0)==0) for r in unresolved if r.get("geometry_available")
        ),
        "unbound_right_zero":sum(
            int(r.get("right_edge_candidate_count",0)==0) for r in unresolved if r.get("geometry_available")
        ),
        "unbound_spanning_positive":sum(
            int(r.get("spanning_candidate_count",0)>0) for r in unresolved if r.get("geometry_available")
        ),
        "rows":rows,
    }
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
