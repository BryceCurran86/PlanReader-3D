from __future__ import annotations

from collections import Counter
import hashlib, json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import JAMB_BOUNDED_TWO_FACE_INTERRUPTION
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector, _opening_raw_relation_sets
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import NATIVE_PDF_VISIBLE_SEGMENT, RASTER_PDF_VISIBLE_SEGMENT, SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"
SCOPE_ID="wall-source:page-3"

def raw_id(obs):
    ref=str(obs.source_primitive_ref or "")
    if obs.observation_kind==NATIVE_PDF_VISIBLE_SEGMENT and ref.startswith("visible:segment:"):
        return ref[len("visible:segment:"):]
    if obs.observation_kind==RASTER_PDF_VISIBLE_SEGMENT and ref.startswith("visible:"):
        return ref[len("visible:"):]
    return None

def main():
    data=PDF.read_bytes()
    assert hashlib.sha256(data).hexdigest()==EXPECTED_SHA
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{EXPECTED_SHA[:32]}",
        source_bytes=data,
        source_locator="memory://lot16.pdf",
        page_ids=(PAGE_ID,),
    )
    comp=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    assert current is not None

    wall=comp.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=SCOPE_ID,
        )
    )
    eq=wall.equivalence
    assert eq is not None
    records=tuple(wall.records)
    ambiguous=set(eq.ambiguous_wall_ids)
    pair_lookup={
        tuple(sorted((str(a),str(b)))):str(c)
        for a,b,c in eq.pair_classifications
    }
    group_lookup={}
    for group in eq.equivalence_groups:
        g=tuple(sorted(group))
        for wid in g:
            group_lookup.setdefault(wid,g)

    owners={}
    for record in records:
        for rid in record.physical_identity.source_primitive_ids:
            owners.setdefault(str(rid),[]).append(record.wall_candidate_id)

    visibility=comp.physical_opening_authority.source_visibility_authority()
    rows=[]
    counts=Counter()
    for trace in comp.opening_bindings:
        result=comp.physical_opening_authority.prove_existence(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        ))
        opening=result.existence_record
        if opening is None or opening.structural_pattern!=JAMB_BOUNDED_TWO_FACE_INTERRUPTION:
            continue
        raw_lines={}
        for oid in opening.source_observation_ids:
            resolved=visibility.resolve_visible(ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=oid,
            ))
            if resolved.observation is None:
                continue
            rid=raw_id(resolved.observation)
            if rid:
                raw_lines[rid]=tuple(float(v) for v in resolved.observation.geometry)
        relations=_opening_raw_relation_sets(raw_lines)
        same_pairs=sorted(
            pair for pair,classes in relations.items()
            if {str(getattr(c,"value",c)) for c in classes}=={"same_physical_wall"}
        )
        pair_rows=[]
        opening_all_four=True
        opening_local_same=True
        opening_any_ambient_ambiguous=False
        for left_raw,right_raw in same_pairs:
            left_owners=sorted(set(owners.get(left_raw,())))
            right_owners=sorted(set(owners.get(right_raw,())))
            if len(left_owners)!=1 or len(right_owners)!=1:
                opening_all_four=False
                pair_rows.append({
                    "raw_pair":[left_raw,right_raw],
                    "left_owner_ids":left_owners,
                    "right_owner_ids":right_owners,
                    "pair_classification":None,
                })
                continue
            left,right=left_owners[0],right_owners[0]
            cls=pair_lookup.get(tuple(sorted((left,right))))
            same=(cls=="same_physical_wall")
            if not same:
                opening_local_same=False
            ambient=(left in ambiguous or right in ambiguous)
            opening_any_ambient_ambiguous |= ambient
            pair_rows.append({
                "raw_pair":[left_raw,right_raw],
                "left_owner_ids":left_owners,
                "right_owner_ids":right_owners,
                "owner_pair":[left,right],
                "pair_classification":cls,
                "left_equivalence_group":list(group_lookup.get(left,(left,))),
                "right_equivalence_group":list(group_lookup.get(right,(right,))),
                "left_globally_ambiguous":left in ambiguous,
                "right_globally_ambiguous":right in ambiguous,
                "left_blockers":list(eq.blockers_for(left)),
                "right_blockers":list(eq.blockers_for(right)),
            })
        if not opening_all_four:
            shape="missing_or_multi_owner"
        elif opening_local_same and opening_any_ambient_ambiguous:
            shape="g17_same_but_ambient_ambiguous"
        elif opening_local_same:
            shape="g17_same_and_globally_clean"
        else:
            shape="g17_same_not_preserved_in_pair_graph"
        counts[shape]+=1
        rows.append({
            "opening_id":opening.record_id,
            "host_reason_codes":list(trace.reason_codes),
            "shape":shape,
            "pairs":pair_rows,
        })

    print(json.dumps({
        "source_sha256":EXPECTED_SHA,
        "two_face_opening_count":len(rows),
        "shape_counts":dict(counts),
        "wall_candidate_count":len(records),
        "global_ambiguous_wall_count":len(ambiguous),
        "rows":[row for row in rows if row["shape"]!="missing_or_multi_owner"][:100],
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
