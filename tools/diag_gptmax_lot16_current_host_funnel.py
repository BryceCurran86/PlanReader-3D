from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
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
ALL_PAGE_IDS = tuple(str(index) for index in range(1, 14))
EVIDENCE_PAGE_IDS = tuple(page_id for page_id in ALL_PAGE_IDS if page_id != PAGE_ID)
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
        page_ids=ALL_PAGE_IDS,
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
        evidence_page_ids=EVIDENCE_PAGE_IDS,
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

    for trace in composition.opening_bindings:
        binding_status_counts[state(trace.status)] += 1
        for reason in trace.reason_codes:
            binding_reason_counts[str(reason)] += 1

        existence = physical.prove_existence(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=trace.representative_observation_id,
            )
        )
        record = existence.existence_record
        pattern = None if record is None else record.structural_pattern
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
        })

    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    areas = publish_live_opening_area_quantities(voids)

    void_trace_by_id = {
        trace.opening_identity_id: trace
        for trace in voids.traces
    }
    binding_row_by_id = {
        row["opening_identity_id"]: row
        for row in rows
    }
    swing_openings = [
        opening
        for opening in voids.canonical_openings
        if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
    ]
    swing_rows = []
    for opening in swing_openings:
        trace = void_trace_by_id.get(opening.physical_opening_id)
        binding_row = binding_row_by_id.get(opening.physical_opening_id, {})
        swing_rows.append({
            "physical_opening_id": opening.physical_opening_id,
            "representative_observation_id": opening.representative_observation_id,
            "host_wall_id": opening.host_wall_id,
            "binding_status": binding_row.get("binding_status"),
            "binding_reason_codes": binding_row.get("binding_reason_codes", []),
            "opening_kind": opening.opening_kind,
            "type_mark": opening.type_mark,
            "width_m": opening.width_m,
            "height_m": opening.height_m,
            "area_m2": opening.area_m2,
            "area_basis": opening.area_basis,
            "geometry_complete": opening.geometry_complete,
            "schedule_declared_width_mm": opening.schedule_declared_width_mm,
            "schedule_declared_height_mm": opening.schedule_declared_height_mm,
            "schedule_binding_record_id": opening.schedule_binding_record_id,
            "width_status": None if trace is None else state(trace.width_status),
            "width_reason_codes": [] if trace is None else list(trace.width_reason_codes),
            "height_status": None if trace is None else state(trace.height_status),
            "height_reason_codes": [] if trace is None else list(trace.height_reason_codes),
            "vertical_status": None if trace is None else state(trace.vertical_status),
            "vertical_reason_codes": [] if trace is None else list(trace.vertical_reason_codes),
            "schedule_binding_status": (
                None if trace is None else state(trace.schedule_binding_status)
            ),
            "schedule_binding_reason_codes": (
                [] if trace is None else list(trace.schedule_binding_reason_codes)
            ),
            "void_status": None if trace is None else state(trace.void_status),
            "void_reason_codes": [] if trace is None else list(trace.void_reason_codes),
        })

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
        "canonical_opening_count": len(voids.canonical_openings),
        "area_resolved_count": sum(1 for opening in voids.canonical_openings if opening.area_m2 is not None),
        "opening_area_quantity_count": len(areas),
        "opening_area_values": sorted(float(q.value) for q in areas),
        "swing_canonical_opening_count": len(swing_openings),
        "swing_host_bound_count": sum(1 for opening in swing_openings if opening.host_wall_id),
        "swing_kind_resolved_count": sum(
            1 for opening in swing_openings
            if opening.opening_kind in {"door", "window"}
        ),
        "swing_width_resolved_count": sum(
            1 for opening in swing_openings if opening.width_m is not None
        ),
        "swing_height_resolved_count": sum(
            1 for opening in swing_openings if opening.height_m is not None
        ),
        "swing_area_resolved_count": sum(
            1 for opening in swing_openings if opening.area_m2 is not None
        ),
        "swing_rows": swing_rows,
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
