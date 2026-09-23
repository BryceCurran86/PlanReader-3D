"""C15 ceiling-finish → room scope binder (authenticated topology only).

Collection emits unscoped candidates. Binding may establish room ownership
only by resolving rooms from a collector-produced ``TopologySnapshot`` whose
``geometry_source`` is an authenticated/source-owned seam, sealed into an
``OwnedTopologyRoomIndex`` — never from caller-supplied ``RoomCandidate``
bodies, polygon maps, free-form proof objects, or diagnostic
``collect_topology_from_segments`` caller-segment bags.

Chain:
  unscoped finish candidates
  → authenticated/source-owned TopologySnapshot (sealed)
  → OwnedTopologyRoomIndex (immutable index_id + rooms by room_ref)
  → sealed CeilingFinishScopeProof
  → scoped finish atoms for a queried room_ref
  → build_ceiling_lining_quantity

If authenticated topology cannot be resolved, binding fails closed (BLOCKED).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_source_room_face_authority import (
    SourceRoomFaceAuthority,
    SourceRoomFaceSelector,
)
from pb_wall_room_topology_contracts import RoomCandidate
from pb_wall_topology_diagnostics import (
    GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS,
    TopologySnapshot,
)

Point = Tuple[float, float]
BBox = Tuple[float, float, float, float]

PROOF_TEXT_BBOX_IN_UNIQUE_ROOM_CANDIDATE = "text_bbox_in_unique_room_candidate"
GEOMETRY_SOURCE_AUTHENTICATED_ROOM_FACES = "source_authenticated_room_faces"

_PROOF_SEAL = object()
_INDEX_SEAL = object()

_BINDABLE_ROOM_STATUSES = frozenset(
    {
        EvidenceResolutionStatus.CANDIDATE,
        EvidenceResolutionStatus.CORROBORATED,
    }
)

# C15 room-index authority requires authenticated/source-owned geometry.
# Diagnostic ``collect_topology_from_segments`` (caller-supplied segments) is
# never eligible — collector seal alone is not authentication.
# Page-native extract becomes eligible only once an authenticated
# document/source-bound page→topology seam is wired into this path.
# Until that seam exists, this frozenset stays empty and C15 stays BLOCKED.
C15_ROOM_INDEX_GEOMETRY_SOURCES: frozenset[str] = frozenset()


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _bbox_center(bbox: BBox) -> Point:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
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
class OwnedTopologyRoomIndex:
    """Immutable room lookup sealed from authenticated topology.

    Callers may hold and pass ``index_id`` / this object, but cannot mint it
    from free-constructed ``RoomCandidate`` tuples or caller-segment
    diagnostic snapshots. Use ``build_owned_topology_room_index``.
    """

    index_id: str
    document_id: str
    source_sha256: str
    revision_id: str
    page_id: str
    page_no: int
    viewport_id: str
    topology_snapshot_fingerprint: str
    geometry_source: str
    _rooms_by_ref: Mapping[str, RoomCandidate] = field(repr=False, compare=False)
    _seal: object = field(default=None, repr=False, compare=False)

    @property
    def is_producer_owned(self) -> bool:
        return self._seal is _INDEX_SEAL

    def room(self, room_ref: str) -> Optional[RoomCandidate]:
        if not self.is_producer_owned:
            return None
        return self._rooms_by_ref.get(_clean(room_ref))

    def rooms(self) -> tuple[RoomCandidate, ...]:
        if not self.is_producer_owned:
            return ()
        return tuple(self._rooms_by_ref[key] for key in sorted(self._rooms_by_ref))


def build_owned_topology_room_index(
    *,
    snapshot: TopologySnapshot,
    context: ProviderContext,
) -> Optional[OwnedTopologyRoomIndex]:
    """Seal rooms from authenticated/source-owned topology under ProviderContext.

    Returns None (fail closed) when:
    - the snapshot is not collector-produced,
    - geometry came from diagnostic caller-supplied segments,
    - geometry_source is not in ``C15_ROOM_INDEX_GEOMETRY_SOURCES``,
    - or ownership fields disagree with context.

    Until an authenticated page→topology seam is listed in
    ``C15_ROOM_INDEX_GEOMETRY_SOURCES``, this always returns None.
    """
    if not snapshot.is_collector_produced:
        return None
    # Explicit: diagnostic collector over caller segments is never C15 authority.
    if snapshot.geometry_source == GEOMETRY_SOURCE_CALLER_SUPPLIED_SEGMENTS:
        return None
    if snapshot.geometry_source not in C15_ROOM_INDEX_GEOMETRY_SOURCES:
        return None
    if not context.revision_id or not context.current_revision_id:
        return None
    if context.revision_id != context.current_revision_id:
        return None
    if snapshot.document_id != context.document_id:
        return None
    if snapshot.viewport_id not in context.trusted_viewport_ids():
        return None
    if int(snapshot.page_number) not in context.trusted_page_numbers():
        return None
    mapped = context.page_for_viewport(snapshot.viewport_id)
    if mapped is not None and int(mapped) != int(snapshot.page_number):
        return None
    if snapshot.fail_closed_reason:
        return None

    rooms_by_ref: dict[str, RoomCandidate] = {}
    room_fingerprints: list[dict[str, object]] = []
    for room in snapshot.rooms:
        ref = _clean(room.room_ref)
        if not ref or ref in rooms_by_ref:
            # Ambiguous duplicate room_ref in one snapshot — fail closed.
            return None
        if room.document_id != snapshot.document_id:
            continue
        if room.viewport_id != snapshot.viewport_id:
            continue
        if int(room.source_page) != int(snapshot.page_number):
            continue
        if room.status not in _BINDABLE_ROOM_STATUSES:
            continue
        if len(room.polygon_pdf_pts) < 3:
            continue
        rooms_by_ref[ref] = room
        room_fingerprints.append(
            {
                "room_ref": ref,
                "document_id": room.document_id,
                "viewport_id": room.viewport_id,
                "source_page": int(room.source_page),
                "status": room.status.value,
                "polygon_pdf_pts": [list(pt) for pt in room.polygon_pdf_pts],
                "evidence": list(room.evidence),
            }
        )

    snapshot_fp = stable_contract_id(
        "topsnap",
        {
            "document_id": snapshot.document_id,
            "page_id": snapshot.page_id,
            "page_number": int(snapshot.page_number),
            "viewport_id": snapshot.viewport_id,
            "geometry_source": snapshot.geometry_source,
            "viewport_authority": snapshot.viewport_authority,
            "rooms": room_fingerprints,
        },
    )
    index_id = stable_contract_id(
        "topidx",
        {
            "snapshot": snapshot_fp,
            "document_id": context.document_id,
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "page_id": snapshot.page_id,
            "page_no": int(snapshot.page_number),
            "viewport_id": snapshot.viewport_id,
            "geometry_source": snapshot.geometry_source,
        },
    )
    return OwnedTopologyRoomIndex(
        index_id=index_id,
        document_id=_clean(context.document_id),
        source_sha256=_clean(context.source_sha256).lower(),
        revision_id=_clean(context.current_revision_id),
        page_id=_clean(snapshot.page_id),
        page_no=int(snapshot.page_number),
        viewport_id=_clean(snapshot.viewport_id),
        topology_snapshot_fingerprint=snapshot_fp,
        geometry_source=_clean(snapshot.geometry_source),
        _rooms_by_ref=dict(rooms_by_ref),
        _seal=_INDEX_SEAL,
    )



def build_owned_source_room_face_index(
    *,
    room_face_authority: SourceRoomFaceAuthority,
    selector: SourceRoomFaceSelector,
    context: ProviderContext,
    viewport: ViewportEvidence,
) -> Optional[OwnedTopologyRoomIndex]:
    """Seal a room index from producer-owned source room-face authority.

    This is the authenticated replacement for the intentionally disabled
    diagnostic TopologySnapshot path.  Callers provide only selector/context
    addresses; room polygons come from the sealed source authority.
    """

    if type(room_face_authority) is not SourceRoomFaceAuthority:
        raise TypeError("room_face_authority must be SourceRoomFaceAuthority")
    if type(selector) is not SourceRoomFaceSelector:
        raise TypeError("selector must be SourceRoomFaceSelector")

    result = room_face_authority.resolve_scope(selector)
    if (
        result.status is not EvidenceResolutionStatus.CORROBORATED
        or not result.scope_complete
        or not result.records
    ):
        return None

    if not context.revision_id or not context.current_revision_id:
        return None
    if context.revision_id != context.current_revision_id:
        return None
    if result.document_id != context.document_id:
        return None
    if result.source_sha256.lower() != context.source_sha256.lower():
        return None
    if result.revision_id != context.current_revision_id:
        return None

    try:
        source_page_no = int(result.page_id)
    except (TypeError, ValueError):
        return None
    if source_page_no not in context.trusted_page_numbers():
        return None
    if viewport.document_id != context.document_id:
        return None
    if viewport.viewport_id not in context.trusted_viewport_ids():
        return None
    if viewport.status not in (
        ViewportResolutionStatus.RESOLVED,
        ViewportResolutionStatus.DERIVED,
    ):
        return None
    mapped_page = context.page_for_viewport(viewport.viewport_id)
    if mapped_page is not None and int(mapped_page) != source_page_no:
        return None

    rooms_by_ref: dict[str, RoomCandidate] = {}
    fingerprints: list[dict[str, object]] = []
    for record in result.records:
        if (
            record.document_id != result.document_id
            or record.revision_id != result.revision_id
            or record.source_sha256.lower() != result.source_sha256.lower()
            or record.snapshot_id != result.snapshot_id
            or record.page_id != result.page_id
            or record.decision_scope_id != result.decision_scope_id
            or len(record.polygon_pdf_pts) < 3
            or record.area_page_pts2 <= 0.0
        ):
            return None
        room_ref = _clean(record.face_id)
        if not room_ref or room_ref in rooms_by_ref:
            return None
        room = RoomCandidate(
            room_ref=room_ref,
            label=room_ref,
            polygon_pdf_pts=record.polygon_pdf_pts,
            polygon_m=None,
            floor_area_m2=None,
            area_page_pts2=float(record.area_page_pts2),
            perimeter_m=None,
            geometry_confidence=1.0,
            evidence=(
                record.record_id,
                *(f"physical_wall:{wall_id}" for wall_id in record.bounding_wall_ids),
            ),
            source_page=source_page_no,
            drawing_number="",
            scale_source=GEOMETRY_SOURCE_AUTHENTICATED_ROOM_FACES,
            calibration_confidence=0.0,
            has_voids=False,
            document_id=result.document_id,
            viewport_id=viewport.viewport_id,
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        rooms_by_ref[room_ref] = room
        fingerprints.append(
            {
                "room_ref": room_ref,
                "record_id": record.record_id,
                "polygon_pdf_pts": [list(point) for point in record.polygon_pdf_pts],
                "bounding_wall_ids": list(record.bounding_wall_ids),
                "area_page_pts2": float(record.area_page_pts2),
            }
        )

    if not rooms_by_ref:
        return None

    source_fingerprint = stable_contract_id(
        "source_room_face_index",
        {
            "document_id": result.document_id,
            "revision_id": result.revision_id,
            "source_sha256": result.source_sha256,
            "snapshot_id": result.snapshot_id,
            "page_id": result.page_id,
            "decision_scope_id": result.decision_scope_id,
            "rooms": fingerprints,
        },
    )
    index_id = stable_contract_id(
        "topidx",
        {
            "source_room_face_index": source_fingerprint,
            "document_id": context.document_id,
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "page_id": result.page_id,
            "page_no": source_page_no,
            "viewport_id": viewport.viewport_id,
            "geometry_source": GEOMETRY_SOURCE_AUTHENTICATED_ROOM_FACES,
        },
    )
    return OwnedTopologyRoomIndex(
        index_id=index_id,
        document_id=_clean(context.document_id),
        source_sha256=_clean(context.source_sha256).lower(),
        revision_id=_clean(context.current_revision_id),
        page_id=_clean(result.page_id),
        page_no=source_page_no,
        viewport_id=_clean(viewport.viewport_id),
        topology_snapshot_fingerprint=source_fingerprint,
        geometry_source=GEOMETRY_SOURCE_AUTHENTICATED_ROOM_FACES,
        _rooms_by_ref=dict(rooms_by_ref),
        _seal=_INDEX_SEAL,
    )


@dataclass(frozen=True)
class CeilingFinishScopeProof:
    """Resolver-minted proof that one finish candidate belongs to one room."""

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
    topology_index_id: str
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
    room_index: OwnedTopologyRoomIndex,
    page_id: str,
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
        "document_id": room_index.document_id,
        "source_sha256": room_index.source_sha256,
        "revision_id": room_index.revision_id,
        "page_id": page_id,
        "page_no": int(room_index.page_no),
        "viewport_id": room_index.viewport_id,
        "topology_index_id": room_index.index_id,
        "proof_evidence_ids": list(proof_evidence_ids),
    }
    return CeilingFinishScopeProof(
        proof_id=stable_contract_id("cfsproof", payload),
        finish_evidence_id=finish_id,
        room_entity_id=room_id,
        proof_kind=proof_kind,
        document_id=room_index.document_id,
        source_sha256=room_index.source_sha256,
        revision_id=room_index.revision_id,
        page_id=_clean(page_id),
        page_no=int(room_index.page_no),
        viewport_id=room_index.viewport_id,
        topology_index_id=room_index.index_id,
        proof_evidence_ids=tuple(_clean(eid) for eid in proof_evidence_ids if _clean(eid)),
        reason_codes=tuple(_clean(code) for code in reason_codes if _clean(code)),
        _seal=_PROOF_SEAL,
    )


def _candidate_owned_by_index(
    *,
    atom: EvidenceAtom,
    room_index: OwnedTopologyRoomIndex,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if atom.document_id != document.document_id or atom.document_id != room_index.document_id:
        blockers.append("finish_document_mismatch")
    if atom.evidence_id not in document.evidence_ids:
        blockers.append("finish_evidence_not_owned_by_document")
    if atom.page_id != viewport.page_id or atom.page_id != room_index.page_id:
        blockers.append("finish_page_mismatch")
    meta = atom.metadata if isinstance(atom.metadata, dict) else {}
    try:
        atom_page = int(meta.get("page_no"))
    except (TypeError, ValueError):
        atom_page = None
    if atom_page is None or atom_page != int(room_index.page_no):
        blockers.append("finish_page_no_mismatch")
    source = _clean(meta.get("source_sha256")).lower()
    if source != room_index.source_sha256:
        blockers.append("finish_source_sha256_mismatch")
    revision = _clean(meta.get("revision_id"))
    if revision != room_index.revision_id:
        blockers.append("finish_revision_mismatch")
    if atom.viewport_id not in (None, "", viewport.viewport_id, room_index.viewport_id):
        blockers.append("finish_viewport_mismatch")
    return tuple(dict.fromkeys(blockers))


def resolve_ceiling_finish_scope_proofs(
    *,
    candidates: Sequence[EvidenceAtom],
    room_index: Optional[OwnedTopologyRoomIndex],
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[CeilingFinishScopeProof, ...]:
    """Mint sealed proofs from unscoped finish candidates + owned room index.

    ``room_index`` must be producer-owned. Caller-supplied ``RoomCandidate``
    sequences are not accepted by this API.
    """
    if room_index is None or not room_index.is_producer_owned:
        return ()
    if document.document_id != room_index.document_id:
        return ()
    if document.source_sha256 != room_index.source_sha256:
        return ()
    if viewport.document_id != room_index.document_id:
        return ()
    if viewport.viewport_id != room_index.viewport_id:
        return ()
    if viewport.page_id != room_index.page_id:
        return ()

    usable_rooms = room_index.rooms()
    if not usable_rooms:
        return ()

    proofs: list[CeilingFinishScopeProof] = []
    for atom in candidates:
        if _candidate_owned_by_index(
            atom=atom,
            room_index=room_index,
            document=document,
            viewport=viewport,
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
                room_index=room_index,
                page_id=atom.page_id,
                proof_kind=PROOF_TEXT_BBOX_IN_UNIQUE_ROOM_CANDIDATE,
                proof_evidence_ids=(
                    f"topology_index:{room_index.index_id}",
                    f"room_candidate:{room.room_ref}",
                    atom.evidence_id,
                    *tuple(room.evidence),
                ),
                reason_codes=("unique_indexed_room_contains_finish_bbox_center",),
            )
        )
    proofs.sort(key=lambda item: item.proof_id)
    return tuple(proofs)


def bind_unscoped_finish_candidates_to_room(
    *,
    candidates: Sequence[EvidenceAtom],
    queried_room_ref: str,
    proofs: Sequence[CeilingFinishScopeProof],
    room_index: OwnedTopologyRoomIndex,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[EvidenceAtom, ...]:
    """Materialize scoped atoms for a queried room_ref from resolver proofs.

    ``queried_room_ref`` selects which resolved proofs to apply. It never
    certifies ownership. The room must exist in the producer-owned index.
    """
    scope = _clean(queried_room_ref)
    if not scope or not room_index.is_producer_owned:
        return ()
    if room_index.room(scope) is None:
        return ()

    trusted: list[CeilingFinishScopeProof] = []
    for proof in proofs:
        if not proof.is_resolver_minted:
            continue
        if _clean(proof.room_entity_id) != scope:
            continue
        if proof.topology_index_id != room_index.index_id:
            continue
        if proof.document_id != room_index.document_id:
            continue
        if proof.source_sha256 != room_index.source_sha256:
            continue
        if proof.revision_id != room_index.revision_id:
            continue
        if int(proof.page_no) != int(room_index.page_no):
            continue
        if proof.viewport_id != room_index.viewport_id:
            continue
        if proof.page_id != room_index.page_id:
            continue
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
                "topology_index_id": proof.topology_index_id,
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
        meta["topology_index_id"] = room_index.index_id
        meta["scope_binding_proof_ids"] = tuple(sorted(proof.proof_id for proof in matching))
        meta["scope_binding_proof_kinds"] = tuple(
            sorted({proof.proof_kind for proof in matching})
        )
        meta["scope_bound"] = True
        scoped_id = stable_contract_id(
            "ev",
            {
                "kind": atom.kind,
                "scoped_from": atom.evidence_id,
                "scope_entity_id": scope,
                "topology_index_id": room_index.index_id,
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
