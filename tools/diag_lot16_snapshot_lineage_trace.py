from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pb_physical_opening_viewport_scope_authority as viewport_scope
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"

events: list[dict] = []


def current_snapshot(producer, revision_id: str) -> str | None:
    published = producer.published_snapshot_for_revision(str(revision_id))
    if published is None:
        return None
    return str(published.snapshot.snapshot_id)


def main() -> None:
    payload = PDF.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_snapshot_lineage_trace_v1",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-snapshot-lineage-trace-v1",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    revision_id = published.revision.revision_id
    events.append({
        "event":"after_ingest",
        "snapshot_id":published.snapshot.snapshot_id,
        "visible_count":len(published.visible_observation_ids),
        "raster_opening_primitive_count":len(
            published.raster_opening_primitive_observation_ids
        ),
    })

    original_classify = viewport_scope.classify_opening_candidate_viewport_scopes
    original_raster = SourceVisibilityProducer.augment_with_raster_opening_primitives
    original_visible = SourceVisibilityProducer.augment_with_raster_visible_segments

    def traced_classify(*, source_visibility_producer, revision_id, page_id,
                        snapshot_id, candidates, records):
        current = current_snapshot(source_visibility_producer, revision_id)
        candidate_snapshots = sorted({
            str(getattr(row, "snapshot_id", "") or "")
            for row in candidates
        })
        record_snapshots = sorted({
            str(getattr(row, "snapshot_id", "") or "")
            for row in records
        })
        before = {
            "event":"viewport_classify_call",
            "page_id":str(page_id),
            "requested_snapshot_id":str(snapshot_id),
            "current_snapshot_id":current,
            "requested_equals_current":str(snapshot_id)==str(current),
            "candidate_count":len(candidates),
            "record_count":len(records),
            "candidate_snapshot_ids":candidate_snapshots,
            "record_snapshot_ids":record_snapshots,
            "all_candidates_requested_snapshot":(
                bool(candidates)
                and candidate_snapshots == [str(snapshot_id)]
            ),
            "all_records_requested_snapshot":(
                bool(records)
                and record_snapshots == [str(snapshot_id)]
            ),
        }
        result = original_classify(
            source_visibility_producer=source_visibility_producer,
            revision_id=revision_id,
            page_id=page_id,
            snapshot_id=snapshot_id,
            candidates=candidates,
            records=records,
        )
        scopes=Counter(
            str(getattr(decision,"scope","") or "")
            for decision in result.decisions.values()
        )
        before.update({
            "status":str(getattr(result.status,"value",result.status)),
            "reason_codes":list(result.reason_codes),
            "authenticated_viewport_count":len(result.authenticated_viewports),
            "decision_count":len(result.decisions),
            "scope_counts":dict(scopes),
        })
        events.append(before)
        return result

    def traced_raster(self, revision_id, *, page_ids=None):
        before=current_snapshot(self, revision_id)
        result=original_raster(self, revision_id, page_ids=page_ids)
        after=current_snapshot(self, revision_id)
        events.append({
            "event":"augment_raster_opening_primitives",
            "before_snapshot_id":before,
            "after_snapshot_id":after,
            "changed":before!=after,
            "page_ids":None if page_ids is None else list(page_ids),
            "raster_opening_primitive_count":len(
                result.raster_opening_primitive_observation_ids
            ),
        })
        return result

    def traced_visible(self, revision_id, *, page_ids=None):
        before=current_snapshot(self, revision_id)
        result=original_visible(self, revision_id, page_ids=page_ids)
        after=current_snapshot(self, revision_id)
        events.append({
            "event":"augment_raster_visible_segments",
            "before_snapshot_id":before,
            "after_snapshot_id":after,
            "changed":before!=after,
            "page_ids":None if page_ids is None else list(page_ids),
            "visible_count":len(result.visible_observation_ids),
        })
        return result

    viewport_scope.classify_opening_candidate_viewport_scopes = traced_classify
    SourceVisibilityProducer.augment_with_raster_opening_primitives = traced_raster
    SourceVisibilityProducer.augment_with_raster_visible_segments = traced_visible
    try:
        composition = compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=revision_id,
            page_ids=(PAGE_ID,),
        )
    finally:
        viewport_scope.classify_opening_candidate_viewport_scopes = original_classify
        SourceVisibilityProducer.augment_with_raster_opening_primitives = original_raster
        SourceVisibilityProducer.augment_with_raster_visible_segments = original_visible

    final_pub = source.published_snapshot_for_revision(revision_id)
    semantic = composition.semantic_enumeration_result
    semantic_record = semantic.record
    events.append({
        "event":"composition_complete",
        "final_snapshot_id":None if final_pub is None else final_pub.snapshot.snapshot_id,
        "composition_status":str(getattr(composition.status,"value",composition.status)),
        "composition_reason_codes":list(composition.reason_codes),
        "semantic_status":str(getattr(semantic.status,"value",semantic.status)),
        "semantic_reason_codes":list(semantic.reason_codes),
        "physical_opening_universe_complete":(
            None if semantic_record is None
            else semantic_record.physical_opening_universe_complete
        ),
        "physical_opening_count":(
            0 if semantic_record is None
            else len(semantic_record.physical_opening_record_ids)
        ),
        "host_bound_count":sum(
            1 for row in composition.opening_bindings if row.host_wall_id is not None
        ),
        "opening_binding_count":len(composition.opening_bindings),
    })

    viewport_calls=[row for row in events if row["event"]=="viewport_classify_call"]
    mismatches=[
        row for row in viewport_calls
        if not row["requested_equals_current"]
        or (row["candidate_count"] and not row["all_candidates_requested_snapshot"])
        or (row["record_count"] and not row["all_records_requested_snapshot"])
    ]
    report={
        "source_sha256":actual,
        "revision_id":revision_id,
        "event_count":len(events),
        "viewport_call_count":len(viewport_calls),
        "viewport_lineage_mismatch_count":len(mismatches),
        "events":events,
        "mismatches":mismatches,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
