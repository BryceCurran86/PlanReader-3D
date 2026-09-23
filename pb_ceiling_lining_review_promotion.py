"""Ceiling-lining authority promotion into the existing estimator-review path.

This module is the explicit authority-promotion boundary required by AGENTS.md.
It does NOT make ceiling quantities FIRM and does NOT bypass estimator review.

The only positive path starts from an already-ingested SourceVisibilityProducer
and reruns the fully source-owned shadow composition. A review-eligible ceiling
quantity may be minted only when:
- the ceiling shadow claim is non-abstained, PROVISIONAL and explicitly shadow-only;
- its same-scope upstream room area is FIRM and PDF_SCALED;
- the numeric value is copied exactly from that room area;
- finish semantics came from producer-owned trusted PDF text and are non-empty;
- source/document/revision/page/viewport identity is current and consistent;
- the physical scale bridge is CORROBORATED and retains a source scale record;
- the ProviderContext carries a positive workspace_record_id.

The promoted QuantityEvidence inherits the existing PDF_SCALED numeric authority
but remains REVIEW_REQUIRED. It is then projected through the canonical M5
commercial adapter as an unreviewed AI draft. Existing estimator, pricing and
JobHub gates remain unchanged and therefore block the row until explicit review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from pb_geometry_takeoff_model import (
    AuthorityStatus,
    MeasurementAuthorityType,
)
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import measurement_authority_for_page_scale
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    CommercialTakeoffSourceTrace,
    existing_commercial_gate_results,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_ceiling_finish_evidence import SOURCE_CEILING_FINISH_METHOD
from pb_source_owned_ceiling_lining_pipeline import (
    SourceOwnedCeilingLiningShadowResult,
    run_source_owned_ceiling_lining_shadow,
)
from pb_source_visibility_authority import SourceVisibilityProducer


CEILING_REVIEW_PROMOTION_SCHEMA_VERSION = "1.0.0"
CEILING_REVIEW_PROMOTION_RESOLVED = "ceiling_review_promotion_resolved"
CEILING_REVIEW_PROMOTION_UNAVAILABLE = "ceiling_review_promotion_unavailable"
CEILING_REVIEW_PROMOTION_CONTEXT_INVALID = "ceiling_review_promotion_context_invalid"

_ACCEPTED_AREA_UNITS = {"m2", "m²", "sqm"}


@dataclass(frozen=True)
class CeilingLiningReviewCandidate:
    shadow_quantity_id: str
    promoted_quantity: QuantityEvidence
    source_trace: CommercialTakeoffSourceTrace
    measurement_authority: CommercialMeasurementAuthority
    review_row: Mapping[str, object]


@dataclass(frozen=True)
class CeilingLiningReviewPromotionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    source_result: SourceOwnedCeilingLiningShadowResult
    candidates: tuple[CeilingLiningReviewCandidate, ...]
    schema_version: str = CEILING_REVIEW_PROMOTION_SCHEMA_VERSION


def _norm(value: object) -> str:
    return str(value if value is not None else "").strip().lower()


def _context_is_commercially_addressable(context: ProviderContext) -> bool:
    if not context.revision_id or not context.current_revision_id:
        return False
    if context.revision_id != context.current_revision_id:
        return False
    if not context.document_id or not context.source_sha256 or not context.project_id:
        return False
    if context.workspace_record_id is None or isinstance(context.workspace_record_id, bool):
        return False
    try:
        return int(context.workspace_record_id) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _area_by_id(
    source_result: SourceOwnedCeilingLiningShadowResult,
) -> dict[str, QuantityEvidence]:
    return {
        quantity.quantity_id: quantity
        for quantity in source_result.room_area_quantities
    }


def _promotion_candidate(
    *,
    shadow: QuantityEvidence,
    source_result: SourceOwnedCeilingLiningShadowResult,
) -> CeilingLiningReviewCandidate | None:
    context = source_result.effective_context
    metadata = shadow.metadata if isinstance(shadow.metadata, Mapping) else {}

    if (
        shadow.family != "ceiling_lining"
        or shadow.abstained
        or shadow.value is None
        or shadow.status != AuthorityStatus.PROVISIONAL.value
        or shadow.authority != MeasurementAuthorityType.MODEL_DERIVED.value
        or metadata.get("shadow_only") is not True
        or metadata.get("commercial_projection_allowed") is not False
        or shadow.blocking_reasons
        or len(shadow.input_entity_ids) != 1
    ):
        return None

    scope = shadow.input_entity_ids[0]
    if metadata.get("scope_entity_id") != scope:
        return None
    if metadata.get("source_sha256") != context.source_sha256:
        return None
    if metadata.get("revision_id") != context.current_revision_id:
        return None

    try:
        page_no = int(metadata.get("page_no"))
    except (TypeError, ValueError):
        return None
    if page_no not in context.trusted_page_numbers():
        return None
    viewport_id = str(metadata.get("viewport_id") or "")
    if viewport_id not in context.trusted_viewport_ids():
        return None
    mapped = context.page_for_viewport(viewport_id)
    if mapped is not None and int(mapped) != page_no:
        return None

    upstream_id = str(metadata.get("upstream_area_quantity_id") or "")
    area = _area_by_id(source_result).get(upstream_id)
    if area is None:
        return None
    if (
        area.abstained
        or area.value is None
        or area.status != AuthorityStatus.FIRM.value
        or area.authority != MeasurementAuthorityType.PDF_SCALED.value
        or _norm(area.unit) not in _ACCEPTED_AREA_UNITS
        or len(area.input_entity_ids) != 1
        or area.input_entity_ids[0] != scope
        or float(area.value) != float(shadow.value)
        or area.blocking_reasons
    ):
        return None

    if metadata.get("upstream_area_status") != area.status:
        return None
    if metadata.get("upstream_area_authority") != area.authority:
        return None
    if metadata.get("upstream_area_family") != area.family:
        return None

    finish_descriptor = str(metadata.get("finish_descriptor") or "").strip()
    finish_methods = tuple(str(value) for value in (metadata.get("finish_source_methods") or ()))
    finish_ids = tuple(str(value) for value in (metadata.get("finish_evidence_ids") or ()))
    if (
        not finish_descriptor
        or not finish_ids
        or SOURCE_CEILING_FINISH_METHOD not in finish_methods
        or not set(finish_ids).issubset(set(shadow.evidence_ids))
    ):
        return None

    scale_bridge = source_result.scale_bridge
    scale_evidence = scale_bridge.physical_scale_evidence
    calibration = scale_bridge.calibration
    if (
        scale_bridge.status is not EvidenceResolutionStatus.CORROBORATED
        or calibration is None
        or scale_evidence is None
        or not scale_evidence.record_id
        or measurement_authority_for_page_scale(calibration)
        != AuthorityStatus.FIRM.value
        or calibration.revision_id != context.current_revision_id
    ):
        return None

    promoted_metadata = dict(metadata)
    promoted_metadata.update(
        {
            "shadow_only": False,
            "commercial_projection_allowed": True,
            "commercial_review_required": True,
            "source_owned_ceiling_promotion": True,
            "promotion_parent_quantity_id": shadow.quantity_id,
            "numeric_authority_source_quantity_id": area.quantity_id,
            "physical_scale_record_id": scale_evidence.record_id,
            "element": "Ceiling lining",
            "finish_system": finish_descriptor,
        }
    )
    promotion_payload = {
        "family": shadow.family,
        "semantic_key": shadow.semantic_key,
        "parent_quantity_id": shadow.quantity_id,
        "upstream_area_quantity_id": area.quantity_id,
        "physical_scale_record_id": scale_evidence.record_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "viewport_id": viewport_id,
        "page_no": page_no,
        "value": float(shadow.value),
        "unit": shadow.unit,
    }
    promoted = QuantityEvidence(
        quantity_id=stable_contract_id("qty", promotion_payload),
        family=shadow.family,
        semantic_key=shadow.semantic_key,
        value=float(shadow.value),
        unit=shadow.unit,
        input_entity_ids=tuple(shadow.input_entity_ids),
        formula=shadow.formula,
        formula_version=shadow.formula_version,
        evidence_ids=tuple(shadow.evidence_ids),
        # Numeric authority is inherited exactly from the FIRM upstream room area.
        authority=area.authority,
        # This is review eligibility, not automated commercial approval.
        status=AuthorityStatus.REVIEW_REQUIRED.value,
        confidence=min(float(shadow.confidence), float(area.confidence)),
        abstained=False,
        blocking_reasons=(),
        reason_codes=tuple(
            dict.fromkeys(
                (
                    *shadow.reason_codes,
                    "numeric_authority_inherited_from_firm_room_area",
                    "ceiling_lining_commercial_review_eligible",
                    "estimator_review_required",
                )
            )
        ),
        metadata=promoted_metadata,
    )

    trace = CommercialTakeoffSourceTrace(
        workspace_id=int(context.workspace_record_id),
        project_id=context.project_id,
        document_id=context.document_id,
        source_sha256=context.source_sha256,
        source_page=str(page_no),
        viewport_id=viewport_id,
        revision_id=str(context.revision_id),
        current_revision_id=str(context.current_revision_id),
        evidence_ids=tuple(promoted.evidence_ids),
        canonical_entity_ids=tuple(promoted.input_entity_ids),
        metadata={
            "ceiling_review_promotion": True,
            "promotion_parent_quantity_id": shadow.quantity_id,
            "upstream_area_quantity_id": area.quantity_id,
        },
    )
    measurement = CommercialMeasurementAuthority(
        method="scaled_geometry",
        resolved_scale_id=scale_evidence.record_id,
        scale_status="resolved",
        scale_conflicts=(),
        metadata={
            "ceiling_review_promotion": True,
            "upstream_area_quantity_id": area.quantity_id,
            "scale_source_kind": scale_evidence.source_kind,
        },
    )
    row = quantity_evidence_to_takeoff_output_row(
        promoted,
        trace=trace,
        authority=measurement,
    )
    if row is None:
        return None

    # Promotion may create only an unreviewed AI draft. If existing gates see
    # it as publishable/pricing/jobhub eligible before estimator review, fail.
    gates = existing_commercial_gate_results(row)
    if any(result[0] for result in gates.values()):
        raise RuntimeError(
            "ceiling review promotion bypassed an existing commercial review gate"
        )

    return CeilingLiningReviewCandidate(
        shadow_quantity_id=shadow.quantity_id,
        promoted_quantity=promoted,
        source_trace=trace,
        measurement_authority=measurement,
        review_row=row,
    )


def build_ceiling_lining_review_promotions(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> CeilingLiningReviewPromotionResult:
    """Build estimator-review candidates from the full producer-owned chain."""

    if not _context_is_commercially_addressable(context):
        raise ValueError(CEILING_REVIEW_PROMOTION_CONTEXT_INVALID)

    source_result = run_source_owned_ceiling_lining_shadow(
        source_visibility_producer=source_visibility_producer,
        context=context,
        viewport=viewport,
        page_no=page_no,
    )

    candidates = tuple(
        candidate
        for quantity in source_result.ceiling_quantities
        if (candidate := _promotion_candidate(
            shadow=quantity,
            source_result=source_result,
        )) is not None
    )
    if not candidates:
        return CeilingLiningReviewPromotionResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(CEILING_REVIEW_PROMOTION_UNAVAILABLE,),
            source_result=source_result,
            candidates=(),
        )

    return CeilingLiningReviewPromotionResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(CEILING_REVIEW_PROMOTION_RESOLVED,),
        source_result=source_result,
        candidates=candidates,
    )


__all__ = [
    "CEILING_REVIEW_PROMOTION_CONTEXT_INVALID",
    "CEILING_REVIEW_PROMOTION_RESOLVED",
    "CEILING_REVIEW_PROMOTION_SCHEMA_VERSION",
    "CEILING_REVIEW_PROMOTION_UNAVAILABLE",
    "CeilingLiningReviewCandidate",
    "CeilingLiningReviewPromotionResult",
    "build_ceiling_lining_review_promotions",
]
