from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


def _enum(value):
    return getattr(value, "value", value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--pages", required=True)
    args = parser.parse_args()

    raw = args.pdf.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="pr627-real-source-trace",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=args.document_id,
        source_bytes=raw,
        source_locator=str(args.pdf),
    )
    page_ids = tuple(v.strip() for v in args.pages.split(",") if v.strip())
    result = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=page_ids,
    )
    payload = {
        "document_id": args.document_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_ids": list(result.page_ids),
        "status": _enum(result.status),
        "reason_codes": list(result.reason_codes),
        "semantic_enumeration": {
            "status": _enum(result.semantic_enumeration_result.status),
            "reason_codes": list(result.semantic_enumeration_result.reason_codes),
            "record_present": result.semantic_enumeration_result.record is not None,
            "opening_count": (
                len(result.semantic_enumeration_result.record.representative_observation_ids)
                if result.semantic_enumeration_result.record is not None else 0
            ),
        },
        "wall_scopes": [
            {
                "page_id": t.page_id,
                "status": _enum(t.status),
                "reason_codes": list(t.reason_codes),
                "scope_complete": t.scope_complete,
                "wall_count": len(t.wall_candidate_ids),
                "wall_candidate_ids": list(t.wall_candidate_ids)[:50],
            }
            for t in result.wall_scopes
        ],
        "opening_bindings": [
            {
                "opening_identity_id": t.opening_identity_id,
                "page_id": t.page_id,
                "status": _enum(t.status),
                "reason_codes": list(t.reason_codes),
                "record_id": t.record_id,
                "host_wall_id": t.host_wall_id,
                "member_wall_candidate_ids": list(t.member_wall_candidate_ids),
            }
            for t in result.opening_bindings
        ],
        "host_frames": [
            {
                "opening_identity_id": t.opening_identity_id,
                "status": _enum(t.status),
                "reason_codes": list(t.reason_codes),
                "record_id": t.record_id,
                "host_wall_id": t.host_wall_id,
                "whole_wall_candidate_ids": list(t.whole_wall_candidate_ids),
            }
            for t in result.host_frames
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
