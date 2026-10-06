from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(
            f"source sha mismatch: expected {EXPECTED_SOURCE_SHA}, got {actual_sha}"
        )

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_host_chain",
        producer_version="1",
    )
    ingested = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-host-chain",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=ingested.revision.revision_id,
        page_ids=(PAGE_ID,),
    )

    semantic = composition.semantic_enumeration_result.record
    opening_ids = tuple(
        semantic.physical_opening_record_ids if semantic is not None else ()
    )

    binding_reasons = Counter(
        reason
        for trace in composition.opening_bindings
        for reason in trace.reason_codes
    )
    frame_reasons = Counter(
        reason
        for trace in composition.host_frames
        for reason in trace.reason_codes
    )
    wall_reasons = Counter(
        reason
        for trace in composition.wall_scopes
        for reason in trace.reason_codes
    )

    payload = {
        "source_sha256": actual_sha,
        "page_id": PAGE_ID,
        "composition_status": composition.status.value,
        "composition_reason_codes": list(composition.reason_codes),
        "semantic_status": composition.semantic_enumeration_result.status.value,
        "semantic_reason_codes": list(composition.semantic_enumeration_result.reason_codes),
        "physical_opening_record_count": len(opening_ids),
        "physical_opening_record_ids": list(opening_ids),
        "semantic_physical_opening_universe_complete": (
            None
            if semantic is None
            else bool(semantic.physical_opening_universe_complete)
        ),
        "wall_scopes": [
            {
                "page_id": trace.page_id,
                "status": trace.status.value,
                "scope_complete": bool(trace.scope_complete),
                "wall_candidate_count": len(trace.wall_candidate_ids),
                "reason_codes": list(trace.reason_codes),
            }
            for trace in composition.wall_scopes
        ],
        "opening_binding_count": len(composition.opening_bindings),
        "host_bound_count": sum(
            1
            for trace in composition.opening_bindings
            if trace.record_id is not None and trace.host_wall_id is not None
        ),
        "opening_bindings": [
            {
                "opening_identity_id": trace.opening_identity_id,
                "representative_observation_id": trace.representative_observation_id,
                "page_id": trace.page_id,
                "status": trace.status.value,
                "reason_codes": list(trace.reason_codes),
                "record_id": trace.record_id,
                "host_wall_id": trace.host_wall_id,
                "member_wall_candidate_count": len(trace.member_wall_candidate_ids),
            }
            for trace in composition.opening_bindings
        ],
        "binding_reason_counts": dict(sorted(binding_reasons.items())),
        "host_frame_count": len(composition.host_frames),
        "host_frame_resolved_count": sum(
            1
            for trace in composition.host_frames
            if trace.record_id is not None and trace.host_wall_id is not None
        ),
        "host_frames": [
            {
                "opening_identity_id": trace.opening_identity_id,
                "status": trace.status.value,
                "reason_codes": list(trace.reason_codes),
                "record_id": trace.record_id,
                "host_wall_id": trace.host_wall_id,
                "whole_wall_candidate_count": len(trace.whole_wall_candidate_ids),
            }
            for trace in composition.host_frames
        ],
        "frame_reason_counts": dict(sorted(frame_reasons.items())),
        "wall_reason_counts": dict(sorted(wall_reasons.items())),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
