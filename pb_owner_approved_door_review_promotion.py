"""Owner-approved door area: estimator-review promotion and sealed export (default-off).

This module is an explicit authority-promotion boundary, modelled on ``pb_ceiling_lining_review_promotion``. It does NOT make a door area FIRM or
CORROBORATED, does NOT bypass estimator review, and is used only by the optional owner-review handoff.

A door with exactly ONE printed figure (its width, bound by the label authority) cannot get a measured height from the drawing. When the owner
supplies an explicit, named, dated, timezone-aware height approval, layer A publishes a shadow ``review_required`` area. This module may turn that
shadow into an estimator-review row ("To review", origin AI, all three existing commercial gates closed) only when, from the retained records alone:

- the shadow quantity is recomputed from its canonical opening (``publish_live_opening_area_quantities``) and is a ``review_required``,
  ``shadow_only`` door area on the owner-approved second-axis basis;
- exactly one explicit ``MeasurementRecord`` approval targets that opening, its recomputed approval id equals the id the canonical opening
  retains, it passes the owner-approval rule (user-approved, named approver, timezone-aware date, mm, page and source hash match, height axis),
  and its value equals the retained approved height and sits inside the opening bounds;
- the numeric value is copied exactly from the shadow quantity;
- the source trace is the canonical opening's exact document/revision/hash/page/viewport/evidence identity;
- the existing commercial adapter projects it to an unreviewed AI row and every existing commercial gate rejects that row.

The promoted quantity states both facts in its authority string: the width is a printed figure, the height is an owner-approved assumption.
Anything unproven is WITHHELD with a typed reason code; nothing is guessed, defaulted or resolved by nearest/first/smallest.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from pb_door_height_owner_gate_shadow import owner_approval_issues, owner_height_approval_id
from pb_geometry_takeoff_model import MeasurementRecord
from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_OWNER_APPROVED_SECOND_AXIS_AREA_QUANTITY_AUTHORITY,
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_opening_label_dimension_authority import (
    _MAX_OPENING_DIMENSION_MM,
    _MIN_OPENING_DIMENSION_MM,
)
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    CommercialTakeoffSourceTrace,
    existing_commercial_gate_results,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)

OWNER_DOOR_REVIEW_PROMOTION_SCHEMA_VERSION = "1.0.0"
OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY = "figured_width_owner_approved_height_area"

_OWNER_BASIS = "owner_approved_second_axis"
_EPS = 1e-6

REASON_OWNER_BASIS_NOT_PUBLISHED = "owner_basis_quantity_not_published"
REASON_SHADOW_NOT_REVIEWABLE = "shadow_quantity_not_review_shadow"
REASON_APPROVAL_ABSENT = "owner_approval_absent"
REASON_APPROVAL_CONFLICT = "owner_approval_conflict"
REASON_APPROVAL_INVALID = "owner_approval_invalid"
REASON_HEIGHT_MISMATCH = "owner_approved_height_mismatch"
REASON_HEIGHT_OUT_OF_BOUNDS = "approved_height_outside_opening_bounds"
REASON_TRACE_NOT_EXACT = "canonical_trace_not_exact"
REASON_NOT_PROJECTABLE = "review_row_not_projectable"


@dataclass(frozen=True)
class OwnerApprovedDoorReviewCandidate:
    shadow_quantity_id: str
    promoted_quantity: QuantityEvidence
    source_trace: CommercialTakeoffSourceTrace
    measurement_authority: CommercialMeasurementAuthority
    review_row: Mapping[str, object]


@dataclass(frozen=True)
class OwnerApprovedDoorReviewWithheld:
    canonical_opening_id: str
    reason_code: str


@dataclass(frozen=True)
class OwnerApprovedDoorReviewCollection:
    candidates: tuple[OwnerApprovedDoorReviewCandidate, ...]
    withheld: tuple[OwnerApprovedDoorReviewWithheld, ...]
    schema_version: str = OWNER_DOOR_REVIEW_PROMOTION_SCHEMA_VERSION


def _clean_id(value: object) -> str:
    return value.strip() if type(value) is str else ""


def _validated_scope(workspace_id: object, project_id: object) -> tuple[int, str]:
    if type(workspace_id) is not int:
        raise TypeError("workspace_id must be an int")
    if workspace_id <= 0:
        raise ValueError("workspace_id must be positive")
    if type(project_id) is not str:
        raise TypeError("project_id must be a str")
    if not project_id.strip() or project_id != project_id.strip():
        raise ValueError("project_id must be non-empty and canonical")
    return workspace_id, project_id


def _targeted_approvals(
    approvals: Sequence[MeasurementRecord], physical_opening_id: str
) -> dict[str, MeasurementRecord]:
    """Approvals aimed at one opening, keyed by their recomputed id. Identical records collapse to one."""
    targeted: dict[str, MeasurementRecord] = {}
    for approval in approvals:
        if approval.geometry_ref == physical_opening_id:
            targeted.setdefault(owner_height_approval_id(approval), approval)
    return targeted


def _candidate_or_reason(
    *,
    shadow: QuantityEvidence,
    opening: LiveCanonicalOpeningObject,
    approvals: Sequence[MeasurementRecord],
    workspace_id: int,
    project_id: str,
) -> OwnerApprovedDoorReviewCandidate | str:
    metadata = shadow.metadata if isinstance(shadow.metadata, Mapping) else {}
    if (
        shadow.family != "opening_area"
        or shadow.abstained
        or shadow.value is None
        or shadow.status != "review_required"
        or shadow.authority != LIVE_OPENING_OWNER_APPROVED_SECOND_AXIS_AREA_QUANTITY_AUTHORITY
        or shadow.blocking_reasons
        or metadata.get("shadow_only") is not True
        or metadata.get("commercial_projection_allowed") is not False
        or metadata.get("area_basis") != _OWNER_BASIS
        or metadata.get("second_axis_basis") != "user_approved"
        or metadata.get("opening_kind") != "door"
        or shadow.input_entity_ids != (opening.canonical_opening_id,)
    ):
        return REASON_SHADOW_NOT_REVIEWABLE

    approval_id = _clean_id(opening.owner_approved_second_axis_record_id)
    label_id = _clean_id(opening.figured_area_record_id)
    if not approval_id or not label_id:
        return REASON_SHADOW_NOT_REVIEWABLE

    targeted = _targeted_approvals(approvals, opening.physical_opening_id)
    if len(targeted) > 1:
        return REASON_APPROVAL_CONFLICT
    approval = targeted.get(approval_id)
    if approval is None:
        return REASON_APPROVAL_ABSENT
    if owner_approval_issues(
        approval, page_id=str(opening.page_id), source_sha256=str(opening.source_sha256)
    ):
        return REASON_APPROVAL_INVALID
    height = float(approval.value)
    if not (_MIN_OPENING_DIMENSION_MM <= height <= _MAX_OPENING_DIMENSION_MM):
        return REASON_HEIGHT_OUT_OF_BOUNDS
    retained_height = opening.owner_approved_height_mm
    if (
        type(retained_height) not in (int, float)
        or not math.isfinite(retained_height)
        or abs(float(retained_height) - height) > _EPS
    ):
        return REASON_HEIGHT_MISMATCH

    evidence_ids = tuple(dict.fromkeys(_clean_id(v) for v in opening.evidence_ids if _clean_id(v)))
    viewport_id = _clean_id(opening.viewport_id)
    if (
        not viewport_id
        or not set(shadow.evidence_ids) <= set(evidence_ids)
        or approval_id not in shadow.evidence_ids
        or label_id not in shadow.evidence_ids
        or opening.physical_opening_id != opening.canonical_opening_id
    ):
        return REASON_TRACE_NOT_EXACT

    approved_by = str(approval.approved_by).strip()
    approved_at = str(approval.approved_at).strip()
    promoted_metadata = dict(metadata)
    promoted_metadata.update(
        {
            "shadow_only": False,
            "commercial_projection_allowed": True,
            "commercial_review_required": True,
            "owner_approved_door_review_promotion": True,
            "promotion_parent_quantity_id": shadow.quantity_id,
            "owner_approved_second_axis_record_id": approval_id,
            "owner_approved_by": approved_by,
            "owner_approved_at": approved_at,
            "label_evidence_id": label_id,
        }
    )
    promotion_payload = {
        "family": shadow.family,
        "semantic_key": shadow.semantic_key,
        "parent_quantity_id": shadow.quantity_id,
        "owner_approval_id": approval_id,
        "owner_approved_by": approved_by,
        "owner_approved_at": approved_at,
        "label_evidence_id": label_id,
        "authority": OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY,
        "source_sha256": opening.source_sha256,
        "revision_id": opening.revision_id,
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
        authority=OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY,
        # Review eligibility only. The height is an owner assumption, never a measurement.
        status="review_required",
        confidence=float(shadow.confidence),
        abstained=False,
        blocking_reasons=(),
        reason_codes=tuple(
            dict.fromkeys(
                (
                    *shadow.reason_codes,
                    "owner_approved_second_axis_is_an_assumption",
                    "owner_approved_door_review_eligible",
                    "estimator_review_required",
                )
            )
        ),
        metadata=promoted_metadata,
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id,
        project_id=project_id,
        document_id=opening.document_id,
        source_sha256=opening.source_sha256,
        source_page=opening.page_id,
        viewport_id=viewport_id,
        revision_id=opening.revision_id,
        current_revision_id=opening.revision_id,
        evidence_ids=evidence_ids,
        canonical_entity_ids=(opening.canonical_opening_id,),
        metadata={
            "owner_approved_door_review_promotion": True,
            "promotion_parent_quantity_id": shadow.quantity_id,
            "area_basis": _OWNER_BASIS,
            "opening_kind": "door",
            "host_wall_id": opening.host_wall_id,
        },
    )
    measurement = CommercialMeasurementAuthority(
        method="figured_dimension",
        figured_dimension_ids=(label_id,),
        metadata={
            "owner_approved_door_review_promotion": True,
            "printed_axis": "width",
            "owner_approved_axis": "height",
            "owner_approval_id": approval_id,
        },
    )
    try:
        row = quantity_evidence_to_takeoff_output_row(promoted, trace=trace, authority=measurement)
    except Exception:  # noqa: BLE001  - a row the adapter refuses is withheld, never forced through
        return REASON_NOT_PROJECTABLE
    if row is None:
        return REASON_NOT_PROJECTABLE
    gates = existing_commercial_gate_results(row)
    if any(result[0] for result in gates.values()):
        raise RuntimeError(
            "owner-approved door review promotion bypassed an existing commercial review gate"
        )
    return OwnerApprovedDoorReviewCandidate(
        shadow_quantity_id=shadow.quantity_id,
        promoted_quantity=promoted,
        source_trace=trace,
        measurement_authority=measurement,
        review_row=row,
    )


def build_owner_approved_door_review_candidates(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    approvals: Sequence[MeasurementRecord],
    workspace_id: int,
    project_id: str,
) -> OwnerApprovedDoorReviewCollection:
    """Promote owner-approved door shadow areas to estimator-review candidates; everything unproven is withheld with a reason."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if not isinstance(approvals, (list, tuple)) or any(
        type(item) is not MeasurementRecord for item in approvals
    ):
        raise TypeError("approvals must be a list or tuple of MeasurementRecord")
    workspace_id, project_id = _validated_scope(workspace_id, project_id)

    # Republishing validates the whole canonical inventory (foreign snapshots, duplicate identities) before anything is narrowed.
    published = publish_live_opening_area_quantities(composition)
    shadow_by_entity: dict[str, QuantityEvidence] = {}
    for quantity in published:
        if len(quantity.input_entity_ids) == 1:
            shadow_by_entity.setdefault(quantity.input_entity_ids[0], quantity)

    candidates: list[OwnerApprovedDoorReviewCandidate] = []
    withheld: list[OwnerApprovedDoorReviewWithheld] = []
    for opening in composition.canonical_openings:
        if opening.area_basis != _OWNER_BASIS:
            continue
        shadow = shadow_by_entity.get(opening.canonical_opening_id)
        if shadow is None:
            withheld.append(
                OwnerApprovedDoorReviewWithheld(opening.canonical_opening_id, REASON_OWNER_BASIS_NOT_PUBLISHED)
            )
            continue
        outcome = _candidate_or_reason(
            shadow=shadow, opening=opening, approvals=approvals,
            workspace_id=workspace_id, project_id=project_id,
        )
        if isinstance(outcome, str):
            withheld.append(OwnerApprovedDoorReviewWithheld(opening.canonical_opening_id, outcome))
        else:
            candidates.append(outcome)

    return OwnerApprovedDoorReviewCollection(
        candidates=tuple(sorted(candidates, key=lambda item: item.promoted_quantity.quantity_id)),
        withheld=tuple(sorted(withheld, key=lambda item: (item.canonical_opening_id, item.reason_code))),
    )


def _validated_candidates(
    candidates: Sequence[OwnerApprovedDoorReviewCandidate],
) -> tuple[OwnerApprovedDoorReviewCandidate, ...]:
    out: list[OwnerApprovedDoorReviewCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, OwnerApprovedDoorReviewCandidate):
            raise TypeError("candidates must contain only OwnerApprovedDoorReviewCandidate records")
        quantity = candidate.promoted_quantity
        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        row = dict(candidate.review_row)
        quantity_id = str(quantity.quantity_id).strip()
        if (
            quantity.family != "opening_area"
            or quantity.abstained
            or quantity.value is None
            or quantity.status != "review_required"
            or quantity.authority != OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY
            or metadata.get("owner_approved_door_review_promotion") is not True
            or metadata.get("area_basis") != _OWNER_BASIS
            or metadata.get("shadow_only") is not False
            or metadata.get("commercial_projection_allowed") is not True
            or metadata.get("commercial_review_required") is not True
            or not quantity_id
        ):
            raise SourceClosedRunConflictError(
                f"door quantity did not pass the owner-approved review-promotion boundary: {quantity_id}"
            )
        if (
            row.get("quantity_id") != quantity.quantity_id
            or row.get("origin") != "AI"
            or row.get("quantity_status") != "To review"
            or type(row.get("quantity")) not in (int, float)
            or float(row["quantity"]) != float(quantity.value)
        ):
            raise SourceClosedRunConflictError(
                f"door review row bypassed estimator review state or disagrees with its quantity: {quantity_id}"
            )
        if any(result[0] for result in existing_commercial_gate_results(row).values()):
            raise SourceClosedRunConflictError(
                f"unreviewed door quantity is commercially authorised: {quantity_id}"
            )
        if candidate.source_trace.project_id != row.get("project_id") or (
            candidate.source_trace.workspace_id != row.get("workspace_id")
        ):
            raise SourceClosedRunConflictError(f"door source trace disagrees with its review row: {quantity_id}")
        if quantity_id in seen:
            raise SourceClosedRunConflictError(f"duplicate door review quantity id: {quantity_id}")
        seen.add(quantity_id)
        out.append(candidate)
    if not out:
        raise SourceClosedRunConflictError("no promoted door review quantities are available to seal")
    return tuple(sorted(out, key=lambda item: item.promoted_quantity.quantity_id))


def seal_owner_approved_door_review_run(
    candidates: Sequence[OwnerApprovedDoorReviewCandidate],
    *,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal already-promoted door review quantities with their exact source traces (review lineage, not firm)."""
    validated = _validated_candidates(candidates)
    return seal_source_closed_run(
        tuple(item.promoted_quantity for item in validated),
        project_id=project_id,
        traces_by_quantity_id={item.promoted_quantity.quantity_id: item.source_trace for item in validated},
    )


__all__ = [
    "OWNER_DOOR_REVIEW_QUANTITY_AUTHORITY",
    "OwnerApprovedDoorReviewCandidate",
    "OwnerApprovedDoorReviewCollection",
    "OwnerApprovedDoorReviewWithheld",
    "build_owner_approved_door_review_candidates",
    "seal_owner_approved_door_review_run",
]
