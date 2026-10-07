from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pb_opening_label_dimension_authority as labels
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def state(value):
    return str(getattr(value, "value", value))


def main():
    data = PDF.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    assert actual == EXPECTED_SHA

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{actual[:32]}",
        source_bytes=data,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(initial.revision.revision_id)
    assert current is not None

    physical = composition.physical_opening_authority
    semantic = composition.semantic_enumeration_result.record
    if semantic is None:
        print(json.dumps({
            "source_sha256": actual,
            "snapshot_id": current.snapshot.snapshot_id,
            "semantic_status": state(composition.semantic_enumeration_result.status),
            "semantic_reason_codes": list(composition.semantic_enumeration_result.reason_codes),
            "physical_opening_count": 0,
            "error": "semantic_enumeration_unavailable",
        }, indent=2, sort_keys=True))
        return

    openings = {}
    selectors = {}
    prove_status_counts = Counter()
    for obs_id in semantic.representative_observation_ids:
        selector = ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=obs_id,
        )
        result = physical.prove_existence(selector)
        prove_status_counts[state(result.status)] += 1
        record = result.existence_record
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and record is not None
            and str(record.page_id) == PAGE_ID
        ):
            openings[record.record_id] = record
            selectors[record.record_id] = selector

    if not openings:
        print(json.dumps({
            "source_sha256": actual,
            "snapshot_id": current.snapshot.snapshot_id,
            "semantic_status": state(composition.semantic_enumeration_result.status),
            "semantic_reason_codes": list(composition.semantic_enumeration_result.reason_codes),
            "semantic_representative_count": len(semantic.representative_observation_ids),
            "prove_status_counts": dict(prove_status_counts),
            "physical_opening_count": 0,
            "error": "no_current_snapshot_openings",
        }, indent=2, sort_keys=True))
        return

    producer = labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    sample = next(iter(openings.values()))
    trusted = producer._trusted_text_lines_for_opening(sample)

    parsed_lines = []
    parsed_870 = []
    for line in trusted:
        parsed = labels.parse_opening_label_dimensions(line.text)
        if parsed is None:
            continue
        row = {
            "text": line.text,
            "bbox": list(line.bbox),
            "observation_ids": list(line.observation_ids),
            "dimension_values_mm": list(parsed.dimension_values_mm),
            "semantic_kind": parsed.semantic_kind,
        }
        parsed_lines.append(row)
        if tuple(parsed.dimension_values_mm) == (870.0,):
            parsed_870.append(row)

    matched = []
    gap_reason_counts = Counter()
    publish_reason_counts = Counter()
    publish_status_counts = Counter()
    for opening_id, opening in openings.items():
        gap = labels._gap_span_for_opening(source, opening)
        if gap is None:
            gap_reason_counts["gap_unavailable"] += 1
            continue
        rows = []
        for line in trusted:
            parsed = labels.parse_opening_label_dimensions(line.text)
            if parsed is None or tuple(parsed.dimension_values_mm) != (870.0,):
                continue
            if labels._label_matches_gap(line, gap):
                rows.append({
                    "text": line.text,
                    "bbox": list(line.bbox),
                    "observation_ids": list(line.observation_ids),
                })
        if not rows:
            gap_reason_counts["no_870_label_matches_gap"] += 1
            continue

        result = producer.publish_scope(selectors[opening_id])
        publish_status_counts[state(result.status)] += 1
        for reason in result.reason_codes:
            publish_reason_counts[reason] += 1
        matched.append({
            "opening_id": opening_id,
            "host_bound": any(
                trace.opening_identity_id == opening_id and trace.host_wall_id
                for trace in composition.opening_bindings
            ),
            "structural_pattern": opening.structural_pattern,
            "aperture_bbox_pt": list(opening.aperture_bbox_pt) if opening.aperture_bbox_pt else None,
            "matching_870_lines": rows,
            "published_status": state(result.status),
            "published_reason_codes": list(result.reason_codes),
            "published_evidence": None if result.evidence is None else {
                "raw_text": result.evidence.raw_text,
                "dimension_values_mm": list(result.evidence.dimension_values_mm),
                "semantic_kind": result.evidence.semantic_kind,
            },
        })

    print(json.dumps({
        "source_sha256": actual,
        "snapshot_id": current.snapshot.snapshot_id,
        "semantic_status": state(composition.semantic_enumeration_result.status),
        "semantic_reason_codes": list(composition.semantic_enumeration_result.reason_codes),
        "semantic_representative_count": len(semantic.representative_observation_ids),
        "physical_opening_count": len(openings),
        "host_bound_count": sum(1 for trace in composition.opening_bindings if trace.host_wall_id),
        "prove_status_counts": dict(prove_status_counts),
        "trusted_text_line_count": len(trusted),
        "parsed_dimension_line_count": len(parsed_lines),
        "parsed_870_line_count": len(parsed_870),
        "parsed_870_lines": parsed_870,
        "gap_reason_counts": dict(gap_reason_counts),
        "opening_870_match_count": len(matched),
        "publish_status_counts": dict(publish_status_counts),
        "publish_reason_counts": dict(publish_reason_counts),
        "matches": matched,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
