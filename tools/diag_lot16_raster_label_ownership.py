from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_label_ownership",
        producer_version="1",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-label-ownership",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    assert published is not None

    physical = composition.physical_opening_authority
    semantic_producer = OpeningLabelSemanticProducer.from_source_visibility_producer(source)
    dimension_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(source)

    semantic_record = composition.semantic_enumeration_result.record
    representatives = (
        tuple(semantic_record.representative_observation_ids)
        if semantic_record is not None
        else ()
    )

    rows = []
    seen = set()
    for observation_id in representatives:
        selector = _selector(published, observation_id)
        existence = physical.prove_existence(selector)
        record = existence.existence_record
        if (
            existence.status is not EvidenceResolutionStatus.CORROBORATED
            or existence.proposition != PHYSICAL_OPENING_EXISTS
            or record is None
            or record.structural_pattern != RASTER_FRAMED_WALL_BAND_INTERRUPTION
            or record.record_id in seen
        ):
            continue
        seen.add(record.record_id)

        semantic = semantic_producer.publish_scope(selector)
        dimension = dimension_producer.publish_scope(selector)
        semantic_evidence = getattr(semantic, "evidence", None)
        dimension_evidence = getattr(dimension, "evidence", None)
        rows.append({
            "opening_id": record.record_id,
            "aperture_bbox_pt": list(record.aperture_bbox_pt or ()),
            "semantic_status": semantic.status.value,
            "semantic_reason_codes": list(semantic.reason_codes),
            "semantic_kind": (
                None if semantic_evidence is None
                else getattr(semantic_evidence, "semantic_kind", None)
            ),
            "semantic_raw_texts": (
                [] if semantic_evidence is None
                else list(getattr(semantic_evidence, "raw_texts", ()))
            ),
            "dimension_status": dimension.status.value,
            "dimension_reason_codes": list(dimension.reason_codes),
            "dimension_values_mm": (
                [] if dimension_evidence is None
                else list(getattr(dimension_evidence, "dimension_values_mm", ()))
            ),
            "dimension_raw_text": (
                None if dimension_evidence is None
                else getattr(dimension_evidence, "raw_text", None)
            ),
            "dimension_area_m2": (
                None if dimension_evidence is None
                else getattr(dimension_evidence, "area_m2", None)
            ),
        })

    payload = {
        "source_sha256": source_sha,
        "page_id": PAGE_ID,
        "raster_opening_count": len(rows),
        "semantic_status_counts": dict(sorted(Counter(row["semantic_status"] for row in rows).items())),
        "dimension_status_counts": dict(sorted(Counter(row["dimension_status"] for row in rows).items())),
        "semantic_kind_counts": dict(sorted(Counter(str(row["semantic_kind"]) for row in rows).items())),
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
