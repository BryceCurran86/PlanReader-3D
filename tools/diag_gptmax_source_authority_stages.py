"""Read-only source-owned physical, canonical and measurement authority handoff."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import ObservationSelector
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    audit_source_room_face_owned_witnesses,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_migration_contracts import EvidenceResolutionStatus


def _opening_identity_text_receipts(source, published, label_traces) -> list[dict]:
    """Reauthenticate owned label locations; no benchmark or quantity inputs."""
    integrity = source.text_integrity_authority()
    rows = []
    for trace in label_traces:
        result = trace["result"]
        evidence = result.get("evidence")
        if result["status"] != EvidenceResolutionStatus.CORROBORATED or evidence is None:
            continue
        opening_id = trace["opening_identity_id"]
        ids = tuple(evidence["source_text_observation_ids"])
        if (evidence["opening_record_id"] != opening_id or not ids
                or len(ids) != len(set(ids))):
            raise ValueError("opening identity label source ownership invalid")
        receipts = []
        for observation_id in ids:
            if observation_id not in published.text_observation_ids:
                raise ValueError("opening label observation outside original text universe")
            selector = ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
            resolved = integrity.resolve_text(selector)
            receipt = resolved.receipt
            if (resolved.status is not EvidenceResolutionStatus.CORROBORATED
                    or not resolved.trusted_text or receipt is None or not receipt.trusted):
                raise ValueError("opening label original text integrity unavailable")
            if (receipt.parent_observation_id != observation_id
                    or receipt.document_id != selector.document_id
                    or receipt.revision_id != selector.revision_id
                    or receipt.source_sha256 != selector.source_sha256
                    or str(receipt.page_id) != str(evidence["page_id"])):
                raise ValueError("opening label original text lineage contradicts owner")
            bbox = receipt.geometry
            if (len(bbox) != 4 or not all(math.isfinite(v) for v in bbox)
                    or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]):
                raise ValueError("opening label original text box invalid")
            receipts.append(asdict(receipt))
        boxes = [r["geometry"] for r in receipts]
        rows.append({
            "opening_identity_id": opening_id,
            "figured_label_evidence_id": evidence["evidence_id"],
            "source_text_observation_ids": ids,
            "source_text_integrity_receipts": receipts,
            "label_bbox_pdf_pt": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                                  max(b[2] for b in boxes), max(b[3] for b in boxes)],
            "snapshot_id": published.snapshot.snapshot_id,
            "location_is_reauthenticated_source_receipt": True,
        })
    if source.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise ValueError("opening label source snapshot changed during export")
    return sorted(rows, key=lambda r: r["opening_identity_id"])


def source_stage_report(source_bytes: bytes, *, page_ids: tuple[str, ...],
                        source_all_pages: bool = False,
                        include_identity_text_receipts: bool = False,
                        include_raw_candidate_source_groups: bool = False,
                        include_room_face_ownership_witnesses: bool = False,
                        include_unhosted_raster_flank_source: bool = False) -> dict:
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
    room_ownership_witness_scopes = []
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
        if include_room_face_ownership_witnesses:
            room_ownership_witness_scopes.append({
                "selector": asdict(selector),
                "owned_face_witnesses": list(
                    audit_source_room_face_owned_witnesses(scope)
                ),
            })
    report = {
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
    if include_identity_text_receipts:
        report["opening_identity_text_receipts"] = _opening_identity_text_receipts(
            source, published, label_dimension_traces,
        )
    if include_room_face_ownership_witnesses:
        report["source_room_face_owned_witness_scopes"] = room_ownership_witness_scopes
    if include_unhosted_raster_flank_source:
        from tools.diag_gptmax_raster_unhosted_flank_source import (
            audit_g17_unhosted_flank_original_ancestry,
        )
        report["unhosted_raster_flank_source_receipts"] = (
            audit_g17_unhosted_flank_original_ancestry(
                source, published, composition,
            )
        )
    if include_raw_candidate_source_groups:
        # Diagnostic-only physical-source receipts. This sidecar is *not* an
        # authenticated opening or a source-universe completeness assertion.
        opening = composition.physical_opening_authority
        report["unresolved_candidate_source_groups"] = {
            "native": [
                {
                    "page_id": page,
                    "groups": list(opening.audited_unresolved_source_candidate_groups(
                        selectors[page], family="native")),
                }
                for page in sorted(selectors, key=int)
            ],
            "raster": [
                {
                    "page_id": page,
                    "groups": list(opening.audited_unresolved_source_candidate_groups(
                        raster_selectors[page], family="raster")),
                }
                for page in sorted(raster_selectors, key=int)
            ],
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--source-all-pages", action="store_true")
    parser.add_argument("--include-identity-text-receipts", action="store_true")
    parser.add_argument("--include-raw-candidate-source-groups", action="store_true")
    parser.add_argument("--include-room-face-ownership-witnesses", action="store_true")
    parser.add_argument("--include-unhosted-raster-flank-source", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = source_stage_report(args.pdf.read_bytes(),
        page_ids=tuple(sorted(set(args.page_id), key=int)),
        source_all_pages=args.source_all_pages,
        include_identity_text_receipts=args.include_identity_text_receipts,
        include_raw_candidate_source_groups=args.include_raw_candidate_source_groups,
        include_room_face_ownership_witnesses=(
            args.include_room_face_ownership_witnesses
        ),
        include_unhosted_raster_flank_source=(
            args.include_unhosted_raster_flank_source
        ))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True,
                                      default=lambda value: value.value) + "\n")
    print(json.dumps({"source_sha256": report["source_sha256"], **report["summary"]}))


if __name__ == "__main__":
    main()
