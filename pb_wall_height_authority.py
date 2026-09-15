"""Fail-closed wall-height QuantityEvidence authority.

Accepts only explicit, provenance-bound wall-height evidence or an explicitly
wall-bound base/top datum pair. Room/ceiling/storey heights and stale evidence
never become wall-height measurement authority merely because their numeric
value is plausible.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext

WALL_HEIGHT_FAMILY = "wall_height"
WALL_HEIGHT_FORMULA_VERSION = "1.2.0"

# Only evidence kinds whose resolved contract already carries wall-height
# semantics may directly establish height. A metadata label cannot promote an
# otherwise-generic value into structural wall-height authority.
_ALLOWED_DIRECT_KINDS = {
    "wall_height_dimension",
    "wall_height_schedule",
}

# Generic level/elevation/roof datums require an independent relationship proving
# they are this wall's base/top. No such relationship object is supplied to this
# function today, so only intrinsically wall-specific/floor-specific datum kinds
# are eligible here.
_ALLOWED_LOWER_DATUM_KINDS = {
    "floor_level_datum",
}
_ALLOWED_UPPER_DATUM_KINDS = {
    "wall_top_level_datum",
}
_FORBIDDEN_DEFAULT_METHOD_TOKENS = {
    "default",
    "assumed",
    "fallback",
    "legacy_default",
    "model_default",
}


def _numeric_to_m(value: float, unit: Optional[str]) -> Optional[float]:
    if not math.isfinite(float(value)):
        return None
    normalized = (unit or "").strip().lower().replace("²", "2")
    if normalized in ("m", "metre", "meter", "metres", "meters"):
        return float(value)
    if normalized in ("mm", "millimetre", "millimeter", "millimetres", "millimeters"):
        return float(value) / 1000.0
    return None


def _metadata(value: EvidenceAtom | EntityEvidence) -> Mapping[str, object]:
    return value.metadata if isinstance(value.metadata, Mapping) else {}


def _evidence_is_default_or_assumed(evidence: EvidenceAtom) -> bool:
    method = str(evidence.method or "").strip().lower()
    if any(token in method for token in _FORBIDDEN_DEFAULT_METHOD_TOKENS):
        return True
    metadata = _metadata(evidence)
    for key in ("default", "assumed", "is_default", "is_assumed", "legacy_default"):
        if bool(metadata.get(key)):
            return True
    origin = str(metadata.get("origin") or "").strip().lower()
    return origin in _FORBIDDEN_DEFAULT_METHOD_TOKENS


def _validate_owned_evidence(
    evidence: EvidenceAtom,
    *,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
) -> tuple[str, ...]:
    """Validate ownership plus freshness for the exact wall target.

    EvidenceAtom predates first-class revision/snapshot fields, so these bindings
    are carried in its immutable metadata. Absence is fail-closed: a caller cannot
    manufacture freshness merely by echoing the current ProviderContext into the
    output QuantityEvidence after the fact.
    """
    blockers: list[str] = []
    meta = _metadata(evidence)
    if evidence.document_id != document.document_id or document.document_id != context.document_id:
        blockers.append("height_document_mismatch")
    if document.source_sha256 != context.source_sha256:
        blockers.append("height_source_sha256_mismatch")

    source_sha = str(meta.get("source_sha256") or "")
    if not source_sha:
        blockers.append("height_source_sha256_missing")
    elif source_sha != context.source_sha256:
        blockers.append("height_source_sha256_mismatch")

    revision_id = meta.get("revision_id")
    if revision_id in (None, ""):
        blockers.append("height_revision_missing")
    elif revision_id != context.current_revision_id:
        blockers.append("height_revision_mismatch")

    evidence_snapshot_id = str(meta.get("evidence_snapshot_id") or "")
    if not evidence_snapshot_id:
        blockers.append("height_evidence_snapshot_missing")
    elif evidence_snapshot_id != context.evidence_snapshot_id:
        blockers.append("height_evidence_snapshot_mismatch")

    expected_graph = context.canonical_graph_snapshot_id
    graph_snapshot_id = meta.get("canonical_graph_snapshot_id")
    if expected_graph is not None:
        if graph_snapshot_id in (None, ""):
            blockers.append("height_graph_snapshot_missing")
        elif graph_snapshot_id != expected_graph:
            blockers.append("height_graph_snapshot_mismatch")

    if evidence.page_id != viewport.page_id:
        blockers.append("height_page_mismatch")
    if evidence.viewport_id != viewport.viewport_id:
        blockers.append("height_viewport_mismatch")
    if viewport.viewport_id not in context.trusted_viewport_ids():
        blockers.append("height_viewport_not_owned")
    if evidence.evidence_id not in document.evidence_ids:
        blockers.append("height_evidence_not_owned_by_document")
    if evidence.evidence_id not in entity.evidence_ids:
        blockers.append("height_evidence_not_owned_by_entity")
    if evidence.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("height_evidence_not_corroborated")
    if _evidence_is_default_or_assumed(evidence):
        blockers.append("default_or_assumed_height_forbidden")

    target_entity_id = str(meta.get("target_entity_id") or "")
    if not target_entity_id:
        blockers.append("height_target_entity_missing")
    elif target_entity_id != entity.candidate_entity_id:
        blockers.append("height_target_entity_mismatch")
    return tuple(dict.fromkeys(blockers))


def _entity_height_profile_blockers(entity: EntityEvidence) -> tuple[str, ...]:
    meta = _metadata(entity)
    profile = str(meta.get("height_profile") or "").strip().lower()
    if profile in {"variable", "sloped", "stepped", "nonuniform"}:
        # ``scalar_height_representative_proven=True`` is only caller metadata.
        # This API has no independently inspectable representativeness evidence,
        # so variable-profile scalar authority must remain fail-closed.
        return ("variable_height_requires_profile_authority",)
    return ()


def _abstain(
    *,
    wall_id: str,
    entity: EntityEvidence,
    context: ProviderContext,
    blockers: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    metadata: Optional[dict[str, object]] = None,
) -> QuantityEvidence:
    payload = {
        "family": WALL_HEIGHT_FAMILY,
        "wall_id": wall_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "blockers": list(blockers),
        "evidence_ids": list(evidence_ids),
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=WALL_HEIGHT_FAMILY,
        semantic_key=f"wall_height:{wall_id}",
        value=None,
        unit="m",
        input_entity_ids=(wall_id,),
        formula="explicit_wall_height OR wall_top_datum - wall_base_datum",
        formula_version=WALL_HEIGHT_FORMULA_VERSION,
        evidence_ids=evidence_ids or tuple(entity.evidence_ids),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.BLOCKED.value,
        confidence=0.0,
        abstained=True,
        blocking_reasons=blockers,
        reason_codes=blockers,
        metadata=metadata or {},
    )


def _firm_metadata(*, context: ProviderContext, viewport: ViewportEvidence, wall_id: str) -> dict[str, object]:
    return {
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "viewport_id": viewport.viewport_id,
        "page_id": viewport.page_id,
        "page_no": context.page_for_viewport(viewport.viewport_id),
        "target_entity_id": wall_id,
    }


def build_wall_height_quantity(
    *,
    wall_id: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
    direct_height_evidence: Optional[EvidenceAtom] = None,
    lower_datum_evidence: Optional[EvidenceAtom] = None,
    upper_datum_evidence: Optional[EvidenceAtom] = None,
) -> QuantityEvidence:
    """Resolve explicit wall height or an explicitly wall-bound datum difference."""
    if entity.candidate_entity_id != wall_id:
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=("wall_height_entity_identity_mismatch",),
            evidence_ids=tuple(entity.evidence_ids),
        )
    if entity.status == EvidenceResolutionStatus.CONFLICT or entity.conflict_evidence_ids:
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=("wall_height_entity_conflict",),
            evidence_ids=tuple(entity.evidence_ids),
        )
    if entity.status != EvidenceResolutionStatus.CORROBORATED:
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=("wall_height_entity_not_corroborated",),
            evidence_ids=tuple(entity.evidence_ids),
        )

    profile_blockers = _entity_height_profile_blockers(entity)
    if profile_blockers:
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=profile_blockers,
            evidence_ids=tuple(entity.evidence_ids),
        )

    if direct_height_evidence is not None:
        blockers = list(
            _validate_owned_evidence(
                direct_height_evidence,
                context=context,
                document=document,
                viewport=viewport,
                entity=entity,
            )
        )
        if direct_height_evidence.kind not in _ALLOWED_DIRECT_KINDS:
            blockers.append("unsupported_direct_height_semantics")
        value_m = None
        if direct_height_evidence.normalized_value is not None:
            value_m = _numeric_to_m(direct_height_evidence.normalized_value, direct_height_evidence.unit)
        if value_m is None or value_m <= 0.0:
            blockers.append("invalid_direct_height_value")
        if blockers:
            return _abstain(
                wall_id=wall_id,
                entity=entity,
                context=context,
                blockers=tuple(dict.fromkeys(blockers)),
                evidence_ids=(direct_height_evidence.evidence_id,),
            )
        payload = {
            "wall_id": wall_id,
            "value_m": round(value_m, 6),
            "evidence_id": direct_height_evidence.evidence_id,
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "evidence_snapshot_id": context.evidence_snapshot_id,
            "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        }
        metadata = _firm_metadata(context=context, viewport=viewport, wall_id=wall_id)
        metadata["evidence_kind"] = direct_height_evidence.kind
        return QuantityEvidence(
            quantity_id=stable_contract_id("qty", payload),
            family=WALL_HEIGHT_FAMILY,
            semantic_key=f"wall_height:{wall_id}",
            value=round(value_m, 6),
            unit="m",
            input_entity_ids=(wall_id,),
            formula="authoritative_explicit_wall_height",
            formula_version=WALL_HEIGHT_FORMULA_VERSION,
            evidence_ids=(direct_height_evidence.evidence_id,),
            authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            status=AuthorityStatus.FIRM.value,
            confidence=min(float(entity.confidence), float(direct_height_evidence.confidence)),
            abstained=False,
            metadata=metadata,
        )

    if lower_datum_evidence is None or upper_datum_evidence is None:
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=("no_authoritative_wall_height_evidence",),
            evidence_ids=tuple(entity.evidence_ids),
        )

    blockers: list[str] = []
    for evidence, label, allowed_kinds in (
        (lower_datum_evidence, "lower", _ALLOWED_LOWER_DATUM_KINDS),
        (upper_datum_evidence, "upper", _ALLOWED_UPPER_DATUM_KINDS),
    ):
        blockers.extend(
            _validate_owned_evidence(
                evidence,
                context=context,
                document=document,
                viewport=viewport,
                entity=entity,
            )
        )
        if evidence.kind not in allowed_kinds:
            blockers.append(f"unsupported_{label}_datum_kind")
        if evidence.normalized_value is None:
            blockers.append(f"missing_{label}_datum_value")

    lower_m = (
        _numeric_to_m(lower_datum_evidence.normalized_value, lower_datum_evidence.unit)
        if lower_datum_evidence.normalized_value is not None
        else None
    )
    upper_m = (
        _numeric_to_m(upper_datum_evidence.normalized_value, upper_datum_evidence.unit)
        if upper_datum_evidence.normalized_value is not None
        else None
    )
    if lower_m is None or upper_m is None:
        blockers.append("invalid_datum_units_or_values")
        height_m = None
    else:
        height_m = upper_m - lower_m
        if not math.isfinite(height_m) or height_m <= 0.0:
            blockers.append("nonpositive_or_invalid_datum_height")

    if blockers:
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=tuple(dict.fromkeys(blockers)),
            evidence_ids=(lower_datum_evidence.evidence_id, upper_datum_evidence.evidence_id),
        )

    assert height_m is not None
    value = round(height_m, 6)
    payload = {
        "wall_id": wall_id,
        "value_m": value,
        "lower": lower_datum_evidence.evidence_id,
        "upper": upper_datum_evidence.evidence_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
    }
    metadata = _firm_metadata(context=context, viewport=viewport, wall_id=wall_id)
    metadata.update(
        {
            "lower_datum_kind": lower_datum_evidence.kind,
            "upper_datum_kind": upper_datum_evidence.kind,
        }
    )
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=WALL_HEIGHT_FAMILY,
        semantic_key=f"wall_height:{wall_id}",
        value=value,
        unit="m",
        input_entity_ids=(wall_id,),
        formula="wall_top_datum - wall_base_datum",
        formula_version=WALL_HEIGHT_FORMULA_VERSION,
        evidence_ids=(lower_datum_evidence.evidence_id, upper_datum_evidence.evidence_id),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=min(
            float(entity.confidence),
            float(lower_datum_evidence.confidence),
            float(upper_datum_evidence.confidence),
        ),
        abstained=False,
        metadata=metadata,
    )
