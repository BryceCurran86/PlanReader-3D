from __future__ import annotations

from collections import Counter, defaultdict
import hashlib, json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def _status(value):
    return str(getattr(value,"value",value))

def main():
    payload=PDF.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==EXPECTED_SHA
    source=SourceVisibilityProducer(
        producer_method="diag-gptmax-lot16-host-failure-census",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gptmax-lot16-host-failure-census",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=("3",),
    )
    comp=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None
    auth=comp.physical_opening_authority

    reason_counts=Counter()
    pattern_counts=Counter()
    pattern_reason_counts=defaultdict(Counter)
    status_counts=Counter()
    rows=[]
    for trace in comp.opening_bindings:
        selector=ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        existence=auth.prove_existence(selector)
        opening=existence.existence_record
        pattern=(None if opening is None else str(opening.structural_pattern))
        status=_status(trace.status)
        status_counts[status]+=1
        if pattern:
            pattern_counts[pattern]+=1
        for reason in trace.reason_codes:
            reason_counts[str(reason)]+=1
            pattern_reason_counts[pattern or "<none>"][str(reason)]+=1
        rows.append({
            "opening_identity_id":trace.opening_identity_id,
            "representative_observation_id":trace.representative_observation_id,
            "structural_pattern":pattern,
            "existence_status":_status(existence.status),
            "binding_status":status,
            "binding_reason_codes":list(trace.reason_codes),
            "host_wall_id":trace.host_wall_id,
            "member_wall_candidate_count":len(trace.member_wall_candidate_ids),
        })

    frame_reason_counts=Counter()
    frame_status_counts=Counter()
    frame_rows=[]
    for trace in comp.host_frames:
        s=_status(trace.status)
        frame_status_counts[s]+=1
        for reason in trace.reason_codes:
            frame_reason_counts[str(reason)]+=1
        frame_rows.append({
            "opening_identity_id":trace.opening_identity_id,
            "status":s,
            "reason_codes":list(trace.reason_codes),
            "host_wall_id":trace.host_wall_id,
            "whole_wall_candidate_count":len(trace.whole_wall_candidate_ids),
        })

    payload_out={
        "composition_status":_status(comp.status),
        "composition_reason_codes":list(comp.reason_codes),
        "opening_binding_count":len(comp.opening_bindings),
        "host_bound_count":sum(1 for r in comp.opening_bindings if r.host_wall_id),
        "binding_status_counts":dict(sorted(status_counts.items())),
        "binding_reason_counts":dict(reason_counts.most_common()),
        "structural_pattern_counts":dict(pattern_counts.most_common()),
        "pattern_reason_counts":{
            p:dict(c.most_common()) for p,c in sorted(pattern_reason_counts.items())
        },
        "host_frame_count":len(comp.host_frames),
        "host_frame_resolved_count":sum(1 for r in comp.host_frames if r.record_id),
        "host_frame_status_counts":dict(sorted(frame_status_counts.items())),
        "host_frame_reason_counts":dict(frame_reason_counts.most_common()),
        "opening_rows":rows,
        "host_frame_rows":frame_rows,
    }
    print(json.dumps(payload_out,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
