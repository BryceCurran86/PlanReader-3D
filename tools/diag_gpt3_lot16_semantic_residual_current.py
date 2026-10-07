from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def state(value):
    return str(getattr(value,"value",value))


def main():
    payload=PDF.read_bytes()
    actual=hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_semantic_residual_current",
        producer_version="1",
    )
    initial=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-semantic-residual-current",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    if current is None:
        raise SystemExit("current published snapshot unavailable")

    semantic=composition.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic opening inventory unavailable")

    visibility=composition.physical_opening_authority.source_visibility_authority()
    if visibility is None:
        raise SystemExit("source visibility authority unavailable")
    physical=composition.physical_opening_authority

    def row(observation_id: str) -> dict:
        selector=ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        visible=visibility.resolve_visible(selector)
        obs=visible.observation
        disposition=physical.classify_disposition(selector)
        return {
            "observation_id":str(observation_id),
            "visible_status":state(visible.status),
            "visible_reasons":list(visible.reason_codes),
            "observation_kind":None if obs is None else obs.observation_kind,
            "source_primitive_ref":None if obs is None else obs.source_primitive_ref,
            "geometry":None if obs is None else list(obs.geometry),
            "disposition_status":state(disposition.status),
            "disposition":disposition.disposition,
            "disposition_reasons":list(disposition.reason_codes),
            "candidate_ids":list(disposition.candidate_ids),
        }

    residual=[row(x) for x in semantic.residual_visible_observation_ids]
    conflicts=[row(x) for x in semantic.conflict_observation_ids]

    def reason_counts(rows):
        c=Counter()
        for item in rows:
            c.update(item["disposition_reasons"])
        return dict(c.most_common())

    def disposition_counts(rows):
        return dict(Counter(item["disposition"] for item in rows).most_common())

    def kind_counts(rows):
        return dict(Counter(str(item["observation_kind"]) for item in rows).most_common())

    report={
        "source_sha256":actual,
        "initial_snapshot_id":initial.snapshot.snapshot_id,
        "current_snapshot_id":current.snapshot.snapshot_id,
        "semantic_status":state(composition.semantic_enumeration_result.status),
        "semantic_reason_codes":list(composition.semantic_enumeration_result.reason_codes),
        "physical_opening_universe_complete":semantic.physical_opening_universe_complete,
        "physical_opening_count":len(semantic.physical_opening_record_ids),
        "support_observation_count":len(semantic.opening_support_observation_ids),
        "residual_visible_count":len(residual),
        "conflict_visible_count":len(conflicts),
        "residual_disposition_counts":disposition_counts(residual),
        "residual_reason_counts":reason_counts(residual),
        "residual_kind_counts":kind_counts(residual),
        "conflict_disposition_counts":disposition_counts(conflicts),
        "conflict_reason_counts":reason_counts(conflicts),
        "conflict_kind_counts":kind_counts(conflicts),
        "stale_snapshot_reason_count":sum(
            1
            for item in (*residual,*conflicts)
            if "opening_viewport_scope_snapshot_mismatch" in item["disposition_reasons"]
        ),
        "residual_rows":residual,
        "conflict_rows":conflicts,
    }
    print(json.dumps(report,indent=2,sort_keys=True))

    if report["stale_snapshot_reason_count"] != 0:
        raise SystemExit(
            "current-snapshot audit unexpectedly reproduced snapshot mismatch"
        )


if __name__=="__main__":
    main()
