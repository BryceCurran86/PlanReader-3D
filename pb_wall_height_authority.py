"""Fail-closed wall-height QuantityEvidence authority.

Direct documented wall-height evidence may establish FIRM authority when its
normal provenance checks pass. Datum subtraction is stricter: current main has
no independently inspectable producer that can certify that a specific datum
observation governs a specific wall segment. Caller-supplied relationship
records therefore remain diagnostic claims only and cannot mint authority.

Room/ceiling/storey heights, nearby datums, labels, confidence, caller metadata,
and stale evidence never become wall-height authority merely because their
numeric value is plausible.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
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
WALL_HEIGHT_FORMULA_VERSION = "1.4.0"
AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE = (
    "authoritative_wall_datum_relationship_unavailable"
)

_ALLOWED_DIRECT_KINDS = {
    "wall_height_dimension",
    "wall_height_schedule",
}
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
_RELATIONSHIP_KIND = "wall_datum_segment_relationship"
_CROSS_VIEW_RELATIONSHIP_KIND = "wall_datum_cross_view_relationship"
_RELATIONSHIP_METHOD = "canonical_graph_relation"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class WallDatumRelationshipProof:
    """Future-facing diagnostic claim for an exact datum-to-segment relation.

    This record is caller-constructible. It intentionally does *not* establish
    authority on current main, even when every field and referenced EvidenceAtom
    appears valid. A future trusted producer must independently emit/attest the
    relation from an authoritative upstream graph/source universe before datum
    subtraction may become FIRM.
    """

    proof_id: str
    wall_id: str
    wall_segment_id: str
    datum_evidence_id: str
    datum_role: str
    source_sha256: str
    revision_id: str
    evidence_snapshot_id: str
    canonical_graph_snapshot_id: str
    datum_page_id: str
    datum_viewport_id: str
    relationship_evidence_ids: tuple[str, ...]
    cross_view_evidence_ids: tuple[str, ...] = ()
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE

    def __post_init__(self) -> None:
        for value, name in (
            (self.proof_id, "proof_id"),
            (self.wall_id, "wall_id"),
            (self.wall_segment_id, "wall_segment_id"),
            (self.datum_evidence_id, "datum_evidence_id"),
            (self.revision_id, "revision_id"),
            (self.evidence_snapshot_id, "evidence_snapshot_id"),
            (self.canonical_graph_snapshot_id, "canonical_graph_snapshot_id"),
            (self.datum_page_id, "datum_page_id"),
            (self.datum_viewport_id, "datum_viewport_id"),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.datum_role not in {"wall_base", "wall_top"}:
            raise ValueError("datum_role must be wall_base or wall_top")
        source_hash = str(self.source_sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(source_hash):
            raise ValueError("source_sha256 must be a 64-character lowercase SHA-256 hex digest")
        object.__setattr__(self, "source_sha256", source_hash)
        if not self.relationship_evidence_ids:
            raise ValueError("relationship_evidence_ids must contain inspectable support")
        if len(set(self.relationship_evidence_ids)) != len(self.relationship_evidence_ids):
            raise ValueError("relationship_evidence_ids must be unique")
        if len(set(self.cross_view_evidence_ids)) != len(self.cross_view_evidence_ids):
            raise ValueError("cross_view_evidence_ids must be unique")


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
    allow_cross_view: bool = False,
) -> tuple[str, ...]:
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

    if allow_cross_view:
        if evidence.viewport_id not in context.trusted_viewport_ids():
            blockers.append("height_viewport_not_owned")
    else:
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
    profile = str(_metadata(entity).get("height_profile") or "").strip().lower()
    if profile in {"variable", "sloped", "stepped", "nonuniform"}:
        return ("variable_height_requires_profile_authority",)
    return ()


def _relation_support_atom_blockers(
    atom: EvidenceAtom,
    *,
    proof: WallDatumRelationshipProof,
    context: ProviderContext,
    document: DocumentEvidence,
    entity: EntityEvidence,
) -> tuple[str, ...]:
    blockers: list[str] = []
    meta = _metadata(atom)
    if atom.evidence_id not in document.evidence_ids:
        blockers.append("datum_relation_support_not_owned_by_document")
    if atom.evidence_id not in entity.evidence_ids:
        blockers.append("datum_relation_support_not_owned_by_entity")
    if atom.document_id != document.document_id or document.document_id != context.document_id:
        blockers.append("datum_relation_document_mismatch")
    if atom.kind != _RELATIONSHIP_KIND or atom.method != _RELATIONSHIP_METHOD:
        blockers.append("datum_relation_support_semantics_invalid")
    if atom.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("datum_relation_support_not_corroborated")
    expected = {
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "target_entity_id": proof.wall_id,
        "target_wall_segment_id": proof.wall_segment_id,
        "datum_evidence_id": proof.datum_evidence_id,
        "datum_role": proof.datum_role,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            blockers.append(f"datum_relation_{key}_mismatch")
    return tuple(dict.fromkeys(blockers))


def _cross_view_support_atom_blockers(
    atom: EvidenceAtom,
    *,
    proof: WallDatumRelationshipProof,
    target_viewport: ViewportEvidence,
    context: ProviderContext,
    document: DocumentEvidence,
    entity: EntityEvidence,
) -> tuple[str, ...]:
    blockers: list[str] = []
    meta = _metadata(atom)
    if atom.evidence_id not in document.evidence_ids:
        blockers.append("datum_cross_view_support_not_owned_by_document")
    if atom.evidence_id not in entity.evidence_ids:
        blockers.append("datum_cross_view_support_not_owned_by_entity")
    if atom.document_id != document.document_id or document.document_id != context.document_id:
        blockers.append("datum_cross_view_document_mismatch")
    if atom.kind != _CROSS_VIEW_RELATIONSHIP_KIND or atom.method != _RELATIONSHIP_METHOD:
        blockers.append("datum_cross_view_support_semantics_invalid")
    if atom.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("datum_cross_view_support_not_corroborated")
    expected = {
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "target_entity_id": proof.wall_id,
        "target_wall_segment_id": proof.wall_segment_id,
        "source_viewport_id": proof.datum_viewport_id,
        "target_viewport_id": target_viewport.viewport_id,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            blockers.append(f"datum_cross_view_{key}_mismatch")
    return tuple(dict.fromkeys(blockers))


def _relationship_proof_blockers(
    proof: WallDatumRelationshipProof,
    *,
    datum: Optional[EvidenceAtom],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
    relationship_evidence: Mapping[str, EvidenceAtom],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if proof.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("datum_relation_proof_not_corroborated")
    if proof.source_sha256 != context.source_sha256 or document.source_sha256 != context.source_sha256:
        blockers.append("datum_relation_source_sha256_mismatch")
    if proof.revision_id != context.current_revision_id:
        blockers.append("datum_relation_revision_mismatch")
    if proof.evidence_snapshot_id != context.evidence_snapshot_id:
        blockers.append("datum_relation_evidence_snapshot_mismatch")
    if not context.canonical_graph_snapshot_id:
        blockers.append("datum_relation_graph_snapshot_required")
    elif proof.canonical_graph_snapshot_id != context.canonical_graph_snapshot_id:
        blockers.append("datum_relation_graph_snapshot_mismatch")
    if proof.datum_evidence_id not in document.evidence_ids:
        blockers.append("datum_relation_datum_not_owned_by_document")
    if proof.datum_evidence_id not in entity.evidence_ids:
        blockers.append("datum_relation_datum_not_owned_by_entity")

    if datum is not None:
        if datum.evidence_id != proof.datum_evidence_id:
            blockers.append("datum_relation_selected_datum_mismatch")
        if datum.page_id != proof.datum_page_id:
            blockers.append("datum_relation_page_mismatch")
        if datum.viewport_id != proof.datum_viewport_id:
            blockers.append("datum_relation_viewport_mismatch")

    for support_id in proof.relationship_evidence_ids:
        atom = relationship_evidence.get(support_id)
        if atom is None:
            blockers.append("datum_relation_support_missing")
            continue
        blockers.extend(
            _relation_support_atom_blockers(
                atom,
                proof=proof,
                context=context,
                document=document,
                entity=entity,
            )
        )

    is_cross_view = proof.datum_viewport_id != viewport.viewport_id or proof.datum_page_id != viewport.page_id
    if is_cross_view:
        if not proof.cross_view_evidence_ids:
            blockers.append("datum_cross_view_relation_unproven")
        for support_id in proof.cross_view_evidence_ids:
            atom = relationship_evidence.get(support_id)
            if atom is None:
                blockers.append("datum_cross_view_support_missing")
                continue
            blockers.extend(
                _cross_view_support_atom_blockers(
                    atom,
                    proof=proof,
                    target_viewport=viewport,
                    context=context,
                    document=document,
                    entity=entity,
                )
            )
    return tuple(dict.fromkeys(blockers))


def _resolve_datum_relationship(
    *,
    role: str,
    selected_datum: EvidenceAtom,
    wall_id: str,
    wall_segment_id: str,
    proofs: tuple[WallDatumRelationshipProof, ...],
    relationship_evidence: Mapping[str, EvidenceAtom],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
) -> tuple[tuple[str, ...], bool]:
    label = "wall_base" if role == "wall_base" else "wall_top"
    claims = tuple(
        proof
        for proof in proofs
        if proof.wall_id == wall_id
        and proof.wall_segment_id == wall_segment_id
        and proof.datum_role == role
    )
    if not claims:
        return (f"{label}_relation_unproven",), False

    valid: list[WallDatumRelationshipProof] = []
    unresolved = False
    detailed: list[str] = []
    for proof in claims:
        datum = selected_datum if proof.datum_evidence_id == selected_datum.evidence_id else None
        proof_blockers = _relationship_proof_blockers(
            proof,
            datum=datum,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            relationship_evidence=relationship_evidence,
        )
        if proof_blockers:
            unresolved = True
            detailed.extend(proof_blockers)
        else:
            valid.append(proof)

    blockers: list[str] = []
    if len({proof.datum_evidence_id for proof in valid}) > 1:
        blockers.append(f"{label}_relation_ambiguous")
    selected_valid = [proof for proof in valid if proof.datum_evidence_id == selected_datum.evidence_id]
    if not selected_valid:
        blockers.append(f"{label}_relation_unproven")
    if unresolved:
        blockers.append(f"{label}_relation_unresolved")
        blockers.extend(detailed)
    if "datum_cross_view_relation_unproven" in detailed:
        blockers.append(f"{label}_cross_view_relation_unproven")

    allow_cross_view = False
    if selected_valid and not blockers:
        selected = selected_valid[0]
        allow_cross_view = (
            selected.datum_viewport_id != viewport.viewport_id
            or selected.datum_page_id != viewport.page_id
        )
    return tuple(dict.fromkeys(blockers)), allow_cross_view


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
        formula="explicit_wall_height OR trusted_wall_top_datum - trusted_wall_base_datum",
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
    wall_segment_id: Optional[str] = None,
    datum_relationship_proofs: tuple[WallDatumRelationshipProof, ...] = (),
    relationship_evidence: Optional[Mapping[str, EvidenceAtom]] = None,
) -> QuantityEvidence:
    """Resolve direct height; keep datum-derived height fail-closed on current main."""
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

    if not str(wall_segment_id or "").strip():
        return _abstain(
            wall_id=wall_id,
            entity=entity,
            context=context,
            blockers=("wall_segment_scope_missing",),
            evidence_ids=(lower_datum_evidence.evidence_id, upper_datum_evidence.evidence_id),
        )

    relationship_evidence = relationship_evidence or {}
    lower_relation_blockers, lower_cross_view = _resolve_datum_relationship(
        role="wall_base",
        selected_datum=lower_datum_evidence,
        wall_id=wall_id,
        wall_segment_id=wall_segment_id,
        proofs=datum_relationship_proofs,
        relationship_evidence=relationship_evidence,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
    )
    upper_relation_blockers, upper_cross_view = _resolve_datum_relationship(
        role="wall_top",
        selected_datum=upper_datum_evidence,
        wall_id=wall_id,
        wall_segment_id=wall_segment_id,
        proofs=datum_relationship_proofs,
        relationship_evidence=relationship_evidence,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
    )

    blockers: list[str] = [*lower_relation_blockers, *upper_relation_blockers]
    for evidence, label, allowed_kinds, allow_cross_view in (
        (lower_datum_evidence, "lower", _ALLOWED_LOWER_DATUM_KINDS, lower_cross_view),
        (upper_datum_evidence, "upper", _ALLOWED_UPPER_DATUM_KINDS, upper_cross_view),
    ):
        blockers.extend(
            _validate_owned_evidence(
                evidence,
                context=context,
                document=document,
                viewport=viewport,
                entity=entity,
                allow_cross_view=allow_cross_view,
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
    else:
        height_m = upper_m - lower_m
        if not math.isfinite(height_m) or height_m <= 0.0:
            blockers.append("nonpositive_or_invalid_datum_height")

    # Critical authority boundary: every object above is caller-constructible on
    # current main. Matching metadata and a plausible graph snapshot identifier
    # can support diagnostics but cannot prove the graph edge actually exists.
    # Until an independent upstream relationship producer is wired here, datum
    # subtraction can never publish FIRM wall height.
    blockers.append(AUTHORITATIVE_WALL_DATUM_RELATIONSHIP_UNAVAILABLE)
    return _abstain(
        wall_id=wall_id,
        entity=entity,
        context=context,
        blockers=tuple(dict.fromkeys(blockers)),
        evidence_ids=(lower_datum_evidence.evidence_id, upper_datum_evidence.evidence_id),
        metadata={
            "wall_segment_id": wall_segment_id,
            "missing_upstream_capability": (
                "independent datum-to-exact-wall-segment relationship producer"
            ),
        },
    )


@dataclass(frozen=True)
class WallHeightSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for field in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
        ):
            if not str(getattr(self, field) or "").strip():
                raise ValueError(f"{field} must be non-empty")

    @property
    def key(self) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.physical_wall_id,
        )


_HEIGHT_AUTHORITY_SEAL = object()
_HEIGHT_PRODUCER_SEAL = object()


class WallHeightAuthority:
    """Sealed selector-only lookup for published wall height QuantityEvidence.

    Construction is only possible through WallHeightProducer.authority().
    There is intentionally no public factory method; the former
    from_quantities() classmethod has been removed because it allowed any
    caller to wrap arbitrary QuantityEvidence and obtain a sealed authority
    object, bypassing provenance checks.
    """

    def __init__(
        self,
        quantities: Mapping[object, QuantityEvidence],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _HEIGHT_AUTHORITY_SEAL:
            raise TypeError(
                "WallHeightAuthority is producer-owned and cannot be constructed directly; "
                "use WallHeightProducer.from_authorities() to obtain one."
            )
        from types import MappingProxyType
        self._quantities = MappingProxyType(dict(quantities))

    def resolve(self, selector: object) -> QuantityEvidence | None:
        """Look up a previously published wall-height quantity by selector.

        Only keys published via WallHeightProducer.publish() are present.
        Returns None (not a fabricated abstain) when no matching entry exists.
        """
        if type(selector) is str:
            return self._quantities.get(selector)
        key = getattr(selector, "key", None)
        if key is not None:
            result = self._quantities.get(key)
            if result is not None:
                return result
        wall_id = (
            getattr(selector, "physical_wall_id", None)
            or getattr(selector, "wall_id", None)
        )
        if wall_id is not None:
            return self._quantities.get(wall_id)
        return None


class WallHeightProducer:
    """Producer-owned wall-height publication.

    Source bytes establish that a height callout exists. They do *not* establish
    which plan wall owns it. Wall-specific FIRM publication therefore requires a
    producer-owned CrossSheetRegistrationAuthority plus producer-owned target
    wall geometry on the registered elevation/section page.
    """

    def __init__(
        self,
        source_visibility_producer: object,
        *,
        cross_sheet_registration_authority: object = None,
        physical_wall_candidate_authority: object = None,
        _seal: object = None,
    ) -> None:
        if _seal is not _HEIGHT_PRODUCER_SEAL:
            raise TypeError(
                "WallHeightProducer must be created via WallHeightProducer.from_authorities()"
            )
        from pb_cross_sheet_registration_authority import CrossSheetRegistrationAuthority
        from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be producer-owned SourceVisibilityProducer"
            )
        if (
            cross_sheet_registration_authority is not None
            and type(cross_sheet_registration_authority)
            is not CrossSheetRegistrationAuthority
        ):
            raise TypeError(
                "cross_sheet_registration_authority must be producer-owned "
                "CrossSheetRegistrationAuthority or None"
            )
        if (
            physical_wall_candidate_authority is not None
            and type(physical_wall_candidate_authority)
            is not PhysicalWallCandidateAuthority
        ):
            raise TypeError(
                "physical_wall_candidate_authority must be producer-owned "
                "PhysicalWallCandidateAuthority or None"
            )

        self._source_visibility_producer = source_visibility_producer
        self._cross_sheet = cross_sheet_registration_authority
        self._wall_candidates = physical_wall_candidate_authority
        self._quantities: dict[object, QuantityEvidence] = {}

    @classmethod
    def from_authorities(
        cls,
        source_visibility_producer: object,
        *,
        cross_sheet_registration_authority: object = None,
        physical_wall_candidate_authority: object = None,
    ) -> "WallHeightProducer":
        return cls(
            source_visibility_producer,
            cross_sheet_registration_authority=cross_sheet_registration_authority,
            physical_wall_candidate_authority=physical_wall_candidate_authority,
            _seal=_HEIGHT_PRODUCER_SEAL,
        )

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: object,
    ) -> "WallHeightProducer":
        # Backward-compatible construction. Without exact cross-sheet identity
        # authority this producer remains fail-closed for wall-specific output.
        return cls.from_authorities(source_visibility_producer)

    def _blocked(
        self,
        selector: WallHeightSelector,
        reason: str,
        *extras: str,
        evidence_ids: tuple[str, ...] = (),
    ) -> QuantityEvidence:
        reasons = tuple(
            dict.fromkeys([reason, *(str(r) for r in extras if str(r))])
        )
        qty = QuantityEvidence(
            quantity_id=stable_contract_id(
                "qty",
                {
                    "selector": selector.key,
                    "reason_codes": list(reasons),
                    "evidence_ids": list(evidence_ids),
                },
            ),
            family=WALL_HEIGHT_FAMILY,
            semantic_key=f"wall_height:{selector.physical_wall_id}",
            value=None,
            unit="m",
            input_entity_ids=(selector.physical_wall_id,),
            formula="cross_sheet_registered_explicit_wall_height",
            formula_version=WALL_HEIGHT_FORMULA_VERSION,
            evidence_ids=evidence_ids,
            authority="unresolved",
            status=AuthorityStatus.BLOCKED.value,
            confidence=0.0,
            abstained=True,
            blocking_reasons=reasons,
            reason_codes=reasons,
            metadata={},
        )
        self._quantities[selector.key] = qty
        return qty

    def _raw_source_bytes(
        self, selector: WallHeightSelector
    ) -> Optional[bytes]:
        import hashlib

        published = (
            self._source_visibility_producer.published_snapshot_for_revision(
                selector.revision_id
            )
        )
        if published is None:
            return None
        if (
            published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or self._source_visibility_producer._producer.current_revision_id(
                selector.document_id
            )
            != selector.revision_id
        ):
            return None
        source_bytes = (
            self._source_visibility_producer._producer._store.source_bytes_by_revision.get(
                selector.revision_id
            )
        )
        if (
            source_bytes is None
            or hashlib.sha256(source_bytes).hexdigest()
            != selector.source_sha256
        ):
            return None
        return bytes(source_bytes)

    def _registered_target_geometry(
        self,
        selector: WallHeightSelector,
        *,
        target_page_id: str,
        target_physical_element_id: str,
    ) -> Optional[tuple[float, float, float, float]]:
        from pb_physical_wall_candidate_authority import (
            PhysicalWallCandidateSelector,
        )

        if self._wall_candidates is None:
            return None
        scope_id = f"wall-source:page-{target_page_id}"
        result = self._wall_candidates.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=target_page_id,
                decision_scope_id=scope_id,
            )
        )
        if result.status is not EvidenceResolutionStatus.CORROBORATED:
            return None
        if (
            result.document_id != selector.document_id
            or result.revision_id != selector.revision_id
            or result.source_sha256 != selector.source_sha256
            or result.snapshot_id != selector.snapshot_id
            or result.page_id != target_page_id
        ):
            return None

        matches = [
            record
            for record in result.records
            if record.wall_candidate_id == target_physical_element_id
            or getattr(
                record.physical_identity, "physical_wall_id", None
            )
            == target_physical_element_id
        ]
        if len(matches) != 1:
            return None

        candidate = matches[0].wall_candidate
        points = getattr(candidate, "centerline_pts", None)
        if not points:
            return None
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return (min(xs), min(ys), max(xs), max(ys))

    def publish_scope(
        self,
        selector: WallHeightSelector,
    ) -> QuantityEvidence:
        if type(selector) is not WallHeightSelector:
            raise TypeError("selector must be WallHeightSelector")

        source_bytes = self._raw_source_bytes(selector)
        if source_bytes is None:
            return self._blocked(
                selector, "no_authoritative_wall_height_evidence"
            )

        # A generic HEIGHT callout is not wall identity. Without both exact
        # producer-owned registration and target geometry, remain blocked.
        if self._cross_sheet is None or self._wall_candidates is None:
            return self._blocked(
                selector, "wall_height_exact_identity_binding_unavailable"
            )

        import fitz

        from pb_cross_sheet_registration_authority import (
            CrossSheetRegistrationSelector,
        )
        from pb_wall_height_evidence import (
            resolve_wall_height_dimension_m,
        )

        try:
            source_page_num = int(str(selector.page_id))
        except (TypeError, ValueError):
            return self._blocked(selector, "wall_height_source_page_invalid")

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        candidates: list[
            tuple[float, str, str, str, str, str]
        ] = []
        # value, dimension id, registration record id, target page,
        # target element id, view id
        try:
            if (
                source_page_num < 1
                or source_page_num > int(pdf.page_count)
            ):
                return self._blocked(
                    selector, "wall_height_source_page_invalid"
                )

            for page_num in range(1, int(pdf.page_count) + 1):
                if page_num == source_page_num:
                    continue
                target_page_id = str(page_num)
                registration = self._cross_sheet.resolve(
                    CrossSheetRegistrationSelector(
                        document_id=selector.document_id,
                        revision_id=selector.revision_id,
                        source_sha256=selector.source_sha256,
                        snapshot_id=selector.snapshot_id,
                        source_page_id=selector.page_id,
                        target_page_id=target_page_id,
                        physical_element_id=selector.physical_wall_id,
                    )
                )
                if (
                    registration.status
                    is not EvidenceResolutionStatus.CORROBORATED
                    or registration.record is None
                ):
                    continue
                record = registration.record
                if (
                    record.document_id != selector.document_id
                    or record.revision_id != selector.revision_id
                    or record.source_sha256 != selector.source_sha256
                    or record.snapshot_id != selector.snapshot_id
                    or record.source_page_id != selector.page_id
                    or record.target_page_id != target_page_id
                    or record.physical_element_id
                    != selector.physical_wall_id
                ):
                    continue

                target_bbox = self._registered_target_geometry(
                    selector,
                    target_page_id=target_page_id,
                    target_physical_element_id=record.target_physical_element_id,
                )
                if target_bbox is None:
                    continue

                evidence = resolve_wall_height_dimension_m(
                    pdf.load_page(page_num - 1),
                    page_num=page_num,
                    target_geometry_bbox=target_bbox,
                )
                if evidence is None:
                    continue
                candidates.append(
                    (
                        float(evidence.height_m),
                        evidence.chain_id,
                        record.record_id,
                        target_page_id,
                        record.target_physical_element_id,
                        evidence.view_id,
                    )
                )
        finally:
            pdf.close()

        if not candidates:
            return self._blocked(
                selector, "no_cross_sheet_bound_wall_height_evidence"
            )

        distinct_values = {round(item[0], 6) for item in candidates}
        if len(distinct_values) != 1:
            return self._blocked(
                selector,
                "conflicting_cross_sheet_wall_height_evidence",
                evidence_ids=tuple(
                    dict.fromkeys(
                        item[1] for item in candidates
                    )
                ),
            )

        # Multiple registered views may corroborate the same value. Identity is
        # still the source wall from producer-owned registration, never the
        # selector alone.
        candidates.sort(key=lambda item: (item[3], item[2], item[1]))
        (
            value_m,
            dimension_id,
            registration_record_id,
            height_page_id,
            target_element_id,
            height_view_id,
        ) = candidates[0]
        value_m = round(float(value_m), 6)
        if not math.isfinite(value_m) or value_m <= 0.0:
            return self._blocked(
                selector,
                "invalid_direct_height_value",
                evidence_ids=(dimension_id, registration_record_id),
            )

        all_evidence_ids = tuple(
            dict.fromkeys(
                [
                    *(item[1] for item in candidates),
                    *(item[2] for item in candidates),
                ]
            )
        )
        payload = {
            "wall_id": selector.physical_wall_id,
            "value_m": value_m,
            "source_sha256": selector.source_sha256,
            "revision_id": selector.revision_id,
            "snapshot_id": selector.snapshot_id,
            "source_page_id": selector.page_id,
            "height_evidence_page_id": height_page_id,
            "cross_sheet_registration_record_id": registration_record_id,
            "target_physical_element_id": target_element_id,
            "evidence_ids": list(all_evidence_ids),
        }
        qty = QuantityEvidence(
            quantity_id=stable_contract_id("qty", payload),
            family=WALL_HEIGHT_FAMILY,
            semantic_key=f"wall_height:{selector.physical_wall_id}",
            value=value_m,
            unit="m",
            input_entity_ids=(selector.physical_wall_id,),
            formula="cross_sheet_registered_explicit_wall_height",
            formula_version=WALL_HEIGHT_FORMULA_VERSION,
            evidence_ids=all_evidence_ids,
            authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            status=AuthorityStatus.FIRM.value,
            confidence=1.0,
            abstained=False,
            metadata={
                "source_sha256": selector.source_sha256,
                "revision_id": selector.revision_id,
                "evidence_snapshot_id": selector.snapshot_id,
                "source_page_id": selector.page_id,
                "height_evidence_page_id": height_page_id,
                "height_evidence_view_id": height_view_id,
                "target_entity_id": selector.physical_wall_id,
                "target_physical_element_id": target_element_id,
                "cross_sheet_registration_record_id": registration_record_id,
                "identity_binding_kind": "cross_sheet_registration",
                "evidence_kind": "wall_height_dimension",
            },
        )
        self._quantities[selector.key] = qty
        return qty

    def publish(
        self, selector: WallHeightSelector
    ) -> QuantityEvidence:
        return self.publish_scope(selector)

    def authority(self) -> WallHeightAuthority:
        return WallHeightAuthority(
            self._quantities, _seal=_HEIGHT_AUTHORITY_SEAL
        )
