"""Classify whether a sealed extra can increment an exact-project match count.

OBSERVED: the original-source floor replay writes an empty identity map and
asserts zero matches with three unmapped extras. Floor-area extras do not
bind to a door/window denominator. INFERENCE: adding another room floor
increments extras, not matches, until a reviewed binding exists.
PROPOSED: report join readiness only. BENCHMARK object names, expected
areas, and project IDs must not enter this classifier.

This module does not publish a quantity, edit identity maps, or call
live wall authority. Detection is not measurement authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def classify_produced_item_join_readiness(
    *,
    produced_family: str,
    produced_object_refs: Sequence[str],
    denominator_families: Sequence[str],
    identity_bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return why one sealed item can or cannot increment matched_within_tolerance.

    Callers supply the sealed family, its object refs, the denominator's
    families, and any reviewed bindings. Empty or malformed inputs fail
    closed. A family that the denominator does not score stays an extra.
    """
    family = str(produced_family or "").strip()
    refs = tuple(str(ref).strip() for ref in produced_object_refs if str(ref).strip())
    scored = {str(item).strip() for item in denominator_families if str(item).strip()}
    if not family or not refs or not scored:
        return {
            "join_status": "inputs_unusable",
            "would_increment_matched_within_tolerance": False,
            "would_increment_unsupported_extra": False,
            "quantity_or_metric_area_published": False,
            "diagnostic_only": True,
        }
    if family not in scored:
        return {
            "join_status": "family_mismatch_increments_extras_not_matches",
            "would_increment_matched_within_tolerance": False,
            "would_increment_unsupported_extra": True,
            "quantity_or_metric_area_published": False,
            "diagnostic_only": True,
        }
    bound_refs = set()
    bound_families = set()
    for binding in identity_bindings:
        if not isinstance(binding, Mapping):
            continue
        bound_family = str(binding.get("production_family") or "").strip()
        bound = binding.get("production_object_identity_refs") or ()
        if not isinstance(bound, (tuple, list)):
            continue
        for ref in bound:
            text = str(ref).strip()
            if text:
                bound_refs.add(text)
                if bound_family:
                    bound_families.add(bound_family)
    if not bound_refs:
        return {
            "join_status": "empty_identity_map_pins_zero_matches",
            "would_increment_matched_within_tolerance": False,
            "would_increment_unsupported_extra": True,
            "quantity_or_metric_area_published": False,
            "diagnostic_only": True,
        }
    if family not in bound_families or not bound_refs.intersection(refs):
        return {
            "join_status": "unmapped_extra_awaits_reviewed_binding",
            "would_increment_matched_within_tolerance": False,
            "would_increment_unsupported_extra": True,
            "quantity_or_metric_area_published": False,
            "diagnostic_only": True,
        }
    return {
        "join_status": "reviewed_binding_present_evaluator_owns_match",
        "would_increment_matched_within_tolerance": True,
        "would_increment_unsupported_extra": False,
        "quantity_or_metric_area_published": False,
        "diagnostic_only": True,
    }
