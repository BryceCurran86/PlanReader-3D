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
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_wall_room_topology_contracts import WallCandidate
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL

PHYSICAL_WALL_EXISTENCE_KIND = "physical_wall_existence"
PHYSICAL_WALL_EXISTENCE_METHOD = "physical_wall_existence_authority"
PHYSICAL_WALL_EXISTENCE_SCHEMA_VERSION = "1.0.0"

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


def _index_atoms(atoms: Sequence[_AtomLike]) -> dict[str, _AtomLike]:
    indexed: dict[str, _AtomLike] = {}
    for atom in atoms:
        evidence_id = str(_atom_field(atom, "evidence_id") or "").strip()
        if evidence_id:
            indexed[evidence_id] = atom
    return indexed


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
    catalog = _index_atoms(evidence_atoms)
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
        atom = catalog.get(evidence_id)
        if atom is None:
            missing_ids.append(evidence_id)
            continue
        family = _family_for_kind(str(_atom_field(atom, "kind") or ""))
        if family is None:
            blockers.append("existence_supporting_kind_unmapped")
            continue
        families_present.add(family)

    for evidence_id in opposing_ids:
        if catalog.get(evidence_id) is None:
            missing_ids.append(evidence_id)

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
    extra ids the caller already owns (for example a figured dimension).
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

    existence = resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=evidence_atoms,
        document=document,
        viewport=viewport,
    )
    real_ids = tuple(dict.fromkeys((*wall.supporting_evidence_ids, *wall.conflicting_evidence_ids)))
    extra = tuple(str(v) for v in additional_owned_evidence_ids if str(v))
    evidence_ids = tuple(dict.fromkeys((*real_ids, *extra)))
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
