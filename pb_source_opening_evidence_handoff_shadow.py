"""Order 6 (MAX #7159430612): Unified schedule-to-physical opening evidence handoff shadow.

Cohesively coordinates the 8 opening source-evidence shadows into a single
consumer-ready handoff packet for Claude (geometry/host) and MAX (authority/issuer):
1. Host-stroke exclusion (rejects leaders, dim rails, dashed & cross-layer strokes)
2. Host wall membership proof (rejects parallel neighbors & cross-viewport hosts)
3. Shared opening cluster & corner callout deduplication
4. Door operation classification (cavity slider vs push/pull & swing)
5. Kind-routed dimension evidence:
   - Garage/panel doors (strictly blocks 2040 mm external-door fallback)
   - External glazing/windows (reconciles schedule vs aperture vs elevation)
   - Unmarked openings (native figure-line witness, abstains on ambiguity)
   - Scheduled openings (mark-to-instance lineage + explicit basis/quantity separation)

Authority boundaries:
- Default-off shadow handoff only (`commercial_authority_granted=False`,
  `host_authority_granted=False`, `frame_authority_granted=False`).
- Preserves explicit source IDs (`document_id`, `revision_id`, `source_sha256`,
  `page_id`, `viewport_id`, `physical_opening_id`) and reports deterministic
  `first_remaining_gate` and `blocking_reasons`.
- Zero job-specific rules (`audit_shared_source == ()`).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_instance_quantity_lineage_shadow import (
    PhysicalOpeningInstanceCandidate,
    ScheduleMarkRowCandidate,
    resolve_schedule_instance_quantity_lineage,
)
from pb_shared_opening_cluster_callout_shadow import (
    ClusterOpeningLegCandidate,
    OpeningClusterCalloutWitness,
    resolve_shared_opening_clusters,
)
from pb_source_cavity_slider_vs_push_pull_shadow import (
    DoorApertureSymbolObservation,
    classify_door_operation_cues,
)
from pb_source_external_glazing_reconciliation_shadow import (
    GlazingElevationWitness,
    GlazingScheduleRowWitness,
    PhysicalGlazingApertureWitness,
    reconcile_external_glazing_evidence_shadow,
)
from pb_source_garage_panel_door_dimension_shadow import (
    GarageDoorDimensionWitness,
    GarageDoorHostWitness,
    evaluate_garage_panel_door_dimension_shadow,
)
from pb_source_host_stroke_exclusion_shadow import (
    ApertureHostCandidateContext,
    SourceMarkerPrimitive,
    SourceTextBox,
    SourceVectorStroke,
    filter_opening_host_wall_strokes_shadow,
)
from pb_source_opening_host_membership_proof_shadow import (
    CandidateHostWallBand,
    PhysicalOpeningApertureWitness,
    prove_opening_host_wall_membership_shadow,
)
from pb_source_unmarked_opening_figure_witness_shadow import (
    NativeVectorSegment,
    TrustedFigureText,
    UnmarkedOpeningTarget,
    prove_unmarked_opening_figure_witness_shadow,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class OpeningConsumerHandoffRecord:
    """Consumer-ready opening evidence record aligned with Claude/MAX authority boundaries."""

    handoff_id: str
    physical_opening_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    opening_category: str  # "scheduled_door" | "garage_panel_door" | "external_glazing" | "unmarked_opening"
    accepted_host_stroke_ids: tuple[str, ...]
    rejected_host_stroke_count: int
    proven_host_wall_id: str | None
    host_membership_proven: bool
    operation_classification: str | None
    operation_subtype: str | None
    cluster_id: str | None
    dimension_proven: bool
    width_mm: float | None
    height_mm: float | None
    dimension_basis: str | None
    standard_door_2040_fallback_blocked: bool
    first_remaining_gate: str
    blocking_reasons: tuple[str, ...]
    host_authority_boundary: str = "HOST_PROOF_SHADOW_ONLY"
    frame_authority_boundary: str = "FRAME_UNISSUED"
    host_authority_granted: bool = False
    frame_authority_granted: bool = False
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "physical_opening_id": self.physical_opening_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "opening_category": self.opening_category,
            "accepted_host_stroke_ids": list(self.accepted_host_stroke_ids),
            "rejected_host_stroke_count": self.rejected_host_stroke_count,
            "proven_host_wall_id": self.proven_host_wall_id,
            "host_membership_proven": self.host_membership_proven,
            "operation_classification": self.operation_classification,
            "operation_subtype": self.operation_subtype,
            "cluster_id": self.cluster_id,
            "dimension_proven": self.dimension_proven,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "dimension_basis": self.dimension_basis,
            "standard_door_2040_fallback_blocked": self.standard_door_2040_fallback_blocked,
            "first_remaining_gate": self.first_remaining_gate,
            "blocking_reasons": list(self.blocking_reasons),
            "host_authority_boundary": self.host_authority_boundary,
            "frame_authority_boundary": self.frame_authority_boundary,
            "host_authority_granted": False,
            "frame_authority_granted": False,
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def build_opening_evidence_handoff_shadow(
    *,
    opening_category: str,
    host_aperture: PhysicalOpeningApertureWitness,
    candidate_walls: Sequence[CandidateHostWallBand],
    same_physical_wall_pairs: Sequence[tuple[str, str]] = (),
    ambiguous_equivalence_wall_ids: Sequence[str] = (),
    stroke_context: ApertureHostCandidateContext | None = None,
    candidate_strokes: Sequence[SourceVectorStroke] = (),
    stroke_texts: Sequence[SourceTextBox] = (),
    stroke_markers: Sequence[SourceMarkerPrimitive] = (),
    operation_observation: DoorApertureSymbolObservation | None = None,
    cluster_legs: Sequence[ClusterOpeningLegCandidate] = (),
    cluster_callouts: Sequence[OpeningClusterCalloutWitness] = (),
    schedule_rows: Sequence[ScheduleMarkRowCandidate] = (),
    schedule_instances: Sequence[PhysicalOpeningInstanceCandidate] = (),
    garage_host: GarageDoorHostWitness | None = None,
    garage_dim_witnesses: Sequence[GarageDoorDimensionWitness] = (),
    glazing_aperture: PhysicalGlazingApertureWitness | None = None,
    glazing_schedule_rows: Sequence[GlazingScheduleRowWitness] = (),
    glazing_elevations: Sequence[GlazingElevationWitness] = (),
    unmarked_target: UnmarkedOpeningTarget | None = None,
    unmarked_segments: Sequence[NativeVectorSegment] = (),
    unmarked_texts: Sequence[TrustedFigureText] = (),
) -> OpeningConsumerHandoffRecord:
    """Assemble an end-to-end opening consumer handoff record across all 8 evidence gates."""
    cat = _clean(opening_category).lower()
    if cat not in {"scheduled_door", "garage_panel_door", "external_glazing", "unmarked_opening"}:
        raise ValueError(f"unsupported opening_category: {opening_category!r}")

    oid = _clean(host_aperture.opening_id)
    doc_id, rev_id, sha, page_id, vp_id = host_aperture.lineage.normalized()
    reasons: list[str] = []

    # 1. Host-stroke filtering (leaders, dim rails, dashed, cross-layer)
    accepted_strokes: tuple[str, ...] = ()
    rejected_stroke_count = 0
    if stroke_context is not None:
        if stroke_context.lineage.normalized_tuple() != (doc_id, rev_id, sha, page_id, vp_id):
            reasons.append("stroke_context_lineage_mismatch")
        else:
            sf = filter_opening_host_wall_strokes_shadow(
                stroke_context,
                candidate_strokes,
                text_boxes=stroke_texts,
                markers=stroke_markers,
            )
            accepted_strokes = sf.accepted_stroke_ids
            rejected_stroke_count = len(sf.rejected_stroke_ids)
            if not accepted_strokes:
                reasons.append("no_accepted_structural_host_strokes")

    # 2. Host wall membership proof (rejects parallel neighbors & cross-viewport hosts)
    host_proof = prove_opening_host_wall_membership_shadow(
        host_aperture,
        candidate_walls,
        same_physical_wall_pairs=same_physical_wall_pairs,
        ambiguous_equivalence_wall_ids=ambiguous_equivalence_wall_ids,
    )
    if not host_proof.proven:
        reasons.extend(host_proof.blocking_reasons)

    # 3. Optional cluster/corner-callout deduplication
    cluster_id: str | None = None
    if cluster_legs:
        cluster_res = resolve_shared_opening_clusters(legs=cluster_legs, callouts=cluster_callouts)
        for cl in cluster_res.clusters:
            if oid in cl.leg_ids:
                cluster_id = cl.cluster_id
                if cl.status is not EvidenceResolutionStatus.CORROBORATED:
                    reasons.extend(cl.reason_codes)
                break

    # 4. Optional door operation classification (cavity slider vs push/pull & swing)
    op_class: str | None = None
    op_sub: str | None = None
    if operation_observation is not None:
        op_res = classify_door_operation_cues(operation_observation)
        if op_res.status is not EvidenceResolutionStatus.CORROBORATED:
            reasons.extend(op_res.reason_codes)
        else:
            op_class = op_res.classification
            op_sub = op_res.subtype

    # 5. Category-specific dimension evidence routing
    dim_proven = False
    width_mm: float | None = None
    height_mm: float | None = None
    dim_basis: str | None = None
    block_2040 = cat in {"garage_panel_door", "external_glazing"}

    if cat == "garage_panel_door":
        if garage_host is None:
            reasons.append("garage_host_witness_missing")
        elif garage_host.lineage.normalized_tuple() != (doc_id, rev_id, sha, page_id, vp_id):
            reasons.append("garage_host_lineage_mismatch")
        else:
            g_res = evaluate_garage_panel_door_dimension_shadow(garage_host, garage_dim_witnesses)
            block_2040 = g_res.standard_door_2040_fallback_blocked
            if g_res.abstained:
                reasons.extend(g_res.blocking_reasons)
            else:
                dim_proven = True
                width_mm = g_res.width_mm
                height_mm = g_res.height_mm
                dim_basis = g_res.dimension_basis

    elif cat == "external_glazing":
        if glazing_aperture is None:
            reasons.append("glazing_aperture_witness_missing")
        elif glazing_aperture.lineage.doc_rev_sha() != (doc_id, rev_id, sha):
            reasons.append("glazing_aperture_lineage_mismatch")
        else:
            gl_res = reconcile_external_glazing_evidence_shadow(
                glazing_aperture,
                schedule_rows=glazing_schedule_rows,
                elevation_witnesses=glazing_elevations,
            )
            if gl_res.abstained:
                reasons.extend(gl_res.blocking_reasons)
            else:
                dim_proven = True
                width_mm = gl_res.resolved_width_mm
                height_mm = gl_res.resolved_height_mm
                dim_basis = gl_res.resolved_basis

    elif cat == "unmarked_opening":
        if unmarked_target is None:
            reasons.append("unmarked_opening_target_missing")
        elif unmarked_target.lineage.normalized() != (doc_id, rev_id, sha, page_id, vp_id):
            reasons.append("unmarked_opening_lineage_mismatch")
        else:
            um_res = prove_unmarked_opening_figure_witness_shadow(
                unmarked_target, unmarked_segments, unmarked_texts, axis_label="width"
            )
            if um_res.abstained:
                reasons.extend(um_res.blocking_reasons)
            else:
                dim_proven = True
                width_mm = um_res.value_mm
                height_mm = None
                dim_basis = "native_figure_line"

    else:  # scheduled_door
        if not schedule_rows or not schedule_instances:
            reasons.append("schedule_lineage_inputs_missing")
        else:
            lin_res = resolve_schedule_instance_quantity_lineage(
                schedule_rows=schedule_rows,
                physical_instances=schedule_instances,
            )
            matched = [b for b in lin_res.installed_openings if b.instance_id == oid]
            if len(matched) != 1:
                reasons.append("schedule_instance_binding_missing_or_ambiguous")
            else:
                b = matched[0]
                if b.status is not EvidenceResolutionStatus.CORROBORATED:
                    reasons.extend(b.reason_codes)
                else:
                    witness = (
                        b.leaf_dimension
                        or b.frame_dimension
                        or b.rough_opening_dimension
                        or b.clear_opening_dimension
                        or b.unknown_basis_dimension
                    )
                    if witness is None or witness.width_mm is None or witness.height_mm is None:
                        reasons.append("schedule_instance_dimensions_incomplete")
                    else:
                        dim_proven = True
                        width_mm = float(witness.width_mm)
                        height_mm = float(witness.height_mm)
                        dim_basis = witness.dimension_class

    dedup = tuple(dict.fromkeys(reasons))
    if not host_proof.proven:
        first_gate = host_proof.blocking_reasons[0] if host_proof.blocking_reasons else "structural_host_unproven"
    elif dedup:
        first_gate = dedup[0]
    else:
        first_gate = "host_and_frame_authority_promotion_required"

    payload = {
        "physical_opening_id": oid,
        "document_id": doc_id,
        "revision_id": rev_id,
        "source_sha256": sha,
        "page_id": page_id,
        "viewport_id": vp_id,
        "opening_category": cat,
        "accepted_host_stroke_ids": list(accepted_strokes),
        "rejected_host_stroke_count": rejected_stroke_count,
        "proven_host_wall_id": host_proof.proven_host_wall_id,
        "host_membership_proven": host_proof.proven,
        "operation_classification": op_class,
        "operation_subtype": op_sub,
        "cluster_id": cluster_id,
        "dimension_proven": dim_proven,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "dimension_basis": dim_basis,
        "standard_door_2040_fallback_blocked": block_2040,
        "first_remaining_gate": first_gate,
        "blocking_reasons": list(dedup),
    }
    digest = _canonical_sha(payload)
    return OpeningConsumerHandoffRecord(
        handoff_id=f"opening_handoff_{digest[:16]}",
        physical_opening_id=oid,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        page_id=page_id,
        viewport_id=vp_id,
        opening_category=cat,
        accepted_host_stroke_ids=accepted_strokes,
        rejected_host_stroke_count=rejected_stroke_count,
        proven_host_wall_id=host_proof.proven_host_wall_id,
        host_membership_proven=host_proof.proven,
        operation_classification=op_class,
        operation_subtype=op_sub,
        cluster_id=cluster_id,
        dimension_proven=dim_proven,
        width_mm=width_mm,
        height_mm=height_mm,
        dimension_basis=dim_basis,
        standard_door_2040_fallback_blocked=block_2040,
        first_remaining_gate=first_gate,
        blocking_reasons=dedup,
        host_authority_boundary="HOST_PROOF_SHADOW_ONLY",
        frame_authority_boundary="FRAME_UNISSUED",
        host_authority_granted=False,
        frame_authority_granted=False,
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
