"""Reconcile independently established orthogonal geometry with a declared area.

This module must never use a printed area claim to choose physical dimensions.
The caller must first supply an independently established length and width.
Native oriented dimension text is then used only to confirm that those supplied
axes exist on the page, and the declared area may be compared for reconciliation.

A successful result is reconciliation evidence only. It is not permission to
manufacture a footprint, replace geometry, or publish a physical quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Optional, Tuple

import fitz


_DIMENSION_LINE_RE = re.compile(
    r"^\s*(?P<major>\d{1,2})[,.]?(?P<minor>\d{3})\s*(?:mm)?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OrientedDimensionObservation:
    value_m: float
    orientation: str
    raw_text: str
    bbox: Tuple[float, float, float, float]
    direction: Tuple[float, float]


@dataclass(frozen=True)
class OrthogonalEnvelopeEvidence:
    """Validation-only reconciliation of already-owned dimensions."""

    length_m: float
    width_m: float
    horizontal_m: float
    vertical_m: float
    declared_floor_area_m2: float
    corroborated_area_m2: float
    relative_area_error: float
    secondary_width_m: Optional[float]
    horizontal_evidence: OrientedDimensionObservation
    vertical_evidence: OrientedDimensionObservation
    authority: str = "orthogonal_dimensions_reconciled_with_declared_area"
    geometry_authority: bool = False


def _parse_standalone_dimension(text: str) -> Optional[float]:
    match = _DIMENSION_LINE_RE.fullmatch(text or "")
    if match is None:
        return None
    value = float(match.group("major")) + float(match.group("minor")) / 1000.0
    if not math.isfinite(value) or not (0.75 <= value <= 35.0):
        return None
    return round(value, 3)


def extract_oriented_dimension_observations(
    page: fitz.Page,
) -> list[OrientedDimensionObservation]:
    """Extract standalone native figured dimensions with source text direction."""
    observations: list[OrientedDimensionObservation] = []
    try:
        payload = page.get_text("dict") or {}
    except Exception:
        return observations

    for block in payload.get("blocks", []) or []:
        for line in block.get("lines", []) or []:
            spans = line.get("spans", []) or []
            text = " ".join(str(span.get("text", "")) for span in spans).strip()
            value = _parse_standalone_dimension(text)
            if value is None:
                continue

            direction = line.get("dir", (1.0, 0.0)) or (1.0, 0.0)
            try:
                dx, dy = float(direction[0]), float(direction[1])
            except (TypeError, ValueError, IndexError):
                continue

            if abs(dx) >= 0.85 and abs(dx) >= abs(dy):
                orientation = "horizontal"
            elif abs(dy) >= 0.85 and abs(dy) > abs(dx):
                orientation = "vertical"
            else:
                continue

            raw_bbox = line.get("bbox")
            if not raw_bbox or len(raw_bbox) != 4:
                continue
            bbox = tuple(float(v) for v in raw_bbox)
            if not all(math.isfinite(v) for v in bbox):
                continue

            observations.append(
                OrientedDimensionObservation(
                    value_m=value,
                    orientation=orientation,
                    raw_text=text,
                    bbox=bbox,
                    direction=(dx, dy),
                )
            )
    return observations


def _unique_by_value(
    observations: Iterable[OrientedDimensionObservation],
) -> list[OrientedDimensionObservation]:
    selected: dict[float, OrientedDimensionObservation] = {}
    for obs in observations:
        current = selected.get(obs.value_m)
        if current is None or (obs.bbox[1], obs.bbox[0]) < (current.bbox[1], current.bbox[0]):
            selected[obs.value_m] = obs
    return [selected[value] for value in sorted(selected, reverse=True)]


def _as_positive_finite(value: object) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0.0:
        return None
    return numeric


def _axis_pair_for_candidates(
    observations: Iterable[OrientedDimensionObservation],
    *,
    length_m: float,
    width_m: float,
) -> Optional[tuple[OrientedDimensionObservation, OrientedDimensionObservation]]:
    """Find the supplied independent dimensions on opposite source-text axes.

    The declared area is deliberately absent from this function.
    """
    horizontal = _unique_by_value(o for o in observations if o.orientation == "horizontal")
    vertical = _unique_by_value(o for o in observations if o.orientation == "vertical")
    matches: list[tuple[OrientedDimensionObservation, OrientedDimensionObservation]] = []
    for h in horizontal:
        for v in vertical:
            if (
                math.isclose(h.value_m, length_m, abs_tol=1e-6)
                and math.isclose(v.value_m, width_m, abs_tol=1e-6)
            ) or (
                math.isclose(h.value_m, width_m, abs_tol=1e-6)
                and math.isclose(v.value_m, length_m, abs_tol=1e-6)
            ):
                matches.append((h, v))
    if len(matches) != 1:
        return None
    return matches[0]


def resolve_orthogonal_envelope_evidence(
    page: fitz.Page,
    *,
    candidate_length_m: float,
    candidate_width_m: float,
    declared_floor_area_m2: float,
    secondary_width_m: Optional[float] = None,
    relative_area_tolerance: float = 0.015,
) -> Optional[OrthogonalEnvelopeEvidence]:
    """Reconcile independent geometry with a declared source area.

    candidate_length_m and candidate_width_m are mandatory independent inputs.
    This function never searches dimension combinations using the declared area.
    A missing/ambiguous candidate axis fails closed.
    """
    length = _as_positive_finite(candidate_length_m)
    width = _as_positive_finite(candidate_width_m)
    declared = _as_positive_finite(declared_floor_area_m2)
    if length is None or width is None or declared is None:
        return None
    if not math.isfinite(relative_area_tolerance) or not (0 < relative_area_tolerance <= 0.05):
        return None

    secondary: Optional[float] = None
    if secondary_width_m is not None:
        secondary = _as_positive_finite(secondary_width_m)
        if secondary is None or secondary > 10.0:
            return None

    axis_pair = _axis_pair_for_candidates(
        extract_oriented_dimension_observations(page),
        length_m=length,
        width_m=width,
    )
    if axis_pair is None:
        return None
    horizontal_evidence, vertical_evidence = axis_pair

    reconciled = length * width
    if secondary is not None:
        reconciled += length * secondary
    relative_error = abs(reconciled - declared) / declared
    if relative_error > relative_area_tolerance:
        return None

    return OrthogonalEnvelopeEvidence(
        length_m=round(max(length, width), 3),
        width_m=round(min(length, width), 3),
        horizontal_m=horizontal_evidence.value_m,
        vertical_m=vertical_evidence.value_m,
        declared_floor_area_m2=round(declared, 4),
        corroborated_area_m2=round(reconciled, 4),
        relative_area_error=round(relative_error, 6),
        secondary_width_m=None if secondary is None else round(secondary, 4),
        horizontal_evidence=horizontal_evidence,
        vertical_evidence=vertical_evidence,
    )
