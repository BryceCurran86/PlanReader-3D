"""C15 independent ceiling-finish → room/scope binder.

Collection emits unscoped candidates. Only this binder may establish room
ownership, and only from independent proof — never from a caller-supplied
room id argument alone.

If ownership cannot be independently proved, binding fails closed (no scoped
atoms). The same page-level note offered for Room A and Room B therefore
cannot become authoritative for both merely by changing an argument.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id

Point = Tuple[float, float]
BBox = Tuple[float, float, float, float]

PROOF_TEXT_BBOX_IN_UNIQUE_ROOM_FACE = "text_bbox_in_unique_room_face"
PROOF_OWNED_SCOPE_LINK_ATOM = "owned_scope_link_atom"


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
    """Independent proof that one finish candidate belongs to one room.

    ``room_entity_id`` here is the *proven* room from geometry/link evidence,
    not a caller request stamp.
    """

    finish_evidence_id: str
    room_entity_id: str
    proof_kind: str
    proof_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _clean(self.finish_evidence_id):
            raise ValueError("finish_evidence_id required")
        if not _clean(self.room_entity_id):
            raise ValueError("room_entity_id required")
        if not _clean(self.proof_kind):
            raise ValueError("proof_kind required")
        if not self.proof_evidence_ids:
            raise ValueError("proof_evidence_ids required")


def prove_text_bbox_in_unique_room_face(
    *,
    finish_evidence_id: str,
    finish_bbox: Optional[BBox],
    room_faces: Mapping[str, Sequence[Point]],
) -> Optional[CeilingFinishScopeProof]:
    """Prove ownership when the finish bbox center lies in exactly one room face.

    Zero or multiple containing rooms → no proof (ambiguous / unknown).
    """
    if finish_bbox is None:
        return None
    try:
        bbox = (
            float(finish_bbox[0]),
            float(finish_bbox[1]),
            float(finish_bbox[2]),
            float(finish_bbox[3]),
        )
    except (TypeError, ValueError, IndexError):
        return None
    center = _bbox_center(bbox)
    owners = [
        _clean(room_id)
        for room_id, polygon in room_faces.items()
        if _clean(room_id) and _point_in_polygon(center, tuple(polygon))
    ]
    if len(owners) != 1:
        return None
    room_id = owners[0]
    return CeilingFinishScopeProof(
        finish_evidence_id=_clean(finish_evidence_id),
        room_entity_id=room_id,
        proof_kind=PROOF_TEXT_BBOX_IN_UNIQUE_ROOM_FACE,
        proof_evidence_ids=(f"room_face:{room_id}", _clean(finish_evidence_id)),
        reason_codes=("unique_room_face_contains_finish_bbox_center",),
    )


def bind_unscoped_finish_candidates_to_room(
    *,
    candidates: Sequence[EvidenceAtom],
    room_entity_id: str,
    proofs: Sequence[CeilingFinishScopeProof],
) -> tuple[EvidenceAtom, ...]:
    """Materialize scoped finish atoms for ``room_entity_id`` from proofs only.

    The ``room_entity_id`` argument selects *which proven bindings to apply*.
    It is never itself treated as proof. Without a matching
    ``CeilingFinishScopeProof`` for that room and candidate, nothing is
    scoped and the caller must remain BLOCKED downstream.
    """
    scope = _clean(room_entity_id)
    if not scope:
        return ()

    proven_finish_ids = {
        _clean(proof.finish_evidence_id)
        for proof in proofs
        if _clean(proof.room_entity_id) == scope and _clean(proof.finish_evidence_id)
    }
    if not proven_finish_ids:
        return ()

    scoped: list[EvidenceAtom] = []
    for atom in candidates:
        if atom.evidence_id not in proven_finish_ids:
            continue
        matching = [
            proof
            for proof in proofs
            if _clean(proof.room_entity_id) == scope
            and _clean(proof.finish_evidence_id) == atom.evidence_id
        ]
        if not matching:
            continue
        # Scope is stamped from the independent proof, not from a collect-time
        # caller argument.
        meta = dict(atom.metadata or {})
        meta.pop("unscoped", None)
        meta["scope_entity_id"] = scope
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
