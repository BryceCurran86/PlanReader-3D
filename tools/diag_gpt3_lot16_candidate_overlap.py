from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from itertools import combinations
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def main():
    source_bytes=PDF.read_bytes()
    actual=hashlib.sha256(source_bytes).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_candidate_overlap",
        producer_version="1",
    )
    initial=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-candidate-overlap",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    if current is None or not current.visible_observation_ids:
        raise SystemExit("current visible snapshot unavailable")

    physical=composition.physical_opening_authority
    seed_id=current.visible_observation_ids[0]
    structures=physical.visible_candidate_structures(
        ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=seed_id,
        )
    )
    candidates=tuple(structures.candidates)
    by_id={c.candidate_id:c for c in candidates}

    membership=defaultdict(list)
    for candidate in candidates:
        for observation_id in candidate.source_observation_ids:
            membership[str(observation_id)].append(candidate.candidate_id)

    multi={
        observation_id:tuple(sorted(ids))
        for observation_id,ids in membership.items()
        if len(ids)>1
    }

    pattern_pair_counts=Counter()
    relationship_counts=Counter()
    pair_examples=[]
    seen_pairs=set()

    for observation_id,ids in sorted(multi.items()):
        for left_id,right_id in combinations(ids,2):
            pair=tuple(sorted((left_id,right_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            left=by_id[pair[0]]
            right=by_id[pair[1]]
            left_support=set(left.source_observation_ids)
            right_support=set(right.source_observation_ids)
            if left_support == right_support:
                relation="equal_support"
            elif left_support < right_support:
                relation="left_subset_right"
            elif right_support < left_support:
                relation="right_subset_left"
            else:
                relation="partial_overlap"
            relationship_counts[relation]+=1
            pattern_pair_counts[tuple(sorted((left.structural_pattern,right.structural_pattern)))]+=1
            if len(pair_examples)<80:
                pair_examples.append({
                    "shared_observation_id":observation_id,
                    "left_candidate_id":left.candidate_id,
                    "left_pattern":left.structural_pattern,
                    "left_support_count":len(left.source_observation_ids),
                    "right_candidate_id":right.candidate_id,
                    "right_pattern":right.structural_pattern,
                    "right_support_count":len(right.source_observation_ids),
                    "relationship":relation,
                    "shared_support_count":len(left_support & right_support),
                    "left_only_count":len(left_support-right_support),
                    "right_only_count":len(right_support-left_support),
                })

    semantic=composition.semantic_enumeration_result.record
    conflict_ids=set(() if semantic is None else semantic.conflict_observation_ids)
    residual_ids=set(() if semantic is None else semantic.residual_visible_observation_ids)

    conflict_multi={
        obs:ids for obs,ids in multi.items() if obs in conflict_ids
    }
    residual_multi={
        obs:ids for obs,ids in multi.items() if obs in residual_ids
    }

    report={
        "source_sha256":actual,
        "candidate_structure_status":str(getattr(structures.status,"value",structures.status)),
        "candidate_count":len(candidates),
        "candidate_pattern_counts":dict(Counter(c.structural_pattern for c in candidates).most_common()),
        "candidate_support_size_counts":dict(Counter(len(c.source_observation_ids) for c in candidates).most_common()),
        "observation_membership_count":len(membership),
        "multi_candidate_observation_count":len(multi),
        "multi_membership_size_counts":dict(Counter(len(ids) for ids in multi.values()).most_common()),
        "semantic_conflict_observation_count":len(conflict_ids),
        "semantic_residual_observation_count":len(residual_ids),
        "conflict_observations_with_multi_membership":len(conflict_multi),
        "residual_observations_with_multi_membership":len(residual_multi),
        "candidate_pair_relationship_counts":dict(relationship_counts.most_common()),
        "candidate_pattern_pair_counts":{
            " | ".join(key):value
            for key,value in pattern_pair_counts.most_common()
        },
        "pair_examples":pair_examples,
    }
    print(json.dumps(report,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
