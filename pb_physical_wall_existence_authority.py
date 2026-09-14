"""Typed physical-wall existence authority, separate from thickness.

``WallCandidate.status == CORROBORATED`` cannot be used as existence proof:
that top-level status is coupled to ``thickness_authority`` by
``WallCandidate.__post_init__``. This module exposes:

- ``wall_physical_existence_status`` — typed ``EvidenceResolutionStatus``
- ``adapt_wall_candidate_to_entity_evidence`` — WallCandidate → EntityEvidence
- ``resolve_physical_wall_existence`` — diagnostic existence atom

It reuses ``EntityEvidence`` / ``EvidenceResolutionStatus`` / ``stable_contract_id``
and the canonical causal-domain map. It does not read
``metadata["physical_evidence_status"]``, invent thickness, or publish
quantities.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Union

from pb_canonical_wall_room_evidence_model import (
    EvidenceDomain,
    FAMILY_DOMAIN,
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_PAIRED_WALL_FACES,
    FAMILY_U2_PHYSICAL_WALL_LINEWORK,
    FAMILY_VALID_JUNCTION_BEHAVIOR,
)
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    canonical_contract_json,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_wall_room_topology_contracts import WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

PHYSICAL_WALL_EXISTENCE_KIND = "physical_wall_existence"
PHYSICAL_WALL_EXISTENCE_METHOD = "physical_wall_existence_authority"
PHYSICAL_WALL_EXISTENCE_SCHEMA_VERSION = "1.1.0"
ADDITIONAL_WALL_EVIDENCE_KIND_FIGURED = "figured_dimension"

_AtomLike = Union[EvidenceAtom, Mapping[str, Any]]

_KIND_TO_FAMILY = {
    KIND_PHYSICAL_WALL: FAMILY_U2_PHYSICAL_WALL_LINEWORK,
    FAMILY_U2_PHYSICAL_WALL_LINEWORK: FAMILY_U2_PHYSICAL_WALL_LINEWORK,
    FAMILY_PAIRED_WALL_FACES: FAMILY_PAIRED_WALL_FACES,
    FAMILY_NATIVE_LAYER_WALL_SUPPORT: FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_VALID_JUNCTION_BEHAVIOR: FAMILY_VALID_JUNCTION_BEHAVIOR,
}

# Same corroborating-domain set as #286: junction/graph topology is contextual only.
_CORROBORATING_DOMAINS = frozenset(
    {
        EvidenceDomain.NATIVE_METADATA,
        EvidenceDomain.GEOMETRIC_RELATION,
        EvidenceDomain.EXTERNAL_INDEPENDENT,
    }
)


def _atom_field(atom: _AtomLike, key: str, default: Any = None) -> Any:
    if isinstance(atom, EvidenceAtom):
        if key == "evidence_id":
            return atom.evidence_id
        if key == "kind":
            return atom.kind
        if key == "metadata":
            return atom.metadata
        return getattr(atom, key, default)
    return atom.get(key, default)


def _family_for_kind(kind: str) -> Optional[str]:
    if kind in FAMILY_DOMAIN:
        return kind
    return _KIND_TO_FAMILY.get(kind)


def _atom_status_value(atom: _AtomLike) -> str:
    status = _atom_field(atom, "status")
    if isinstance(status, EvidenceResolutionStatus):
        return status.value
    return str(status or "")


def _atom_content_key(atom: _AtomLike) -> str:
    metadata = _atom_field(atom, "metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    payload = {
        "kind": str(_atom_field(atom, "kind") or ""),
        "document_id": str(_atom_field(atom, "document_id") or ""),
        "page_id": str(_atom_field(atom, "page_id") or ""),
        "viewport_id": str(_atom_field(atom, "viewport_id") or ""),
        "method": str(_atom_field(atom, "method") or ""),
        "raw_text": str(_atom_field(atom, "raw_text") or ""),
        "normalized_value": _atom_field(atom, "normalized_value"),
        "unit": _atom_field(atom, "unit"),
        "status": _atom_status_value(atom),
        "reason_codes": list(_atom_field(atom, "reason_codes") or ()),
        "metadata": dict(metadata),
    }
    return canonical_contract_json(payload)


def _index_atoms(atoms: Sequence[_AtomLike]) -> tuple[dict[str, _AtomLike], frozenset[str]]:
    """Index atoms without last-write-wins.

    Identical same-id copies collapse to one observation. Same-id atoms with
    differing content are removed and reported as collisions. Order cannot
    change which content wins because conflicting content never wins.
    """
    first: dict[str, _AtomLike] = {}
    content_by_id: dict[str, str] = {}
    collisions: set[str] = set()
    for atom in atoms:
        evidence_id = str(_atom_field(atom, "evidence_id") or "").strip()
        if not evidence_id:
            continue
        content = _atom_content_key(atom)
        if evidence_id in collisions:
            continue
        if evidence_id not in first:
            first[evidence_id] = atom
            content_by_id[evidence_id] = content
            continue
        if content_by_id[evidence_id] != content:
            collisions.add(evidence_id)
            first.pop(evidence_id, None)
    return first, frozenset(collisions)


def _wall_edge_ids(wall: WallCandidate) -> set[str]:
    ids = set(wall.face_a_segment_ids)
    if wall.face_b_segment_ids:
        ids.update(wall.face_b_segment_ids)
    return ids


def _wall_source_primitive_ids(wall: WallCandidate) -> set[str]:
    metadata = wall.metadata or {}
    raw = metadata.get("source_primitive_ids") if isinstance(metadata, Mapping) else None
    return {str(item) for item in (raw or ()) if item not in (None, "")}


def _atom_metadata(atom: _AtomLike) -> Mapping[str, Any]:
    metadata = _atom_field(atom, "metadata") or {}
    return metadata if isinstance(metadata, Mapping) else {}


def _atom_bound_to_wall(atom: _AtomLike, wall: WallCandidate) -> bool:
    metadata = _atom_metadata(atom)
    wall_id = str(metadata.get("wall_candidate_id") or "").strip()
    if wall_id and wall_id == wall.candidate_id:
        return True
    target_edge = str(metadata.get("target_edge_id") or "").strip()
    if target_edge and target_edge in _wall_edge_ids(wall):
        return True
    atom_prims = {str(item) for item in (metadata.get("source_primitive_ids") or ()) if item}
    wall_prims = _wall_source_primitive_ids(wall)
    return bool(atom_prims and wall_prims and atom_prims & wall_prims)


def _atom_target_ownership_reasons(
    atom: _AtomLike,
    *,
    wall: WallCandidate,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if str(_atom_field(atom, "document_id") or "") != document.document_id:
        reasons.append("existence_atom_document_mismatch")
    if str(_atom_field(atom, "page_id") or "") != viewport.page_id:
        reasons.append("existence_atom_page_mismatch")
    atom_viewport = _atom_field(atom, "viewport_id")
    if not (atom_viewport and atom_viewport == wall.viewport_id == viewport.viewport_id):
        reasons.append("existence_atom_viewport_mismatch")
    if not _atom_bound_to_wall(atom, wall):
        reasons.append("existence_atom_not_bound_to_wall")
    return tuple(reasons)


def bind_additional_wall_owned_evidence(
    *,
    wall: WallCandidate,
    atom: _AtomLike,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> Optional[str]:
    """Typed extra-evidence seam. Figured dimensions only, wall-bound."""
    evidence_id = str(_atom_field(atom, "evidence_id") or "").strip()
    if not evidence_id:
        return None
    if evidence_id not in document.evidence_ids:
        return None
    if str(_atom_field(atom, "kind") or "") != ADDITIONAL_WALL_EVIDENCE_KIND_FIGURED:
        return None
    if _atom_target_ownership_reasons(atom, wall=wall, document=document, viewport=viewport):
        return None
    return evidence_id


def resolve_physical_wall_existence(
    *,
    wall: WallCandidate,
    evidence_atoms: Sequence[_AtomLike],
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> EvidenceAtom:
    """Mint one existence atom from owned supporting/opposing source atoms.

    Existence is CORROBORATED only when two or more *independent causal
    domains* support the wall and no opposing atoms are present. Thickness,
    height, scale, and scope are out of scope.
    """
    catalog, collided_ids = _index_atoms(evidence_atoms)
    supporting_ids = tuple(wall.supporting_evidence_ids)
    opposing_ids = tuple(wall.conflicting_evidence_ids)

    blockers: list[str] = []
    families_present: set[str] = set()
    missing_ids: list[str] = []

    if wall.viewport_id != viewport.viewport_id:
        blockers.append("existence_wall_viewport_mismatch")
    if viewport.document_id != document.document_id:
        blockers.append("existence_viewport_document_mismatch")

    for evidence_id in supporting_ids:
        if evidence_id in collided_ids:
            blockers.append("existence_evidence_id_collision")
            continue
        atom = catalog.get(evidence_id)
        if atom is None:
            missing_ids.append(evidence_id)
            continue
        ownership = _atom_target_ownership_reasons(
            atom, wall=wall, document=document, viewport=viewport
        )
        if ownership:
            blockers.extend(ownership)
            continue
        family = _family_for_kind(str(_atom_field(atom, "kind") or ""))
        if family is None:
            blockers.append("existence_supporting_kind_unmapped")
            continue
        families_present.add(family)

    for evidence_id in opposing_ids:
        if evidence_id in collided_ids:
            blockers.append("existence_evidence_id_collision")
            continue
        atom = catalog.get(evidence_id)
        if atom is None:
            missing_ids.append(evidence_id)
            continue
        ownership = _atom_target_ownership_reasons(
            atom, wall=wall, document=document, viewport=viewport
        )
        if ownership:
            blockers.extend(ownership)

    if missing_ids:
        blockers.append("existence_source_atom_missing")

    has_supporting = bool(supporting_ids)
    has_opposing = bool(opposing_ids)
    corroborating_domains = {
        FAMILY_DOMAIN[family]
        for family in families_present
        if FAMILY_DOMAIN[family] in _CORROBORATING_DOMAINS
    }

    if blockers:
        status = EvidenceResolutionStatus.ABSTAINED
        reason_codes = tuple(dict.fromkeys(blockers))
        confidence = 0.0
    elif has_opposing and has_supporting:
        status = EvidenceResolutionStatus.CONFLICT
        reason_codes = ("supporting_and_opposing_physical_wall_evidence",)
        confidence = min(float(wall.confidence), 0.5)
    elif has_opposing and not has_supporting:
        status = EvidenceResolutionStatus.ABSTAINED
        reason_codes = ("opposing_physical_wall_evidence_without_support",)
        confidence = 0.0
    elif len(corroborating_domains) >= 2:
        status = EvidenceResolutionStatus.CORROBORATED
        reason_codes = (
            "corroborated_by_independent_domains:"
            + ",".join(sorted(d.value for d in corroborating_domains)),
        )
        confidence = max(float(wall.confidence), 0.75)
    elif families_present:
        status = EvidenceResolutionStatus.CANDIDATE
        reason_codes = (
            "insufficient_independent_domains_for_physical_wall_existence:"
            + ",".join(sorted(families_present)),
        )
        confidence = float(wall.confidence)
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reason_codes = ("no_physical_wall_existence_evidence",)
        confidence = 0.0

    payload = {
        "kind": PHYSICAL_WALL_EXISTENCE_KIND,
        "method": PHYSICAL_WALL_EXISTENCE_METHOD,
        "wall_candidate_id": wall.candidate_id,
        "document_id": document.document_id,
        "page_id": viewport.page_id,
        "viewport_id": viewport.viewport_id,
        "supporting_evidence_ids": list(supporting_ids),
        "opposing_evidence_ids": list(opposing_ids),
        "families_present": sorted(families_present),
        "corroborating_domains": sorted(d.value for d in corroborating_domains),
        "status": status.value,
        "reason_codes": list(reason_codes),
        "schema_version": PHYSICAL_WALL_EXISTENCE_SCHEMA_VERSION,
    }
    return EvidenceAtom(
        evidence_id=stable_contract_id("wev", payload),
        document_id=document.document_id,
        page_id=viewport.page_id,
        viewport_id=viewport.viewport_id,
        kind=PHYSICAL_WALL_EXISTENCE_KIND,
        method=PHYSICAL_WALL_EXISTENCE_METHOD,
        confidence=confidence,
        status=status,
        reason_codes=reason_codes,
        metadata={
            "wall_candidate_id": wall.candidate_id,
            "supporting_evidence_ids": list(supporting_ids),
            "opposing_evidence_ids": list(opposing_ids),
            "families_present": sorted(families_present),
            "corroborating_domains": sorted(d.value for d in corroborating_domains),
            "schema_version": PHYSICAL_WALL_EXISTENCE_SCHEMA_VERSION,
        },
    )


def wall_physical_existence_status(
    wall: WallCandidate,
    *,
    evidence_atoms: Sequence[_AtomLike],
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> EvidenceResolutionStatus:
    """Typed existence status. Does not read wall.metadata or wall.status."""
    return resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=evidence_atoms,
        document=document,
        viewport=viewport,
    ).status


def adapt_wall_candidate_to_entity_evidence(
    wall: WallCandidate,
    *,
    evidence_atoms: Sequence[_AtomLike],
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    context: ProviderContext,
    additional_owned_evidence_ids: Sequence[str] = (),
) -> Optional[EntityEvidence]:
    """WallCandidate → EntityEvidence using typed existence, not wall.status.

    ``evidence_ids`` are the wall's real supporting/conflicting ids plus any
    extra ids that pass ``bind_additional_wall_owned_evidence`` (figured
    dimension, document-owned, and bound to this wall). Raw document-owned
    IDs are not authority. Existence status never consults extras.
    Missing ownership or empty real provenance returns None (abstain).
    """
    if wall.viewport_id != viewport.viewport_id:
        return None
    if document.document_id != context.document_id:
        return None
    if viewport.document_id != context.document_id:
        return None
    if document.source_sha256 != context.source_sha256:
        return None
    if viewport.viewport_id not in context.trusted_viewport_ids():
        return None

    catalog, collided_ids = _index_atoms(evidence_atoms)
    existence = resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=evidence_atoms,
        document=document,
        viewport=viewport,
    )
    real_ids = tuple(dict.fromkeys((*wall.supporting_evidence_ids, *wall.conflicting_evidence_ids)))
    extra_ids: list[str] = []
    for raw_id in additional_owned_evidence_ids:
        evidence_id = str(raw_id or "").strip()
        if not evidence_id or evidence_id in collided_ids:
            continue
        atom = catalog.get(evidence_id)
        if atom is None:
            continue
        bound = bind_additional_wall_owned_evidence(
            wall=wall,
            atom=atom,
            document=document,
            viewport=viewport,
        )
        if bound:
            extra_ids.append(bound)
    evidence_ids = tuple(dict.fromkeys((*real_ids, *extra_ids)))
    if not evidence_ids:
        return None
    if not set(evidence_ids).issubset(set(document.evidence_ids)):
        return None

    conflict_ids = tuple(wall.conflicting_evidence_ids)
    status = existence.status
    if status == EvidenceResolutionStatus.CORROBORATED:
        conflict_ids = ()
    elif status == EvidenceResolutionStatus.CONFLICT and not conflict_ids:
        status = EvidenceResolutionStatus.ABSTAINED

    return EntityEvidence(
        candidate_entity_id=wall.candidate_id,
        candidate_type="wall",
        evidence_ids=evidence_ids,
        status=status,
        confidence=existence.confidence,
        conflict_evidence_ids=conflict_ids,
        reason_codes=existence.reason_codes,
        metadata={"viewport_id": wall.viewport_id, "existence_evidence_id": existence.evidence_id},
    )
