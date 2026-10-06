from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pb_physical_opening_viewport_scope_authority as scope_mod
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"

def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(actual)

    source=SourceVisibilityProducer(
        producer_method="diag-gptmax-lot16-viewport-snapshot-trace",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gptmax-lot16-viewport-snapshot-trace",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )

    original=scope_mod.classify_opening_candidate_viewport_scopes
    calls=[]

    def wrapped(**kwargs):
        revision_id=str(kwargs["revision_id"])
        requested_snapshot=str(kwargs["snapshot_id"])
        current=source.published_snapshot_for_revision(revision_id)
        current_snapshot=None if current is None else str(current.snapshot.snapshot_id)
        candidates=tuple(kwargs.get("candidates") or ())
        records=tuple(kwargs.get("records") or ())
        result=original(**kwargs)
        calls.append({
            "page_id":str(kwargs["page_id"]),
            "requested_snapshot_id":requested_snapshot,
            "current_snapshot_id":current_snapshot,
            "snapshot_equal_before_call":requested_snapshot==current_snapshot,
            "candidate_count":len(candidates),
            "record_count":len(records),
            "candidate_snapshot_ids":sorted({
                str(getattr(c,"snapshot_id","") or "") for c in candidates
            }),
            "record_snapshot_ids":sorted({
                str(getattr(r,"snapshot_id","") or "") for r in records
            }),
            "status":str(getattr(result.status,"value",result.status)),
            "reason_codes":list(result.reason_codes),
            "authenticated_viewport_count":len(result.authenticated_viewports),
        })
        return result

    scope_mod.classify_opening_candidate_viewport_scopes=wrapped
    try:
        wall=compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=published.revision.revision_id,
            page_ids=(PAGE_ID,),
        )
    finally:
        scope_mod.classify_opening_candidate_viewport_scopes=original

    final=source.published_snapshot_for_revision(published.revision.revision_id)
    out={
        "initial_snapshot_id":published.snapshot.snapshot_id,
        "final_snapshot_id":None if final is None else final.snapshot.snapshot_id,
        "call_count":len(calls),
        "mismatch_call_count":sum(not c["snapshot_equal_before_call"] for c in calls),
        "calls":calls,
        "wall_status":str(getattr(wall.status,"value",wall.status)),
        "wall_reason_codes":list(wall.reason_codes),
        "host_bound_count":sum(1 for x in wall.opening_bindings if x.host_wall_id),
        "opening_binding_count":len(wall.opening_bindings),
    }
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
