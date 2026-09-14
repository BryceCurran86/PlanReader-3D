"""Deterministic wall-length QuantityEvidence from W1-W10 topology.

Linear wall length requires physical-wall existence, a measurable centerline,
and firm scale or a documented dimension. It does not require thickness or
height. ``WallCandidate.status`` is not existence authority: that field is
coupled to thickness by the WallCandidate invariant.

This module does not read ``metadata["physical_evidence_status"]``, does not
invent thickness, does not publish commercial takeoff, and does not guess
external/internal scope.

PUBLICATION BOUNDARY (2026-09-14 remediation)
----------------------------------------------
``build_wall_length_quantity`` is the only function that may return
``AuthorityStatus.FIRM``. It cannot be called safely with caller-curated
inputs alone: every one of the checks below is mandatory and cannot be
skipped by omission.

1. ``entity: EntityEvidence`` is never trusted at face value.
   ``evidence_atoms`` is REQUIRED and this module independently recomputes
   existence via ``pb_physical_wall_existence_authority.
   resolve_physical_wall_existence``; a caller-supplied ``entity`` whose
   status disagrees with the recomputed, collision-checked, revision/
   snapshot/SHA-owned result is rejected. A hand-built ``EntityEvidence``
   asserting ``CORROBORATED`` with no real atoms behind it cannot reach
   FIRM (closes GPT-2 blockers 2 and 3 -- collision-safety already lived
   inside ``resolve_physical_wall_existence``; the gap was that this
   boundary never called it).
2. ``equivalence: PhysicalWallEquivalenceResolution`` is REQUIRED (no
   default). Only a wall in ``equivalence.representative_wall_ids`` may
   reach FIRM (closes blocker 5 -- reconciliation used to be an optional
   batch-only parameter that defaulted to being skipped entirely, and
   blocker 6 -- the single-wall function could reach FIRM independently of
   any batch/equivalence boundary).
3. Scale-binding universe completeness: when ``context.viewport_page_
   ownership`` (or, absent that, ``context.trusted_viewport_ids()`` on a
   multi-viewport page) names sibling viewports on this page, every named
   viewport must be represented in ``scale_bindings`` or FIRM is blocked
   (closes the sibling-viewport-omission shape of blocker 1). Callers that
   pass ``page_viewports`` (the complete F.07 ``SegmentedViewport`` list for
   the page) get the stronger, structural closure: bindings are derived
   internally via ``pb_viewport_scale_binding.bind_page_viewport_scales``
   and any caller-supplied ``scale_bindings`` are ignored, which also closes
   the same-viewport-competing-binding shape of blocker 1 (a caller cannot
   hide a second binding for one viewport_id, because there is only one
   binding derivable from one ``SegmentedViewport`` record). Direct
   ``scale_bindings``-only callers keep the weaker, partial mitigation
   above; this is a known, documented residual gap, not silently claimed as
   closed (see the remediation report).
4. A generic ``figured_dimension`` atom cannot independently create FIRM
   wall length in this PR (closes blocker 7). ``pb_figured_dimension_
   authority.resolve_measurement_authority`` remains reused unchanged and
   still FIRMs a scalar figured-vs-scaled comparison for other, unrelated
   consumers listed in AGENTS.md; only THIS publication boundary downgrades
   a documented-dimension-sourced result to BLOCKED, with an explicit,
   diagnosable reason code, pending the dedicated figured-dimension span
   authority workstream (dimension line -> terminators -> witnesses ->
   endpoints -> exact physical span -> exact target entity).

``build_wall_length_quantities`` (the batch entrypoint) computes ``entity``
recomputation and ``equivalence`` once for the whole candidate set and
forwards them into ``build_wall_length_quantity`` per wall, so there is
exactly one place the completeness proofs are assembled.
"""
from __future__ import annotations

import math
from dataclasses import replace as dc_replace
from typing import Mapping, Optional, Sequence

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_measurement_input_authority import MeasurementInputResolution, resolve_linear_measurement_input
from pb_physical_wall_existence_authority import resolve_physical_wall_existence
from pb_physical_wall_identity import (
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
    resolve_physical_wall_equivalence,
)
from pb_viewport_scale_binding import ViewportScaleBinding, bind_page_viewport_scales
from pb_viewport_segmentation import SegmentedViewport
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
WALL_LENGTH_FORMULA_VERSION = "1.3.0"

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
    """Independently re-derive existence from raw atoms; never trust ``entity``.

    GPT-2 blockers 2 and 3: collision-safe, revision/snapshot/SHA-owned
    existence resolution already exists in ``resolve_physical_wall_existence``,
    but a caller who skips that resolver and hands ``build_wall_length_quantity``
    a pre-built ``EntityEvidence`` bypassed it entirely. Recomputing here and
    requiring agreement closes that route without removing ``entity`` (which
    still carries the real ``evidence_ids``/identity bookkeeping the output
    QuantityEvidence needs).
    """
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


def _scale_universe_completeness_blockers(
    *,
    scale_bindings: Sequence[ViewportScaleBinding],
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[str, ...]:
    """Partial closure of blocker 1 for direct ``scale_bindings`` callers.

    Cross-checks the supplied bindings against ``context.viewport_page_
    ownership`` (falling back to ``trusted_viewport_ids()`` when ownership
    pairs are not populated but more than one viewport is trusted): every
    sibling viewport known to the current revision on this page must be
    represented, so a caller cannot silently omit a sibling viewport's
    binding. This does NOT prove completeness for two competing bindings
    that both claim the SAME viewport_id -- that requires the
    ``page_viewports``-derived path below, which is structurally complete
    by construction.
    """
    if not scale_bindings:
        return ()
    expected = {
        str(vp) for vp, pg in context.viewport_page_ownership if int(pg) == int(page_no)
    }
    if not expected and len(context.trusted_viewport_ids()) > 1:
        expected = set(context.trusted_viewport_ids())
    if not expected or viewport.viewport_id not in expected:
        return ()
    supplied = {b.viewport_id for b in scale_bindings}
    if expected - supplied:
        return ("incomplete_scale_binding_universe",)
    return ()


def _scale_bindings_from_page_viewports(
    page_viewports: Sequence[SegmentedViewport],
    *,
    page_no: int,
    context: ProviderContext,
    document: DocumentEvidence,
) -> tuple[Optional[tuple[ViewportScaleBinding, ...]], tuple[str, ...]]:
    """Derive the complete per-page binding universe from F.07's own output.

    Structural closure of blocker 1 (Option A): ``bind_viewport_scale`` is a
    pure function of one ``SegmentedViewport``, so there is exactly one
    binding derivable per ``view_id`` once the caller supplies the complete,
    duplicate-free viewport list for the page -- there is no second,
    competing binding a caller could hide, because none can exist outside
    what this function derives.
    """
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


def _downgrade_figured_dimension_result(
    resolved: MeasurementInputResolution,
) -> MeasurementInputResolution:
    """Blocker 7: a generic figured_dimension atom cannot create FIRM here.

    ``resolve_linear_measurement_input`` / ``pb_figured_dimension_authority``
    remain unchanged and still reused as-is (AGENTS.md's own "may become
    firm" seam) -- this downgrade is local to the wall-length publication
    boundary only, pending the dedicated figured-dimension span-identity
    workstream (dimension line -> terminators -> witnesses -> endpoints ->
    exact physical span -> exact target entity), which this PR does not
    implement.
    """
    if resolved.abstained:
        return resolved
    if resolved.source_type != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value:
        return resolved
    return dc_replace(
        resolved,
        value_m=None,
        authority_status=AuthorityStatus.BLOCKED.value,
        blocking_reasons=(*resolved.blocking_reasons, FIGURED_DIMENSION_WALL_LENGTH_DISABLED_REASON),
        notes=(resolved.notes + "; " if resolved.notes else "") + "figured-dimension FIRM route disabled for #288 wall length",
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
) -> QuantityEvidence:
    """Build one wall-length quantity. See module docstring for the four
    mandatory completeness proofs this function now owns unavoidably:
    independent existence recomputation, mandatory physical-equivalence
    representative selection, scale-binding universe completeness, and the
    figured-dimension FIRM downgrade. There is no parameter combination that
    skips any of them -- ``evidence_atoms`` and ``equivalence`` have no
    default and must be supplied on every call.
    """
    topology_blockers: list[str] = []
    topology_blockers.extend(
        _existence_blockers(wall=wall, context=context, document=document, viewport=viewport, entity=entity)
    )
    topology_blockers.extend(
        _existence_recomputation_blockers(
            wall=wall, entity=entity, evidence_atoms=evidence_atoms, context=context, document=document, viewport=viewport,
        )
    )
    if wall.candidate_id not in equivalence.representative_wall_ids:
        equivalence_reasons = equivalence.blockers_for(wall.candidate_id)
        topology_blockers.extend(equivalence_reasons or ("physical_wall_not_reconciled_as_representative",))
    if len(wall.centerline_pts) < 2:
        topology_blockers.append("wall_centerline_unresolved")
    page_length = _polyline_length(wall.centerline_pts)
    if not math.isfinite(page_length) or page_length <= 0.0:
        topology_blockers.append("wall_centerline_length_invalid")
    if topology_blockers:
        return _abstention(wall=wall, entity=entity, context=context, page_no=page_no, blockers=tuple(topology_blockers))

    resolved_scale_bindings = scale_bindings
    if page_viewports is not None:
        derived, derive_reasons = _scale_bindings_from_page_viewports(
            page_viewports, page_no=page_no, context=context, document=document,
        )
        if derive_reasons or derived is None:
            return _abstention(
                wall=wall, entity=entity, context=context, page_no=page_no,
                blockers=derive_reasons or ("page_viewports_binding_derivation_failed",),
            )
        resolved_scale_bindings = derived
    else:
        universe_blockers = _scale_universe_completeness_blockers(
            scale_bindings=scale_bindings, context=context, viewport=viewport, page_no=page_no,
        )
        if universe_blockers:
            return _abstention(wall=wall, entity=entity, context=context, page_no=page_no, blockers=universe_blockers)

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
    evidence_atoms: Sequence[EvidenceAtom],
    physical_identities: Mapping[str, Optional[PhysicalWallIdentity]],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
    scale_bindings: Sequence[ViewportScaleBinding] = (),
    page_viewports: Optional[Sequence[SegmentedViewport]] = None,
    figured_evidence_by_wall_id: Optional[dict[str, EvidenceAtom]] = None,
) -> tuple[QuantityEvidence, ...]:
    """Batch builder with fail-closed duplicate representation protection.

    ``physical_identities`` and ``evidence_atoms`` are REQUIRED (GPT-2
    blocker 5): there is no argument combination that skips physical-
    equivalence reconciliation or existence recomputation. Every wall's
    identity is looked up (``physical_identities.get(wall.candidate_id)``
    may legitimately be ``None`` for a wall with no resolvable identity,
    which ``resolve_physical_wall_equivalence`` already treats as an
    abstention) so a caller cannot silently omit a specific wall from
    reconciliation while still publishing it -- every wall in ``walls`` is
    represented in the equivalence pass, one way or another.
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

    equivalence = resolve_physical_wall_equivalence(
        tuple(physical_identities.get(wall.candidate_id) for wall in walls),
        walls_by_id={wall.candidate_id: wall for wall in walls},
    )

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
                evidence_atoms=evidence_atoms,
                equivalence=equivalence,
                page_no=page_no,
                scale_bindings=scale_bindings,
                page_viewports=page_viewports,
                figured_evidence=figured.get(wall.candidate_id),
            )
        )
    return tuple(output)
