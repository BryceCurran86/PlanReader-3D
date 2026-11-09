"""Owner policy: external doors use a *provisional* 2100 mm height when unstated.

This is an estimating decision, NOT source measurement authority. It cannot
issue a FIRM QuantityEvidence, a source-closed customer row or benchmark score.
The original producer still authenticates each physical door, width, host,
frame, schedule/elevation evidence and every downstream commercial permission.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM = 2100
OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS = (
    "assumed_external_door_height_2100_mm_owner_policy"
)


@dataclass(frozen=True)
class ExternalDoorHeightEstimate:
    """Read-only height input for a clearly labelled *review* estimate."""

    opening_id: str
    height_mm: float | None
    basis: str
    reason_code: str
    source_evidence_ids: tuple[str, ...]
    source_authenticated_height: bool
    assumption_used: bool
    verify_on_site: bool
    commercial_review_required: bool = True
    can_issue_firm_quantity: bool = False
    can_seal_source_closed_customer: bool = False
    benchmark_score_granted: bool = False


def _positive_height(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _blocked(opening_id: str, reason: str) -> ExternalDoorHeightEstimate:
    return ExternalDoorHeightEstimate(
        opening_id, None, "unresolved_external_door_height", reason,
        (), False, False, True,
    )


def resolve_external_door_height_estimate(
    *,
    opening_id: str,
    external_door_authenticated: bool,
    external_door_identity_evidence_id: str | None,
    schedule_height_mm: float | None = None,
    schedule_height_evidence_id: str | None = None,
    schedule_owned_to_opening: bool = False,
    elevation_height_mm: float | None = None,
    elevation_height_evidence_id: str | None = None,
    elevation_owned_to_opening: bool = False,
    specific_exception_noted: bool = False,
) -> ExternalDoorHeightEstimate:
    """Schedule > elevation > 2100 mm assumption, for proven external doors.

    A printed height only counts as a source height when its source-owned
    evidence and *this opening's* unique association are positively supplied.
    Unsupported or conflicting claims block fallback rather than being silently
    ignored. A specific undimensioned exception also blocks defaulting.
    All results are review inputs, never FIRM/customer/sealed outputs by
    themselves. No assumption applies to internal doors, windows or joinery.
    """
    if type(opening_id) is not str or not opening_id.strip():
        raise ValueError("physical opening identity required")
    if (type(external_door_authenticated) is not bool
            or type(schedule_owned_to_opening) is not bool
            or type(elevation_owned_to_opening) is not bool
            or type(specific_exception_noted) is not bool):
        raise TypeError("source ownership and exception flags must be booleans")
    opening_id = opening_id.strip()
    if (not external_door_authenticated
            or type(external_door_identity_evidence_id) is not str
            or not external_door_identity_evidence_id.strip()):
        return _blocked(opening_id, "external_door_identity_not_authenticated")

    def claimed(value: object, evidence: object, owned: bool) -> bool:
        return value is not None or evidence is not None or owned

    sched = claimed(schedule_height_mm, schedule_height_evidence_id, schedule_owned_to_opening)
    elev = claimed(elevation_height_mm, elevation_height_evidence_id, elevation_owned_to_opening)
    if sched and (
        not _positive_height(schedule_height_mm)
        or type(schedule_height_evidence_id) is not str
        or not schedule_height_evidence_id.strip()
        or not schedule_owned_to_opening
    ):
        return _blocked(opening_id, "specific_schedule_height_unverified")
    if elev and (
        not _positive_height(elevation_height_mm)
        or type(elevation_height_evidence_id) is not str
        or not elevation_height_evidence_id.strip()
        or not elevation_owned_to_opening
    ):
        return _blocked(opening_id, "specific_elevation_height_unverified")
    if sched and elev and not math.isclose(
        float(schedule_height_mm), float(elevation_height_mm),
        rel_tol=0, abs_tol=1e-6,
    ):
        return _blocked(opening_id, "schedule_elevation_height_conflict")

    if sched:
        ids = (
            (schedule_height_evidence_id.strip(), elevation_height_evidence_id.strip())
            if elev else (schedule_height_evidence_id.strip(),)
        )
        return ExternalDoorHeightEstimate(
            opening_id, float(schedule_height_mm), "authenticated_door_schedule",
            "specific_source_height_available", ids, True, False, False,
        )
    if elev:
        return ExternalDoorHeightEstimate(
            opening_id, float(elevation_height_mm), "authenticated_door_elevation",
            "specific_source_height_available",
            (elevation_height_evidence_id.strip(),), True, False, False,
        )
    if specific_exception_noted:
        return _blocked(opening_id, "specific_height_exception_unresolved")
    return ExternalDoorHeightEstimate(
        opening_id, float(OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM),
        OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS,
        "external_door_height_not_specified_owner_2100_assumption",
        (external_door_identity_evidence_id.strip(),),
        False, True, True,
    )
