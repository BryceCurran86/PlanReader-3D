"""Audit original native text receipts; never infer an opening filling role."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def original_role_text_audit(payload: bytes, queries: tuple[str, ...]) -> dict:
    if type(payload) is not bytes or not payload:
        raise TypeError("original PDF bytes required")
    if not queries or any(type(q) is not str or not q.strip() for q in queries):
        raise ValueError("nonempty literal source text queries required")
    digest = sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=payload,
        source_locator="memory://original-role-text-audit.pdf",
    )
    native = {}
    for oid in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        result = source._producer.authority().resolve(selector)
        record = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or record is None
            or record.observation_kind != "native_pdf_word"
            or record.origin_kind != "native"
        ):
            raise RuntimeError("original native text inventory does not authenticate")
        native[oid] = record
    # Raw words nominate blocks only. Only the independently resolved native
    # text integrity result below may be described as trusted source text.
    needles = frozenset(q.casefold().strip() for q in queries)
    blocks = set()
    for oid, record in native.items():
        words = set(re.findall(r"[\w]+", record.raw_text.casefold()))
        if not words & needles:
            continue
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        text = source.text_integrity_authority().resolve_text(selector)
        if text.receipt is not None:
            blocks.add((record.page_id, text.receipt.block_no))
    text_authority = source.text_integrity_authority()
    # Receipt block addresses are producer-owned; no nearest text or geometric
    # overlap is used to create a door/window association.
    selected = []
    for oid in sorted(native):
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        receipt = source._text_integrity_receipts.get((selector.snapshot_id, oid))
        if receipt is None or (receipt.page_id, receipt.block_no) not in blocks:
            continue
        selected.append(
            dict(
                selector=asdict(selector),
                text_result=asdict(text_authority.resolve_text(selector)),
            )
        )
    if (
        source.published_snapshot_for_revision(published.revision.revision_id)
        != published
    ):
        raise RuntimeError("original source snapshot changed during audit")
    if (
        sha256(
            source._producer._store.source_bytes_by_revision[
                published.revision.revision_id
            ]
        ).hexdigest()
        != digest
    ):
        raise RuntimeError("original source bytes changed during audit")
    return dict(
        source_sha256=digest,
        original_published_snapshot=asdict(published),
        literal_query_tokens=sorted(needles),
        original_native_word_count=len(native),
        original_native_text_blocks=selected,
        filling_role_granted=False,
        physical_identity_transfer_granted=False,
        quantity_granted=False,
        count_granted=False,
        signed_scope_lineage_granted=False,
        scope_limit="Selected native text blocks only; no OCR/image symbol role, schedule completeness or opening association proof.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = original_role_text_audit(args.pdf.read_bytes(), tuple(args.query))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
