"""Read-only source-owned physical, canonical and measurement authority handoff."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import ObservationSelector
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_source_room_face_authority import build_source_room_face_authority, SourceRoomFaceSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def source_stage_report(source_bytes: bytes, *, page_ids: tuple[str, ...],
                        source_all_pages: bool = False) -> dict:
    sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=None if source_all_pages else page_ids,
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=page_ids,
    )
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    if published is None:
        raise RuntimeError("source snapshot unavailable")
    visibility = source.authority()
    rows = visibility.authenticated_visible_observations(published)
    selectors = {}
    for oid, observation in rows:
        if str(observation.page_id) in page_ids:
            selectors.setdefault(str(observation.page_id), ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id, source_sha256=sha,
                snapshot_id=published.snapshot.snapshot_id, observation_id=oid,
            ))
    native_closures = [
        asdict(composition.physical_opening_authority.assess_visible_candidate_closure(selectors[page]))
        for page in sorted(selectors, key=int)
    ]
    raster_audit = getattr(composition.physical_opening_authority,
                           "assess_raster_candidate_closure", None)
    raster_selectors = {}
    for oid in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=sha,
            snapshot_id=published.snapshot.snapshot_id, observation_id=oid,
        )
        result = visibility.resolve_raster_opening_primitive(selector)
        if result.observation is None:
            raise RuntimeError("isolated raster source ownership unavailable")
        page = str(result.observation.page_id)
        if page in page_ids:
            raster_selectors.setdefault(page, selector)
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=composition,
    )
    label_dimensions = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    label_semantics = OpeningLabelSemanticProducer.from_source_visibility_producer(source)
    label_dimension_traces = []
    label_semantic_traces = []
    for row in composition.opening_bindings:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=sha,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=row.representative_observation_id,
        )
        label_dimension_traces.append({"opening_identity_id": row.opening_identity_id,
                                       "result": asdict(label_dimensions.publish_scope(selector))})
        label_semantic_traces.append({"opening_identity_id": row.opening_identity_id,
                                      "result": asdict(label_semantics.publish_scope(selector))})
    room_authority = build_source_room_face_authority(composition.physical_wall_candidate_authority)
    room_scopes = []
    wall_scopes = []
    for scope in composition.physical_wall_candidate_authority._scopes.values():
        if str(scope.page_id) not in page_ids:
            continue
        wall_selector = composition.physical_wall_candidate_authority._selector_for_result(scope)
        wall_scopes.append(asdict(
            composition.physical_wall_candidate_authority.resolve_scope(wall_selector)))
        selector = SourceRoomFaceSelector(
            document_id=scope.document_id, revision_id=scope.revision_id,
            source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
            page_id=scope.page_id, decision_scope_id=scope.decision_scope_id,
        )
        room_scopes.append({"selector": asdict(selector),
                            "result": asdict(room_authority.resolve_scope(selector))})
    return {
        "source_sha256": sha,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "source_decode_coverage": asdict(published.coverage),
        "all_source_pages_requested": source_all_pages,
        "selected_geometry_page_ids": tuple(composition.page_ids),
        "primitive_safety_cap": MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "composition_status": composition.status.value,
        "composition_reason_codes": composition.reason_codes,
        "semantic_inventory": asdict(composition.semantic_enumeration_result),
        "native_candidate_closures": native_closures,
        "raster_candidate_audit_available": raster_audit is not None,
        "raster_candidate_closures": (
            [asdict(raster_audit(raster_selectors[page]))
             for page in sorted(raster_selectors, key=int)]
            if raster_audit is not None else None
        ),
        "opening_bindings": [asdict(row) for row in composition.opening_bindings],
        "host_frame_traces": [asdict(row) for row in composition.host_frames],
        "resolved_host_frame_evidence": [
            asdict(result.evidence)
            for selector in composition.host_frame_selectors.values()
            if (result := composition.opening_host_frame_authority.resolve(selector)).evidence is not None
        ],
        "canonical_openings": [row.to_dict() for row in voids.canonical_openings],
        "opening_measurement_traces": [asdict(row) for row in voids.traces],
        "opening_figured_label_traces": label_dimension_traces,
        "opening_label_semantic_traces": label_semantic_traces,
        "opening_void_status": voids.status.value,
        "opening_void_reason_codes": voids.reason_codes,
        "source_owned_wall_scopes": wall_scopes,
        "source_room_face_scopes": room_scopes,
        "summary": {
            "physical_existence_claims": len(composition.opening_bindings),
            "authenticated_hosts": sum(bool(row.host_wall_id) for row in composition.opening_bindings),
            "resolved_source_frames": sum(bool(row.record_id) for row in composition.host_frames),
            "canonical_opening_records": len(voids.canonical_openings),
            "complete_opening_geometry_records": sum(row.geometry_complete for row in voids.canonical_openings),
            "canonical_opening_area_records": sum(row.area_m2 is not None for row in voids.canonical_openings),
            "label_dimension_reason_counts": dict(Counter(
                reason for row in label_dimension_traces for reason in row["result"]["reason_codes"])),
            "label_semantic_reason_counts": dict(Counter(
                reason for row in label_semantic_traces for reason in row["result"]["reason_codes"])),
            "width_reason_counts": dict(Counter(reason for row in voids.traces for reason in row.width_reason_codes)),
            "height_reason_counts": dict(Counter(reason for row in voids.traces for reason in row.height_reason_codes)),
            "schedule_reason_counts": dict(Counter(reason for row in voids.traces for reason in row.schedule_binding_reason_codes)),
            "room_scope_reason_counts": dict(Counter(
                reason for row in room_scopes for reason in row["result"]["reason_codes"])),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--source-all-pages", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = source_stage_report(args.pdf.read_bytes(),
        page_ids=tuple(sorted(set(args.page_id), key=int)),
        source_all_pages=args.source_all_pages)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True,
                                      default=lambda value: value.value) + "\n")
    print(json.dumps({"source_sha256": report["source_sha256"], **report["summary"]}))


if __name__ == "__main__":
    main()
