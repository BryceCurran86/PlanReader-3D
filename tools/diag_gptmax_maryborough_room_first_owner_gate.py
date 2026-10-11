"""Original-source Maryborough room-face first-gate diagnostic. NEVER publish rooms.

Replays the same SHA-authenticated topology page and room-support sheet used
by the production handoff. A page-wide wall scope may abstain; separately
inspect only source-authenticated FLOOR_PLAN viewport wall selectors.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
)
from pb_source_room_face_authority import (
    SourceRoomFaceScopeResult,
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


_SCOPE_KEYS = (
    "document_id", "revision_id", "source_sha256", "snapshot_id",
    "page_id", "decision_scope_id",
)


def source_room_owner_first_gate(
    wall: PhysicalWallCandidateScopeResult,
    room: SourceRoomFaceScopeResult,
    *,
    expected_source_sha: str,
) -> dict:
    """Summarise producer-owned negative room-face evidence, without promotion."""
    if (type(wall) is not PhysicalWallCandidateScopeResult
            or type(room) is not SourceRoomFaceScopeResult):
        raise TypeError("original wall/room authority scopes required")
    if (not isinstance(expected_source_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_source_sha) is None
            or wall.source_sha256 != expected_source_sha):
        raise ValueError("original source SHA authority mismatch")
    for key in _SCOPE_KEYS:
        value = getattr(wall, key)
        if (not isinstance(value, str) or not value.strip()
                or getattr(room, key) != value):
            raise ValueError("wall/room source scope identity mismatch: " + key)
    if not isinstance(wall.reason_codes, tuple) or not isinstance(room.reason_codes, tuple):
        raise ValueError("invalid producer reason inventory")
    if any(not isinstance(value, str) or not value.strip()
           for value in (*wall.reason_codes, *room.reason_codes)):
        raise ValueError("invalid original source reason receipt")
    original_room_ids = []
    original_face_ids = []
    for face in (*room.records, *room.abstained_faces):
        if any(getattr(face, key, None) != getattr(wall, key) for key in _SCOPE_KEYS):
            raise ValueError("foreign original room face source provenance")
        face_id = getattr(face, "face_id", None)
        if not isinstance(face_id, str) or not face_id.strip():
            raise ValueError("original source face has no identity")
        original_face_ids.append(face_id)
        if face in room.records:
            record_id = getattr(face, "record_id", None)
            if not isinstance(record_id, str) or not record_id.strip():
                raise ValueError("original source face receipt missing")
            original_room_ids.append(record_id)
    if len(original_room_ids) != len(set(original_room_ids)):
        raise ValueError("duplicate original published room face receipt")
    if len(original_face_ids) != len(set(original_face_ids)):
        raise ValueError("duplicate original source physical face identity")

    if wall.status is not EvidenceResolutionStatus.CORROBORATED or not wall.records:
        gate = "PHYSICAL_WALL_SCOPE_NOT_AUTHENTICATED"
    elif room.status is not EvidenceResolutionStatus.CORROBORATED or not room.records:
        gate = "SOURCE_ROOM_FACE_SCOPE_NOT_AUTHENTICATED"
    elif room.abstained_faces or not room.face_universe_complete:
        gate = "PARTIAL_SOURCE_ROOM_FACE_UNIVERSE"
    else:
        gate = "SOURCE_ROOM_FACE_SCOPE_AVAILABLE_NOT_A_METRIC_ROOM_PROOF"

    abstentions = Counter(face.reason for face in room.abstained_faces)
    if any(not isinstance(reason, str) or not reason.strip()
           for reason in abstentions):
        raise ValueError("invalid producer-owned face abstention reason")
    return {
        "document_id": wall.document_id,
        "source_sha256": expected_source_sha,
        "snapshot_id": wall.snapshot_id,
        "page_id": wall.page_id,
        "decision_scope_id": wall.decision_scope_id,
        "scope_kind": wall.scope_kind,
        "viewport_id": wall.viewport_id,
        "wall_status": wall.status.value,
        "wall_scope_complete": wall.scope_complete,
        "wall_source_candidate_count": len(wall.records),
        "wall_reason_codes": list(wall.reason_codes),
        "room_status": room.status.value,
        "room_scope_complete": room.scope_complete,
        "room_face_universe_complete": room.face_universe_complete,
        "room_source_face_count": len(room.records),
        "room_source_face_receipt_ids": sorted(original_room_ids),
        "room_abstained_face_count": len(room.abstained_faces),
        "room_abstention_reason_counts": dict(sorted(abstentions.items())),
        "room_reason_codes": list(room.reason_codes),
        "first_unproved_authority": gate,
        "diagnostic_only": True,
        "wall_host_publication_allowed": False,
        "room_area_quantity_publication_allowed": False,
        "room_face_promotion_allowed": False,
        "benchmark_accuracy": None,
    }


def replay_original_maryborough_room_gate(
    pdf_bytes: bytes, *, expected_source_sha: str,
) -> dict:
    """Match production's 0-index page=(6,), support=(10,) source universe."""
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if digest != expected_source_sha:
        raise ValueError("original Maryborough PDF SHA mismatch")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=("7", "11"),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("7",),
        evidence_page_ids=(),
    )
    final = source.published_snapshot_for_revision(composition.revision_id)
    if final is None or final.revision.source_sha256 != digest:
        raise ValueError("source snapshot changed or disappeared")
    page_selector = PhysicalWallCandidateSelector(
        document_id=final.revision.document_id,
        revision_id=final.revision.revision_id,
        source_sha256=digest,
        snapshot_id=final.snapshot.snapshot_id,
        page_id="7",
        decision_scope_id="wall-source:page-7",
    )
    wall_auth = composition.physical_wall_candidate_authority
    room_auth = build_source_room_face_authority(wall_auth)
    page_wall = wall_auth.resolve_scope(page_selector)
    page_room = room_auth.resolve_scope(SourceRoomFaceSelector(
        **{key: getattr(page_selector, key) for key in _SCOPE_KEYS}
    ))
    scopes = [source_room_owner_first_gate(
        page_wall, page_room, expected_source_sha=digest,
    )]

    # Production only permits independently authenticated FLOOR_PLAN viewports,
    # never a caller-defined bbox or support-sheet geometry.
    viewport_producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source, page_ids=("7",),
    )
    viewport_auth = viewport_producer.authority()
    viewport_room_auth = build_source_room_face_authority(viewport_auth)
    selectors = viewport_auth.selectors_for_authenticated_viewports(
        document_id=final.revision.document_id,
        revision_id=final.revision.revision_id,
        source_sha256=digest,
        snapshot_id=final.snapshot.snapshot_id,
        page_id="7",
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    for wall_selector in selectors:
        w = viewport_auth.resolve_scope(wall_selector)
        r = viewport_room_auth.resolve_scope(SourceRoomFaceSelector(
            **{key: getattr(wall_selector, key) for key in _SCOPE_KEYS}
        ))
        scopes.append(source_room_owner_first_gate(
            w, r, expected_source_sha=digest,
        ))
    return {
        "schema_version": "1.0.0",
        "original_pdf_sha_verified": digest,
        "topology_page_id": "7",
        "documented_area_support_page_id": "11",
        "source_scope_first_failures": scopes,
        "authenticated_floor_plan_viewport_count": len(selectors),
        "published_source_room_faces_diagnostic_only": sum(
            row["room_source_face_count"] for row in scopes
        ),
        "diagnostic_only": True,
        "wall_host_publication_allowed": False,
        "room_area_quantity_publication_allowed": False,
        "benchmark_accuracy": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay_original_maryborough_room_gate(
        args.pdf.read_bytes(), expected_source_sha=args.expected_source_sha,
    )
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "source_verified": True,
        "authenticated_viewports": report["authenticated_floor_plan_viewport_count"],
        "scope_gates": [
            (row["decision_scope_id"], row["first_unproved_authority"])
            for row in report["source_scope_first_failures"]
        ],
        "quantity_published": False,
    }))


if __name__ == "__main__":
    main()
