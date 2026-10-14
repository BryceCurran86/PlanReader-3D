"""Read-only figured-dimension scale CONSISTENCY, never scale authority.

Each input row is emitted only after the existing producer has attempted one
original-source native-text-and-vector WITNESS-bound orthogonal pair. The
pair may fail local *room* intersection while still supporting a source
diagnosis that the drawing's original dimension systems use consistent
physical-to-PDF ratios.

No quantity, verified page scale, area, canonical floor association, ruler,
commercial approval or benchmark identity can be returned from this module.
The separate PhysicalScaleProducer and cross-view figured-dimension binding
remain the only owners of physical measurement decisions.
"""
from __future__ import annotations

from math import hypot, isfinite
from statistics import median
from typing import Mapping, Sequence


SHADOW_SCHEMA_VERSION = "1.0.0"
_SHADOW_REASON_UNAVAILABLE = "source_figured_scale_shadow_unavailable"
_SHADOW_REASON_CONFLICT = "source_figured_scale_shadow_conflict"
_SHADOW_REASON_CONSISTENT = "source_figured_scale_shadow_consistent_not_authority"


def _positive(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    real = float(value)
    return real if isfinite(real) and real > 0 else None


def _source_witness(row: Mapping, axis: str) -> dict | None:
    """Validate one diagnostic dimension, including its two source witnesses.

    The drawing scale is not published from this return value. Original
    authentication belongs to the upstream producer, not caller mappings.
    """
    dim_id = row.get(f"{axis}_dimension_id")
    mm = _positive(row.get(f"{axis}_value_mm"))
    raw = row.get(f"{axis}_endpoints_pt")
    witnesses = row.get(f"{axis}_source_witness_ids")
    segments = row.get(f"{axis}_witness_segments")
    if (
        type(dim_id) is not str or not dim_id or dim_id != dim_id.strip()
        or mm is None
        or type(raw) not in (list, tuple) or len(raw) != 2
        or type(witnesses) not in (list, tuple) or len(witnesses) < 2
        or any(type(w) is not str or not w or w != w.strip() for w in witnesses)
        or len(set(witnesses)) != len(witnesses)
        or type(segments) not in (list, tuple) or len(segments) < 2
    ):
        return None
    try:
        if any(
            type(value) not in (int, float) or not isfinite(float(value))
            for point in raw for value in point
        ) or any(type(point) not in (tuple, list) or len(point) != 2 for point in raw):
            return None
        p, q = (tuple(float(v) for v in pt) for pt in raw)
        for seg in segments:
            if (
                type(seg) not in (list, tuple) or len(seg) != 4
                or any(type(v) not in (int, float) or not isfinite(float(v)) for v in seg)
            ):
                return None
    except (TypeError, ValueError, OverflowError):
        return None
    delta_x, delta_y = abs(q[0] - p[0]), abs(q[1] - p[1])
    span = hypot(delta_x, delta_y)
    if span <= 1e-9:
        return None
    # Exact source-native dimension axis classification, not a tilted guide.
    if axis == "horizontal":
        if delta_y > max(1e-5, delta_x * 1e-6):
            return None
    elif axis == "vertical":
        if delta_x > max(1e-5, delta_y * 1e-6):
            return None
    else:
        return None
    return {
        "dimension_id": dim_id,
        "source_ratio_mm_per_point": mm / span,
        "source_witness_ids": tuple(witnesses),
        "value_mm": mm,
        "span_pdf_points": span,
    }


def source_figured_scale_shadow(audit: Mapping) -> dict:
    """Report consistent original-axis candidate ratios without authorizing m²."""
    results = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "diagnostic_only": True,
        "quantity_published": False,
        "physical_scale_authority_granted": False,
        "room_area_authority_granted": False,
        "source_room_to_dimension_owner_proven": False,
        "commercial_projection_allowed": False,
        "ratio_candidate_mm_per_pdf_point": None,
        "horizontal_unique_source_dimension_count": 0,
        "vertical_unique_source_dimension_count": 0,
        "original_pair_attempt_count": 0,
        "original_pair_sample_count": 0,
        "room_local_pair_intersection_count": 0,
        "first_unclosed_gate": _SHADOW_REASON_UNAVAILABLE,
    }
    if not isinstance(audit, Mapping):
        return results
    original_attempts = audit.get("attempted_pairs")
    intersections = audit.get("intersecting_pairs")
    failed = audit.get("failed_pair_samples")
    if (
        type(original_attempts) is not int or original_attempts < 0
        or type(intersections) is not int or intersections < 0
        or type(failed) not in (tuple, list)
    ):
        return results
    results["original_pair_attempt_count"] = original_attempts
    results["original_pair_sample_count"] = len(failed)
    results["room_local_pair_intersection_count"] = intersections
    # The instrument only stores a bounded sample: partial coverage cannot
    # authenticate even an advisory full-source consistency result.
    if original_attempts != len(failed) + intersections or original_attempts < 4:
        return results
    by_axis: dict[str, dict[str, dict]] = {"horizontal": {}, "vertical": {}}
    for row in failed:
        if not isinstance(row, Mapping):
            return results
        for axis in by_axis:
            receipt = _source_witness(row, axis)
            if receipt is None:
                return results
            existing = by_axis[axis].get(receipt["dimension_id"])
            if existing is not None and existing != receipt:
                results["first_unclosed_gate"] = _SHADOW_REASON_CONFLICT
                return results
            by_axis[axis][receipt["dimension_id"]] = receipt
    # Independent axes require two distinct original dimension systems each.
    if any(len(group) < 2 for group in by_axis.values()):
        return results
    h, v = by_axis["horizontal"], by_axis["vertical"]
    if set(h) & set(v):
        results["first_unclosed_gate"] = _SHADOW_REASON_CONFLICT
        return results
    # A reused original native witness cannot independently corroborate both
    # axes. Do not allow record duplication to become artificial consensus.
    if set(w for row in h.values() for w in row["source_witness_ids"]) & set(
        w for row in v.values() for w in row["source_witness_ids"]
    ):
        results["first_unclosed_gate"] = _SHADOW_REASON_CONFLICT
        return results
    ratios = [r["source_ratio_mm_per_point"]
              for group in by_axis.values() for r in group.values()]
    mid = median(ratios)
    if not isfinite(mid) or mid <= 0:
        return results
    results["horizontal_unique_source_dimension_count"] = len(h)
    results["vertical_unique_source_dimension_count"] = len(v)
    results["source_ratio_range_mm_per_point_diagnostic_only"] = [
        min(ratios), max(ratios)
    ]
    results["source_ratio_relative_spread"] = (max(ratios) - min(ratios)) / mid
    if any(abs(r - mid) > mid * 0.005 for r in ratios):
        results["first_unclosed_gate"] = _SHADOW_REASON_CONFLICT
        return results
    results["ratio_candidate_mm_per_pdf_point"] = mid
    results["first_unclosed_gate"] = _SHADOW_REASON_CONSISTENT
    return results


__all__ = ["SHADOW_SCHEMA_VERSION", "source_figured_scale_shadow"]
