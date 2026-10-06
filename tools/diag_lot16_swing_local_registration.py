from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_AMBIGUOUS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual_sha}")

    producer = SourceVisibilityProducer(
        producer_method="diag_lot16_swing_local_registration",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="diag-lot16-swing-local-registration",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    primitive_count = len(published.raster_opening_primitive_observation_ids)
    authority = producer.physical_opening_authority()

    records = {}
    conflict_reasons = Counter()
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
            records[result.existence_record.record_id] = result.existence_record
        elif result.status is EvidenceResolutionStatus.CONFLICT:
            for reason in result.reason_codes:
                conflict_reasons[str(reason)] += 1

    framed = sorted(
        record.record_id
        for record in records.values()
        if record.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    )
    swings = sorted(
        record.record_id
        for record in records.values()
        if record.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
    )
    payload = {
        "source_sha256": actual_sha,
        "page_id": PAGE_ID,
        "primitive_count": primitive_count,
        "physical_opening_count": len(records),
        "framed_count": len(framed),
        "swing_count": len(swings),
        "framed_ids": framed,
        "swing_ids": swings,
        "swing_ambiguous_support_count": int(
            conflict_reasons.get(RASTER_DOOR_SWING_AMBIGUOUS, 0)
        ),
        "conflict_reason_counts": dict(sorted(conflict_reasons.items())),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if primitive_count <= 0:
        raise SystemExit("raster primitive universe disappeared")
    if len(framed) != 14:
        raise SystemExit(f"framed regression: expected 14, got {len(framed)}")


if __name__ == "__main__":
    main()
