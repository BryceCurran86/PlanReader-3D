"""Orthogonal figured-dimension observations and declared-area reconciliation.

IMPORTANT AUTHORITY BOUNDARY: a printed/declared area is a quantity claim, not
physical-shape authority. It must never choose a length/width pair or manufacture
an envelope.

The old ``resolve_orthogonal_envelope_evidence`` contract used a declared FLOOR
AREA value to select one pair of figured dimensions. That promotion is disabled.
The replacement reconciliation helper accepts dimensions that were established
independently and only reports agreement/discrepancy against a declared area.

This module knows nothing about benchmark identities, BOQ quantities, project
names, or expected answers.
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
_SECONDARY_LABELS = frozenset({"verandah", "veranda"})


@dataclass(frozen=True)
class OrientedDimensionObservation:
    value_m: float
    orientation: str  # "horizontal" or "vertical"
    raw_text: str
    bbox: Tuple[float, float, float, float]
    direction: Tuple[float, float]


@dataclass(frozen=True)
class SecondaryAreaLabelEvidence:
    text: str
    bbox: Tuple[float, float, float, float]


@dataclass(frozen=True)
class OrthogonalEnvelopeEvidence:
    length_m: float
    width_m: float
    horizontal_m: float
    vertical_m: float
    explicit_floor_area_m2: float
    corroborated_area_m2: float
    relative_area_error: float
    secondary_width_m: Optional[float]
    horizontal_evidence: OrientedDimensionObservation
    vertical_evidence: OrientedDimensionObservation
    secondary_width_evidence: Optional[OrientedDimensionObservation] = None
    secondary_label_evidence: Optional[SecondaryAreaLabelEvidence] = None
    authority: str = "deprecated_non_authoritative_reconciliation"


def _parse_standalone_dimension(text: str) -> Optional[float]:
    match = _DIMENSION_LINE_RE.fullmatch(text or "")
    if match is None:
        return None
    value = float(match.group("major")) + float(match.group("minor")) / 1000.0
    # Small standalone figured dimensions are retained because they may be the
    # width of a named secondary strip. Main-envelope candidates are filtered
    # more strictly later.
    if not math.isfinite(value) or not (0.75 <= value <= 35.0):
        return None
    return round(value, 3)


def extract_oriented_dimension_observations(
    page: fitz.Page,
) -> list[OrientedDimensionObservation]:
    """Extract standalone native figured dimensions with text orientation.

    PyMuPDF exposes each native text line's direction vector. Horizontal and
    90-degree rotated dimension strings therefore remain distinct even on a
    dense sheet containing many dimension chains. Diagonal / uncertain text
    directions are ignored.
    """
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
                    bbox=bbox,  # type: ignore[arg-type]
                    direction=(dx, dy),
                )
            )
    return observations


def _unique_by_value(
    observations: Iterable[OrientedDimensionObservation],
) -> list[OrientedDimensionObservation]:
    """Keep one deterministic observation for each figured value."""
    selected: dict[float, OrientedDimensionObservation] = {}
    for obs in observations:
        current = selected.get(obs.value_m)
        if current is None or (obs.bbox[1], obs.bbox[0]) < (current.bbox[1], current.bbox[0]):
            selected[obs.value_m] = obs
    return [selected[value] for value in sorted(selected, reverse=True)]


def _centre(bbox: Tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _find_unique_secondary_label(page: fitz.Page) -> Optional[SecondaryAreaLabelEvidence]:
    """Return one unique native secondary-area label, otherwise fail closed."""
    try:
        words = page.get_text("words") or []
    except Exception:
        return None

    matches: list[SecondaryAreaLabelEvidence] = []
    for word in words:
        token = re.sub(r"[^a-z]", "", str(word[4]).lower())
        if token not in _SECONDARY_LABELS:
            continue
        bbox = tuple(float(v) for v in word[:4])
        if not all(math.isfinite(v) for v in bbox):
            continue
        matches.append(SecondaryAreaLabelEvidence(text=str(word[4]), bbox=bbox))  # type: ignore[arg-type]

    if len(matches) != 1:
        return None
    return matches[0]


def _bound_secondary_width_candidates(
    page: fitz.Page,
    observations: Iterable[OrientedDimensionObservation],
    label: SecondaryAreaLabelEvidence,
) -> list[OrientedDimensionObservation]:
    """Bind small figured widths to the same spatial band as a secondary label.

    A rotated vertical dimension owns a horizontal page band, so its y-centre
    must align with the label's y-centre. A horizontal dimension owns a vertical
    page band, so x-centres must align. The tolerance scales with the page rather
    than using a benchmark coordinate or fixed pixel constant.
    """
    try:
        page_short_side = min(float(page.rect.width), float(page.rect.height))
    except Exception:
        return []
    if not math.isfinite(page_short_side) or page_short_side <= 0:
        return []

    band_tolerance = max(4.0, page_short_side * 0.02)
    label_x, label_y = _centre(label.bbox)
    candidates: list[OrientedDimensionObservation] = []
    for obs in observations:
        if not (0.75 <= obs.value_m <= 5.0):
            continue
        obs_x, obs_y = _centre(obs.bbox)
        distance = (
            abs(obs_y - label_y)
            if obs.orientation == "vertical"
            else abs(obs_x - label_x)
        )
        if distance <= band_tolerance:
            candidates.append(obs)
    return _unique_by_value(candidates)


@dataclass(frozen=True)
class DeclaredAreaReconciliation:
    """Compare already-established dimensions with a declared source area."""

    length_m: float
    width_m: float
    reconstructed_area_m2: float
    declared_area_m2: float
    delta_m2: float
    relative_error: float
    status: str
    binding: str = "unbound"
    authority: str = "reconciliation_only"


def reconcile_orthogonal_envelope_against_declared_area(
    *,
    length_m: float,
    width_m: float,
    declared_floor_area_m2: float,
    secondary_width_m: Optional[float] = None,
    relative_area_tolerance: float = 0.015,
) -> Optional[DeclaredAreaReconciliation]:
    """Reconcile known dimensions against a declared area without selecting shape.

    ``length_m`` and ``width_m`` are inputs, never outputs chosen from candidate
    dimension observations. The declared area therefore cannot mint or disambiguate
    geometry. A secondary strip contributes only when its independently-established
    width is supplied by the caller.
    """
    try:
        length = float(length_m)
        width = float(width_m)
        declared = float(declared_floor_area_m2)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) and v > 0.0 for v in (length, width, declared)):
        return None
    if not math.isfinite(relative_area_tolerance) or not (0 < relative_area_tolerance <= 0.05):
        return None

    secondary: Optional[float] = None
    if secondary_width_m is not None:
        try:
            secondary = float(secondary_width_m)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(secondary) or secondary <= 0.0:
            return None

    reconstructed = length * width
    if secondary is not None:
        reconstructed += length * secondary
    delta = reconstructed - declared
    relative_error = abs(delta) / declared
    return DeclaredAreaReconciliation(
        length_m=round(length, 6),
        width_m=round(width, 6),
        reconstructed_area_m2=round(reconstructed, 6),
        declared_area_m2=round(declared, 6),
        delta_m2=round(delta, 6),
        relative_error=round(relative_error, 6),
        status=(
            "agrees_with_declared_area"
            if relative_error <= relative_area_tolerance
            else "declared_area_discrepancy"
        ),
    )


def resolve_orthogonal_envelope_evidence(
    page: fitz.Page,
    *,
    explicit_floor_area_m2: float,
    secondary_width_m: Optional[float] = None,
    relative_area_tolerance: float = 0.015,
) -> Optional[OrthogonalEnvelopeEvidence]:
    """Deprecated: declared area may not select physical dimensions.

    Retained temporarily for import compatibility. It intentionally returns
    ``None`` for every input. Callers that already own authoritative dimensions
    may use ``reconcile_orthogonal_envelope_against_declared_area`` instead.
    """
    del page, explicit_floor_area_m2, secondary_width_m, relative_area_tolerance
    return None
