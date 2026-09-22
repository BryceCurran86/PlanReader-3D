from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


def _status(value):
    return getattr(value, "value", value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--page-ids", required=True)
    args = parser.parse_args()

    raw = args.pdf.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="pr627-live-composition-diagnostic",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=args.document_id,
        source_bytes=raw,
        source_locator=str(args.pdf),
    )
    pages = tuple(v.strip() for v in args.page_ids.split(",") if v.strip())
    composed = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=pages,
    )
    payload = {
        "status": _status(composed.status),
        "reason_codes": list(composed.reason_codes),
        "revision_id": composed.revision_id,
        "page_ids": list(composed.page_ids),
        "semantic": {
            "status": _status(composed.semantic_enumeration_result.status),
            "reason_codes": list(composed.semantic_enumeration_result.reason_codes),
            "record_present": composed.semantic_enumeration_result.record is not None,
            "opening_count": (
                len(composed.semantic_enumeration_result.record.representative_observation_ids)
                if composed.semantic_enumeration_result.record is not None
                else 0
            ),
        },
        "wall_scopes": [
            {
                "page_id": row.page_id,
                "status": _status(row.status),
                "reason_codes": list(row.reason_codes),
                "scope_complete": row.scope_complete,
                "wall_count": len(row.wall_candidate_ids),
                "wall_candidate_ids": list(row.wall_candidate_ids),
            }
            for row in composed.wall_scopes
        ],
        "opening_bindings": [
            {
                "opening_identity_id": row.opening_identity_id,
                "representative_observation_id": row.representative_observation_id,
                "page_id": row.page_id,
                "status": _status(row.status),
                "reason_codes": list(row.reason_codes),
                "record_id": row.record_id,
                "host_wall_id": row.host_wall_id,
                "member_wall_candidate_ids": list(row.member_wall_candidate_ids),
            }
            for row in composed.opening_bindings
        ],
        "host_frames": [
            {
                "opening_identity_id": row.opening_identity_id,
                "status": _status(row.status),
                "reason_codes": list(row.reason_codes),
                "record_id": row.record_id,
                "host_wall_id": row.host_wall_id,
                "whole_wall_candidate_ids": list(row.whole_wall_candidate_ids),
            }
            for row in composed.host_frames
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
