from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_AMBIGUOUS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


ROOT = Path("documents/sources")
LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def scan_pdf(path: Path) -> dict:
    source_bytes = path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    doc = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page_ids = tuple(str(index + 1) for index in range(doc.page_count))
    finally:
        doc.close()

    producer = SourceVisibilityProducer(
        producer_method="diag_raster_swing_real_source",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=f"diag:{path.as_posix()}",
        source_bytes=source_bytes,
        source_locator=str(path),
        page_ids=page_ids,
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=page_ids,
    )
    authority = producer.physical_opening_authority()

    unique_records = {}
    conflict_by_page = Counter()
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            record = result.existence_record
            unique_records[record.record_id] = record
        elif (
            result.status is EvidenceResolutionStatus.CONFLICT
            and RASTER_DOOR_SWING_AMBIGUOUS in result.reason_codes
            and result.source_observation is not None
            and result.source_observation.observation is not None
        ):
            conflict_by_page[str(result.source_observation.observation.page_id)] += 1

    by_page = defaultdict(Counter)
    ids_by_page = defaultdict(lambda: defaultdict(list))
    for record in unique_records.values():
        page_id = str(record.page_id)
        by_page[page_id][record.structural_pattern] += 1
        ids_by_page[page_id][record.structural_pattern].append(record.record_id)

    page_rows = {}
    for page_id in sorted(set(by_page) | set(conflict_by_page), key=lambda x: int(x) if x.isdigit() else x):
        page_rows[page_id] = {
            "framed_count": int(by_page[page_id][RASTER_FRAMED_WALL_BAND_INTERRUPTION]),
            "swing_count": int(by_page[page_id][RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION]),
            "swing_ambiguous_support_count": int(conflict_by_page[page_id]),
            "framed_ids": sorted(ids_by_page[page_id][RASTER_FRAMED_WALL_BAND_INTERRUPTION]),
            "swing_ids": sorted(ids_by_page[page_id][RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION]),
        }

    return {
        "path": path.as_posix(),
        "source_sha256": source_sha,
        "page_count": len(page_ids),
        "raster_primitive_count": len(published.raster_opening_primitive_observation_ids),
        "framed_count": sum(row["framed_count"] for row in page_rows.values()),
        "swing_count": sum(row["swing_count"] for row in page_rows.values()),
        "swing_ambiguous_support_count": sum(
            row["swing_ambiguous_support_count"] for row in page_rows.values()
        ),
        "pages": page_rows,
    }


def main() -> None:
    pdfs = tuple(sorted(ROOT.rglob("*.pdf")))
    if not pdfs:
        raise SystemExit("no source PDFs found")

    rows = []
    for path in pdfs:
        row = scan_pdf(path)
        rows.append(row)
        print(
            f"SCANNED {row['path']} pages={row['page_count']} "
            f"framed={row['framed_count']} swing={row['swing_count']} "
            f"ambiguous={row['swing_ambiguous_support_count']}",
            flush=True,
        )

    lot16_rows = [row for row in rows if row["source_sha256"] == LOT16_SHA]
    payload = {
        "pdf_count": len(rows),
        "total_pages": sum(row["page_count"] for row in rows),
        "total_framed": sum(row["framed_count"] for row in rows),
        "total_swing": sum(row["swing_count"] for row in rows),
        "total_swing_ambiguous_support": sum(
            row["swing_ambiguous_support_count"] for row in rows
        ),
        "lot16_sha_found": len(lot16_rows) == 1,
        "lot16": lot16_rows[0] if len(lot16_rows) == 1 else None,
        "non_lot16_swing_positives": [
            {
                "path": row["path"],
                "source_sha256": row["source_sha256"],
                "swing_count": row["swing_count"],
                "pages": {
                    page_id: page
                    for page_id, page in row["pages"].items()
                    if page["swing_count"]
                },
            }
            for row in rows
            if row["source_sha256"] != LOT16_SHA and row["swing_count"]
        ],
        "rows": rows,
    }
    print("FINAL_JSON")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
