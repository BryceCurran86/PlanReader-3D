from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    _canonical_line,
    _point_close,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_migration_contracts import EvidenceResolutionStatus

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"

def endpoints(record):
    line=tuple(float(v) for v in record.geometry)
    if len(line)!=4:
        return None
    return ((line[0],line[1]),(line[2],line[3]))

def bridge_ids(records):
    rows=[]
    for record in records:
        ep=endpoints(record)
        if ep is None:
            continue
        touched=[]
        for point in ep:
            hit=False
            for other in records:
                if other.observation_id==record.observation_id:
                    continue
                oep=endpoints(other)
                if oep is None:
                    continue
                if any(_point_close(point,candidate) for candidate in oep):
                    hit=True
                    break
            touched.append(hit)
        if touched==[True,True]:
            rows.append(record)
    return tuple(rows)

def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_jamb_pair_groups",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-jamb-pair-groups",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=tuple(str(i) for i in range(1,14)),
    )
    comp=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise SystemExit("current snapshot unavailable")
    visibility=source.authority()

    page_visible=[]
    resolved_by_id={}
    for observation_id in current.visible_observation_ids:
        selector=ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        result=visibility.resolve_visible(selector)
        obs=result.observation
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and obs is not None
            and str(obs.page_id)==PAGE_ID
        ):
            page_visible.append(obs)
            resolved_by_id[str(obs.observation_id)]=obs
    if not page_visible:
        raise SystemExit("no page-3 visible observation")
    seed=page_visible[0]
    structures=comp.physical_opening_authority.visible_candidate_structures(
        ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=seed.observation_id,
        )
    )
    candidates=tuple(
        c for c in structures.candidates
        if c.structural_pattern==JAMB_BOUNDED_TWO_FACE_INTERRUPTION
    )

    groups=defaultdict(list)
    unclassified=[]
    candidate_roles={}
    for candidate in candidates:
        records=tuple(
            resolved_by_id[oid]
            for oid in candidate.source_observation_ids
            if oid in resolved_by_id
        )
        if len(records)!=len(candidate.source_observation_ids):
            unclassified.append({
                "candidate_id":candidate.candidate_id,
                "reason":"support_unresolved",
            })
            continue
        bridges=bridge_ids(records)
        if len(bridges)!=2:
            unclassified.append({
                "candidate_id":candidate.candidate_id,
                "reason":"bridge_role_not_unique",
                "bridge_count":len(bridges),
                "support_count":len(records),
            })
            continue
        key=tuple(sorted(_canonical_line(row) for row in bridges))
        groups[key].append(candidate)
        candidate_roles[candidate.candidate_id]={
            "bridge_observation_ids":tuple(sorted(row.observation_id for row in bridges)),
            "face_observation_ids":tuple(sorted(
                row.observation_id for row in records
                if row.observation_id not in {b.observation_id for b in bridges}
            )),
        }

    group_sizes=Counter(len(rows) for rows in groups.values())
    observation_raw_membership=Counter()
    observation_group_membership=defaultdict(set)
    for candidate in candidates:
        for oid in candidate.source_observation_ids:
            observation_raw_membership[oid]+=1
    for group_index,(key,rows) in enumerate(sorted(groups.items(),key=lambda item:repr(item[0]))):
        gid=f"group:{group_index}"
        support=set()
        bridge_sets=set()
        for candidate in rows:
            support.update(candidate.source_observation_ids)
            role=candidate_roles[candidate.candidate_id]
            bridge_sets.add(tuple(role["bridge_observation_ids"]))
        for oid in support:
            observation_group_membership[oid].add(gid)

    raw_multi=Counter(count for count in observation_raw_membership.values() if count>1)
    group_multi=Counter(
        len(group_ids)
        for group_ids in observation_group_membership.values()
        if len(group_ids)>1
    )
    group_rows=[]
    for key,rows in sorted(groups.items(),key=lambda item:(-len(item[1]),repr(item[0]))):
        bridge_sets=sorted({
            tuple(candidate_roles[c.candidate_id]["bridge_observation_ids"])
            for c in rows
        })
        face_sets=sorted({
            tuple(candidate_roles[c.candidate_id]["face_observation_ids"])
            for c in rows
        })
        group_rows.append({
            "jamb_geometry":key,
            "candidate_count":len(rows),
            "unique_bridge_observation_sets":len(bridge_sets),
            "bridge_observation_sets":bridge_sets,
            "unique_face_support_sets":len(face_sets),
            "candidate_ids":[c.candidate_id for c in rows],
        })

    payload_out={
        "source_sha256":actual,
        "snapshot_id":current.snapshot.snapshot_id,
        "structure_status":structures.status.value,
        "total_candidate_count":len(structures.candidates),
        "two_face_candidate_count":len(candidates),
        "classified_two_face_candidate_count":sum(len(v) for v in groups.values()),
        "unclassified_two_face_candidate_count":len(unclassified),
        "unique_exact_jamb_pair_group_count":len(groups),
        "group_size_distribution":dict(sorted(group_sizes.items())),
        "raw_multi_membership_observation_count":sum(1 for v in observation_raw_membership.values() if v>1),
        "raw_membership_size_distribution":dict(sorted(raw_multi.items())),
        "post_group_multi_membership_observation_count":sum(1 for v in observation_group_membership.values() if len(v)>1),
        "post_group_membership_size_distribution":dict(sorted(group_multi.items())),
        "largest_groups":group_rows[:100],
        "unclassified_examples":unclassified[:100],
    }
    print(json.dumps(payload_out,indent=2,sort_keys=True,default=list))

if __name__=="__main__":
    main()
