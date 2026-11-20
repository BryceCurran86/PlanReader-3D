"""Count-only audit of the actual original opening-area issuer vetoes.

Does not discover openings, infer dimensions, alter source authority or score.
Only observes existing canonical physical objects and actual issued quantities.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Any, Iterable

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_migration_contracts import QuantityEvidence


REASON_CODES = (
    "foreign_or_malformed_opening_object",
    "canonical_physical_identity_missing_or_mismatch",
    "opening_kind_unresolved",
    "opening_host_wall_missing",
    "opening_host_binding_or_frame_missing",
    "positive_measured_area_missing",
    "opening_source_evidence_missing",
    "opening_host_receipt_not_in_source_evidence",
    "opening_measurement_basis_missing",
    "figured_area_receipt_missing",
    "geometry_axes_unproven",
    "schedule_or_elevation_metric_receipt_missing",
    "remaining_canonical_issuer_veto",
    "canonical_quantity_not_retained",
    "source_issued_and_retained",
)


def _positive_area(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _valid_identity(value: Any) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _first_observable_gate(opening: LiveCanonicalOpeningObject) -> str:
    if type(opening) is not LiveCanonicalOpeningObject:
        return "foreign_or_malformed_opening_object"
    if not (_valid_identity(opening.canonical_opening_id)
            and opening.canonical_opening_id == opening.physical_opening_id):
        return "canonical_physical_identity_missing_or_mismatch"
    if str(opening.opening_kind or "").strip().lower() not in ("window", "door"):
        return "opening_kind_unresolved"
    if not _valid_identity(opening.host_wall_id):
        return "opening_host_wall_missing"
    if not (opening.host_binding_record_id or opening.host_frame_record_id):
        return "opening_host_binding_or_frame_missing"
    if not _positive_area(opening.area_m2):
        return "positive_measured_area_missing"
    if (
        not isinstance(opening.evidence_ids, (tuple, list))
        or not opening.evidence_ids
        or not isinstance(opening.source_observation_ids, (tuple, list))
        or not opening.source_observation_ids
        or opening.representative_observation_id not in opening.evidence_ids
        or opening.representative_observation_id not in opening.source_observation_ids
    ):
        return "opening_source_evidence_missing"
    if any(
        receipt_id and receipt_id not in opening.evidence_ids
        for receipt_id in (opening.host_binding_record_id, opening.host_frame_record_id)
    ):
        return "opening_host_receipt_not_in_source_evidence"
    if not _valid_identity(opening.area_basis):
        return "opening_measurement_basis_missing"
    if opening.area_basis == "figured_opening_label":
        if not _valid_identity(opening.figured_area_record_id) or opening.figured_area_record_id not in opening.evidence_ids:
            return "figured_area_receipt_missing"
    elif opening.area_basis == "resolved_opening_geometry":
        if (
            opening.geometry_complete is not True
            or not _positive_area(opening.width_m)
            or not _positive_area(opening.height_m)
        ):
            return "geometry_axes_unproven"
    elif opening.area_basis in ("authenticated_elevation_frame", "authenticated_frame_schedule"):
        if (
            opening.area_basis == "authenticated_elevation_frame"
            and (not _valid_identity(opening.figured_area_record_id)
                 or opening.figured_area_record_id not in opening.evidence_ids)
        ):
            return "schedule_or_elevation_metric_receipt_missing"
        if (
            opening.area_basis == "authenticated_frame_schedule"
            and (not _valid_identity(opening.schedule_binding_record_id)
                 or opening.schedule_binding_record_id not in opening.evidence_ids)
        ):
            return "schedule_or_elevation_metric_receipt_missing"
    return "remaining_canonical_issuer_veto"



_INDEPENDENT_GATES = (
    "source_opening_kind_unproved",
    "source_physical_wall_host_unproved",
    "source_wall_host_receipt_unproved",
    "source_numeric_area_unproved",
    "source_metric_basis_unproved",
    "source_representative_observation_unproved",
)


def _independent_unproven_prerequisites(
    opening: LiveCanonicalOpeningObject,
) -> tuple[str, ...]:
    """Separate missing prerequisites; one first veto may conceal five more.

    These are *observations* about existing fields, not alternative
    assertions of a door/window, host, metric or commercial permission.
    A fully populated candidate may still fail the original publisher.
    """
    missing = []
    if str(opening.opening_kind or "").strip().lower() not in {"door", "window"}:
        missing.append("source_opening_kind_unproved")
    if not _valid_identity(opening.host_wall_id):
        missing.append("source_physical_wall_host_unproved")
    if not (
        _valid_identity(opening.host_binding_record_id)
        or _valid_identity(opening.host_frame_record_id)
    ):
        missing.append("source_wall_host_receipt_unproved")
    if not _positive_area(opening.area_m2):
        missing.append("source_numeric_area_unproved")
    if not _valid_identity(opening.area_basis):
        missing.append("source_metric_basis_unproved")
    if not (
        _valid_identity(opening.representative_observation_id)
        and opening.representative_observation_id in opening.source_observation_ids
        and opening.representative_observation_id in opening.evidence_ids
    ):
        missing.append("source_representative_observation_unproved")
    return tuple(missing)


def audit_original_opening_area_gates(
    canonical_openings: Iterable[LiveCanonicalOpeningObject],
    published_quantities: Iterable[QuantityEvidence],
) -> dict[str, Any]:
    """Observe original source issuer decisions without private entity IDs or metric values."""
    objects = tuple(canonical_openings)
    issued = tuple(published_quantities)
    retained = {}
    quantity_ids = set()
    for quantity in issued:
        if (
            type(quantity) is not QuantityEvidence
            or quantity.family != "opening_area"
            or len(quantity.input_entity_ids) != 1
            or not _valid_identity(quantity.input_entity_ids[0])
            or quantity.input_entity_ids[0] in retained
            or quantity.quantity_id in quantity_ids
        ):
            raise ValueError("original opening audit requires unique typed area publications")
        retained[quantity.input_entity_ids[0]] = quantity
        quantity_ids.add(quantity.quantity_id)
    seen = set()
    counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    basis_counts: Counter[str] = Counter()
    independent_gates: Counter[str] = Counter()
    independent_by_kind: dict[str, Counter[str]] = {
        "door": Counter(), "window": Counter(), "unresolved": Counter(),
    }
    first_gate_by_kind: dict[str, Counter[str]] = {
        "door": Counter(), "window": Counter(), "unresolved": Counter(),
    }
    # Never serialize arbitrary producer/customer text as a metric basis.
    known_bases = frozenset({
        "figured_opening_label", "resolved_opening_geometry",
        "authenticated_elevation_frame", "authenticated_frame_schedule",
        "owner_approved_second_axis", "assumed_external_door_height_2100_mm",
    })
    for opening in objects:
        if type(opening) is not LiveCanonicalOpeningObject:
            counts["foreign_or_malformed_opening_object"] += 1
            continue
        normalized_kind = str(opening.opening_kind or "").strip().lower()
        kind = normalized_kind if normalized_kind in ("door", "window") else "unresolved"
        kind_counts[kind] += 1
        for unresolved_gate in _independent_unproven_prerequisites(opening):
            independent_gates[unresolved_gate] += 1
            independent_by_kind[kind][unresolved_gate] += 1
        basis = opening.area_basis if opening.area_basis in known_bases else "unrecognized_or_missing"
        basis_counts[basis] += 1
        canonical_id = opening.canonical_opening_id
        if canonical_id in seen:
            raise ValueError("duplicate canonical source opening identities")
        seen.add(canonical_id)
        # The original canonical issuer, not this diagnostic, decides whether
        # a quantity is actually source-authorized.
        published = _opening_quantity(opening)
        if published is not None:
            reason = (
                "source_issued_and_retained"
                if canonical_id in retained and published.to_dict() == retained[canonical_id].to_dict()
                else "canonical_quantity_not_retained"
            )
        else:
            reason = _first_observable_gate(opening)
        counts[reason] += 1
        first_gate_by_kind[kind][reason] += 1
    if not set(retained) <= seen:
        raise ValueError("original opening audit found published area without canonical owner")
    if counts["source_issued_and_retained"] != len(issued):
        raise ValueError("original opening area receipt differs from canonical issuer audit")
    return {
        "status": "ORIGINAL_ISSUER_DIAGNOSTIC_ONLY",
        "measurement_authorized": False,
        "official_benchmark_scored": False,
        "source_opening_candidate_count": len(objects),
        "published_opening_area_count": len(issued),
        "observable_gate_counts": {
            name: counts[name] for name in REASON_CODES if counts[name]
        },
        "source_kind_counts": {
            kind: kind_counts[kind] for kind in ("window", "door", "unresolved")
            if kind_counts[kind]
        },
        "source_metric_basis_counts": {
            kind: basis_counts[kind] for kind in sorted(basis_counts)
        },
        "independent_prerequisites_unproved": {
            name: independent_gates[name] for name in _INDEPENDENT_GATES
            if independent_gates[name]
        },
        "independent_prerequisites_by_kind": {
            kind: {
                name: independent_by_kind[kind][name] for name in _INDEPENDENT_GATES
                if independent_by_kind[kind][name]
            }
            for kind in ("window", "door", "unresolved") if kind_counts[kind]
        },
        "first_gate_by_opening_kind": {
            kind: {
                name: first_gate_by_kind[kind][name] for name in REASON_CODES
                if first_gate_by_kind[kind][name]
            }
            for kind in ("window", "door", "unresolved") if kind_counts[kind]
        },
    }
