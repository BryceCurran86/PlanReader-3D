from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


def _status(value):
    return getattr(value, "value", str(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page-id", required=True)
    args = parser.parse_args()

    source = SourceVisibilityProducer(
        producer_method="live-wall-opening-real-trace",
        producer_version="1",
    )
    data = args.pdf.read_bytes()
    published = source.ingest_native_pdf_bytes(
        document_id="live-wall-opening-real-trace",
        source_bytes=data,
        source_locator=str(args.pdf),
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(str(args.page_id),),
    )

    payload = {
        "source": {
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "coverage_state": str(published.coverage.state),
            "decoded_pages": list(published.coverage.decoded_pages),
            "visible_observation_count": len(published.visible_observation_ids),
        },
        "composition": {
            "status": _status(composition.status),
            "reason_codes": list(composition.reason_codes),
            "page_ids": list(composition.page_ids),
            "semantic_status": _status(composition.semantic_enumeration_result.status),
            "semantic_reason_codes": list(composition.semantic_enumeration_result.reason_codes),
            "semantic_record_id": (
                composition.semantic_enumeration_result.record.record_id
                if composition.semantic_enumeration_result.record is not None
                else None
            ),
            "semantic_opening_record_ids": (
                list(composition.semantic_enumeration_result.record.physical_opening_record_ids)
                if composition.semantic_enumeration_result.record is not None
                else []
            ),
            "semantic_universe_complete": (
                composition.semantic_enumeration_result.record.physical_opening_universe_complete
                if composition.semantic_enumeration_result.record is not None
                else False
            ),
        },
        "wall_scopes": [
            {
                "file": "pb_physical_wall_candidate_authority.py",
                "class_function": "PhysicalWallCandidateProducer.from_source_visibility_producer / PhysicalWallCandidateAuthority.resolve_scope",
                "status": _status(trace.status),
                "reason_codes": list(trace.reason_codes),
                "record_present": bool(trace.wall_candidate_ids),
                "record_ids": list(trace.wall_candidate_ids),
                "scope_complete": trace.scope_complete,
                "page_id": trace.page_id,
                "input_lineage": {
                    "document_id": published.revision.document_id,
                    "revision_id": published.revision.revision_id,
                    "source_sha256": published.revision.source_sha256,
                    "snapshot_id": published.snapshot.snapshot_id,
                    "page_id": trace.page_id,
                },
                "output_lineage": {
                    "physical_wall_candidate_ids": list(trace.wall_candidate_ids),
                },
            }
            for trace in composition.wall_scopes
        ],
        "opening_bindings": [
            {
                "file": "pb_opening_host_binding_authority.py",
                "class_function": "OpeningHostBindingProducer.publish",
                "status": _status(trace.status),
                "reason_codes": list(trace.reason_codes),
                "record_present": trace.record_id is not None,
                "record_id": trace.record_id,
                "opening_identity_id": trace.opening_identity_id,
                "host_wall_id": trace.host_wall_id,
                "member_wall_candidate_ids": list(trace.member_wall_candidate_ids),
                "input_lineage": {
                    "document_id": published.revision.document_id,
                    "revision_id": published.revision.revision_id,
                    "source_sha256": published.revision.source_sha256,
                    "snapshot_id": published.snapshot.snapshot_id,
                    "page_id": trace.page_id,
                    "representative_observation_id": trace.representative_observation_id,
                },
                "output_lineage": {
                    "opening_identity_id": trace.opening_identity_id,
                    "host_wall_id": trace.host_wall_id,
                    "member_wall_candidate_ids": list(trace.member_wall_candidate_ids),
                },
            }
            for trace in composition.opening_bindings
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
