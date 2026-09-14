"""Deterministic wall-length QuantityEvidence from W1-W10 topology.

Linear wall length requires physical-wall existence, a measurable centerline,
and firm scale or a documented dimension. It does not require thickness or
height. ``WallCandidate.status`` is not existence authority: that field is
coupled to thickness by the WallCandidate invariant.

This module does not read ``metadata["physical_evidence_status"]``, does not
invent thickness, does not publish commercial takeoff, and does not guess
external/internal scope.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import resolve_linear_measurement_input
from pb_physical_wall_identity import (
    PhysicalWallIdentity,
    resolve_physical_wall_equivalence,
)
from pb_viewport_scale_binding import ViewportScaleBinding
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
from pb_wall_room_topology_contracts import WallCandidate

WALL_LENGTH_FAMILY = "wall_length"
WALL_LENGTH_FORMULA_VERSION = "1.2.0"


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    return sum(
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
    )


def _wall_source_segment_ids(wall: WallCandidate) -> frozenset[str]:
    ids = set(wall.face_a_segment_ids)
    if wall.face_b_segment_ids:
        ids.update(wall.face_b_segment_ids)
    return frozenset(ids)


def _existence_blockers(
    *,
    wall: WallCandidate,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if entity.candidate_entity_id != wall.candidate_id:
        blockers.append("wall_entity_identity_mismatch")
    if entity.candidate_type != "wall":
        blockers.append("wall_entity_type_mismatch")
    if document.document_id != context.document_id:
        blockers.append("physical_wall_existence_document_mismatch")
    if document.source_sha256 != context.source_sha256:
        blockers.append("physical_wall_existence_source_sha_mismatch")
    if wall.viewport_id != viewport.viewport_id:
        blockers.append("wall_viewport_mismatch")
    if viewport.viewport_id not in context.trusted_viewport_ids():
        blockers.append("physical_wall_existence_viewport_mismatch")
    if not set(entity.evidence_ids).issubset(set(document.evidence_ids)):
        blockers.append("physical_wall_existence_not_owned_by_document")
    if entity.status == EvidenceResolutionStatus.CONFLICT:
        blockers.append("physical_wall_existence_conflict")
    elif entity.status == EvidenceResolutionStatus.ABSTAINED:
        blockers.append("physical_wall_existence_abstained")
    elif entity.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("physical_wall_existence_not_corroborated")
    if entity.conflict_evidence_ids or wall.conflicting_evidence_ids:
        blockers.append("physical_wall_conflict_evidence_present")
    return tuple(dict.fromkeys(blockers))


def _abstention(
    *,
    wall: WallCandidate,
    entity: EntityEvidence,
    context: ProviderContext,
    page_no: int,
    blockers: tuple[str, ...],
    authority: str = "unresolved",
    metadata: Optional[dict[str, object]] = None,
) -> QuantityEvidence:
    payload = {
        "family": WALL_LENGTH_FAMILY,
        "wall_id": wall.candidate_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "page_no": page_no,
        "viewport_id": wall.viewport_id,
        "blockers": list(blockers),
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=WALL_LENGTH_FAMILY,
        semantic_key=f"wall_length:{wall.candidate_id}",
        value=None,
        unit="m",
        input_entity_ids=(wall.candidate_id,),
        formula="polyline_length / trusted_px_per_m OR authoritative_figured_dimension",
        formula_version=WALL_LENGTH_FORMULA_VERSION,
        evidence_ids=tuple(entity.evidence_ids),
        authority=authority,
        status=AuthorityStatus.BLOCKED.value,
        confidence=0.0,
        abstained=True,
        blocking_reasons=blockers,
        reason_codes=blockers,
        metadata=metadata or {},
    )


def build_wall_length_quantity(
    *,
    wall: WallCandidate,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
    page_no: int,
    scale_bindings: Sequence[ViewportScaleBinding] = (),
    figured_evidence: Optional[EvidenceAtom] = None,
) -> QuantityEvidence:
    """Build one wall-length quantity from existence + geometry + measurement.

    Scaled FIRM length requires the complete candidate ``scale_bindings`` set to
    reconcile to exactly one owned ``ViewportScaleBinding``. A bare
    ``ScaleCalibration`` is not accepted.
    """
    topology_blockers: list[str] = []
    topology_blockers.extend(
        _existence_blockers(
            wall=wall,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
        )
    )
    if len(wall.centerline_pts) < 2:
        topology_blockers.append("wall_centerline_unresolved")
    page_length = _polyline_length(wall.centerline_pts)
    if not math.isfinite(page_length) or page_length <= 0.0:
        topology_blockers.append("wall_centerline_length_invalid")
    if topology_blockers:
        return _abstention(
            wall=wall,
            entity=entity,
            context=context,
            page_no=page_no,
            blockers=tuple(topology_blockers),
        )

    resolved = resolve_linear_measurement_input(
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=page_no,
        scaled_length_page_units=page_length if scale_bindings else None,
        scale_bindings=scale_bindings,
        figured_evidence=figured_evidence,
        wall_viewport_id=wall.viewport_id,
    )
    if resolved.abstained:
        return _abstention(
            wall=wall,
            entity=entity,
            context=context,
            page_no=page_no,
            blockers=resolved.blocking_reasons or ("measurement_input_abstained",),
            authority=resolved.source_type or "unresolved",
            metadata={
                "measurement_input_fingerprint": resolved.fingerprint(),
                "source_sha256": resolved.source_sha256,
                "revision_id": resolved.revision_id,
                "page_no": resolved.page_no,
                "viewport_id": resolved.viewport_id,
                "scale_fingerprint": resolved.scale_fingerprint,
                "figured_evidence_id": resolved.figured_evidence_id,
                "notes": resolved.notes,
            },
        )

    payload = {
        "family": WALL_LENGTH_FAMILY,
        "wall_id": wall.candidate_id,
        "entity_status": entity.status.value,
        "measurement_input_fingerprint": resolved.fingerprint(),
        "value_m": resolved.value_m,
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=WALL_LENGTH_FAMILY,
        semantic_key=f"wall_length:{wall.candidate_id}",
        value=resolved.value_m,
        unit="m",
        input_entity_ids=(wall.candidate_id,),
        formula="authoritative_figured_dimension" if resolved.source_type == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value else "polyline_length / trusted_px_per_m",
        formula_version=WALL_LENGTH_FORMULA_VERSION,
        evidence_ids=tuple(entity.evidence_ids),
        authority=resolved.source_type or "unresolved",
        status=AuthorityStatus.FIRM.value,
        confidence=min(float(wall.confidence), float(entity.confidence)),
        abstained=False,
        reason_codes=(),
        metadata={
            "measurement_input_fingerprint": resolved.fingerprint(),
            "source_sha256": resolved.source_sha256,
            "revision_id": resolved.revision_id,
            "page_no": resolved.page_no,
            "viewport_id": resolved.viewport_id,
            "scale_fingerprint": resolved.scale_fingerprint,
            "figured_evidence_id": resolved.figured_evidence_id,
            "source_segment_ids": sorted(_wall_source_segment_ids(wall)),
            "topology_schema_version": wall.schema_version,
            "thickness_authority": wall.thickness_authority.value,
            "thickness_m": wall.thickness_m,
            "wall_status": wall.status.value,
            "entity_status": entity.status.value,
        },
    )


def build_wall_length_quantities(
    *,
    walls: Sequence[WallCandidate],
    entities_by_wall_id: dict[str, EntityEvidence],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
    scale_bindings: Sequence[ViewportScaleBinding] = (),
    figured_evidence_by_wall_id: Optional[dict[str, EvidenceAtom]] = None,
    physical_identities: Optional[Mapping[str, PhysicalWallIdentity]] = None,
) -> tuple[QuantityEvidence, ...]:
    """Batch builder with fail-closed duplicate representation protection.

    Duplicate candidate identities or overlapping source-segment ownership mean two
    wall records could represent the same physical geometry. Every affected claim
    abstains rather than silently summing fragmented/duplicated representations.
    """
    figured = figured_evidence_by_wall_id or {}
    duplicate_ids: set[str] = set()
    seen_ids: set[str] = set()
    for wall in walls:
        if wall.candidate_id in seen_ids:
            duplicate_ids.add(wall.candidate_id)
        seen_ids.add(wall.candidate_id)

    overlapping_ids: set[str] = set()
    for i, left in enumerate(walls):
        left_segments = _wall_source_segment_ids(left)
        for right in walls[i + 1 :]:
            if left.candidate_id == right.candidate_id:
                continue
            if left_segments & _wall_source_segment_ids(right):
                overlapping_ids.add(left.candidate_id)
                overlapping_ids.add(right.candidate_id)

    equivalence_blockers: dict[str, tuple[str, ...]] = {}
    if physical_identities is not None:
        equivalence = resolve_physical_wall_equivalence(
            tuple(physical_identities.get(wall.candidate_id) for wall in walls),
            walls_by_id={wall.candidate_id: wall for wall in walls},
        )
        allowed = set(equivalence.representative_wall_ids)
        for wall in walls:
            reasons: list[str] = []
            if wall.candidate_id not in physical_identities:
                reasons.append("physical_wall_identity_unavailable")
            reasons.extend(equivalence.blockers_for(wall.candidate_id))
            identity = physical_identities.get(wall.candidate_id)
            if identity is not None and not identity.usable and not reasons:
                reasons.extend(identity.blocking_reasons or ("physical_wall_identity_abstained",))
            if identity is not None and identity.usable and wall.candidate_id not in allowed:
                reasons.append("physical_wall_not_selected_representative")
            if reasons:
                equivalence_blockers[wall.candidate_id] = tuple(dict.fromkeys(reasons))

    output: list[QuantityEvidence] = []
    for wall in walls:
        entity = entities_by_wall_id.get(wall.candidate_id)
        if entity is None:
            # QuantityEvidence requires an evidence-bearing EntityEvidence for this path.
            # Construct no synthetic entity: skip impossible binding as a deterministic
            # explicit error rather than fabricating provenance.
            raise ValueError(f"missing EntityEvidence for wall {wall.candidate_id!r}")
        blockers: list[str] = []
        if wall.candidate_id in duplicate_ids:
            blockers.append("duplicate_wall_identity")
        if wall.candidate_id in overlapping_ids:
            blockers.append("overlapping_wall_source_segments")
        blockers.extend(equivalence_blockers.get(wall.candidate_id, ()))
        if blockers:
            output.append(
                _abstention(
                    wall=wall,
                    entity=entity,
                    context=context,
                    page_no=page_no,
                    blockers=tuple(blockers),
                    metadata={"source_segment_ids": sorted(_wall_source_segment_ids(wall))},
                )
            )
            continue
        output.append(
            build_wall_length_quantity(
                wall=wall,
                context=context,
                document=document,
                viewport=viewport,
                entity=entity,
                page_no=page_no,
                scale_bindings=scale_bindings,
                figured_evidence=figured.get(wall.candidate_id),
            )
        )
    return tuple(output)
