from __future__ import annotations

from collections import Counter
import hashlib, json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import JAMB_BOUNDED_TWO_FACE_INTERRUPTION
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateSelector,
    _filter_repeated_non_physical_drafting_primitives,
    _opening_raw_relation_sets,
    _producer_opening_wall_face_source_ids,
    _source_page_segments,
)
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
    actual=hashlib.sha256(data).hexdigest()
    assert actual==EXPECTED_SHA
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
    visible_rows=[]
    visibility=comp.physical_opening_authority.source_visibility_authority()
    for oid in current.visible_observation_ids:
        resolved=visibility.resolve_visible(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=oid,
        ))
        if resolved.status is EvidenceResolutionStatus.CORROBORATED and resolved.observation is not None and str(resolved.observation.page_id)==PAGE_ID:
            visible_rows.append((oid,resolved.observation))

    protected=_producer_opening_wall_face_source_ids(
        source_producer=source,
        published=current,
        page_id=PAGE_ID,
        resolved_visible_observations=visible_rows,
        physical_opening_authority=comp.physical_opening_authority,
    )

    segments,_,pw,ph=_source_page_segments(
        source_producer=source,
        published=current,
        source_bytes=data,
        page_id=PAGE_ID,
        decision_scope_id=SCOPE_ID,
        resolved_visible_observations=visible_rows,
    )
    baseline_ids={str(s.get("id") or "") for s in _filter_repeated_non_physical_drafting_primitives(segments,page_width=pw,page_height=ph)}
    protected_ids={str(s.get("id") or "") for s in _filter_repeated_non_physical_drafting_primitives(
        segments,page_width=pw,page_height=ph,protected_source_primitive_ids=protected
    )}

    face_occurrences=[]
    record_ids=set()
    for trace in comp.opening_bindings:
        result=comp.physical_opening_authority.prove_existence(ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        ))
        opening=result.existence_record
        if opening is None or opening.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION:
            continue
        record_ids.add(opening.record_id)
        lines={}
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
                lines[rid]=tuple(float(v) for v in resolved.observation.geometry)
        relations=_opening_raw_relation_sets(lines)
        pairs=[pair for pair,classes in relations.items() if {str(getattr(c,"value",c)) for c in classes}=={"same_physical_wall"}]
        faces=sorted({rid for pair in pairs for rid in pair})
        for rid in faces:
            face_occurrences.append({
                "opening_id":opening.record_id,
                "raw_id":rid,
                "helper_protected":rid in protected,
                "survives_baseline_filter":rid in baseline_ids,
                "survives_protected_filter":rid in protected_ids,
            })

    counts=Counter()
    for row in face_occurrences:
        if row["survives_baseline_filter"]:
            key="already_survived_baseline"
        elif row["helper_protected"] and row["survives_protected_filter"]:
            key="restored_by_helper"
        elif row["helper_protected"]:
            key="helper_protected_but_still_filtered"
        else:
            key="not_protected_by_helper"
        counts[key]+=1

    unique_face_ids={row["raw_id"] for row in face_occurrences}
    report={
        "source_sha256":actual,
        "two_face_opening_record_count":len(record_ids),
        "face_occurrence_count":len(face_occurrences),
        "unique_face_source_id_count":len(unique_face_ids),
        "helper_protected_unique_id_count":len(protected),
        "helper_protected_face_unique_id_count":len(unique_face_ids & set(protected)),
        "classification_counts":dict(counts),
        "missing_unique_face_ids":sorted(unique_face_ids-set(protected)),
        "rows":[row for row in face_occurrences if not row["helper_protected"]][:120],
    }
    print(json.dumps(report,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
