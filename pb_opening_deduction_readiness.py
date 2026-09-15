"""Strict opening-deduction dependency readiness.

This authority layer consumes W7 ``OpeningHostCandidate`` records plus M1
evidence contracts. Geometry/proximity may nominate a host, but caller-supplied
candidate cardinality cannot certify that the relevant host universe was
complete. Current main has no independent authenticated host-universe producer,
so otherwise-ready deductions fail closed with an explicit completeness reason.

No schedule count is interpreted as a dimension and ``gap_width_m`` is never
treated as authoritative width.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

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
from pb_wall_room_topology_contracts import OpeningHostCandidate

OPENING_DEDUCTION_FAMILY = "opening_deduction_area"
OPENING_DEDUCTION_FORMULA_VERSION = "1.1.0"

_WIDTH_KINDS = frozenset({
    "opening_width_dimension",
    "door_width_dimension",
    "window_width_dimension",
    "opening_width_schedule",
})
_HEIGHT_KINDS = frozenset({
    "opening_height_dimension",
    "door_height_dimension",
    "window_height_dimension",
    "opening_height_schedule",
})

_HOST_NOMINATION_BLOCKERS = {
    "nearest_wall_only": "opening_host_nearest_only_not_authoritative",
    "bbox_overlap_only": "opening_host_bbox_overlap_only_not_authoritative",
    "regional_clip_only": "opening_host_regional_clip_not_complete",
    "centerline_distance_only": "opening_host_centerline_distance_only_not_authoritative",
}


def _meta(value: EvidenceAtom | EntityEvidence) -> Mapping[str, object]:
    return value.metadata if isinstance(value.metadata, Mapping) else {}


def _value_m(evidence: EvidenceAtom) -> Optional[float]:
    if evidence.normalized_value is None:
        return None
    value = float(evidence.normalized_value)
    if not math.isfinite(value) or value <= 0.0:
        return None
    unit = str(evidence.unit or "").strip().lower()
    if unit in {"m", "metre", "meter", "metres", "meters"}:
        return value
    if unit in {"mm", "millimetre", "millimeter", "millimetres", "millimeters"}:
        return value / 1000.0
    return None


def _validate_opening_entity(
    opening_entity: EntityEvidence,
    *,
    opening_id: str,
    context: ProviderContext,
) -> tuple[str, ...]:
    blockers: list[str] = []
    meta = _meta(opening_entity)
    if opening_entity.candidate_entity_id != opening_id:
        blockers.append("opening_entity_identity_mismatch")
    if opening_entity.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("opening_entity_not_corroborated")

    physical_id = str(meta.get("physical_opening_id") or "")
    if str(meta.get("physical_identity_status") or "") != "proven" or physical_id != opening_id:
        blockers.append("opening_physical_identity_unproven")

    source_sha = str(meta.get("source_sha256") or "")
    if source_sha and source_sha != context.source_sha256:
        blockers.append("opening_entity_source_sha_mismatch")
    revision = meta.get("revision_id")
    if revision not in (None, "") and revision != context.current_revision_id:
        blockers.append("opening_entity_revision_mismatch")
    snapshot = str(meta.get("evidence_snapshot_id") or "")
    if snapshot and snapshot != context.evidence_snapshot_id:
        blockers.append("opening_entity_evidence_snapshot_mismatch")
    graph = meta.get("canonical_graph_snapshot_id")
    if context.canonical_graph_snapshot_id is not None and graph not in (None, ""):
        if graph != context.canonical_graph_snapshot_id:
            blockers.append("opening_entity_graph_snapshot_mismatch")

    if bool(meta.get("phase_conflict")):
        blockers.append("opening_phase_conflict")
    if str(meta.get("phase") or "").lower() in {"conflict", "unknown", "unresolved"}:
        blockers.append("opening_phase_unresolved")
    if str(meta.get("commercial_applicability") or "").lower() not in {"applicable", "proven_applicable"}:
        blockers.append("opening_commercial_applicability_unproven")
    return tuple(dict.fromkeys(blockers))


def _validate_evidence(
    evidence: EvidenceAtom,
    *,
    allowed_kinds: frozenset[str],
    label: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    opening_entity: EntityEvidence,
) -> tuple[str, ...]:
    blockers: list[str] = []
    meta = _meta(evidence)
    if evidence.kind not in allowed_kinds:
        blockers.append(f"{label}_evidence_kind_not_authoritative")
    if evidence.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append(f"{label}_evidence_not_corroborated")
    if evidence.document_id != document.document_id or document.document_id != context.document_id:
        blockers.append(f"{label}_document_mismatch")
    if document.source_sha256 != context.source_sha256:
        blockers.append(f"{label}_source_sha_mismatch")

    source_sha = str(meta.get("source_sha256") or "")
    if not source_sha:
        blockers.append(f"{label}_source_sha_missing")
    elif source_sha != context.source_sha256:
        blockers.append(f"{label}_source_sha_mismatch")

    revision_id = meta.get("revision_id")
    if revision_id in (None, ""):
        blockers.append(f"{label}_revision_missing")
    elif revision_id != context.current_revision_id:
        blockers.append(f"{label}_revision_mismatch")

    evidence_snapshot_id = str(meta.get("evidence_snapshot_id") or "")
    if not evidence_snapshot_id:
        blockers.append(f"{label}_evidence_snapshot_missing")
    elif evidence_snapshot_id != context.evidence_snapshot_id:
        blockers.append(f"{label}_evidence_snapshot_mismatch")

    expected_graph = context.canonical_graph_snapshot_id
    graph_snapshot_id = meta.get("canonical_graph_snapshot_id")
    if expected_graph is not None:
        if graph_snapshot_id in (None, ""):
            blockers.append(f"{label}_graph_snapshot_missing")
        elif graph_snapshot_id != expected_graph:
            blockers.append(f"{label}_graph_snapshot_mismatch")

    if evidence.page_id != viewport.page_id:
        blockers.append(f"{label}_page_mismatch")
    if evidence.viewport_id != viewport.viewport_id:
        blockers.append(f"{label}_viewport_mismatch")
    if viewport.viewport_id not in context.trusted_viewport_ids():
        blockers.append(f"{label}_viewport_not_owned")
    if evidence.evidence_id not in document.evidence_ids:
        blockers.append(f"{label}_evidence_not_owned_by_document")
    if evidence.evidence_id not in opening_entity.evidence_ids:
        blockers.append(f"{label}_evidence_not_owned_by_opening")

    target = str(meta.get("target_entity_id") or "")
    if not target:
        blockers.append(f"{label}_target_entity_missing")
    elif target != opening_entity.candidate_entity_id:
        blockers.append(f"{label}_target_entity_mismatch")

    if bool(meta.get("dimension_conflict")):
        blockers.append("opening_dimension_conflict")
    if _value_m(evidence) is None:
        blockers.append(f"{label}_dimension_invalid")
    return tuple(dict.fromkeys(blockers))


def _host_blockers(host: OpeningHostCandidate, wall_id: str) -> tuple[str, ...]:
    blockers: list[str] = []
    if host.host_status != "hosted":
        blockers.append("opening_host_not_uniquely_resolved")
    if len(host.candidate_wall_ids_considered) != 1:
        blockers.append("opening_host_candidate_cardinality_not_one")
    elif host.candidate_wall_ids_considered[0] != host.wall_candidate_id:
        blockers.append("opening_host_identity_inconsistent")
    if host.wall_candidate_id != wall_id:
        blockers.append("opening_host_wall_mismatch")

    reasons = set(host.reason_codes)
    for reason, blocker in _HOST_NOMINATION_BLOCKERS.items():
        if reason in reasons:
            blockers.append(blocker)
    if "opening_crosses_viewport_boundary" in reasons:
        blockers.append("opening_crosses_viewport_boundary")

    # Current main has no authenticated, independently enumerated host universe.
    # A caller-created hosted record with one wall cannot prove no competing wall
    # was omitted from a crop/list. Keep deduction authority blocked until such a
    # producer exists and is wired as a separate proof object.
    if host.host_status == "hosted":
        blockers.append("opening_host_universe_completeness_not_authenticated")
    return tuple(dict.fromkeys(blockers))


def _abstain(
    *,
    opening_id: str,
    wall_id: str,
    opening_entity: EntityEvidence,
    context: ProviderContext,
    blockers: tuple[str, ...],
    evidence_ids: tuple[str, ...] = (),
    metadata: Optional[Mapping[str, object]] = None,
) -> QuantityEvidence:
    payload = {
        "family": OPENING_DEDUCTION_FAMILY,
        "opening_id": opening_id,
        "wall_id": wall_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "blockers": list(blockers),
    }
    traced = evidence_ids or tuple(opening_entity.evidence_ids)
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=OPENING_DEDUCTION_FAMILY,
        semantic_key=f"opening_deduction:{opening_id}",
        value=None,
        unit="m2",
        input_entity_ids=(opening_id, wall_id),
        formula="authoritative_opening_width_m * authoritative_opening_height_m",
        formula_version=OPENING_DEDUCTION_FORMULA_VERSION,
        evidence_ids=traced,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.BLOCKED.value,
        confidence=0.0,
        abstained=True,
        blocking_reasons=blockers,
        reason_codes=blockers,
        metadata=dict(metadata or {}),
    )


def build_opening_deduction_quantity(
    *,
    host: OpeningHostCandidate,
    wall_id: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    opening_entity: EntityEvidence,
    width_evidence: Optional[EvidenceAtom],
    height_evidence: Optional[EvidenceAtom],
) -> QuantityEvidence:
    """Return opening area only for a fully authoritative physical opening.

    On current main this intentionally cannot reach FIRM because host-universe
    completeness has no independent authenticated producer yet.
    """
    opening_id = host.host_candidate_id
    blockers: list[str] = []
    blockers.extend(
        _validate_opening_entity(opening_entity, opening_id=opening_id, context=context)
    )
    if document.document_id != context.document_id:
        blockers.append("opening_document_mismatch")
    if document.source_sha256 != context.source_sha256:
        blockers.append("opening_source_sha_mismatch")
    if viewport.viewport_id not in context.trusted_viewport_ids():
        blockers.append("opening_viewport_not_owned")
    blockers.extend(_host_blockers(host, wall_id))

    if width_evidence is None:
        blockers.append("opening_width_missing")
    else:
        blockers.extend(
            _validate_evidence(
                width_evidence,
                allowed_kinds=_WIDTH_KINDS,
                label="opening_width",
                context=context,
                document=document,
                viewport=viewport,
                opening_entity=opening_entity,
            )
        )
    if height_evidence is None:
        blockers.append("opening_height_missing")
    else:
        blockers.extend(
            _validate_evidence(
                height_evidence,
                allowed_kinds=_HEIGHT_KINDS,
                label="opening_height",
                context=context,
                document=document,
                viewport=viewport,
                opening_entity=opening_entity,
            )
        )

    if width_evidence is not None and height_evidence is not None:
        if width_evidence.evidence_id == height_evidence.evidence_id:
            blockers.append("opening_width_height_evidence_not_distinct")

    evidence_ids = tuple(
        e.evidence_id for e in (width_evidence, height_evidence) if e is not None
    )
    if blockers:
        return _abstain(
            opening_id=opening_id,
            wall_id=wall_id,
            opening_entity=opening_entity,
            context=context,
            blockers=tuple(dict.fromkeys(blockers)),
            evidence_ids=evidence_ids,
            metadata={
                "host_status": host.host_status,
                "candidate_wall_ids_considered": list(host.candidate_wall_ids_considered),
                "w7_gap_width_ignored": host.gap_width_m,
            },
        )

    # Unreachable until an independently authenticated host-universe proof is
    # introduced. Kept as the deterministic quantity construction for that future
    # proof path; no caller flags or self-hashes are accepted here.
    assert width_evidence is not None and height_evidence is not None
    width_m = _value_m(width_evidence)
    height_m = _value_m(height_evidence)
    assert width_m is not None and height_m is not None
    value_m2 = round(width_m * height_m, 6)
    payload = {
        "family": OPENING_DEDUCTION_FAMILY,
        "opening_id": opening_id,
        "wall_id": wall_id,
        "width_evidence_id": width_evidence.evidence_id,
        "height_evidence_id": height_evidence.evidence_id,
        "value_m2": value_m2,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "evidence_snapshot_id": context.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "viewport_id": viewport.viewport_id,
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=OPENING_DEDUCTION_FAMILY,
        semantic_key=f"opening_deduction:{opening_id}",
        value=value_m2,
        unit="m2",
        input_entity_ids=(opening_id, wall_id),
        formula="authoritative_opening_width_m * authoritative_opening_height_m",
        formula_version=OPENING_DEDUCTION_FORMULA_VERSION,
        evidence_ids=(width_evidence.evidence_id, height_evidence.evidence_id),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=min(
            float(opening_entity.confidence),
            float(width_evidence.confidence),
            float(height_evidence.confidence),
            float(host.confidence),
        ),
        abstained=False,
        metadata={
            "source_sha256": context.source_sha256,
            "revision_id": context.current_revision_id,
            "evidence_snapshot_id": context.evidence_snapshot_id,
            "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
            "viewport_id": viewport.viewport_id,
            "page_id": viewport.page_id,
            "wall_id": wall_id,
            "host_candidate_id": opening_id,
            "host_status": host.host_status,
            "candidate_wall_ids_considered": list(host.candidate_wall_ids_considered),
            "w7_gap_width_ignored": host.gap_width_m,
        },
    )


def build_opening_deduction_quantities(
    *,
    hosts: Sequence[OpeningHostCandidate],
    wall_id: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    opening_entities: Mapping[str, EntityEvidence],
    width_evidence: Mapping[str, EvidenceAtom],
    height_evidence: Mapping[str, EvidenceAtom],
) -> tuple[QuantityEvidence, ...]:
    """Batch builder with duplicate physical-evidence protection."""
    duplicate_ids: set[str] = set()
    seen_ids: set[str] = set()
    for host in hosts:
        if host.host_candidate_id in seen_ids:
            duplicate_ids.add(host.host_candidate_id)
        seen_ids.add(host.host_candidate_id)

    evidence_to_openings: dict[str, set[str]] = {}
    for host in hosts:
        opening_id = host.host_candidate_id
        for ev in (width_evidence.get(opening_id), height_evidence.get(opening_id)):
            if ev is not None:
                evidence_to_openings.setdefault(ev.evidence_id, set()).add(opening_id)
    shared_evidence_openings = {
        opening_id
        for openings in evidence_to_openings.values()
        if len(openings) > 1
        for opening_id in openings
    }

    physical_to_candidates: dict[str, set[str]] = {}
    for opening_id, entity in opening_entities.items():
        physical_id = str(_meta(entity).get("physical_opening_id") or "")
        if physical_id:
            physical_to_candidates.setdefault(physical_id, set()).add(opening_id)
    duplicate_physical_ids = {
        opening_id
        for candidates in physical_to_candidates.values()
        if len(candidates) > 1
        for opening_id in candidates
    }

    out: list[QuantityEvidence] = []
    for host in hosts:
        opening_id = host.host_candidate_id
        entity = opening_entities.get(opening_id)
        if entity is None:
            raise ValueError(f"missing EntityEvidence for opening {opening_id!r}")
        duplicate_blockers: list[str] = []
        if opening_id in duplicate_ids:
            duplicate_blockers.append("duplicate_opening_identity")
        if opening_id in shared_evidence_openings:
            duplicate_blockers.append("opening_dimension_evidence_reused_across_identities")
        if opening_id in duplicate_physical_ids:
            duplicate_blockers.append("duplicate_physical_opening_identity")
        if duplicate_blockers:
            out.append(
                _abstain(
                    opening_id=opening_id,
                    wall_id=wall_id,
                    opening_entity=entity,
                    context=context,
                    blockers=tuple(duplicate_blockers),
                    evidence_ids=tuple(
                        ev.evidence_id
                        for ev in (width_evidence.get(opening_id), height_evidence.get(opening_id))
                        if ev is not None
                    ),
                )
            )
            continue
        out.append(
            build_opening_deduction_quantity(
                host=host,
                wall_id=wall_id,
                context=context,
                document=document,
                viewport=viewport,
                opening_entity=entity,
                width_evidence=width_evidence.get(opening_id),
                height_evidence=height_evidence.get(opening_id),
            )
        )
    return tuple(out)
