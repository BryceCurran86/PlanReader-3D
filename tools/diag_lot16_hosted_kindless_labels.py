from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionProducer,
    _gap_span_for_opening,
    _label_matches_gap,
    parse_opening_label_dimensions,
)
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual_sha}")

    doc = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page_count = int(doc.page_count)
    finally:
        doc.close()

    all_indices = tuple(range(page_count))
    scope = source_floor_plan_topology_scope(PDF, all_indices)
    topology_indices = (
        tuple(scope.topology_page_indices() or ())
        if scope is not None
        else all_indices
    )
    topology_page_ids = tuple(str(i + 1) for i in topology_indices)
    all_page_ids = tuple(str(i + 1) for i in all_indices)
    evidence_page_ids = tuple(
        page_id for page_id in all_page_ids
        if page_id not in topology_page_ids
    )

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_hosted_kindless_labels",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-hosted-kindless-labels",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=all_page_ids,
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_page_ids,
        evidence_page_ids=evidence_page_ids,
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    semantic_record = wall_opening.semantic_enumeration_result.record
    if semantic_record is None:
        raise SystemExit("semantic opening enumeration unavailable")

    representatives = dict(zip(
        semantic_record.physical_opening_record_ids,
        semantic_record.representative_observation_ids,
    ))
    current = source.published_snapshot_for_revision(
        wall_opening.semantic_enumeration_result.record.revision_id
    )
    if current is None:
        raise SystemExit("published source snapshot unavailable")

    physical = wall_opening.physical_opening_authority
    dimensions = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    semantics = OpeningLabelSemanticProducer.from_source_visibility_producer(source)

    rows = []
    for canonical in voids.canonical_openings:
        if not canonical.host_wall_id or canonical.opening_kind:
            continue

        physical_id = str(canonical.physical_opening_id or "")
        representative_id = representatives.get(physical_id)
        if not representative_id:
            continue

        selector = ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=representative_id,
        )
        result = physical.prove_existence(selector)
        opening = result.existence_record
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or opening is None
        ):
            continue

        gap = _gap_span_for_opening(source, opening)
        lines = dimensions._trusted_text_lines_for_opening(opening)
        owned = []
        if gap is not None:
            for line in lines:
                if not _label_matches_gap(line, gap):
                    continue
                parsed = parse_opening_label_dimensions(line.text)
                owned.append({
                    "text": line.text,
                    "bbox": list(line.bbox),
                    "observation_ids": list(line.observation_ids),
                    "parsed": None if parsed is None else {
                        "raw_text": parsed.raw_text,
                        "dimension_tokens": list(parsed.dimension_tokens),
                        "dimension_values_mm": list(parsed.dimension_values_mm),
                        "suffix_text": parsed.suffix_text,
                        "semantic_kind": parsed.semantic_kind,
                        "compact_hundreds_present": bool(parsed.compact_hundreds_present),
                        "compact_hundreds_used": bool(parsed.compact_hundreds_used),
                    },
                })

        semantic = semantics.publish_scope(selector)
        dimension = dimensions.publish_scope(selector)
        rows.append({
            "physical_opening_id": physical_id,
            "structural_pattern": opening.structural_pattern,
            "page_id": opening.page_id,
            "aperture_bbox_pt": opening.aperture_bbox_pt,
            "host_wall_id": canonical.host_wall_id,
            "host_frame_record_id": canonical.host_frame_record_id,
            "semantic_status": semantic.status.value,
            "semantic_reason_codes": list(semantic.reason_codes),
            "semantic_kind": (
                None if semantic.evidence is None
                else semantic.evidence.semantic_kind
            ),
            "dimension_status": dimension.status.value,
            "dimension_reason_codes": list(dimension.reason_codes),
            "dimension_raw_text": (
                None if dimension.evidence is None
                else dimension.evidence.raw_text
            ),
            "dimension_values_mm": (
                [] if dimension.evidence is None
                else list(dimension.evidence.dimension_values_mm)
            ),
            "dimension_area_m2": (
                None if dimension.evidence is None
                else dimension.evidence.area_m2
            ),
            "owned_text_lines": owned,
        })

    print(json.dumps({
        "source_sha256": actual_sha,
        "topology_page_ids": list(topology_page_ids),
        "hosted_kindless_count": len(rows),
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
