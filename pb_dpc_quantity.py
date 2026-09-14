"""Shadow DPC QuantityEvidence that consumes walls, roles, and explicit spec.

DPC does not invent wall geometry. It sums in-scope FIRM wall-length
quantities whose wall-boundary role matches an explicit specification
scope. Bare "DPC" without scope abstains. This module is not wired into
live commercial publishing.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Sequence

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_wall_boundary_role_authority import WallBoundaryRole, WallBoundaryRoleEvidence
from pb_wall_length_quantity import WALL_LENGTH_FAMILY

DPC_FAMILY = "damp_proof_course"
DPC_FORMULA_VERSION = "1.0.0"


class DpcScope(str, Enum):
    ALL_WALLS = "all_walls"
    EXTERNAL = "external"
    INTERNAL = "internal"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"
    ABSENT = "absent"


def resolve_dpc_specification_scope(page_text: str) -> tuple[DpcScope, tuple[str, ...]]:
    """Clause-bound DPC scope. Reuses extractor note splitting and spec detection."""
    if not GenericPlanReaderExtractor._has_dpc_specification(page_text):
        return DpcScope.ABSENT, ("dpc_specification_absent",)
    notes = [
        note
        for note in GenericPlanReaderExtractor._split_into_logical_notes(page_text)
        if GenericPlanReaderExtractor._has_dpc_specification(note)
    ]
    if not notes:
        return DpcScope.ABSENT, ("dpc_specification_absent",)

    scopes: list[DpcScope] = []
    for note in notes:
        normalized = re.sub(r"\s+", " ", note.lower())
        if GenericPlanReaderExtractor._has_dpc_all_walls_scope(note):
            scopes.append(DpcScope.ALL_WALLS)
            continue
        external = bool(re.search(r"\b(?:external|perimeter)\s+walls?\b", normalized))
        internal = bool(re.search(r"\binternal\s+(?:walls?|partitions?)\b", normalized))
        only_external = bool(re.search(r"\bexternal\s+walls?\s+only\b", normalized))
        only_internal = bool(re.search(r"\binternal\s+(?:walls?|partitions?)\s+only\b", normalized))
        if only_external and internal and not only_internal:
            scopes.append(DpcScope.CONFLICT)
        elif only_internal and external and not only_external:
            scopes.append(DpcScope.CONFLICT)
        elif only_external or (external and not internal):
            scopes.append(DpcScope.EXTERNAL)
        elif only_internal or (internal and not external):
            scopes.append(DpcScope.INTERNAL)
        elif external and internal:
            scopes.append(DpcScope.ALL_WALLS)
        else:
            scopes.append(DpcScope.AMBIGUOUS)

    distinct = tuple(dict.fromkeys(scopes))
    if DpcScope.CONFLICT in distinct:
        return DpcScope.CONFLICT, ("conflicting_dpc_scope_notes",)
    if DpcScope.AMBIGUOUS in distinct and len(distinct) == 1:
        return DpcScope.AMBIGUOUS, ("dpc_scope_not_explicit",)
    if len(distinct) > 1 and DpcScope.AMBIGUOUS in distinct:
        distinct = tuple(s for s in distinct if s != DpcScope.AMBIGUOUS)
    if DpcScope.ALL_WALLS in distinct:
        return DpcScope.ALL_WALLS, ("explicit_all_walls_dpc_scope",)
    if set(distinct) == {DpcScope.EXTERNAL, DpcScope.INTERNAL}:
        return DpcScope.CONFLICT, ("conflicting_external_and_internal_dpc_scope",)
    if distinct == (DpcScope.EXTERNAL,):
        return DpcScope.EXTERNAL, ("explicit_external_dpc_scope",)
    if distinct == (DpcScope.INTERNAL,):
        return DpcScope.INTERNAL, ("explicit_internal_dpc_scope",)
    return DpcScope.AMBIGUOUS, ("dpc_scope_not_explicit",)


def _roles_for_scope(scope: DpcScope) -> frozenset[WallBoundaryRole]:
    if scope == DpcScope.ALL_WALLS:
        return frozenset({WallBoundaryRole.EXTERNAL, WallBoundaryRole.INTERNAL_PARTITION})
    if scope == DpcScope.EXTERNAL:
        return frozenset({WallBoundaryRole.EXTERNAL})
    if scope == DpcScope.INTERNAL:
        return frozenset({WallBoundaryRole.INTERNAL_PARTITION})
    return frozenset()


def _abstain(
    *,
    context: ProviderContext,
    page_no: int,
    viewport_id: str,
    blockers: tuple[str, ...],
    scope: DpcScope,
) -> QuantityEvidence:
    payload = {
        "family": DPC_FAMILY,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "page_no": page_no,
        "viewport_id": viewport_id,
        "blockers": list(blockers),
        "scope": scope.value,
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=DPC_FAMILY,
        semantic_key="damp_proof_course",
        value=None,
        unit="m",
        formula="sum(in_scope FIRM wall_length)",
        formula_version=DPC_FORMULA_VERSION,
        authority="unresolved",
        status=AuthorityStatus.BLOCKED.value,
        confidence=0.0,
        abstained=True,
        blocking_reasons=blockers,
        reason_codes=blockers,
        metadata={"dpc_scope": scope.value},
    )


def build_dpc_quantity(
    *,
    wall_lengths: Sequence[QuantityEvidence],
    roles: Sequence[WallBoundaryRoleEvidence],
    page_text: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> QuantityEvidence:
    """Sum in-scope FIRM wall lengths. Does not invent geometry or scale."""
    scope, scope_reasons = resolve_dpc_specification_scope(page_text)
    if document.document_id != context.document_id:
        return _abstain(
            context=context, page_no=page_no, viewport_id=viewport.viewport_id,
            blockers=("dpc_document_mismatch",), scope=scope,
        )
    if document.source_sha256 != context.source_sha256:
        return _abstain(
            context=context, page_no=page_no, viewport_id=viewport.viewport_id,
            blockers=("dpc_source_sha_mismatch",), scope=scope,
        )
    if viewport.viewport_id not in context.trusted_viewport_ids():
        return _abstain(
            context=context, page_no=page_no, viewport_id=viewport.viewport_id,
            blockers=("dpc_viewport_not_owned",), scope=scope,
        )
    if scope in (DpcScope.ABSENT, DpcScope.AMBIGUOUS, DpcScope.CONFLICT):
        return _abstain(
            context=context, page_no=page_no, viewport_id=viewport.viewport_id,
            blockers=scope_reasons, scope=scope,
        )

    wanted = _roles_for_scope(scope)
    roles_by_wall = {r.wall_candidate_id: r for r in roles}
    included: list[QuantityEvidence] = []
    blockers: list[str] = list(scope_reasons)
    for length in wall_lengths:
        if length.family != WALL_LENGTH_FAMILY:
            blockers.append("non_wall_length_input")
            continue
        if length.abstained or length.status != AuthorityStatus.FIRM.value or length.value is None:
            continue
        wall_ids = tuple(length.input_entity_ids)
        if len(wall_ids) != 1:
            return _abstain(
                context=context, page_no=page_no, viewport_id=viewport.viewport_id,
                blockers=("wall_length_identity_not_unique",), scope=scope,
            )
        wall_id = wall_ids[0]
        role = roles_by_wall.get(wall_id)
        if role is None or role.status != EvidenceResolutionStatus.CORROBORATED:
            return _abstain(
                context=context, page_no=page_no, viewport_id=viewport.viewport_id,
                blockers=("firm_wall_length_without_corroborated_role",), scope=scope,
            )
        if role.viewport_id != viewport.viewport_id:
            return _abstain(
                context=context, page_no=page_no, viewport_id=viewport.viewport_id,
                blockers=("dpc_role_viewport_mismatch",), scope=scope,
            )
        if role.role not in (WallBoundaryRole.EXTERNAL, WallBoundaryRole.INTERNAL_PARTITION):
            return _abstain(
                context=context, page_no=page_no, viewport_id=viewport.viewport_id,
                blockers=("firm_wall_length_role_not_external_or_internal",), scope=scope,
            )
        if role.role in wanted:
            included.append(length)
    if not included:
        return _abstain(
            context=context, page_no=page_no, viewport_id=viewport.viewport_id,
            blockers=tuple(dict.fromkeys([*blockers, "no_firm_in_scope_wall_lengths"])),
            scope=scope,
        )

    total = round(sum(float(q.value or 0.0) for q in included), 6)
    evidence_ids = tuple(dict.fromkeys(eid for q in included for eid in q.evidence_ids))
    wall_ids = tuple(dict.fromkeys(wid for q in included for wid in q.input_entity_ids))
    payload = {
        "family": DPC_FAMILY,
        "scope": scope.value,
        "wall_ids": list(wall_ids),
        "value_m": total,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "page_no": page_no,
        "viewport_id": viewport.viewport_id,
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=DPC_FAMILY,
        semantic_key="damp_proof_course",
        value=total,
        unit="m",
        input_entity_ids=wall_ids,
        formula="sum(in_scope FIRM wall_length)",
        formula_version=DPC_FORMULA_VERSION,
        evidence_ids=evidence_ids,
        authority="composed_from_firm_wall_lengths",
        status=AuthorityStatus.FIRM.value,
        confidence=min(float(q.confidence) for q in included),
        abstained=False,
        reason_codes=tuple(dict.fromkeys(scope_reasons)),
        metadata={
            "dpc_scope": scope.value,
            "included_wall_ids": list(wall_ids),
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "page_no": page_no,
            "viewport_id": viewport.viewport_id,
        },
    )
