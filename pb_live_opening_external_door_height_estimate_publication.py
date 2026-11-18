"""Apply the owner 2100 mm external-door height estimate after wall roles exist.

An authenticated door hosted on a unique EXTERNAL whole-wall may receive a
labelled provisional area when the plans print one width and no height. This
does not mint FIRM source measurement, invent a host/frame/kind/width, or
grant a frozen120 score.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import math
import re
from typing import Mapping

from pb_external_door_height_estimate_policy import (
    OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM,
    OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS,
    OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL,
    resolve_external_door_height_estimate,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_live_whole_wall_role_composition import LiveWholeWallRoleComposition
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification

_NON_PERSONNEL_DOOR_RE = re.compile(
    r"\b(?:garage|overhead|roller|joinery|panel\s*lift)\b",
    re.IGNORECASE,
)


def _positive_mm(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def _clean(value: object) -> str:
    return str(value).strip() if type(value) is str else ""


def _provenance_ids(*values: object) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in values
                if value is not None and str(value).strip()
            }
        )
    )


def _blocked_non_personnel_door(opening: LiveCanonicalOpeningObject) -> bool:
    blob = " ".join(
        part
        for part in (
            str(opening.schedule_row_description or ""),
            str(opening.type_mark or ""),
        )
        if part
    )
    return bool(_NON_PERSONNEL_DOOR_RE.search(blob))


def _external_wall_role_record_ids(
    whole_wall_role_composition: LiveWholeWallRoleComposition,
) -> tuple[Mapping[tuple[str, str], str], frozenset[tuple[str, str]]]:
    """Index source-verified external roles by their actual sheet and wall.

    A conflicting, duplicated or unresolved role for the same physical wall
    poisons that wall, even if another trace claims EXTERNAL. No source record
    may authenticate two distinct wall identities on the same sheet.
    """
    mapping: dict[tuple[str, str], str] = {}
    blocked: set[tuple[str, str]] = set()
    for trace in whole_wall_role_composition.traces:
        wall_id, page_id = _clean(trace.physical_wall_id), _clean(trace.page_id)
        if not wall_id or not page_id:
            continue
        key = (page_id, wall_id)
        record_id = _clean(trace.record_id)
        positive = (
            bool(record_id)
            and trace.role is WallRoleClassification.EXTERNAL
            and trace.status is EvidenceResolutionStatus.CORROBORATED
        )
        if key in blocked:
            continue
        if not positive or key in mapping:
            blocked.add(key)
            mapping.pop(key, None)
            continue
        mapping[key] = record_id

    # The producer must uniquely bind every role receipt to one source wall.
    owners: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for key, record_id in mapping.items():
        owners.setdefault((key[0], record_id), []).append(key)
    for shared in owners.values():
        if len(shared) > 1:
            for key in shared:
                blocked.add(key)
                mapping.pop(key, None)
    return mapping, frozenset(blocked)


def _schedule_height_kwargs(opening: LiveCanonicalOpeningObject) -> dict[str, object]:
    height = opening.schedule_declared_height_mm
    evidence = opening.schedule_binding_record_id
    evidence_id = _clean(evidence)
    claimed = height is not None or bool(evidence_id)
    if not claimed:
        return {}
    owned = _positive_mm(height) and bool(evidence_id)
    return {
        "schedule_height_mm": height if _positive_mm(height) else None,
        "schedule_height_evidence_id": evidence_id or None,
        "schedule_owned_to_opening": owned,
    }


def _estimate_area_m2(width_mm: float) -> float:
    return (
        float(width_mm) * float(OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM) / 1_000_000.0
    )


def _apply_one(
    opening: LiveCanonicalOpeningObject,
    *,
    external_wall_role_record_ids: Mapping[tuple[str, str], str],
    blocked_wall_role_keys: frozenset[tuple[str, str]],
) -> LiveCanonicalOpeningObject:
    if type(opening) is not LiveCanonicalOpeningObject:
        raise TypeError("opening must be LiveCanonicalOpeningObject")
    if opening.area_m2 is not None or opening.area_basis:
        return opening
    if (opening.owner_approved_second_axis_record_id
            or opening.owner_approved_width_mm is not None
            or opening.owner_approved_height_mm is not None
            or opening.external_wall_role_record_id):
        return opening
    if opening.geometry_complete and opening.height_m is None:
        return opening
    if not (_clean(opening.host_binding_record_id)
            or _clean(opening.host_frame_record_id)):
        return opening
    if str(opening.opening_kind or "").strip().lower() != "door":
        return opening
    if opening.height_m is not None:
        return opening
    if _blocked_non_personnel_door(opening):
        return opening
    page_id = _clean(opening.page_id)
    host_wall_id = _clean(opening.host_wall_id)
    framed_wall_id = _clean(opening.wall_local_frame_id)
    keys = tuple(
        (page_id, value)
        for value in dict.fromkeys((host_wall_id, framed_wall_id))
        if value
    )
    if not page_id or any(key in blocked_wall_role_keys for key in keys):
        return opening
    matched_role_ids = {
        _clean(external_wall_role_record_ids.get(key))
        for key in keys
        if _clean(external_wall_role_record_ids.get(key))
    }
    if len(matched_role_ids) != 1:
        return opening
    role_record_id = next(iter(matched_role_ids))
    width_mm = opening.figured_single_axis_mm
    if not _positive_mm(width_mm):
        return opening
    # An independently printed schedule width that contradicts the plan's
    # single-figure width cannot be hidden by the assumed height.
    if (opening.schedule_declared_width_mm is not None
            and (not _positive_mm(opening.schedule_declared_width_mm)
                 or not math.isclose(
                     float(opening.schedule_declared_width_mm),
                     float(width_mm), rel_tol=0.0, abs_tol=1e-6,
                 ))):
        return opening
    if opening.width_m is not None:
        if not _positive_mm(opening.width_m):
            return opening
        if not math.isclose(
            float(opening.width_m) * 1000.0, float(width_mm),
            rel_tol=0.0, abs_tol=1e-6,
        ):
            return opening
    label_record_id = _clean(opening.figured_area_record_id)
    if not label_record_id:
        return opening

    estimate = resolve_external_door_height_estimate(
        opening_id=opening.canonical_opening_id,
        external_door_authenticated=True,
        external_door_identity_evidence_id=role_record_id,
        **_schedule_height_kwargs(opening),
    )
    if (
        not estimate.assumption_used
        or not estimate.can_issue_labelled_provisional_customer
        or estimate.height_mm != OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM
        or estimate.basis != OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
        or estimate.can_issue_firm_quantity
        or estimate.benchmark_score_granted
    ):
        return opening
    area_m2 = _estimate_area_m2(float(width_mm))
    if not math.isfinite(area_m2) or area_m2 <= 0.0:
        return opening
    return replace(
        opening,
        area_m2=area_m2,
        area_basis=OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS,
        external_wall_role_record_id=role_record_id,
        evidence_ids=_provenance_ids(
            *opening.evidence_ids,
            role_record_id,
            label_record_id,
        ),
    )


def apply_live_external_door_height_estimates(
    *,
    composition: LivePhysicalOpeningVoidComposition,
    whole_wall_role_composition: LiveWholeWallRoleComposition,
) -> LivePhysicalOpeningVoidComposition:
    """Stamp labelled 2100 mm provisional areas onto qualifying external doors."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if type(whole_wall_role_composition) is not LiveWholeWallRoleComposition:
        raise TypeError(
            "whole_wall_role_composition must be LiveWholeWallRoleComposition"
        )

    if whole_wall_role_composition.revision_id != composition.revision_id:
        return composition
    external_ids, blocked_keys = _external_wall_role_record_ids(
        whole_wall_role_composition
    )
    if not external_ids:
        return composition

    # A duplicated canonical or physical opening would otherwise be counted
    # twice when the same provisional area is projected into customer rows.
    canonical_counts = Counter(
        opening.canonical_opening_id for opening in composition.canonical_openings
    )
    physical_counts = Counter(
        opening.physical_opening_id for opening in composition.canonical_openings
    )
    updated = tuple(
        opening if (
            not _clean(opening.canonical_opening_id)
            or not _clean(opening.physical_opening_id)
            or canonical_counts[opening.canonical_opening_id] != 1
            or physical_counts[opening.physical_opening_id] != 1
            or opening.revision_id != composition.revision_id
        ) else _apply_one(
            opening,
            external_wall_role_record_ids=external_ids,
            blocked_wall_role_keys=blocked_keys,
        )
        for opening in composition.canonical_openings
    )
    if updated == composition.canonical_openings:
        return composition
    return replace(composition, canonical_openings=updated)


__all__ = [
    "OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL",
    "apply_live_external_door_height_estimates",
]
