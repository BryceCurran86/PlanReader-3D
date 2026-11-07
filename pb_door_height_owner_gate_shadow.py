"""Mission item 12 — door height owner gate (never invents a second axis).

Typical / assumed / default heights (including 2100 mm) are not evidence.
Only an owned figured height atom or USER_APPROVED height may clear the gate
into review; this module never publishes measurement.
"""
from __future__ import annotations

from typing import Any, Sequence

# Explicit denylist for convention values Cursor must never invent as height.
_FORBIDDEN_INVENTED_HEIGHT_MM = frozenset({2100.0, 2040.0, 1980.0, 2400.0})


def assess_door_height_owner_gate_shadow(
    *,
    physical_opening_id: str,
    owned_height_evidence_ids: Sequence[str] = (),
    owned_height_mm: float | None = None,
    user_approved_height: bool = False,
    label_width_only_mm: float | None = None,
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    height_ids = tuple(str(e).strip() for e in owned_height_evidence_ids if str(e).strip())
    height = None
    if owned_height_mm is not None:
        try:
            height = float(owned_height_mm)
        except (TypeError, ValueError):
            raise ValueError("owned_height_mm must be numeric when provided") from None
        if height != height or height <= 0:  # NaN / non-positive
            raise ValueError("owned_height_mm must be a positive finite value")
    # Owner approval or owned figured atom may enter review; bare convention
    # numerics (including common door heights) never clear the gate alone.
    if user_approved_height and height is not None:
        gate = "door_height_user_approved_review_only"
        height_for_report = height
        used_convention = False
    elif height_ids and height is not None:
        gate = "door_height_owned_figured_review_only"
        height_for_report = height
        used_convention = False
    elif height_ids and height is None:
        gate = "door_height_evidence_without_resolved_value"
        height_for_report = None
        used_convention = False
    elif height is not None and not height_ids:
        gate = "door_height_unproven_no_owned_atom"
        height_for_report = None
        used_convention = height in _FORBIDDEN_INVENTED_HEIGHT_MM
    else:
        gate = "door_height_second_axis_unavailable"
        height_for_report = None
        used_convention = False
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "owned_height_evidence_ids": list(height_ids),
        "owned_height_mm": height_for_report,
        "label_width_only_mm": (
            float(label_width_only_mm) if label_width_only_mm is not None else None
        ),
        "user_approved_height": bool(user_approved_height),
        "invented_second_axis_mm": None,
        "used_typical_door_height_convention": used_convention,
        "measurement_published": False,
        "shadow_only": True,
    }


# ---------------------------------------------------------------------------
# Owner-approved second axis for a door that prints exactly ONE figure
# ---------------------------------------------------------------------------
#
# The owner may approve a documented door height for a named scope (see
# docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md s4). That
# approval is an ASSUMPTION the owner supplies, not a measurement: it is never
# FIRM, never a default in code, and it exists only as an explicit
# ``MeasurementRecord`` bound to one proven physical opening. This function is a
# review-only shadow: it publishes nothing and changes no quantity.

_OWNER_AREA_REVIEW_GATE = "owner_approved_door_area_review_only"


def _owner_area_result(record_id: str, gate: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "physical_opening_id": record_id,
        "first_remaining_gate": gate,
        "width_mm": None,
        "height_mm": None,
        "area_m2": None,
        "second_axis_basis": None,
        "approval_id": None,
        "approved_by": None,
        "label_evidence_id": None,
        "invalid_reasons": [],
        "used_typical_door_height_convention": False,
        "measurement_published": False,
        "shadow_only": True,
    }
    result.update(extra)
    return result


def _is_real_number(value: object) -> bool:
    import math

    return (
        type(value) in (int, float)
        and math.isfinite(value)  # type: ignore[arg-type]
        and value > 0  # type: ignore[operator]
    )


def _owner_approval_issues(
    approval: Any, *, page_id: str, source_sha256: str,
) -> list[str]:
    """Why an approval cannot stand as the owner's record for this opening."""
    from datetime import datetime

    from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType

    issues: list[str] = []
    if approval.source_type != MeasurementAuthorityType.USER_APPROVED.value:
        issues.append("approval_source_type_not_user_approved")
    if approval.authority_status != AuthorityStatus.USER_APPROVED.value:
        issues.append("approval_authority_status_not_user_approved")
    if type(approval.approved_by) is not str or not approval.approved_by.strip():
        issues.append("approval_named_approver_missing")
    stamp = None
    if type(approval.approved_at) is str:
        try:
            stamp = datetime.fromisoformat(approval.approved_at)
        except ValueError:
            stamp = None
    if stamp is None or stamp.tzinfo is None or stamp.utcoffset() is None:
        issues.append("approval_timezone_aware_date_missing")
    if approval.unit != "mm":
        issues.append("approval_unit_not_mm")
    if not _is_real_number(approval.value):
        issues.append("approval_value_not_finite_positive")
    if type(approval.page) is not int or str(approval.page) != str(page_id):
        issues.append("approval_page_mismatch")
    metadata = approval.metadata if isinstance(approval.metadata, dict) else {}
    if metadata.get("second_axis") != "height":
        issues.append("approval_second_axis_not_height")
    if metadata.get("single_figure_axis") != "width":
        issues.append("approval_single_figure_axis_not_width")
    if metadata.get("source_sha256") != source_sha256:
        issues.append("approval_source_sha256_mismatch")
    return issues


def owner_height_approval_id(approval: Any) -> str:
    """Deterministic identity of one owner height approval record (the id the canonical opening retains)."""
    from dataclasses import asdict

    from pb_migration_contracts import stable_contract_id

    return stable_contract_id("opening_owner_height_approval", asdict(approval), digest_chars=32)


# Public name for the same check, so a later promotion step re-verifies approvals with the identical rule.
owner_approval_issues = _owner_approval_issues


def assess_owner_approved_door_area_shadow(
    *,
    existence_record: Any,
    label_result: Any,
    approvals: Sequence[Any],
) -> dict[str, Any]:
    """Combine ONE printed door figure with the owner's approved height (review only).

    Every input is a sealed record: the opening's existence record, the label
    authority's result for that same opening, and explicit ``MeasurementRecord``
    approvals. Nothing is read from geometry, scale, a swing radius, a default or
    a caller-supplied area. A two-figure label always keeps its own path; the
    approval is ignored there so existing signed areas cannot change.
    """
    import math

    from pb_geometry_takeoff_model import MeasurementRecord
    from pb_migration_contracts import EvidenceResolutionStatus
    from pb_opening_label_dimension_authority import (
        _MAX_OPENING_DIMENSION_MM,
        _MIN_OPENING_DIMENSION_MM,
        OpeningLabelDimensionResult,
    )
    from pb_physical_opening_authority import (
        PHYSICAL_OPENING_EXISTS,
        PhysicalOpeningExistenceRecord,
    )

    if type(existence_record) is not PhysicalOpeningExistenceRecord:
        raise TypeError("existence_record must be PhysicalOpeningExistenceRecord")
    if type(label_result) is not OpeningLabelDimensionResult:
        raise TypeError("label_result must be OpeningLabelDimensionResult")
    if not isinstance(approvals, (list, tuple)):
        raise TypeError("approvals must be a list or tuple of MeasurementRecord")
    if any(type(item) is not MeasurementRecord for item in approvals):
        raise TypeError("every approval must be a MeasurementRecord")

    record_id = str(existence_record.record_id)
    if (
        existence_record.status is not EvidenceResolutionStatus.CORROBORATED
        or existence_record.proposition != PHYSICAL_OPENING_EXISTS
    ):
        return _owner_area_result(record_id, "physical_opening_not_proven")

    evidence = label_result.evidence
    if label_result.status is not EvidenceResolutionStatus.CORROBORATED or evidence is None:
        return _owner_area_result(record_id, "label_dimension_not_corroborated")
    label_id = str(evidence.evidence_id)
    if (
        evidence.opening_record_id != record_id
        or str(evidence.page_id) != str(existence_record.page_id)
    ):
        return _owner_area_result(record_id, "label_not_bound_to_opening")

    figures = tuple(evidence.dimension_values_mm)
    if len(figures) == 2:
        return _owner_area_result(
            record_id, "printed_second_axis_present", label_evidence_id=label_id)
    if len(figures) != 1:
        return _owner_area_result(
            record_id, "single_figure_not_available", label_evidence_id=label_id)
    if evidence.semantic_kind != "door":
        return _owner_area_result(
            record_id, "opening_kind_not_door_authenticated", label_evidence_id=label_id)
    width = figures[0]
    if (
        not _is_real_number(width)
        or not (_MIN_OPENING_DIMENSION_MM <= width <= _MAX_OPENING_DIMENSION_MM)
        or evidence.area_m2 is not None
    ):
        return _owner_area_result(
            record_id, "printed_figure_invalid", label_evidence_id=label_id)

    targeted: dict[str, Any] = {}
    for approval in approvals:
        if approval.geometry_ref == record_id:
            targeted.setdefault(owner_height_approval_id(approval), approval)
    if not targeted:
        return _owner_area_result(
            record_id, "owner_approval_absent", label_evidence_id=label_id)
    if len(targeted) > 1:
        return _owner_area_result(
            record_id, "owner_approval_conflict", label_evidence_id=label_id)

    (approval_id, approval), = targeted.items()
    issues = _owner_approval_issues(
        approval, page_id=str(existence_record.page_id),
        source_sha256=str(existence_record.source_sha256))
    if issues:
        return _owner_area_result(
            record_id, "owner_approval_invalid", label_evidence_id=label_id,
            approval_id=approval_id, invalid_reasons=issues)
    height = float(approval.value)
    if not (_MIN_OPENING_DIMENSION_MM <= height <= _MAX_OPENING_DIMENSION_MM):
        return _owner_area_result(
            record_id, "approved_height_outside_opening_bounds",
            label_evidence_id=label_id, approval_id=approval_id)
    area = float(width) * height / 1_000_000.0
    if not math.isfinite(area) or area <= 0.0:
        return _owner_area_result(
            record_id, "printed_figure_invalid", label_evidence_id=label_id)
    return _owner_area_result(
        record_id, _OWNER_AREA_REVIEW_GATE,
        width_mm=float(width), height_mm=height, area_m2=area,
        second_axis_basis="user_approved", approval_id=approval_id,
        approved_by=str(approval.approved_by), label_evidence_id=label_id)
