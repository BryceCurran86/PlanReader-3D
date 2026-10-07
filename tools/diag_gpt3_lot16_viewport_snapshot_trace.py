from __future__ import annotations

import json
from pathlib import Path

import pb_physical_opening_viewport_scope_authority as scope_mod
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
PAGE_ID="3"
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def main():
    payload=PDF.read_bytes()
    import hashlib
    actual=hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_viewport_snapshot_trace",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-viewport-snapshot-trace",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=tuple(str(i) for i in range(1,14)),
    )

    calls=[]
    original=scope_mod.classify_opening_candidate_viewport_scopes

    def traced(**kwargs):
        current=source.published_snapshot_for_revision(str(kwargs["revision_id"]))
        requested=str(kwargs["snapshot_id"])
        current_id=None if current is None else str(current.snapshot.snapshot_id)
        candidate_rows=tuple(kwargs.get("candidates") or ())
        record_rows=tuple(kwargs.get("records") or ())
        candidate_snapshot_ids=sorted({
            str(getattr(row,"snapshot_id","") or "")
            for row in candidate_rows
            if str(getattr(row,"snapshot_id","") or "")
        })
        record_snapshot_ids=sorted({
            str(getattr(row,"snapshot_id","") or "")
            for row in record_rows
            if str(getattr(row,"snapshot_id","") or "")
        })
        result=original(**kwargs)
        calls.append({
            "page_id":str(kwargs["page_id"]),
            "requested_snapshot_id":requested,
            "current_snapshot_id":current_id,
            "requested_equals_current":requested == current_id,
            "candidate_count":len(candidate_rows),
            "record_count":len(record_rows),
            "candidate_snapshot_ids":candidate_snapshot_ids,
            "record_snapshot_ids":record_snapshot_ids,
            "result_status":result.status.value,
            "result_reason_codes":list(result.reason_codes),
            "authenticated_viewport_count":len(result.authenticated_viewports),
            "decision_count":len(result.decisions),
            "scope_counts":{},
        })
        scope_counts={}
        for decision in result.decisions.values():
            scope=str(decision.scope)
            scope_counts[scope]=scope_counts.get(scope,0)+1
        calls[-1]["scope_counts"]=scope_counts
        return result

    scope_mod.classify_opening_candidate_viewport_scopes=traced
    try:
        comp=compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=published.revision.revision_id,
            page_ids=(PAGE_ID,),
        )
    finally:
        scope_mod.classify_opening_candidate_viewport_scopes=original

    current=source.published_snapshot_for_revision(published.revision.revision_id)
    payload_out={
        "source_sha256":actual,
        "initial_snapshot_id":published.snapshot.snapshot_id,
        "final_snapshot_id":None if current is None else current.snapshot.snapshot_id,
        "composition_status":comp.status.value,
        "composition_reason_codes":list(comp.reason_codes),
        "semantic_status":comp.semantic_enumeration_result.status.value,
        "semantic_reason_codes":list(comp.semantic_enumeration_result.reason_codes),
        "semantic_record_count":(
            0 if comp.semantic_enumeration_result.record is None
            else len(comp.semantic_enumeration_result.record.physical_opening_record_ids)
        ),
        "opening_binding_count":len(comp.opening_bindings),
        "host_bound_count":sum(1 for row in comp.opening_bindings if row.host_wall_id),
        "host_frame_count":len(comp.host_frames),
        "host_frame_bound_count":sum(1 for row in comp.host_frames if row.host_wall_id),
        "viewport_scope_call_count":len(calls),
        "viewport_scope_calls":calls,
    }
    print(json.dumps(payload_out,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
