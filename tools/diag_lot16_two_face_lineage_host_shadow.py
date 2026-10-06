from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import JAMB_BOUNDED_TWO_FACE_INTERRUPTION
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector, SourceObservationRecord
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def state(value):
    return str(getattr(value,"value",value))


def positive_gap_pairs(records):
    pairs=[]
    for i,first_record in enumerate(records):
        first=host._line(first_record)
        if first is None:
            return ()
        for second_record in records[i+1:]:
            second=host._line(second_record)
            if second is None or not host._collinear(first,second):
                continue
            axis=host._canonical_unit(first)
            if axis is None:
                continue
            a=host._scalar_interval(first,axis)
            b=host._scalar_interval(second,axis)
            left_iv,right_iv=(a,b) if a[0] <= b[0] else (b,a)
            if right_iv[0]-left_iv[1] > host._COORD_TOL:
                pairs.append((first_record,second_record,axis,left_iv[1],right_iv[0]))
    return tuple(pairs)


def shadow_two_face_lineage(opening_records, wall_records, equivalence):
    pairs=positive_gap_pairs(opening_records)
    if len(pairs) != 2:
        return {"status":"abstained","reason":"two_face_gap_pair_count","pair_count":len(pairs)}

    # Require same aperture station on parallel, physically distinct axes.
    first,second=pairs
    axis_a=first[2]
    axis_b=second[2]
    if abs(abs(axis_a[0]*axis_b[0]+axis_a[1]*axis_b[1])-1.0) > host._COORD_TOL:
        return {"status":"abstained","reason":"gap_axes_not_parallel"}
    if abs(first[3]-second[3]) > host._COORD_TOL or abs(first[4]-second[4]) > host._COORD_TOL:
        return {"status":"abstained","reason":"gap_stations_differ"}

    face_records=(first[0],first[1],second[0],second[1])
    if len({r.observation_id for r in face_records}) != 4:
        return {"status":"abstained","reason":"face_roles_not_distinct"}

    raw_ids=[]
    for record in face_records:
        raw=host._raw_source_primitive_id(record)
        if raw is None:
            return {"status":"abstained","reason":"raw_source_lineage_unavailable"}
        raw_ids.append(raw)
    if len(set(raw_ids)) != 4:
        return {"status":"abstained","reason":"raw_source_roles_not_distinct"}

    ambiguous=set(equivalence.ambiguous_wall_ids)
    group_lookup=host._equivalence_group_lookup(equivalence)
    role_members=[]
    role_audit=[]
    for raw_id in raw_ids:
        owners=tuple(
            record for record in wall_records
            if record.physical_identity.usable
            and raw_id in set(record.physical_identity.source_primitive_ids)
        )
        role_audit.append({
            "raw_id":raw_id,
            "owner_ids":[r.wall_candidate_id for r in owners],
        })
        if not owners:
            return {
                "status":"abstained","reason":"lineage_unmapped",
                "roles":role_audit,
            }
        if any(r.wall_candidate_id in ambiguous for r in owners):
            return {
                "status":"conflict","reason":"lineage_ambiguous_equivalence",
                "roles":role_audit,
            }
        by_group={}
        for record in owners:
            group=host._equivalence_group_for(
                equivalence,record.wall_candidate_id,group_lookup=group_lookup
            )
            by_group.setdefault(group,[]).append(record)
        if len(by_group) != 1:
            return {
                "status":"conflict","reason":"lineage_multiple_groups",
                "roles":role_audit,
            }
        group,members=next(iter(by_group.items()))
        chosen=sorted(members,key=lambda r:r.wall_candidate_id)[0]
        role_members.append((chosen,group))

    member_ids=tuple(sorted({r.wall_candidate_id for r,_g in role_members}))
    identity_ids=tuple(sorted({
        str(r.physical_identity.candidate_identity_id)
        for r,_g in role_members
        if r.physical_identity.candidate_identity_id
    }))
    groups=tuple(sorted({tuple(sorted(g)) for _r,g in role_members}))
    if len(member_ids) < 2 or not identity_ids:
        return {"status":"abstained","reason":"resolved_lineage_identity_unavailable","roles":role_audit}

    return {
        "status":"corroborated",
        "reason":"two_face_source_lineage_host_resolved",
        "member_ids":member_ids,
        "identity_ids":identity_ids,
        "groups":groups,
        "roles":role_audit,
    }


def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_lot16_two_face_lineage_shadow",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-lot16-two-face-lineage-shadow",
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
    visibility=physical.source_visibility_authority()
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
            if opening is None or opening.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION:
                continue
            source_records=[]
            ok=True
            for source_id in opening.source_observation_ids:
                result=visibility.resolve_visible(ObservationSelector(
                    document_id=opening.document_id,
                    revision_id=opening.revision_id,
                    source_sha256=opening.source_sha256,
                    snapshot_id=opening.snapshot_id,
                    observation_id=source_id,
                ))
                if result.status is not EvidenceResolutionStatus.CORROBORATED or result.observation is None:
                    ok=False
                    break
                source_records.append(result.observation)
            if not ok:
                shadow={"status":"abstained","reason":"source_observation_unavailable"}
            else:
                shadow=shadow_two_face_lineage(
                    tuple(source_records),wall_scope.records,wall_scope.equivalence
                )
            trace=next(
                (x for x in composition.opening_bindings
                 if x.opening_identity_id==opening.record_id),
                None,
            )
            rows.append({
                "opening_id":opening.record_id,
                "current_binding_status":None if trace is None else state(trace.status),
                "current_binding_reasons":[] if trace is None else list(trace.reason_codes),
                "current_host_wall_id":None if trace is None else trace.host_wall_id,
                "shadow":shadow,
            })

    shadow_counts=Counter(r["shadow"]["status"] for r in rows)
    reasons=Counter(r["shadow"]["reason"] for r in rows)
    recoverable=[
        r for r in rows
        if not r["current_host_wall_id"] and r["shadow"]["status"]=="corroborated"
    ]
    conflicts=[
        r for r in rows
        if r["shadow"]["status"]=="conflict"
    ]
    report={
        "jamb_bounded_opening_count":len(rows),
        "current_bound_count":sum(bool(r["current_host_wall_id"]) for r in rows),
        "shadow_status_counts":dict(shadow_counts),
        "shadow_reason_counts":dict(reasons),
        "newly_recoverable_count":len(recoverable),
        "shadow_conflict_count":len(conflicts),
        "recoverable":recoverable,
        "rows":rows,
    }
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
