from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_opening_authority import _physical_opening_geometry_identity
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    assert actual==EXPECTED_SHA

    source=SourceVisibilityProducer(
        producer_method="diag-gptmax-lot16-candidate-physical-identity-overlap",
        producer_version="1",
    )
    initial=source.ingest_native_pdf_bytes(
        document_id="diag-gptmax-lot16-candidate-physical-identity-overlap",
        source_bytes=data,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    assert current is not None and current.visible_observation_ids
    physical=composition.physical_opening_authority

    seed=ObservationSelector(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        observation_id=current.visible_observation_ids[0],
    )
    structures=physical.visible_candidate_structures(seed)
    candidates=tuple(structures.candidates)

    source_result=physical._resolve_visible_cached(seed)
    records,failures=physical._visible_snapshot_records(source_result)
    assert not failures

    geometry_by_candidate={}
    geometry_groups=defaultdict(list)
    unresolved=[]
    for candidate in candidates:
        geometry=_physical_opening_geometry_identity(candidate,records)
        if geometry is None:
            unresolved.append(candidate.candidate_id)
            continue
        key=json.dumps(geometry,sort_keys=True,separators=(",",":"))
        geometry_by_candidate[candidate.candidate_id]=key
        geometry_groups[key].append(candidate.candidate_id)

    membership=defaultdict(list)
    for candidate in candidates:
        for observation_id in candidate.source_observation_ids:
            membership[str(observation_id)].append(candidate.candidate_id)

    multi_rows=[]
    geometry_multiplicity=Counter()
    candidate_multiplicity=Counter()
    for observation_id,candidate_ids in sorted(membership.items()):
        if len(candidate_ids)<=1:
            continue
        geometry_ids=sorted({
            geometry_by_candidate[candidate_id]
            for candidate_id in candidate_ids
            if candidate_id in geometry_by_candidate
        })
        candidate_multiplicity[len(candidate_ids)]+=1
        geometry_multiplicity[len(geometry_ids)]+=1
        if len(multi_rows)<100:
            multi_rows.append({
                "observation_id":observation_id,
                "candidate_count":len(candidate_ids),
                "resolved_geometry_identity_count":len(geometry_ids),
                "candidate_ids":sorted(candidate_ids),
            })

    report={
        "source_sha256":actual,
        "candidate_count":len(candidates),
        "resolved_candidate_geometry_count":len(geometry_by_candidate),
        "unresolved_candidate_geometry_count":len(unresolved),
        "unique_physical_geometry_count":len(geometry_groups),
        "geometry_group_size_counts":dict(Counter(len(v) for v in geometry_groups.values()).most_common()),
        "multi_candidate_observation_count":sum(1 for ids in membership.values() if len(ids)>1),
        "multi_candidate_count_distribution":dict(sorted(candidate_multiplicity.items())),
        "multi_observation_geometry_identity_count_distribution":dict(sorted(geometry_multiplicity.items())),
        "same_geometry_multi_observation_count":sum(
            count for geometry_count,count in geometry_multiplicity.items() if geometry_count==1
        ),
        "true_multi_geometry_observation_count":sum(
            count for geometry_count,count in geometry_multiplicity.items() if geometry_count>1
        ),
        "rows":multi_rows,
    }
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
