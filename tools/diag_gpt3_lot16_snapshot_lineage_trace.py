from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pb_physical_opening_viewport_scope_authority as viewport_scope
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def _snapshot_set(rows):
    return sorted({
        str(getattr(row,"snapshot_id","") or "")
        for row in rows
        if str(getattr(row,"snapshot_id","") or "")
    })


def main() -> None:
    source_bytes=PDF.read_bytes()
    actual=hashlib.sha256(source_bytes).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_snapshot_lineage_trace",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-snapshot-lineage-trace",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=tuple(str(i) for i in range(1,14)),
    )

    events=[]
    original=viewport_scope.classify_opening_candidate_viewport_scopes

    def traced(*,source_visibility_producer,revision_id,page_id,snapshot_id,candidates,records):
        current=source_visibility_producer.published_snapshot_for_revision(str(revision_id))
        current_snapshot=(
            None if current is None else str(current.snapshot.snapshot_id)
        )
        event={
            "call_index":len(events),
            "revision_id":str(revision_id),
            "page_id":str(page_id),
            "requested_snapshot_id":str(snapshot_id),
            "current_snapshot_id":current_snapshot,
            "requested_equals_current":str(snapshot_id)==str(current_snapshot),
            "candidate_count":len(tuple(candidates)),
            "record_count":len(tuple(records)),
            "candidate_snapshot_ids":_snapshot_set(candidates),
            "record_snapshot_ids":_snapshot_set(records),
        }
        result=original(
            source_visibility_producer=source_visibility_producer,
            revision_id=revision_id,
            page_id=page_id,
            snapshot_id=snapshot_id,
            candidates=candidates,
            records=records,
        )
        event.update({
            "status":result.status.value,
            "reason_codes":list(result.reason_codes),
            "authenticated_viewport_count":len(result.authenticated_viewports),
            "decision_count":len(result.decisions),
            "decision_scope_counts":{},
        })
        for decision in result.decisions.values():
            scope=str(decision.scope)
            event["decision_scope_counts"][scope]=event["decision_scope_counts"].get(scope,0)+1
        events.append(event)
        return result

    viewport_scope.classify_opening_candidate_viewport_scopes=traced
    try:
        composition=compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=published.revision.revision_id,
            page_ids=(PAGE_ID,),
        )
    finally:
        viewport_scope.classify_opening_candidate_viewport_scopes=original

    current=source.published_snapshot_for_revision(published.revision.revision_id)
    payload={
        "source_sha256":actual,
        "initial_snapshot_id":published.snapshot.snapshot_id,
        "final_snapshot_id":None if current is None else current.snapshot.snapshot_id,
        "composition_status":composition.status.value,
        "composition_reason_codes":list(composition.reason_codes),
        "semantic_status":composition.semantic_enumeration_result.status.value,
        "semantic_reason_codes":list(composition.semantic_enumeration_result.reason_codes),
        "opening_binding_count":len(composition.opening_bindings),
        "host_bound_count":sum(1 for row in composition.opening_bindings if row.host_wall_id),
        "host_frame_count":len(composition.host_frames),
        "trace_event_count":len(events),
        "snapshot_mismatch_event_count":sum(1 for row in events if not row["requested_equals_current"]),
        "events":events,
    }
    print(json.dumps(payload,indent=2,sort_keys=True))

    # Diagnostic invariant: if viewport scope reports a snapshot mismatch,
    # expose at least one concrete requested/current lineage divergence.
    if "opening_viewport_scope_snapshot_mismatch" in payload["composition_reason_codes"]:
        if not payload["snapshot_mismatch_event_count"]:
            raise SystemExit(
                "composition reports snapshot mismatch but trace found no requested/current divergence"
            )


if __name__=="__main__":
    main()
