"""C15 ceiling-lining shadow wiring adapter.

Feeds already-finalized authoritative area ``QuantityEvidence`` plus explicit
ceiling-finish ``EvidenceAtom``s into ``build_ceiling_lining_quantity``.

This adapter:

* never selects among competing raw area candidates;
* never invents floor/ceiling geometry or scale;
* never emits live ``ExtractedPrediction`` rows;
* never projects commercial / JobHub takeoff;
* never promotes shadow results to FIRM.

Live ``GenericPlanReaderExtractor`` remains unchanged by this module. Callers
that already hold a finalized room/floor/footprint ``QuantityEvidence`` (for
example the room-area quantity path) invoke ``resolve_ceiling_lining_shadow``.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from pb_ceiling_lining_quantity import (
    CEILING_LINING_FAMILY,
    CEILING_LINING_FORMULA_VERSION,
    build_ceiling_lining_quantity,
    explicit_ceiling_finish_descriptor,
    iter_explicit_ceiling_finish_matches,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext

SHADOW_ADAPTER_VERSION = "1.0.0"
_ACCEPTED_AREA_FAMILIES = frozenset(
    {
        "room_area",
        "floor_area",
        "footprint_area",
        "floor_footprint_area",
    }
)


def empty_ceiling_lining_shadow(*, reason: str) -> dict[str, Any]:
    """Fail-closed shadow bag used when wiring cannot proceed."""
    return {
        "status": "abstained",
        "reason": str(reason or "ceiling_lining_shadow_unresolved"),
        "adapter_version": SHADOW_ADAPTER_VERSION,
        "quantities": [],
        "finish_evidence_ids": [],
        "shadow_only": True,
        "commercial_projection_allowed": False,
    }


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: object) -> str:
    return " ".join(_clean(value).replace("\u00a0", " ").split()).casefold()


def _scope_of_area(area: QuantityEvidence) -> str:
    ids = tuple(_clean(item) for item in area.input_entity_ids if _clean(item))
    if len(ids) != 1:
        return ""
    return ids[0]


def collect_explicit_ceiling_finish_atoms(
    *,
    page_text: str,
    scope_entity_id: str,
    document_id: str,
    page_id: str,
    viewport_id: str,
    method: str = "native_pdf_text",
    kind: str = "ceiling_finish",
    confidence: float = 0.95,
) -> tuple[EvidenceAtom, ...]:
    """Collect explicit ceiling-finish / ceiling-lining atoms from native text.

    Only the C15 explicit grammar is accepted.  Height text, bare RCP mentions,
    and unresolved schedule references produce no atoms.  OCR-only methods remain
    allowed as atoms; ``build_ceiling_lining_quantity`` still fails closed unless a
    non-OCR corroborating atom exists for the same descriptor.
    """
    scope = _clean(scope_entity_id)
    if not scope:
        return ()

    atoms: list[EvidenceAtom] = []
    for raw in iter_explicit_ceiling_finish_matches(page_text):
        descriptor = explicit_ceiling_finish_descriptor(raw)
        if descriptor is None:
            continue
        evidence_id = stable_contract_id(
            "ev",
            {
                "kind": kind,
                "scope_entity_id": scope,
                "document_id": document_id,
                "page_id": page_id,
                "viewport_id": viewport_id,
                "method": method,
                "descriptor": descriptor,
            },
        )
        atoms.append(
            EvidenceAtom(
                evidence_id=evidence_id,
                document_id=document_id,
                page_id=page_id,
                kind=kind,
                method=method,
                viewport_id=viewport_id,
                raw_text=raw,
                confidence=float(confidence),
                status=EvidenceResolutionStatus.RAW,
                metadata={"scope_entity_id": scope},
            )
        )
    return tuple(atoms)


def _competing_area_abstention(
    *,
    scope_entity_id: str,
    competing_areas: Sequence[QuantityEvidence],
    finish_evidence_atoms: Sequence[EvidenceAtom],
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> QuantityEvidence:
    """Abstain when more than one finalized area claims the same scope."""
    scope = _clean(scope_entity_id)
    blockers = ("competing_authoritative_area_quantities",)
    evidence_ids = tuple(
        sorted(
            {
                *(atom.evidence_id for atom in finish_evidence_atoms),
                *(eid for area in competing_areas for eid in area.evidence_ids),
            }
        )
    )
    payload = {
        "family": CEILING_LINING_FAMILY,
        "scope_entity_id": scope,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "viewport_id": viewport.viewport_id,
        "page_no": int(page_no),
        "blockers": list(blockers),
        "competing_area_quantity_ids": [area.quantity_id for area in competing_areas],
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=CEILING_LINING_FAMILY,
        semantic_key=f"ceiling_lining:{scope or 'unresolved'}",
        value=None,
        unit="m2",
        input_entity_ids=(scope,) if scope else (),
        formula="reuse_same_scope_authoritative_area_with_explicit_ceiling_finish",
        formula_version=CEILING_LINING_FORMULA_VERSION,
        evidence_ids=evidence_ids,
        authority=MeasurementAuthorityType.MODEL_DERIVED.value,
        status=AuthorityStatus.BLOCKED.value,
        confidence=0.0,
        abstained=True,
        blocking_reasons=blockers,
        reason_codes=blockers,
        metadata={
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "page_no": int(page_no),
            "viewport_id": viewport.viewport_id,
            "shadow_only": True,
            "commercial_projection_allowed": False,
            "competing_area_quantity_ids": tuple(
                area.quantity_id for area in competing_areas
            ),
        },
    )


def resolve_ceiling_lining_shadow(
    *,
    authoritative_area_quantities: Sequence[QuantityEvidence],
    finish_evidence_atoms: Sequence[EvidenceAtom],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> dict[str, Any]:
    """Wire finalized areas + finish atoms into shadow ceiling-lining quantities.

    Each accepted area quantity is consumed as already finalized.  When more than
    one area quantity claims the same ``input_entity_ids`` scope, this adapter
    abstains for that scope rather than choosing among them.
    """
    finish_atoms = tuple(finish_evidence_atoms)
    finish_ids = tuple(sorted({atom.evidence_id for atom in finish_atoms}))

    if not authoritative_area_quantities:
        bag = empty_ceiling_lining_shadow(reason="missing_authoritative_area_quantity")
        bag["finish_evidence_ids"] = list(finish_ids)
        return bag

    # Deterministic traversal — never "first wins" among scopes.
    areas = tuple(
        sorted(
            authoritative_area_quantities,
            key=lambda item: (item.quantity_id, item.semantic_key, item.family),
        )
    )

    by_scope: dict[str, list[QuantityEvidence]] = {}
    unscoped: list[QuantityEvidence] = []
    for area in areas:
        if _norm(area.family) not in _ACCEPTED_AREA_FAMILIES:
            # Not an area family this dependent claim understands — ignore, do
            # not attempt to reinterpret as floor/ceiling area.
            continue
        scope = _scope_of_area(area)
        if not scope:
            unscoped.append(area)
            continue
        by_scope.setdefault(scope, []).append(area)

    quantities: list[QuantityEvidence] = []

    for area in unscoped:
        quantities.append(
            build_ceiling_lining_quantity(
                scope_entity_id="",
                area_quantity=area,
                finish_evidence_atoms=finish_atoms,
                context=context,
                document=document,
                viewport=viewport,
                page_no=page_no,
            )
        )

    for scope in sorted(by_scope):
        scoped_areas = by_scope[scope]
        if len(scoped_areas) != 1:
            quantities.append(
                _competing_area_abstention(
                    scope_entity_id=scope,
                    competing_areas=scoped_areas,
                    finish_evidence_atoms=finish_atoms,
                    context=context,
                    viewport=viewport,
                    page_no=page_no,
                )
            )
            continue

        quantities.append(
            build_ceiling_lining_quantity(
                scope_entity_id=scope,
                area_quantity=scoped_areas[0],
                finish_evidence_atoms=finish_atoms,
                context=context,
                document=document,
                viewport=viewport,
                page_no=page_no,
            )
        )

    if not quantities:
        bag = empty_ceiling_lining_shadow(
            reason="no_accepted_floor_or_footprint_area_family"
        )
        bag["finish_evidence_ids"] = list(finish_ids)
        return bag

    serialized = tuple(qty.to_dict() for qty in quantities)
    any_numeric = any(
        (not qty.abstained) and qty.value is not None for qty in quantities
    )
    return {
        "status": "shadow_quantities" if any_numeric else "abstained",
        "reason": (
            "same_scope_authoritative_area_with_explicit_ceiling_finish"
            if any_numeric
            else "ceiling_lining_shadow_blocked"
        ),
        "adapter_version": SHADOW_ADAPTER_VERSION,
        "quantities": list(serialized),
        "finish_evidence_ids": list(finish_ids),
        "shadow_only": True,
        "commercial_projection_allowed": False,
        "quantity_records": quantities,
    }


def shadow_quantity_records(
    shadow_bag: Mapping[str, Any],
) -> tuple[QuantityEvidence, ...]:
    """Return in-memory QuantityEvidence records from a shadow bag when present."""
    records = shadow_bag.get("quantity_records")
    if isinstance(records, (list, tuple)):
        return tuple(records)
    return ()
