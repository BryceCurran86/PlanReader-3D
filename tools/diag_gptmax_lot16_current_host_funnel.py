from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import _resolve_two_face_lineage_host
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"
SCOPE_ID = "wall-source:page-3"


def state(value):
    return str(getattr(value, "value", value))


def main():
    source_bytes = PDF.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{EXPECTED_SHA[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(initial.revision.revision_id)
    if current is None:
        raise SystemExit("missing current source snapshot")

    wall_result = composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=SCOPE_ID,
        )
    )

    physical = composition.physical_opening_authority
    binding_status_counts = Counter()
    binding_reason_counts = Counter()
    pattern_counts = Counter()
    pattern_host_counts = Counter()
    pattern_reason_counts = {}
    exact_helper_status_counts = Counter()
    exact_helper_reason_counts = Counter()
    rows = []
    label_dimension = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    swing_label_status_counts = Counter()
    swing_label_reason_counts = Counter()

    for trace in composition.opening_bindings:
        binding_status_counts[state(trace.status)] += 1
        for reason in trace.reason_codes:
            binding_reason_counts[str(reason)] += 1

        opening_selector = ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        existence = physical.prove_existence(opening_selector)
        record = existence.existence_record
        pattern = None if record is None else record.structural_pattern
        label_result = None
        if record is not None and pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION:
            label_result = label_dimension.publish_scope(opening_selector)
            swing_label_status_counts[state(label_result.status)] += 1
            for reason in label_result.reason_codes:
                swing_label_reason_counts[str(reason)] += 1
        pattern_counts[str(pattern)] += 1
        if trace.host_wall_id:
            pattern_host_counts[str(pattern)] += 1
        bucket = pattern_reason_counts.setdefault(str(pattern), Counter())
        for reason in trace.reason_codes:
            bucket[str(reason)] += 1

        helper_status = None
        helper_reasons = ()
        if (
            record is not None
            and record.structural_pattern == JAMB_BOUNDED_TWO_FACE_INTERRUPTION
        ):
            helper = _resolve_two_face_lineage_host(
                physical,
                record,
                wall_result.records,
                wall_result.equivalence,
            )
            if helper is not None:
                helper_status = state(helper.status)
                helper_reasons = helper.reason_codes
                exact_helper_status_counts[helper_status] += 1
                for reason in helper.reason_codes:
                    exact_helper_reason_counts[str(reason)] += 1

        rows.append({
            "opening_identity_id": trace.opening_identity_id,
            "representative_observation_id": trace.representative_observation_id,
            "structural_pattern": pattern,
            "host_wall_id": trace.host_wall_id,
            "binding_status": state(trace.status),
            "binding_reason_codes": list(trace.reason_codes),
            "exact_helper_status": helper_status,
            "exact_helper_reason_codes": list(helper_reasons),
            "label_dimension_status": (
                None if label_result is None else state(label_result.status)
            ),
            "label_dimension_reason_codes": (
                [] if label_result is None else list(label_result.reason_codes)
            ),
            "label_dimension_values_mm": (
                None
                if label_result is None or label_result.evidence is None
                else list(label_result.evidence.dimension_values_mm)
            ),
            "label_raw_text": (
                None
                if label_result is None or label_result.evidence is None
                else label_result.evidence.raw_text
            ),
            "label_semantic_kind": (
                None
                if label_result is None or label_result.evidence is None
                else label_result.evidence.semantic_kind
            ),
        })

    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    areas = publish_live_opening_area_quantities(voids)

    payload = {
        "source_sha256": actual,
        "snapshot_id": current.snapshot.snapshot_id,
        "semantic_status": state(composition.semantic_enumeration_result.status),
        "opening_count": len(composition.opening_bindings),
        "host_bound_count": sum(1 for trace in composition.opening_bindings if trace.host_wall_id),
        "binding_status_counts": dict(binding_status_counts.most_common()),
        "binding_reason_counts": dict(binding_reason_counts.most_common()),
        "structural_pattern_counts": dict(pattern_counts.most_common()),
        "pattern_host_counts": dict(pattern_host_counts.most_common()),
        "pattern_reason_counts": {
            key: dict(value.most_common())
            for key, value in pattern_reason_counts.items()
        },
        "wall_scope_status": state(wall_result.status),
        "wall_scope_complete": bool(wall_result.scope_complete),
        "wall_record_count": len(wall_result.records),
        "equivalence_ambiguous_wall_count": len(wall_result.equivalence.ambiguous_wall_ids),
        "exact_helper_status_counts": dict(exact_helper_status_counts.most_common()),
        "exact_helper_reason_counts": dict(exact_helper_reason_counts.most_common()),
        "swing_label_status_counts": dict(swing_label_status_counts.most_common()),
        "swing_label_reason_counts": dict(swing_label_reason_counts.most_common()),
        "canonical_opening_count": len(voids.canonical_openings),
        "swing_canonical_opening_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
        ),
        "swing_host_frame_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.host_frame_record_id
        ),
        "swing_host_bound_canonical_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.host_wall_id
        ),
        "swing_width_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.width_m is not None
        ),
        "swing_height_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.height_m is not None
        ),
        "swing_kind_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.opening_kind in {"door", "window"}
        ),
        "swing_kind_counts": dict(Counter(
            str(opening.opening_kind or "<none>")
            for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
        ).most_common()),
        "swing_area_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.area_m2 is not None
        ),
        "area_resolved_count": sum(1 for opening in voids.canonical_openings if opening.area_m2 is not None),
        "opening_area_quantity_count": len(areas),
        "opening_area_values": sorted(float(q.value) for q in areas),
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
