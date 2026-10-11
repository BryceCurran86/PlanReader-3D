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
import math
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
from pb_source_room_label_authority import (
    SourceRoomLabelProducer,
    SourceRoomLabelScopeResult,
    SourceRoomLabelSelector,
    SourceRoomLabelRecord,
    SourceRoomSplitLabelCandidate,
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




def _distinct_source_faces_for_word_ownership(
    word_face_ids, face_receipts, physical_faces,
) -> tuple[str, ...]:
    """Match repeated per-word source faces to one original receipt per face."""
    if not isinstance(word_face_ids, (tuple, list)):
        raise ValueError("invalid original word-face ownership")
    if not isinstance(face_receipts, (tuple, list)):
        raise ValueError("invalid original source face receipts")
    if not isinstance(physical_faces, dict):
        raise TypeError("exact original physical face census required")
    words = tuple(word_face_ids)
    if any(not isinstance(f, str) or not f.strip() or f != f.strip()
           for f in words):
        raise ValueError("foreign original word face identity")
    distinct = tuple(dict.fromkeys(words))
    receipts = tuple(face_receipts)
    if (len(distinct) < 2 or len(distinct) != len(receipts)
            or any(not isinstance(rid, str) or not rid.strip()
                   for rid in receipts)
            or len(set(receipts)) != len(receipts)
            or any(f not in physical_faces
                   or physical_faces[f].record_id != rid
                   for f, rid in zip(distinct, receipts))):
        raise ValueError("original split word face has no unique source receipt")
    return distinct


def source_room_label_first_gate(
    room: SourceRoomFaceScopeResult,
    labels: SourceRoomLabelScopeResult,
    *,
    expected_source_sha: str,
) -> dict:
    """Trace exact source-label ownership without converting text into geometry."""
    if (type(room) is not SourceRoomFaceScopeResult
            or type(labels) is not SourceRoomLabelScopeResult):
        raise TypeError("producer-owned source room/label scope required")
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected_source_sha or "")):
        raise ValueError("invalid original source hash")
    if any(
        getattr(room, key) != getattr(labels, key)
        for key in _SCOPE_KEYS
    ) or room.source_sha256 != expected_source_sha:
        raise ValueError("source room/label scope provenance mismatch")
    if (not isinstance(labels.reason_codes, tuple)
            or any(not isinstance(code, str) or not code.strip()
                   for code in labels.reason_codes)):
        raise ValueError("invalid original label reason receipt")
    physical_faces = {row.face_id: row for row in room.records}
    if len(physical_faces) != len(room.records):
        raise ValueError("ambiguous original physical face identities")

    direct, split, observation_ids = [], [], set()
    for row in labels.records:
        if type(row) is not SourceRoomLabelRecord:
            raise TypeError("label must be producer sealed")
        if any(getattr(row, key) != getattr(room, key) for key in _SCOPE_KEYS):
            raise ValueError("foreign original label source scope")
        target = physical_faces.get(row.face_id)
        if target is None or target.record_id != row.source_room_face_record_id:
            raise ValueError("label has no exact source physical face receipt")
        ids = tuple(row.observation_ids)
        if (not ids or len(set(ids)) != len(ids)
                or any(not isinstance(i, str) or not i.strip()
                       or i in observation_ids for i in ids)):
            raise ValueError("reused or invalid original text observation")
        observation_ids.update(ids)
        if row.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("untrusted direct room label is not publishable")
        direct.append({
            "label": row.label,
            "source_face_id": row.face_id,
            "source_face_receipt_id": row.source_room_face_record_id,
            "original_text_observation_ids": sorted(ids),
        })
    for row in labels.split_face_candidates:
        if type(row) is not SourceRoomSplitLabelCandidate:
            raise TypeError("split label must be producer sealed")
        if any(getattr(row, key) != getattr(room, key) for key in _SCOPE_KEYS):
            raise ValueError("foreign split source label scope")
        # Each WORD has one face ID. Multiple words may legitimately
        # occupy one face, whereas producer receipts are one per DISTINCT
        # face in first-occurrence word order. Never zip these inventories.
        word_face_ids = tuple(row.word_face_ids)
        receipts = tuple(row.source_room_face_record_ids)
        distinct_face_ids = _distinct_source_faces_for_word_ownership(
            word_face_ids, receipts, physical_faces,
        )
        ids = tuple(row.observation_ids)
        if (not ids or len(set(ids)) != len(ids)
                or any(not isinstance(i, str) or not i.strip()
                       or i in observation_ids for i in ids)):
            raise ValueError("reused or invalid split source text observation")
        observation_ids.update(ids)
        if row.status is not EvidenceResolutionStatus.CANDIDATE:
            raise ValueError("split face label must remain candidate only")
        split.append({
            "label": row.label,
            "original_word_face_ids": list(word_face_ids),
            "original_source_face_ids": list(distinct_face_ids),
            "original_source_face_receipt_ids": list(receipts),
            "original_text_observation_ids": sorted(ids),
            "room_identity_publication_allowed": False,
        })
    return {
        "original_label_scope_status": labels.status.value,
        "original_label_reason_codes": list(labels.reason_codes),
        "direct_source_label_count": len(direct),
        "split_source_label_candidate_count": len(split),
        "direct_source_labels": sorted(
            direct, key=lambda v:(v["label"],v["source_face_id"])
        ),
        "split_source_label_candidates": sorted(
            split, key=lambda v:(v["label"],tuple(v["original_source_face_ids"]))
        ),
        "all_label_source_observation_ids_unique": True,
        "source_room_face_universe_complete": room.face_universe_complete,
        "source_room_geometry_inferred_from_labels": False,
        "split_label_room_publication_allowed": False,
        "firm_room_area_publication_allowed": False,
    }



def source_withheld_boundary_w4_census(
    room: SourceRoomFaceScopeResult,
    label_gate: dict,
    *,
    expected_source_sha: str,
) -> list[dict]:
    """Report original W4 IDs common to withheld boundaries and proven labels.

    This is a source-ID intersection only, NOT proof that the two geometries
    touch, that a withheld face is a room, or that a wall host can publish.
    """
    if type(room) is not SourceRoomFaceScopeResult or not isinstance(label_gate, dict):
        raise TypeError("original room scope and authenticated label ledger required")
    if (not isinstance(expected_source_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_source_sha) is None
            or room.source_sha256 != expected_source_sha):
        raise ValueError("untrusted boundary source revision")
    if label_gate.get("firm_room_area_publication_allowed") is not False:
        raise ValueError("source label ledger must be nonpublishing")
    direct = label_gate.get("direct_source_labels")
    if not isinstance(direct, list):
        raise ValueError("original source-labelled face ledger unavailable")

    def wall_ids(face):
        ids = getattr(face, "bounding_wall_ids", None)
        if not isinstance(ids, (tuple, list)):
            raise ValueError("missing source W4 wall ID inventory")
        if (any(not isinstance(x, str) or not x or x != x.strip() for x in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("ambiguous original W4 wall candidate inventory")
        return set(ids)

    positive_by_receipt = {}
    for face in room.records:
        if any(getattr(face, key, None) != getattr(room, key) for key in _SCOPE_KEYS):
            raise ValueError("foreign source positive face")
        rid = face.record_id
        if (not isinstance(rid, str) or not rid or rid != rid.strip()
                or rid in positive_by_receipt):
            raise ValueError("duplicate or invalid positive source face receipt")
        positive_by_receipt[rid] = face
    attached = []
    owned_faces = set()
    for label in direct:
        if not isinstance(label, dict):
            raise ValueError("invalid original direct source label")
        rid, face_id = label.get("source_face_receipt_id"), label.get("source_face_id")
        face = positive_by_receipt.get(rid)
        if face is None or face.face_id != face_id or rid in owned_faces:
            raise ValueError("label does not have one exact positive physical face")
        owned_faces.add(rid)
        name = label.get("label")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("missing original authenticated room label")
        attached.append((name, rid, face_id, wall_ids(face)))

    census = []
    face_ids = set()
    for face in room.abstained_faces:
        if any(getattr(face, key, None) != getattr(room, key) for key in _SCOPE_KEYS):
            raise ValueError("foreign withheld source face revision")
        face_id = face.face_id
        if (not isinstance(face_id, str) or not face_id or face_id != face_id.strip()
                or face_id in face_ids
                or face_id in {f.face_id for f in room.records}):
            raise ValueError("duplicate or foreign withheld source face identity")
        face_ids.add(face_id)
        if face.reason != "source_room_face_boundary_unresolved":
            continue
        walls = wall_ids(face)
        source_points = getattr(face, "polygon_pdf_pts", None)
        if (not isinstance(source_points, (tuple, list))
                or len(source_points) < 3 or any(
                    not isinstance(point, (tuple, list)) or len(point) != 2
                    or any(type(value) not in (int, float)
                           or not math.isfinite(value) for value in point)
                    for point in source_points
                )):
            raise ValueError("untrusted original withheld polygon points")
        overlaps = [
            {
                "original_authenticated_label": name,
                "source_positive_room_face_id": positive_face_id,
                "source_positive_room_face_receipt_id": positive_receipt,
                "shared_source_w4_candidate_ids": sorted(walls & candidate_ids),
                "physical_wall_adjacency_proven": False,
                "withheld_face_promotion_allowed": False,
            }
            for name, positive_receipt, positive_face_id, candidate_ids in attached
            if walls & candidate_ids
        ]
        census.append({
            "source_withheld_face_id": face_id,
            "source_withheld_reason": face.reason,
            "original_source_polygon_pdf_pts": [list(pt) for pt in source_points],
            "original_w4_candidate_ids": sorted(walls),
            "same_w4_candidate_receipt_seen_on_authenticated_label": sorted(
                overlaps, key=lambda r: (
                    r["original_authenticated_label"],
                    r["source_positive_room_face_receipt_id"],
                )
            ),
            "original_physical_wall_adjacency_proven": False,
            "original_withheld_face_room_publication_allowed": False,
            "original_metric_quantity_publication_allowed": False,
        })
    return sorted(census, key=lambda r:r["source_withheld_face_id"])


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
    # Viewport wall materialization may advance the immutable source snapshot.
    # Match production's late selector creation against the new sealed
    # revision/snapshot rather than addressing the pre-viewport snapshot.
    viewport_published = source.published_snapshot_for_revision(
        composition.revision_id
    )
    if (viewport_published is None
            or viewport_published.revision.document_id != final.revision.document_id
            or viewport_published.revision.revision_id != final.revision.revision_id
            or viewport_published.revision.source_sha256 != digest):
        raise ValueError("foreign authenticated viewport source revision")
    # Reuse production's sealed label producer and explicit real source faces.
    # Text never mints physical rooms; ambiguous split labels remain CANDIDATE.
    viewport_labels = SourceRoomLabelProducer.from_authorities(
        source, viewport_room_auth, page_ids=("7",),
    ).authority()
    selectors = viewport_auth.selectors_for_authenticated_viewports(
        document_id=viewport_published.revision.document_id,
        revision_id=viewport_published.revision.revision_id,
        source_sha256=digest,
        snapshot_id=viewport_published.snapshot.snapshot_id,
        page_id="7",
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    for wall_selector in selectors:
        w = viewport_auth.resolve_scope(wall_selector)
        r = viewport_room_auth.resolve_scope(SourceRoomFaceSelector(
            **{key: getattr(wall_selector, key) for key in _SCOPE_KEYS}
        ))
        report = source_room_owner_first_gate(
            w, r, expected_source_sha=digest,
        )
        label_scope = viewport_labels.resolve_scope(SourceRoomLabelSelector(
            **{key: getattr(wall_selector, key) for key in _SCOPE_KEYS}
        ))
        report["original_source_label_gate"] = source_room_label_first_gate(
            r, label_scope, expected_source_sha=digest,
        )
        report["original_withheld_boundary_w4_census"] = (
            source_withheld_boundary_w4_census(
                r, report["original_source_label_gate"],
                expected_source_sha=digest,
            )
        )
        scopes.append(report)
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
