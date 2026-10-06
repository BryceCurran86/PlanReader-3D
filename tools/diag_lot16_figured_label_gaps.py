from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def value(status) -> str:
    return str(getattr(status, "value", status))


def main() -> None:
    payload = PDF.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_figured_label_gaps",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-figured-label-gaps",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    wall = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    semantic_record = wall.semantic_enumeration_result.record
    if semantic_record is None:
        raise SystemExit("semantic opening enumeration unavailable")

    physical = wall.physical_opening_authority
    selectors = {}
    existence = {}
    for observation_id in semantic_record.representative_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.existence_record is not None
        ):
            oid = result.existence_record.record_id
            selectors[oid] = selector
            existence[oid] = result.existence_record

    dim = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    sem = OpeningLabelSemanticProducer.from_source_visibility_producer(source)
    host = {
        str(trace.opening_identity_id): trace
        for trace in wall.opening_bindings
        if trace.opening_identity_id
    }
    frames = {
        str(trace.opening_identity_id): trace
        for trace in wall.host_frames
        if trace.opening_identity_id
    }

    rows = []
    for oid in sorted(selectors):
        d = dim.publish_scope(selectors[oid])
        s = sem.publish_scope(selectors[oid])
        de = getattr(d, "evidence", None)
        se = getattr(s, "evidence", None)
        h = host.get(oid)
        f = frames.get(oid)
        record = existence[oid]
        if (
            de is None
            and se is None
            and not (h is not None and h.host_wall_id)
            and record.structural_pattern != "raster_framed_wall_band_interruption"
        ):
            continue
        rows.append({
            "opening_id": oid,
            "structural_pattern": record.structural_pattern,
            "aperture_bbox_pt": list(record.aperture_bbox_pt) if record.aperture_bbox_pt else None,
            "dimension_status": value(d.status),
            "dimension_reasons": list(d.reason_codes),
            "dimension_raw_text": getattr(de, "raw_text", None),
            "dimension_values_mm": list(getattr(de, "dimension_values_mm", ()) or ()),
            "dimension_semantic_kind": getattr(de, "semantic_kind", None),
            "dimension_area_m2": getattr(de, "area_m2", None),
            "semantic_status": value(s.status),
            "semantic_reasons": list(s.reason_codes),
            "semantic_kind": getattr(se, "semantic_kind", None),
            "semantic_raw_text": getattr(se, "raw_text", None),
            "semantic_source_text_ids": list(getattr(se, "source_text_observation_ids", ()) or ()),
            "host_status": None if h is None else value(h.status),
            "host_reasons": [] if h is None else list(h.reason_codes),
            "host_wall_id": None if h is None else h.host_wall_id,
            "host_frame_status": None if f is None else value(f.status),
            "host_frame_reasons": [] if f is None else list(f.reason_codes),
            "host_frame_record_id": None if f is None else f.record_id,
        })

    print(json.dumps({
        "source_sha256": actual,
        "physical_opening_count": len(selectors),
        "interesting_row_count": len(rows),
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
