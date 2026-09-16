"""C15 ceiling-finish → room scope binder (authoritative proof resolution).

Collection emits unscoped candidates. Binding may establish room ownership
only by independently resolving against repository-owned ``RoomCandidate``
topology evidence — never from a caller-supplied room id, polygon map, or
free-form proof object.

Chain:
  unscoped finish candidates
  → canonical RoomCandidate geometry (owned document/viewport/page)
  → sealed CeilingFinishScopeProof (resolver-minted only)
  → scoped finish atoms for a queried room_ref
  → build_ceiling_lining_quantity

If canonical room ownership cannot be resolved, binding fails closed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_wall_room_topology_contracts import RoomCandidate

Point = Tuple[float, float]
BBox = Tuple[float, float, float, float]

PROOF_TEXT_BBOX_IN_UNIQUE_ROOM_CANDIDATE = "text_bbox_in_unique_room_candidate"

# Only the resolver may mint proofs. External ``CeilingFinishScopeProof(...)``
# construction without this seal is rejected at bind time.
_PROOF_SEAL = object()

_BINDABLE_ROOM_STATUSES = frozenset(
    {
        EvidenceResolutionStatus.CANDIDATE,
        EvidenceResolutionStatus.CORROBORATED,
    }
)


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _bbox_center(bbox: BBox) -> Point:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray-casting inclusion. Degenerate polygons never contain a point."""
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


@dataclass(frozen=True)
class CeilingFinishScopeProof:
    """Resolver-minted proof that one finish candidate belongs to one room.

    Must be created by ``resolve_ceiling_finish_scope_proofs``. Caller-built
    instances lack the seal and are rejected by the binder.
    """

    proof_id: str
    finish_evidence_id: str
    room_entity_id: str
    proof_kind: str
    document_id: str
    source_sha256: str
    revision_id: str
    page_id: str
    page_no: int
    viewport_id: str
    proof_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()
    _seal: object = field(default=None, repr=False, compare=False)

    @property
    def is_resolver_minted(self) -> bool:
        return self._seal is _PROOF_SEAL


def _mint_proof(
    *,
    finish_evidence_id: str,
    room: RoomCandidate,
    context: ProviderContext,
    page_id: str,
    page_no: int,
    proof_kind: str,
    proof_evidence_ids: Sequence[str],
    reason_codes: Sequence[str],
) -> CeilingFinishScopeProof:
    finish_id = _clean(finish_evidence_id)
    room_id = _clean(room.room_ref)
    payload = {
        "proof_kind": proof_kind,
        "finish_evidence_id": finish_id,
        "room_entity_id": room_id,
        "document_id": context.document_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "page_id": page_id,
        "page_no": int(page_no),
        "viewport_id": room.viewport_id,
        "proof_evidence_ids": list(proof_evidence_ids),
    }
    return CeilingFinishScopeProof(
        proof_id=stable_contract_id("cfsproof", payload),
        finish_evidence_id=finish_id,
        room_entity_id=room_id,
        proof_kind=proof_kind,
        document_id=_clean(context.document_id),
        source_sha256=_clean(context.source_sha256).lower(),
        revision_id=_clean(context.current_revision_id),
        page_id=_clean(page_id),
        page_no=int(page_no),
        viewport_id=_clean(room.viewport_id),
        proof_evidence_ids=tuple(_clean(eid) for eid in proof_evidence_ids if _clean(eid)),
        reason_codes=tuple(_clean(code) for code in reason_codes if _clean(code)),
        _seal=_PROOF_SEAL,
    )


def _room_owned_by_context(
    *,
    room: RoomCandidate,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[str, ...]:
    """Return blockers when a RoomCandidate is not usable for C15 binding."""
    blockers: list[str] = []
    if room.document_id != context.document_id or room.document_id != document.document_id:
        blockers.append("room_document_mismatch")
    if room.viewport_id != viewport.viewport_id:
        blockers.append("room_viewport_mismatch")
    if room.viewport_id not in context.trusted_viewport_ids():
        blockers.append("room_viewport_not_owned")
    if int(room.source_page) != int(page_no):
        blockers.append("room_page_mismatch")
    if int(page_no) not in context.trusted_page_numbers():
        blockers.append("page_not_owned")
    mapped = context.page_for_viewport(viewport.viewport_id)
    if mapped is not None and int(mapped) != int(page_no):
        blockers.append("viewport_page_mismatch")
    if room.status not in _BINDABLE_ROOM_STATUSES:
        blockers.append("room_status_not_bindable")
    if len(room.polygon_pdf_pts) < 3:
        blockers.append("room_polygon_unavailable")
    return tuple(dict.fromkeys(blockers))


def _candidate_owned_by_context(
    *,
    atom: EvidenceAtom,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if atom.document_id != document.document_id or atom.document_id != context.document_id:
        blockers.append("finish_document_mismatch")
    if atom.evidence_id not in document.evidence_ids:
        blockers.append("finish_evidence_not_owned_by_document")
    if atom.page_id != viewport.page_id:
        blockers.append("finish_page_mismatch")
    meta = atom.metadata if isinstance(atom.metadata, dict) else {}
    try:
        atom_page = int(meta.get("page_no"))
    except (TypeError, ValueError):
        atom_page = None
    if atom_page is None or atom_page != int(page_no):
        blockers.append("finish_page_no_mismatch")
    source = _clean(meta.get("source_sha256")).lower()
    if source != context.source_sha256:
        blockers.append("finish_source_sha256_mismatch")
    revision = _clean(meta.get("revision_id"))
    if revision != _clean(context.current_revision_id):
        blockers.append("finish_revision_mismatch")
    if atom.viewport_id not in (None, "", viewport.viewport_id):
        blockers.append("finish_viewport_mismatch")
    return tuple(dict.fromkeys(blockers))


def resolve_ceiling_finish_scope_proofs(
    *,
    candidates: Sequence[EvidenceAtom],
    rooms: Sequence[RoomCandidate],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[CeilingFinishScopeProof, ...]:
    """Mint sealed proofs from unscoped finish candidates + RoomCandidates.

    Uses only ``RoomCandidate.polygon_pdf_pts`` (canonical topology contract).
    Caller-supplied bare polygon maps are not accepted. Zero or multiple
    containing rooms → no proof for that finish (fail closed / ambiguous).
    """
    if not context.revision_id or not context.current_revision_id:
        return ()
    if context.revision_id != context.current_revision_id:
        return ()
    if document.document_id != context.document_id:
        return ()
    if document.source_sha256 != context.source_sha256:
        return ()
    if viewport.document_id != context.document_id:
        return ()
    if viewport.viewport_id not in context.trusted_viewport_ids():
        return ()

    usable_rooms: list[RoomCandidate] = []
    for room in rooms:
        if _room_owned_by_context(
            room=room,
            context=context,
            document=document,
            viewport=viewport,
            page_no=page_no,
        ):
            continue
        usable_rooms.append(room)
    if not usable_rooms:
        return ()

    proofs: list[CeilingFinishScopeProof] = []
    for atom in candidates:
        if _candidate_owned_by_context(
            atom=atom,
            context=context,
            document=document,
            viewport=viewport,
            page_no=page_no,
        ):
            continue
        if atom.bbox is None:
            continue
        try:
            bbox = (
                float(atom.bbox[0]),
                float(atom.bbox[1]),
                float(atom.bbox[2]),
                float(atom.bbox[3]),
            )
        except (TypeError, ValueError, IndexError):
            continue
        if not all(math.isfinite(v) for v in bbox):
            continue
        center = _bbox_center(bbox)
        owners = [
            room
            for room in usable_rooms
            if _point_in_polygon(center, room.polygon_pdf_pts)
        ]
        if len(owners) != 1:
            continue
        room = owners[0]
        proofs.append(
            _mint_proof(
                finish_evidence_id=atom.evidence_id,
                room=room,
                context=context,
                page_id=atom.page_id,
                page_no=page_no,
                proof_kind=PROOF_TEXT_BBOX_IN_UNIQUE_ROOM_CANDIDATE,
                proof_evidence_ids=(
                    f"room_candidate:{room.room_ref}",
                    atom.evidence_id,
                    *tuple(room.evidence),
                ),
                reason_codes=("unique_room_candidate_contains_finish_bbox_center",),
            )
        )
    proofs.sort(key=lambda item: item.proof_id)
    return tuple(proofs)


def bind_unscoped_finish_candidates_to_room(
    *,
    candidates: Sequence[EvidenceAtom],
    queried_room_ref: str,
    proofs: Sequence[CeilingFinishScopeProof],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[EvidenceAtom, ...]:
    """Materialize scoped atoms for a queried room from resolver-minted proofs.

    ``queried_room_ref`` selects which resolved proofs to apply. It never
    certifies ownership. Non-sealed / ownership-mismatched proofs are ignored.
    """
    scope = _clean(queried_room_ref)
    if not scope:
        return ()

    trusted: list[CeilingFinishScopeProof] = []
    for proof in proofs:
        if not proof.is_resolver_minted:
            continue
        if _clean(proof.room_entity_id) != scope:
            continue
        if proof.document_id != context.document_id:
            continue
        if proof.source_sha256 != context.source_sha256:
            continue
        if proof.revision_id != _clean(context.current_revision_id):
            continue
        if int(proof.page_no) != int(page_no):
            continue
        if proof.viewport_id != viewport.viewport_id:
            continue
        if proof.page_id != viewport.page_id:
            continue
        # Re-derive proof_id; reject tampered field sets.
        expected = stable_contract_id(
            "cfsproof",
            {
                "proof_kind": proof.proof_kind,
                "finish_evidence_id": proof.finish_evidence_id,
                "room_entity_id": proof.room_entity_id,
                "document_id": proof.document_id,
                "source_sha256": proof.source_sha256,
                "revision_id": proof.revision_id,
                "page_id": proof.page_id,
                "page_no": int(proof.page_no),
                "viewport_id": proof.viewport_id,
                "proof_evidence_ids": list(proof.proof_evidence_ids),
            },
        )
        if proof.proof_id != expected:
            continue
        trusted.append(proof)

    proven_finish_ids = {
        _clean(proof.finish_evidence_id) for proof in trusted if _clean(proof.finish_evidence_id)
    }
    if not proven_finish_ids:
        return ()

    scoped: list[EvidenceAtom] = []
    for atom in candidates:
        if atom.evidence_id not in proven_finish_ids:
            continue
        if atom.evidence_id not in document.evidence_ids:
            continue
        matching = [proof for proof in trusted if proof.finish_evidence_id == atom.evidence_id]
        if not matching:
            continue
        meta = dict(atom.metadata or {})
        meta.pop("unscoped", None)
        meta["scope_entity_id"] = scope
        meta["scope_binding_proof_ids"] = tuple(sorted(proof.proof_id for proof in matching))
        meta["scope_binding_proof_kinds"] = tuple(
            sorted({proof.proof_kind for proof in matching})
        )
        meta["scope_binding_proof_evidence_ids"] = tuple(
            sorted(
                {
                    eid
                    for proof in matching
                    for eid in proof.proof_evidence_ids
                    if _clean(eid)
                }
            )
        )
        meta["scope_bound"] = True
        scoped_id = stable_contract_id(
            "ev",
            {
                "kind": atom.kind,
                "scoped_from": atom.evidence_id,
                "scope_entity_id": scope,
                "document_id": atom.document_id,
                "page_id": atom.page_id,
                "viewport_id": atom.viewport_id,
                "proof_ids": list(meta["scope_binding_proof_ids"]),
                "descriptor": meta.get("finish_descriptor"),
            },
        )
        scoped.append(
            EvidenceAtom(
                evidence_id=scoped_id,
                document_id=atom.document_id,
                page_id=atom.page_id,
                kind=atom.kind,
                method=atom.method,
                viewport_id=atom.viewport_id,
                raw_text=atom.raw_text,
                bbox=atom.bbox,
                normalized_value=atom.normalized_value,
                unit=atom.unit,
                confidence=float(atom.confidence),
                status=EvidenceResolutionStatus.RAW,
                reason_codes=tuple(atom.reason_codes),
                metadata=meta,
            )
        )
    return tuple(scoped)


# Removed APIs (intentionally absent):
# - prove_text_bbox_in_unique_room_face(room_faces=...) — caller polygon maps
# - trusting externally constructed CeilingFinishScopeProof without seal
