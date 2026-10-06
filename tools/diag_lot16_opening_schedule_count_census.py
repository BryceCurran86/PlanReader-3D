from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    _row_groups_for_page,
    _schedule_entries_for_page,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def main() -> None:
    source_bytes = PDF.read_bytes()
    sha = hashlib.sha256(source_bytes).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        page_ids = tuple(str(index + 1) for index in range(doc.page_count))

    source = SourceVisibilityProducer(
        producer_method="diag-lot16-opening-schedule-count-census",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-opening-schedule-count-census",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=page_ids,
    )
    integrity = source.text_integrity_authority()
    trusted = defaultdict(list)
    for observation_id in published.text_observation_ids:
        result = integrity.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = getattr(result, "receipt", None)
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.trusted_text is None
            or receipt is None
        ):
            continue
        trusted[str(receipt.page_id)].append(
            (
                observation_id,
                result.trusted_text,
                tuple(float(value) for value in receipt.geometry),
            )
        )

    rows = []
    for page_id in page_ids:
        grouped = _row_groups_for_page(trusted.get(page_id, ()))
        entries = _schedule_entries_for_page(grouped, int(page_id))
        for entry, observation_ids in entries:
            rows.append({
                "page_id": page_id,
                "type_mark": entry.type_mark,
                "width_mm": entry.width_mm,
                "height_mm": entry.height_mm,
                "description": entry.description,
                "count": entry.count,
                "count_explicit": bool(entry.count_explicit),
                "dimension_basis": entry.dimension_basis,
                "basis_source": entry.basis_source,
                "parse_source": entry.parse_source,
                "observation_ids": list(observation_ids),
            })

    explicit = [row for row in rows if row["count_explicit"]]
    print(json.dumps({
        "source_sha256": sha,
        "page_count": len(page_ids),
        "trusted_text_page_count": len(trusted),
        "schedule_entry_count": len(rows),
        "explicit_count_entry_count": len(explicit),
        "explicit_count_entries": explicit,
        "all_schedule_entries": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
