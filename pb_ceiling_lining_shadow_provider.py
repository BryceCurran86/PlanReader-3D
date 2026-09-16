"""C15 ceiling-lining shadow MigrationProvider.

Rebuild of the parked #316 wiring with mandatory authority corrections:

1. Finish collection is unscoped (``collect_unscoped_ceiling_finish_candidates``).
2. Room ownership requires an independent ``CeilingFinishScopeProof``.
3. Final contract is ``ProviderResult`` via the standard migration envelope —
   not an ad-hoc shadow dictionary.

Shadow-only: no live ExtractedPrediction, no commercial/JobHub publication,
no FIRM promotion, no roof/perimeter/accessory/wastage claims.

Preserves the #315 fail-closed quantity contract in
``build_ceiling_lining_quantity``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from pb_ceiling_lining_quantity import (
    CEILING_LINING_FAMILY,
    CEILING_LINING_FORMULA_VERSION,
    build_ceiling_lining_quantity,
)
from pb_ceiling_lining_scope_binder import (
    CeilingFinishScopeProof,
    bind_unscoped_finish_candidates_to_room,
)
from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    QuantityEvidence,
    ViewportEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import (
    EligibilityDecision,
    ProviderContext,
    ProviderDescriptor,
    ProviderResult,
    fingerprint_source_files,
)
from pb_provider_gold_isolation import assert_provider_gold_free

PROVIDER_ENGINE_ID = "shadow_ceiling_lining"
PROVIDER_ENGINE_VERSION = "2.0.0"
PROVIDER_OUTPUT_SCHEMA_VERSION = "1.0.0"
PROVIDER_FAMILY = CEILING_LINING_FAMILY

_CODE_MODULES = (
    "pb_ceiling_lining_shadow_provider",
    "pb_ceiling_lining_finish_evidence",
    "pb_ceiling_lining_scope_binder",
    "pb_ceiling_lining_quantity",
)

_ACCEPTED_AREA_FAMILIES = frozenset(
    {
        "room_area",
        "floor_area",
        "footprint_area",
        "floor_footprint_area",
    }
)


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: object) -> str:
    return " ".join(_clean(value).replace("\u00a0", " ").split()).casefold()


def ceiling_lining_descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=PROVIDER_ENGINE_ID,
        family=PROVIDER_FAMILY,
        provider_version=PROVIDER_ENGINE_VERSION,
        output_schema_version=PROVIDER_OUTPUT_SCHEMA_VERSION,
        code_fingerprint=fingerprint_source_files(_CODE_MODULES),
    )


@dataclass(frozen=True)
class CeilingLiningShadowInputs:
    """Injected shadow inputs for the provider (tests / shadow harness).

    Live PDF extraction is intentionally not wired: this provider consumes
    already-finalized authoritative area quantities plus unscoped finish
    candidates and independent scope proofs.
    """

    document: DocumentEvidence
    viewport: ViewportEvidence
    page_no: int
    authoritative_area_quantities: tuple[QuantityEvidence, ...]
    unscoped_finish_candidates: tuple[EvidenceAtom, ...]
    scope_proofs: tuple[CeilingFinishScopeProof, ...] = ()


def _scope_of_area(area: QuantityEvidence) -> str:
    ids = tuple(_clean(item) for item in area.input_entity_ids if _clean(item))
    if len(ids) != 1:
        return ""
    return ids[0]


def _competing_area_blocked(
    *,
    scope: str,
    competing_areas: Sequence[QuantityEvidence],
    finish_candidates: Sequence[EvidenceAtom],
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> QuantityEvidence:
    blockers = ("competing_authoritative_area_quantities",)
    evidence_ids = tuple(
        sorted(
            {
                *(eid for area in competing_areas for eid in area.evidence_ids),
                *(atom.evidence_id for atom in finish_candidates),
            }
        )
    )
    payload = {
        "family": PROVIDER_FAMILY,
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
        family=PROVIDER_FAMILY,
        semantic_key=f"ceiling_lining:{scope}",
        value=None,
        unit="m2",
        input_entity_ids=(scope,),
        formula="reuse_same_scope_authoritative_area_with_explicit_ceiling_finish",
        formula_version=CEILING_LINING_FORMULA_VERSION,
        evidence_ids=evidence_ids,
        authority="model_derived",
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
            "competing_area_quantity_ids": tuple(area.quantity_id for area in competing_areas),
        },
    )


class CeilingLiningShadowProvider:
    """MigrationProvider for shadow ceiling-lining quantities."""

    def __init__(self, inputs: Optional[CeilingLiningShadowInputs] = None) -> None:
        assert_provider_gold_free(PROVIDER_ENGINE_ID, "pb_ceiling_lining_shadow_provider")
        self._inputs = inputs
        self.engine_id = PROVIDER_ENGINE_ID
        self.engine_version = PROVIDER_ENGINE_VERSION

    def with_inputs(self, inputs: CeilingLiningShadowInputs) -> "CeilingLiningShadowProvider":
        return CeilingLiningShadowProvider(inputs=inputs)

    def descriptor(self) -> ProviderDescriptor:
        return ceiling_lining_descriptor()

    def eligibility(self, context: ProviderContext) -> EligibilityDecision:
        reasons: list[str] = []
        if not context.source_sha256:
            reasons.append("source_sha256_missing")
        if not context.revision_id or not context.current_revision_id:
            reasons.append("revision_unbound")
        elif context.revision_id != context.current_revision_id:
            reasons.append("stale_revision")
        if not context.trusted_viewport_ids():
            reasons.append("no_owned_viewports")
        if not context.trusted_page_numbers():
            reasons.append("no_owned_pages")
        if self._inputs is None:
            reasons.append("shadow_inputs_not_provided")
        eligible = not reasons
        if eligible:
            reasons.append("shadow_ceiling_lining_eligible")
        return EligibilityDecision(
            eligible=eligible,
            family=PROVIDER_FAMILY,
            reasons=tuple(reasons),
            declared_identity_grammar="ceiling_lining:<scope_entity_id>",
            eligible_semantic_keys=(),
        )

    def extract(self, context: ProviderContext) -> ProviderResult:
        eligibility = self.eligibility(context)
        if not eligibility.eligible or self._inputs is None:
            return ProviderResult.build(
                descriptor=self.descriptor(),
                context=context,
                quantities=(),
                entities=(),
            )

        inputs = self._inputs
        areas = tuple(
            sorted(
                inputs.authoritative_area_quantities,
                key=lambda item: (item.quantity_id, item.semantic_key, item.family),
            )
        )
        by_scope: dict[str, list[QuantityEvidence]] = {}
        for area in areas:
            if _norm(area.family) not in _ACCEPTED_AREA_FAMILIES:
                continue
            scope = _scope_of_area(area)
            if not scope:
                continue
            by_scope.setdefault(scope, []).append(area)

        quantities: list[QuantityEvidence] = []
        for scope in sorted(by_scope):
            scoped_areas = by_scope[scope]
            if len(scoped_areas) != 1:
                quantities.append(
                    _competing_area_blocked(
                        scope=scope,
                        competing_areas=scoped_areas,
                        finish_candidates=inputs.unscoped_finish_candidates,
                        context=context,
                        viewport=inputs.viewport,
                        page_no=inputs.page_no,
                    )
                )
                continue

            scoped_finish = bind_unscoped_finish_candidates_to_room(
                candidates=inputs.unscoped_finish_candidates,
                room_entity_id=scope,
                proofs=inputs.scope_proofs,
            )
            owned_ids = set(inputs.document.evidence_ids)
            owned_ids.update(atom.evidence_id for atom in scoped_finish)
            owned_ids.update(scoped_areas[0].evidence_ids)
            document = DocumentEvidence(
                document_id=inputs.document.document_id,
                source_sha256=inputs.document.source_sha256,
                page_count=inputs.document.page_count,
                page_ids=inputs.document.page_ids,
                evidence_ids=tuple(sorted(owned_ids)),
                producer=inputs.document.producer,
                producer_version=inputs.document.producer_version,
                metadata=dict(inputs.document.metadata or {}),
            )
            quantities.append(
                build_ceiling_lining_quantity(
                    scope_entity_id=scope,
                    area_quantity=scoped_areas[0],
                    finish_evidence_atoms=scoped_finish,
                    context=context,
                    document=document,
                    viewport=inputs.viewport,
                    page_no=inputs.page_no,
                )
            )

        for qty in quantities:
            if qty.status == AuthorityStatus.FIRM.value:
                raise RuntimeError("ceiling lining shadow provider must not emit FIRM")
            if not qty.metadata.get("shadow_only", True):
                raise RuntimeError("ceiling lining quantities must remain shadow_only")
            if qty.metadata.get("commercial_projection_allowed"):
                raise RuntimeError("ceiling lining must not allow commercial projection")

        return ProviderResult.build(
            descriptor=self.descriptor(),
            context=context,
            quantities=tuple(quantities),
            entities=(),
        )
