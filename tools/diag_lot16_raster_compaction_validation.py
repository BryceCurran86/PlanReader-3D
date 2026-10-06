from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_raster_opening_source_primitives import MAX_PRIMITIVES
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _page12_count(source_bytes: bytes) -> int:
    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_compaction_page12",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-compaction-page12",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=("12",),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("12",),
    )
    return len(published.raster_opening_primitive_observation_ids)


def _page3_raster_openings(source_bytes: bytes) -> tuple[int, tuple[str, ...]]:
    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_compaction_page3",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-compaction-page3",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=("3",),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
    )
    published = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert published is not None

    semantic = composition.semantic_enumeration_result.record
    if semantic is None:
        return 0, ()

    raster_ids: set[str] = set()
    for observation_id in semantic.representative_observation_ids:
        result = composition.physical_opening_authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        record = result.existence_record
        if (
            result.proposition == PHYSICAL_OPENING_EXISTS
            and record is not None
            and record.structural_pattern
            == RASTER_FRAMED_WALL_BAND_INTERRUPTION
        ):
            raster_ids.add(record.record_id)
    return len(raster_ids), tuple(sorted(raster_ids))


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(
            f"source sha mismatch: expected {EXPECTED_SOURCE_SHA}, got {source_sha}"
        )

    page12_count = _page12_count(source_bytes)
    page3_count, page3_ids = _page3_raster_openings(source_bytes)

    payload = {
        "source_sha256": source_sha,
        "max_primitives": MAX_PRIMITIVES,
        "page12_primitive_count": page12_count,
        "page12_under_bound": page12_count <= MAX_PRIMITIVES,
        "page3_raster_framed_opening_count": page3_count,
        "page3_raster_framed_opening_ids": list(page3_ids),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if page12_count > MAX_PRIMITIVES:
        raise SystemExit("page 12 still exceeds raster opening primitive safety bound")
    if page3_count != 14:
        raise SystemExit(
            f"page 3 framed-raster regression: expected 14, got {page3_count}"
        )


if __name__ == "__main__":
    main()
