from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    _row_groups_for_page,
    _schedule_entries_for_page,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "28"
TARGETS = ("M-AMB", "F-AMB")

def norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())

def main() -> int:
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="gpt2-ambulant-schedule-row-diag",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot unavailable")

    integrity = source.text_integrity_authority()
    trusted = []
    for observation_id in current.text_observation_ids:
        result = integrity.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.trusted_text is None
            or result.receipt is None
            or str(result.receipt.page_id) != PAGE_ID
        ):
            continue
        trusted.append(
            (
                observation_id,
                result.trusted_text,
                tuple(float(v) for v in result.receipt.geometry),
            )
        )

    rows = _row_groups_for_page(trusted)
    parsed = []
    for entry, ids in _schedule_entries_for_page(rows, int(PAGE_ID)):
        blob = norm(entry.description)
        if not any(target in blob for target in TARGETS):
            continue
        parsed.append(
            {
                "type_mark": entry.type_mark,
                "description": entry.description,
                "width_mm": entry.width_mm,
                "height_mm": entry.height_mm,
                "count": entry.count if entry.count_explicit else None,
                "count_explicit": bool(entry.count_explicit),
                "dimension_basis": entry.dimension_basis,
                "basis_source": entry.basis_source,
                "schedule_row_observation_ids": list(ids),
            }
        )

    print(json.dumps({
        "source_sha256": source_sha,
        "trusted_text_observation_count": len(trusted),
        "schedule_row_group_count": len(rows),
        "matched_schedule_rows": parsed,
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
