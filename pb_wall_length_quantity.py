"""Deterministic wall-length QuantityEvidence with scoped completeness proofs.

A FIRM wall length is permitted only when all authority inputs are bound to the
exact document/revision/snapshot/viewport universe used for the decision.
Completeness is dimensional: only the wall-length scale and physical-candidate
universes are required here; unrelated opening/height completeness is not read.

A caller-supplied AuthorityUniverseFingerprint + CompletenessManifest is not a
proof that enumeration was complete.  FIRM publication additionally requires
an EnumeratorSnapshotCommitment verified against the current immutable
upstream snapshot fingerprint and a universe re-enumerated from that snapshot.
"""
from __future__ import annotations

import math
from dataclasses import replace as dc_replace
from typing import Mapping, Optional, Sequence

from pb_authority_completeness import (
    DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
    DOMAIN_WALL_LENGTH_SCALE,
    AuthorityScope,
    AuthorityUniverseFingerprint,
    BoundResolutionFingerprint,
    CompletenessManifest,
    bind_resolution_fingerprint,
    physical_wall_identity_member,
    scale_binding_member,
    verify_bound_resolution_fingerprint,
    verify_completeness_manifest,
)
from pb_enumerator_snapshot_commitment import (
    EnumeratorSnapshotCommitment,
    verify_enumerator_snapshot_commitment,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import MeasurementInputResolution, resolve_linear_measurement_input
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
from pb_physical_wall_existence_authority import resolve_physical_wall_existence
from pb_physical_wall_identity import (
    PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
    resolve_physical_wall_equivalence,
)
from pb_viewport_scale_binding import ViewportScaleBinding, bind_page_viewport_scales
from pb_viewport_segmentation import SegmentedViewport
from pb_wall_room_topology_contracts import WallCandidate

WALL_LENGTH_FAMILY = "wall_length"
WALL_LENGTH_FORMULA_VERSION = "1.5.0"
FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON = (
    "figured_dimension_wall_length_disabled_pending_span_authority"
)


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


def _authority_scope(
    domain: str,
    *,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> AuthorityScope:
    return AuthorityScope(
        domain=domain,
        document_id=document.document_id,
        source_sha256=document.source_sha256,
        revision_id=context.current_revision_id,
        evidence_snapshot_id=context.evidence_snapshot_id,
        graph_snapshot_id=context.canonical_graph_snapshot_id,
        page_id=viewport.page_id,
        viewport_id=viewport.viewport_id,
    )


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


def _existence_recomputation_blockers(
    *,
    wall: WallCandidate,
    entity: EntityEvidence,
    evidence_atoms: Sequence[EvidenceAtom],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[str, ...]:
    recomputed = resolve_physical_wall_existence(
        wall=wall,
        evidence_atoms=evidence_atoms,
        document=document,
        viewport=viewport,
        context=context,
    )
    blockers: list[str] = []
    if recomputed.status != EvidenceResolutionStatus.CORROBORATED:
        blockers.append("existence_not_independently_recorroborated")
        blockers.extend(f"existence_recompute:{reason}" for reason in recomputed.reason_codes)
    if entity.status != recomputed.status:
        blockers.append("entity_status_does_not_match_recomputed_existence")
    return tuple(dict.fromkeys(blockers))


def _scale_bindings_from_page_viewports(
    page_viewports: Sequence[SegmentedViewport],
    *,
    page_no: int,
    context: ProviderContext,
    document: DocumentEvidence,
) -> tuple[Optional[tuple[ViewportScaleBinding, ...]], tuple[str, ...]]:
    view_ids = [str(v.view_id) for v in page_viewports]
    if len(view_ids) != len(set(view_ids)):
        return None, ("duplicate_segmented_viewport_id_in_page_viewports",)
    if any(int(v.page_number) != int(page_no) for v in page_viewports):
        return None, ("page_viewports_page_mismatch",)
    bindings = bind_page_viewport_scales(
        page_viewports,
        page_no=page_no,
        revision_id=context.current_revision_id,
        source_sha256=document.source_sha256,
    )
    return bindings, ()


def _resolve_scale_authority_inputs(
    *,
    scale_bindings: Sequence[ViewportScaleBinding],
    page_viewports: Optional[Sequence[SegmentedViewport]],
    scale_universe: Optional[AuthorityUniverseFingerprint],
    scale_manifest: Optional[CompletenessManifest],
    page_no: int,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[
    tuple[ViewportScaleBinding, ...],
    Optional[AuthorityUniverseFingerprint],
    Optional[CompletenessManifest],
    tuple[str, ...],
]:
    if page_viewports is not None:
        derived, reasons = _scale_bindings_from_page_viewports(
            page_viewports,
            page_no=page_no,
            context=context,
            document=document,
        )
        if reasons or derived is None:
            return (), scale_universe, scale_manifest, reasons or (
                "page_viewports_binding_derivation_failed",
            )
        # IMPORTANT: a duplicate-free caller-supplied page_viewports sequence is
        # not evidence that viewport enumeration was complete.  Derive the local
        # bindings, but never synthesize a completeness universe/manifest here.
        local_bindings = tuple(item for item in derived if item.viewport_id == viewport.viewport_id)
        return local_bindings, scale_universe, scale_manifest, ()
    return tuple(scale_bindings), scale_universe, scale_manifest, ()


def _scale_completeness_blockers(
    *,
    bindings: Sequence[ViewportScaleBinding],
    universe: Optional[AuthorityUniverseFingerprint],
    manifest: Optional[CompletenessManifest],
    enumerator_commitment: Optional[EnumeratorSnapshotCommitment],
    current_upstream_snapshot_id: Optional[str],
    current_upstream_snapshot_fingerprint: Optional[str],
    current_enumerated_universe: Optional[AuthorityUniverseFingerprint],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[str, ...]:
    expected_scope = _authority_scope(
        DOMAIN_WALL_LENGTH_SCALE,
        context=context,
        document=document,
        viewport=viewport,
    )
    supplied_ids = tuple(scale_binding_member(item).candidate_id for item in bindings)
    commitment_verification = verify_enumerator_snapshot_commitment(
        enumerator_commitment,
        expected_scope=expected_scope,
        current_upstream_snapshot_id=current_upstream_snapshot_id,
        current_upstream_snapshot_fingerprint=current_upstream_snapshot_fingerprint,
        current_enumerated_universe=current_enumerated_universe,
        manifest=manifest,
        supplied_admitted_ids=supplied_ids,
        require_resolved=True,
    )
    if not commitment_verification.authentic:
        reasons = list(commitment_verification.reasons)
        if commitment_verification.status.value == "UNBOUND":
            reasons.insert(0, "scale_enumerator_commitment_unavailable")
        else:
            reasons.insert(0, "scale_enumerator_commitment_mismatch")
        return tuple(dict.fromkeys(reasons))

    verification = verify_completeness_manifest(
        manifest,
        current_universe=universe,
        expected_scope=expected_scope,
        supplied_admitted_ids=supplied_ids,
        require_resolved=True,
    )
    if verification.authentic:
        return ()
    reasons = list(verification.reasons)
    if verification.status.value == "UNBOUND":
        reasons.insert(0, "scale_universe_completeness_unproven")
    else:
        reasons.insert(0, "scale_universe_completeness_mismatch")
    return tuple(dict.fromkeys(reasons))


def _local_physical_identities(
    identities: Sequence[PhysicalWallIdentity],
    viewport_id: str,
) -> tuple[PhysicalWallIdentity, ...]:
    return tuple(item for item in identities if item.viewport_id == viewport_id)


def _local_walls(
    walls_by_id: Optional[Mapping[str, WallCandidate]],
    viewport_id: str,
) -> dict[str, WallCandidate]:
    return {
        wall_id: wall
        for wall_id, wall in (walls_by_id or {}).items()
        if wall.viewport_id == viewport_id
    }


def _candidate_and_equivalence_blockers(
    *,
    wall: WallCandidate,
    equivalence: PhysicalWallEquivalenceResolution,
    equivalence_binding: Optional[BoundResolutionFingerprint],
    physical_identity_universe: Sequence[PhysicalWallIdentity],
    physical_walls_by_id: Optional[Mapping[str, WallCandidate]],
    candidate_universe: Optional[AuthorityUniverseFingerprint],
    candidate_manifest: Optional[CompletenessManifest],
    enumerator_commitment: Optional[EnumeratorSnapshotCommitment],
    current_upstream_snapshot_id: Optional[str],
    current_upstream_snapshot_fingerprint: Optional[str],
    current_enumerated_universe: Optional[AuthorityUniverseFingerprint],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
) -> tuple[str, ...]:
    expected_scope = _authority_scope(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        context=context,
        document=document,
        viewport=viewport,
    )
    local_identities = _local_physical_identities(
        physical_identity_universe,
        viewport.viewport_id,
    )
    local_walls = _local_walls(physical_walls_by_id, viewport.viewport_id)
    supplied_ids = tuple(sorted(local_walls))
    blockers: list[str] = []

    commitment_verification = verify_enumerator_snapshot_commitment(
        enumerator_commitment,
        expected_scope=expected_scope,
        current_upstream_snapshot_id=current_upstream_snapshot_id,
        current_upstream_snapshot_fingerprint=current_upstream_snapshot_fingerprint,
        current_enumerated_universe=current_enumerated_universe,
        manifest=candidate_manifest,
        supplied_admitted_ids=supplied_ids,
        require_resolved=True,
    )
    if not commitment_verification.authentic:
        if commitment_verification.status.value == "UNBOUND":
            blockers.append("physical_candidate_enumerator_commitment_unavailable")
        else:
            blockers.append("physical_candidate_enumerator_commitment_mismatch")
        blockers.extend(commitment_verification.reasons)
        blockers.append("physical_equivalence_authenticity_unproven")
        return tuple(dict.fromkeys(blockers))

    verification = verify_completeness_manifest(
        candidate_manifest,
        current_universe=candidate_universe,
        expected_scope=expected_scope,
        supplied_admitted_ids=supplied_ids,
        require_resolved=True,
    )
    if not verification.authentic:
        blockers.append("physical_candidate_universe_completeness_unproven")
        blockers.extend(verification.reasons)
        blockers.append("physical_equivalence_authenticity_unproven")
        return tuple(dict.fromkeys(blockers))

    admitted = set(candidate_manifest.admitted_candidate_ids if candidate_manifest else ())
    identities_by_id = {item.wall_candidate_id: item for item in local_identities}
    if len(identities_by_id) != len(local_identities):
        blockers.append("duplicate_physical_identity_id")
    if set(identities_by_id) != admitted:
        blockers.append("physical_identity_universe_admitted_set_mismatch")
    if set(local_walls) != admitted:
        blockers.append("physical_wall_universe_admitted_set_mismatch")
    if blockers:
        blockers.append("physical_equivalence_authenticity_unproven")
        return tuple(dict.fromkeys(blockers))

    ordered_identities = tuple(identities_by_id[item] for item in sorted(admitted))
    expected_resolution = resolve_physical_wall_equivalence(
        ordered_identities,
        walls_by_id=local_walls,
    )
    if candidate_universe is None:
        return (
            "physical_candidate_universe_completeness_unproven",
            "physical_equivalence_authenticity_unproven",
        )
    equivalence_verification = verify_bound_resolution_fingerprint(
        equivalence,
        equivalence_binding,
        expected_resolution=expected_resolution,
        expected_scope=expected_scope,
        candidate_universe=candidate_universe,
        identities=ordered_identities,
        resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
    )
    if not equivalence_verification.authentic:
        blockers.append("physical_equivalence_authenticity_unproven")
        blockers.extend(equivalence_verification.reasons)
    if wall.candidate_id not in equivalence.representative_wall_ids:
        equivalence_reasons = equivalence.blockers_for(wall.candidate_id)
        blockers.extend(
            equivalence_reasons or ("physical_wall_not_reconciled_as_representative",)
        )
    return tuple(dict.fromkeys(blockers))


def _downgrade_figured_dimension_result(
    resolved: MeasurementInputResolution,
) -> MeasurementInputResolution:
    if resolved.abstained:
        return resolved
    if resolved.source_type != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value:
        return resolved
    return dc_replace(
        resolved,
        value_m=None,
        authority_status=AuthorityStatus.BLOCKED.value,
        blocking_reasons=(
            *resolved.blocking_reasons,
            FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON,
        ),
        notes=(resolved.notes + "; " if resolved.notes else "")
        + "figured-dimension FIRM route disabled pending exact span authority",
    )


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
    evidence_atoms: Sequence[EvidenceAtom],
    equivalence: PhysicalWallEquivalenceResolution,
    page_no: int,
    scale_bindings: Sequence[ViewportScaleBinding] = (),
    page_viewports: Optional[Sequence[SegmentedViewport]] = None,
    figured_evidence: Optional[EvidenceAtom] = None,
    scale_universe: Optional[AuthorityUniverseFingerprint] = None,
    scale_manifest: Optional[CompletenessManifest] = None,
    scale_enumerator_commitment: Optional[EnumeratorSnapshotCommitment] = None,
    scale_upstream_snapshot_id: Optional[str] = None,
    scale_upstream_snapshot_fingerprint: Optional[str] = None,
    scale_enumerated_universe: Optional[AuthorityUniverseFingerprint] = None,
    candidate_universe: Optional[AuthorityUniverseFingerprint] = None,
    candidate_manifest: Optional[CompletenessManifest] = None,
    candidate_enumerator_commitment: Optional[EnumeratorSnapshotCommitment] = None,
    candidate_upstream_snapshot_id: Optional[str] = None,
    candidate_upstream_snapshot_fingerprint: Optional[str] = None,
    candidate_enumerated_universe: Optional[AuthorityUniverseFingerprint] = None,
    physical_identity_universe: Sequence[PhysicalWallIdentity] = (),
    physical_walls_by_id: Optional[Mapping[str, WallCandidate]] = None,
    equivalence_binding: Optional[BoundResolutionFingerprint] = None,
) -> QuantityEvidence:
    """Build one wall length; FIRM requires exact scoped universe proofs."""
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
    topology_blockers.extend(
        _existence_recomputation_blockers(
            wall=wall,
            entity=entity,
            evidence_atoms=evidence_atoms,
            context=context,
            document=document,
            viewport=viewport,
        )
    )
    topology_blockers.extend(
        _candidate_and_equivalence_blockers(
            wall=wall,
            equivalence=equivalence,
            equivalence_binding=equivalence_binding,
            physical_identity_universe=physical_identity_universe,
            physical_walls_by_id=physical_walls_by_id,
            candidate_universe=candidate_universe,
            candidate_manifest=candidate_manifest,
            enumerator_commitment=candidate_enumerator_commitment,
            current_upstream_snapshot_id=candidate_upstream_snapshot_id,
            current_upstream_snapshot_fingerprint=candidate_upstream_snapshot_fingerprint,
            current_enumerated_universe=candidate_enumerated_universe,
            context=context,
            document=document,
            viewport=viewport,
        )
    )
    if len(wall.centerline_pts) < 2:
        topology_blockers.append("wall_centerline_unresolved")
    page_length = _polyline_length(wall.centerline_pts)
    if not math.isfinite(page_length) or page_length <= 0.0:
        topology_blockers.append("wall_centerline_length_invalid")

    resolved_scale_bindings, resolved_scale_universe, resolved_scale_manifest, scale_input_reasons = (
        _resolve_scale_authority_inputs(
            scale_bindings=scale_bindings,
            page_viewports=page_viewports,
            scale_universe=scale_universe,
            scale_manifest=scale_manifest,
            page_no=page_no,
            context=context,
            document=document,
            viewport=viewport,
        )
    )
    topology_blockers.extend(scale_input_reasons)
    # Scale completeness is required only when scale evidence participates in
    # this wall-length decision.  An absent scale cannot be promoted by a
    # missing commitment; it simply reaches the normal no-input/figured route.
    if resolved_scale_bindings:
        topology_blockers.extend(
            _scale_completeness_blockers(
                bindings=resolved_scale_bindings,
                universe=resolved_scale_universe,
                manifest=resolved_scale_manifest,
                enumerator_commitment=scale_enumerator_commitment,
                current_upstream_snapshot_id=scale_upstream_snapshot_id,
                current_upstream_snapshot_fingerprint=scale_upstream_snapshot_fingerprint,
                current_enumerated_universe=scale_enumerated_universe,
                context=context,
                document=document,
                viewport=viewport,
            )
        )
    if topology_blockers:
        return _abstention(
            wall=wall,
            entity=entity,
            context=context,
            page_no=page_no,
            blockers=tuple(dict.fromkeys(topology_blockers)),
        )

    resolved = resolve_linear_measurement_input(
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=page_no,
        scaled_length_page_units=page_length if resolved_scale_bindings else None,
        scale_bindings=resolved_scale_bindings,
        figured_evidence=figured_evidence,
        wall_viewport_id=wall.viewport_id,
    )
    resolved = _downgrade_figured_dimension_result(resolved)
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
        "scale_universe_fingerprint": (
            resolved_scale_universe.fingerprint if resolved_scale_universe else None
        ),
        "candidate_universe_fingerprint": (
            candidate_universe.fingerprint if candidate_universe else None
        ),
        "scale_enumerator_commitment": (
            scale_enumerator_commitment.commitment_fingerprint
            if scale_enumerator_commitment
            else None
        ),
        "candidate_enumerator_commitment": (
            candidate_enumerator_commitment.commitment_fingerprint
            if candidate_enumerator_commitment
            else None
        ),
        "equivalence_binding_fingerprint": (
            equivalence_binding.fingerprint if equivalence_binding else None
        ),
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", payload),
        family=WALL_LENGTH_FAMILY,
        semantic_key=f"wall_length:{wall.candidate_id}",
        value=resolved.value_m,
        unit="m",
        input_entity_ids=(wall.candidate_id,),
        formula=(
            "authoritative_figured_dimension"
            if resolved.source_type == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
            else "polyline_length / trusted_px_per_m"
        ),
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
            "scale_universe_fingerprint": resolved_scale_universe.fingerprint,
            "scale_manifest_fingerprint": resolved_scale_manifest.manifest_fingerprint,
            "scale_enumerator_commitment_fingerprint": (
                scale_enumerator_commitment.commitment_fingerprint
                if scale_enumerator_commitment
                else None
            ),
            "candidate_universe_fingerprint": candidate_universe.fingerprint,
            "candidate_manifest_fingerprint": candidate_manifest.manifest_fingerprint,
            "candidate_enumerator_commitment_fingerprint": (
                candidate_enumerator_commitment.commitment_fingerprint
                if candidate_enumerator_commitment
                else None
            ),
            "equivalence_binding_fingerprint": equivalence_binding.fingerprint,
        },
    )


def build_wall_length_quantities(
    *,
    walls: Sequence[WallCandidate],
    entities_by_wall_id: dict[str, EntityEvidence],
    evidence_atoms: Sequence[EvidenceAtom],
    physical_identities: Mapping[str, Optional[PhysicalWallIdentity]],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
    scale_bindings: Sequence[ViewportScaleBinding] = (),
    page_viewports: Optional[Sequence[SegmentedViewport]] = None,
    figured_evidence_by_wall_id: Optional[dict[str, EvidenceAtom]] = None,
    scale_universe: Optional[AuthorityUniverseFingerprint] = None,
    scale_manifest: Optional[CompletenessManifest] = None,
    scale_enumerator_commitment: Optional[EnumeratorSnapshotCommitment] = None,
    scale_upstream_snapshot_id: Optional[str] = None,
    scale_upstream_snapshot_fingerprint: Optional[str] = None,
    scale_enumerated_universe: Optional[AuthorityUniverseFingerprint] = None,
    candidate_universe: Optional[AuthorityUniverseFingerprint] = None,
    candidate_manifest: Optional[CompletenessManifest] = None,
    candidate_enumerator_commitment: Optional[EnumeratorSnapshotCommitment] = None,
    candidate_upstream_snapshot_id: Optional[str] = None,
    candidate_upstream_snapshot_fingerprint: Optional[str] = None,
    candidate_enumerated_universe: Optional[AuthorityUniverseFingerprint] = None,
    physical_identity_universe: Optional[Sequence[PhysicalWallIdentity]] = None,
) -> tuple[QuantityEvidence, ...]:
    """Batch publication with complete candidate-universe reconciliation."""
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

    identity_universe = tuple(
        physical_identity_universe
        if physical_identity_universe is not None
        else tuple(item for item in physical_identities.values() if item is not None)
    )
    local_identities = _local_physical_identities(identity_universe, viewport.viewport_id)
    local_walls_by_id = {
        wall.candidate_id: wall for wall in walls if wall.viewport_id == viewport.viewport_id
    }
    expected_candidate_scope = _authority_scope(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        context=context,
        document=document,
        viewport=viewport,
    )
    candidate_commitment_verification = verify_enumerator_snapshot_commitment(
        candidate_enumerator_commitment,
        expected_scope=expected_candidate_scope,
        current_upstream_snapshot_id=candidate_upstream_snapshot_id,
        current_upstream_snapshot_fingerprint=candidate_upstream_snapshot_fingerprint,
        current_enumerated_universe=candidate_enumerated_universe,
        manifest=candidate_manifest,
        supplied_admitted_ids=tuple(sorted(local_walls_by_id)),
        require_resolved=True,
    )
    candidate_verification = verify_completeness_manifest(
        candidate_manifest,
        current_universe=candidate_universe,
        expected_scope=expected_candidate_scope,
        supplied_admitted_ids=tuple(sorted(local_walls_by_id)),
        require_resolved=True,
    )

    identities_by_id = {item.wall_candidate_id: item for item in local_identities}
    candidate_blockers: list[str] = []
    if not candidate_commitment_verification.authentic:
        if candidate_commitment_verification.status.value == "UNBOUND":
            candidate_blockers.append("physical_candidate_enumerator_commitment_unavailable")
        else:
            candidate_blockers.append("physical_candidate_enumerator_commitment_mismatch")
        candidate_blockers.extend(candidate_commitment_verification.reasons)
    if not candidate_verification.authentic:
        candidate_blockers.append("physical_candidate_universe_completeness_unproven")
        candidate_blockers.extend(candidate_verification.reasons)
    if candidate_manifest is not None:
        admitted = set(candidate_manifest.admitted_candidate_ids)
        if set(identities_by_id) != admitted:
            candidate_blockers.append("physical_identity_universe_admitted_set_mismatch")
    if len(identities_by_id) != len(local_identities):
        candidate_blockers.append("duplicate_physical_identity_id")

    equivalence = resolve_physical_wall_equivalence(
        tuple(identities_by_id.get(wall.candidate_id) for wall in walls),
        walls_by_id={wall.candidate_id: wall for wall in walls},
    )
    equivalence_binding: Optional[BoundResolutionFingerprint] = None
    if not candidate_blockers and candidate_universe is not None:
        ordered_identities = tuple(
            identities_by_id[item]
            for item in sorted(candidate_manifest.admitted_candidate_ids)
        )
        equivalence_binding = bind_resolution_fingerprint(
            equivalence,
            scope=expected_candidate_scope,
            candidate_universe=candidate_universe,
            identities=ordered_identities,
            resolver_rule_version=PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION,
        )

    output: list[QuantityEvidence] = []
    for wall in walls:
        entity = entities_by_wall_id.get(wall.candidate_id)
        if entity is None:
            raise ValueError(f"missing EntityEvidence for wall {wall.candidate_id!r}")
        blockers: list[str] = list(candidate_blockers)
        if wall.candidate_id in duplicate_ids:
            blockers.append("duplicate_wall_identity")
        if wall.candidate_id in overlapping_ids:
            blockers.append("overlapping_wall_source_segments")
        if blockers:
            output.append(
                _abstention(
                    wall=wall,
                    entity=entity,
                    context=context,
                    page_no=page_no,
                    blockers=tuple(dict.fromkeys(blockers)),
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
                evidence_atoms=evidence_atoms,
                equivalence=equivalence,
                page_no=page_no,
                scale_bindings=scale_bindings,
                page_viewports=page_viewports,
                figured_evidence=figured.get(wall.candidate_id),
                scale_universe=scale_universe,
                scale_manifest=scale_manifest,
                scale_enumerator_commitment=scale_enumerator_commitment,
                scale_upstream_snapshot_id=scale_upstream_snapshot_id,
                scale_upstream_snapshot_fingerprint=scale_upstream_snapshot_fingerprint,
                scale_enumerated_universe=scale_enumerated_universe,
                candidate_universe=candidate_universe,
                candidate_manifest=candidate_manifest,
                candidate_enumerator_commitment=candidate_enumerator_commitment,
                candidate_upstream_snapshot_id=candidate_upstream_snapshot_id,
                candidate_upstream_snapshot_fingerprint=candidate_upstream_snapshot_fingerprint,
                candidate_enumerated_universe=candidate_enumerated_universe,
                physical_identity_universe=identity_universe,
                physical_walls_by_id={wall.candidate_id: wall for wall in walls},
                equivalence_binding=equivalence_binding,
            )
        )
    return tuple(output)