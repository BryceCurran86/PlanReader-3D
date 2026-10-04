from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def test_diagnostic_lot16_current_host_binding_histogram() -> None:
    pdf_path = Path("benchmarks/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
    payload = pdf_path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="diagnostic-lot16-host-binding-current-main",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diagnostic-live-source:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://diagnostic-lot16-host-binding.pdf",
        page_ids=("3",),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
    )

    status_histogram = Counter(trace.status.value for trace in composition.opening_bindings)
    reason_histogram = Counter(
        "|".join(trace.reason_codes) if trace.reason_codes else "<none>"
        for trace in composition.opening_bindings
    )
    bound = sum(
        1
        for trace in composition.opening_bindings
        if trace.status is EvidenceResolutionStatus.CORROBORATED
        and trace.record_id is not None
    )
    host_frame_status_histogram = Counter(
        trace.status.value for trace in composition.host_frames
    )
    host_frame_reason_histogram = Counter(
        "|".join(trace.reason_codes) if trace.reason_codes else "<none>"
        for trace in composition.host_frames
    )
    wall_scope = composition.wall_scopes[0] if composition.wall_scopes else None
    semantic_record = composition.semantic_enumeration_result.record

    report = {
        "source_sha256": source_sha,
        "revision_id": composition.revision_id,
        "composition_status": composition.status.value,
        "composition_reason_codes": list(composition.reason_codes),
        "wall_scope": (
            None
            if wall_scope is None
            else {
                "status": wall_scope.status.value,
                "reason_codes": list(wall_scope.reason_codes),
                "scope_complete": wall_scope.scope_complete,
                "wall_candidate_count": len(wall_scope.wall_candidate_ids),
            }
        ),
        "semantic_representative_count": (
            0 if semantic_record is None else len(semantic_record.representative_observation_ids)
        ),
        "opening_binding_trace_count": len(composition.opening_bindings),
        "host_bound_count": bound,
        "binding_status_histogram": dict(sorted(status_histogram.items())),
        "binding_reason_histogram": dict(sorted(reason_histogram.items())),
        "host_frame_count": len(composition.host_frames),
        "host_frame_status_histogram": dict(sorted(host_frame_status_histogram.items())),
        "host_frame_reason_histogram": dict(sorted(host_frame_reason_histogram.items())),
        "opening_traces": [
            {
                "opening_identity_id": trace.opening_identity_id,
                "representative_observation_id": trace.representative_observation_id,
                "page_id": trace.page_id,
                "status": trace.status.value,
                "reason_codes": list(trace.reason_codes),
                "record_id": trace.record_id,
                "host_wall_id": trace.host_wall_id,
                "member_wall_candidate_ids": list(trace.member_wall_candidate_ids),
            }
            for trace in composition.opening_bindings
        ],
    }

    pytest.fail("LOT16_CURRENT_HOST_BINDING_DIAGNOSTIC\n" + json.dumps(report, indent=2, sort_keys=True))
