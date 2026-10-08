"""Read-only, benchmark-free physical geometry and identity handoff.

Source page addresses select geometry scope; they never inject objects, scale,
dimensions, wall owners or completeness. No quantity writer or evaluator is
called. Every object is re-proven through existing producer-owned authorities.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import fitz

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import build_source_room_face_authority, SourceRoomFaceSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def candidate_handoff(source_bytes: bytes, *, page_ids: tuple[str, ...]) -> dict:
    """Inventory physical existence without materializing wall/room topology.

    Older main revisions have no raster closure audit. Report that capability
    as unavailable rather than substituting a fabricated empty inventory.
    """
    sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=page_ids,
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=page_ids,
    )
    physical = PhysicalOpeningAuthority.from_source_visibility_producer(source)
    openings = {}
    selectors = {}
    for observation_id in (
        *published.visible_observation_ids,
        *published.raster_opening_primitive_observation_ids,
    ):
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=sha, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        existence = physical.prove_existence(selector)
        if existence.existence_record is not None:
            openings[existence.existence_record.record_id] = asdict(existence.existence_record)
        if observation_id in published.raster_opening_primitive_observation_ids:
            result = source.authority().resolve_raster_opening_primitive(selector)
            if result.observation is None:
                raise RuntimeError("raster source ownership unavailable")
            selectors.setdefault(str(result.observation.page_id), selector)
    audit = getattr(physical, "assess_raster_candidate_closure", None)
    return {
        "source_sha256": sha,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "source_decode_coverage": asdict(published.coverage),
        "selected_geometry_page_ids": page_ids,
        "primitive_safety_cap": MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "physical_openings": [openings[key] for key in sorted(openings)],
        "raster_audit_available": audit is not None,
        "raster_candidate_audits": (
            [asdict(audit(selectors[key])) for key in sorted(selectors, key=int)]
            if audit is not None else None
        ),
        "summary": {"physical_openings": len(openings)},
    }


def physical_handoff(source_bytes: bytes, *, page_ids: tuple[str, ...]) -> dict:
    sha = hashlib.sha256(source_bytes).hexdigest()
    # Reuse the production source identity namespace so the handoff does not
    # manufacture alternate physical IDs merely because it is a diagnostic.
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=page_ids)
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=page_ids)
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    assert published is not None
    visibility = source.authority()
    physical = composition.physical_opening_authority
    room_authority = build_source_room_face_authority(composition.physical_wall_candidate_authority)
    openings = []
    for trace in composition.opening_bindings:
        selector = ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=sha, snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id)
        existence = physical.prove_existence(selector)
        opening = existence.existence_record
        binding_selector = composition.binding_selectors.get(trace.opening_identity_id)
        binding = (composition.opening_host_binding_authority.resolve(binding_selector)
                   if binding_selector is not None else None)
        frame_selector = composition.host_frame_selectors.get(trace.opening_identity_id)
        frame = (composition.opening_host_frame_authority.resolve(frame_selector)
                 if frame_selector is not None else None)
        openings.append({
            "existence": asdict(existence.existence_record) if opening else None,
            "existence_status": existence.status.value,
            "existence_reason_codes": existence.reason_codes,
            "representative_observation_id": trace.representative_observation_id,
            "host_binding": asdict(binding) if binding else None,
            "host_frame": asdict(frame) if frame else None,
        })
    raster_audits = []
    seen_pages = set()
    for observation_id in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=sha, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id)
        result = visibility.resolve_raster_opening_primitive(selector)
        if result.observation is None:
            raise RuntimeError("raster source ownership unavailable")
        page_id = str(result.observation.page_id)
        if page_id in page_ids and page_id not in seen_pages:
            seen_pages.add(page_id)
            raster_audits.append(asdict(physical.assess_raster_candidate_closure(selector)))
    room_scopes = []
    # Scope addresses come directly from the sealed physical-wall producer,
    # including partial viewports; callers cannot supply a face universe.
    for scope in composition.physical_wall_candidate_authority._scopes.values():
        if str(scope.page_id) not in page_ids:
            continue
        selector = SourceRoomFaceSelector(
            document_id=scope.document_id, revision_id=scope.revision_id,
            source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
            page_id=scope.page_id, decision_scope_id=scope.decision_scope_id)
        result = room_authority.resolve_scope(selector)
        room_scopes.append({"selector": asdict(selector), "result": asdict(result)})
    return {
        "source_sha256": sha,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "source_decode_coverage": asdict(published.coverage),
        "selected_geometry_page_ids": tuple(composition.page_ids),
        "primitive_safety_cap": MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "composition_status": composition.status.value,
        "composition_reason_codes": composition.reason_codes,
        "semantic_inventory": asdict(composition.semantic_enumeration_result),
        "opening_universes": {key: asdict(value) for key, value in composition.opening_universe_results.items()},
        "wall_scopes": [asdict(trace) for trace in composition.wall_scopes],
        "physical_openings": openings,
        "raster_candidate_audits": raster_audits,
        "source_room_face_scopes": room_scopes,
        "summary": {
            "physical_openings": len(openings),
            "host_bindings": sum(bool(trace.host_wall_id) for trace in composition.opening_bindings),
            "host_frames": sum(bool(trace.record_id) for trace in composition.host_frames),
            "host_binding_reason_counts": dict(Counter(
                reason for trace in composition.opening_bindings for reason in trace.reason_codes)),
            "host_frame_reason_counts": dict(Counter(
                reason for trace in composition.host_frames for reason in trace.reason_codes)),
            "published_room_faces": sum(len(row["result"]["records"]) for row in room_scopes),
            "room_scope_reason_counts": dict(Counter(
                reason for row in room_scopes for reason in row["result"]["reason_codes"])),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-only", action="store_true")
    args = parser.parse_args()
    pages = tuple(sorted(set(args.page_id), key=int))
    source_bytes = args.pdf.read_bytes()
    # Decode all pages independently without retaining every page's primitive
    # graph in memory. This audit does not enlarge the selected authority scope.
    audit = {"decoded_pages": [], "failed_pages": []}
    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        audit["total_pages"] = len(doc)
        for index, page in enumerate(doc):
            try:
                page.get_text("words")
                page.get_drawings()
                audit["decoded_pages"].append(index + 1)
            except Exception as exc:
                audit["failed_pages"].append({"page_id": index + 1, "reason": type(exc).__name__})
    handoff = candidate_handoff if args.candidate_only else physical_handoff
    payload = handoff(source_bytes, page_ids=pages)
    payload["all_page_native_decode_audit"] = audit
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True,
                                      default=lambda value: value.value) + "\n")
    print(json.dumps({"source_sha256": payload["source_sha256"], **payload["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
