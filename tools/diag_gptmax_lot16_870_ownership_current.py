from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pb_opening_label_dimension_authority as labels
import pb_opening_label_semantic_authority as semantics
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

        semantic_lines = semantics._trusted_native_lines(source, opening)
        legend, legend_conflicts = semantics._legend_semantics(semantic_lines)
        semantic_matches = []
        for block_no, line_no, semantic_line in semantic_lines:
            if not labels._label_matches_gap(semantic_line, gap):
                continue
            direct_kind, direct_conflict = semantics._explicit_word_kind(semantic_line.text)
            compact_kind, compact_conflict = semantics.classify_compact_source_opening_text(
                semantic_line.text
            )
            tokens = sorted({
                match.group(0).upper()
                for match in semantics._LABEL_CODE_TOKEN_RE.finditer(
                    semantic_line.text or ""
                )
            })
            legend_kinds = {
                token: (None if legend.get(token) is None else legend[token][0])
                for token in tokens
                if token in legend or token in legend_conflicts
            }
            x0, y0, x1, y1 = semantic_line.bbox
            center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
            corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
            along_values = [labels._dot(point, gap.axis) for point in corners]
            cross = labels._dot(center, gap.normal)
            semantic_matches.append({
                "text": semantic_line.text,
                "bbox": list(semantic_line.bbox),
                "observation_ids": list(semantic_line.observation_ids),
                "block_no": block_no,
                "line_no": line_no,
                "direct_kind": direct_kind,
                "direct_conflict": direct_conflict,
                "compact_kind": compact_kind,
                "compact_conflict": compact_conflict,
                "legend_kinds": legend_kinds,
                "along_min": min(along_values),
                "along_max": max(along_values),
                "cross_center": cross,
                "cross_delta": abs(cross - gap.cross_center),
            })
        opening_semantic_result = (
            semantics.OpeningLabelSemanticProducer.from_source_visibility_producer(
                source
            ).publish_scope(selectors[opening_id])
        )

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
            "gap": {
                "axis": list(gap.axis),
                "normal": list(gap.normal),
                "along_min": gap.along_min,
                "along_max": gap.along_max,
                "cross_center": gap.cross_center,
                "cross_spread": gap.cross_spread,
            },
            "matching_870_lines": rows,
            "semantic_matches": semantic_matches,
            "opening_semantic_status": state(opening_semantic_result.status),
            "opening_semantic_reason_codes": list(opening_semantic_result.reason_codes),
            "opening_semantic_evidence": (
                None
                if opening_semantic_result.evidence is None
                else {
                    "semantic_kind": opening_semantic_result.evidence.semantic_kind,
                    "raw_texts": list(opening_semantic_result.evidence.raw_texts),
                    "source_text_observation_ids": list(
                        opening_semantic_result.evidence.source_text_observation_ids
                    ),
                }
            ),
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
