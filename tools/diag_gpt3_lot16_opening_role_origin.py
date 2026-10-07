from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def raw_id(record):
    ref=str(getattr(record,"source_primitive_ref","") or "")
    return ref[len("visible:"):] if ref.startswith("visible:") else None


def bbox_of_line(geometry):
    try:
        x0,y0,x1,y1=(float(v) for v in geometry)
    except Exception:
        return None
    return (min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))


def bbox_inside(inner,outer,tol=0.5):
    if inner is None:
        return False
    ix0,iy0,ix1,iy1=inner
    ox0,oy0,ox1,oy1=outer
    return (
        ix0 >= ox0-tol and iy0 >= oy0-tol
        and ix1 <= ox1+tol and iy1 <= oy1+tol
    )


def main():
    source_bytes=PDF.read_bytes()
    sha=hashlib.sha256(source_bytes).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_opening_role_origin",
        producer_version="1",
    )
    initial=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-opening-role-origin",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    comp=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    if current is None:
        raise SystemExit("current snapshot unavailable")
    physical=comp.physical_opening_authority
    visibility=physical.source_visibility_authority()
    if visibility is None:
        raise SystemExit("visibility unavailable")

    seed=current.visible_observation_ids[0]
    candidates=physical.visible_candidate_structures(
        ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=seed,
        )
    ).candidates

    wall_scope=comp.physical_wall_candidate_authority.resolve_scope(
        __import__("pb_physical_wall_candidate_authority").PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=f"wall-source:page-{PAGE_ID}",
        )
    )
    wall_records=tuple(wall_scope.records)
    wall_owner=defaultdict(list)
    for wall in wall_records:
        for rid in wall.physical_identity.source_primitive_ids:
            wall_owner[str(rid)].append(wall.wall_candidate_id)

    placements=source.raster_opening_image_placements(
        current.revision.revision_id,
        PAGE_ID,
    )
    placement_boxes=[
        tuple(float(v) for v in p.bbox_pt)
        for p in placements
    ]

    observation_cache={}
    def obs(observation_id):
        if observation_id in observation_cache:
            return observation_cache[observation_id]
        result=visibility.resolve_visible(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation_cache[observation_id]=result.observation
        return result.observation

    rows=[]
    pattern_counts=Counter()
    owner_state_counts=Counter()
    origin_counts=Counter()
    placement_counts=Counter()
    raw_prefix_counts=Counter()

    for candidate in candidates:
        pattern=str(candidate.structural_pattern)
        pattern_counts[pattern]+=1
        support=[]
        owned_roles=0
        unowned_roles=0
        raster_roles=0
        native_roles=0
        inside_image_roles=0
        for oid in candidate.source_observation_ids:
            record=obs(str(oid))
            if record is None:
                continue
            rid=raw_id(record)
            owners=() if rid is None else tuple(sorted(wall_owner.get(rid,())))
            kind=str(record.observation_kind)
            origin=str(record.origin_kind)
            ref=str(record.source_primitive_ref)
            if owners:
                owned_roles+=1
            else:
                unowned_roles+=1
            if "raster" in origin.lower() or "raster" in kind.lower() or "raster" in ref.lower():
                raster_roles+=1
            else:
                native_roles+=1
            bb=bbox_of_line(record.geometry)
            inside=any(bbox_inside(bb,pb) for pb in placement_boxes)
            if inside:
                inside_image_roles+=1
            if rid:
                raw_prefix_counts[rid.split(":",1)[0]]+=1
            origin_counts[origin]+=1
            placement_counts["inside_image" if inside else "outside_image"]+=1
            support.append({
                "observation_id":str(oid),
                "raw_id":rid,
                "owner_ids":list(owners),
                "observation_kind":kind,
                "origin_kind":origin,
                "source_primitive_ref":ref,
                "geometry":list(record.geometry),
                "inside_embedded_image_bbox":inside,
            })
        state=(
            "all_owned" if support and unowned_roles==0
            else "none_owned" if support and owned_roles==0
            else "partially_owned"
        )
        owner_state_counts[(pattern,state)]+=1
        if pattern=="jamb_bounded_two_face_interruption":
            rows.append({
                "candidate_id":candidate.candidate_id,
                "pattern":pattern,
                "support_count":len(support),
                "owned_role_count":owned_roles,
                "unowned_role_count":unowned_roles,
                "raster_role_count":raster_roles,
                "native_role_count":native_roles,
                "inside_embedded_image_role_count":inside_image_roles,
                "owner_state":state,
                "support":support,
            })

    payload={
        "source_sha256":sha,
        "candidate_count":len(candidates),
        "wall_candidate_count":len(wall_records),
        "embedded_image_placement_count":len(placement_boxes),
        "pattern_counts":dict(pattern_counts.most_common()),
        "owner_state_counts":{
            f"{pattern} | {state}":count
            for (pattern,state),count in owner_state_counts.most_common()
        },
        "origin_counts":dict(origin_counts.most_common()),
        "placement_counts":dict(placement_counts.most_common()),
        "raw_prefix_counts":dict(raw_prefix_counts.most_common()),
        "two_face_rows":rows,
    }
    print(json.dumps(payload,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
