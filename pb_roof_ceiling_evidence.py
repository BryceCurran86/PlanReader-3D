"""Source-backed roof/ceiling area and length evidence (PlanReader Item 31).

Two narrow, source-only evidence primitives, both requiring a unique
family-labelled callout inside one eligible plan/roof-plan/elevation/
section viewport -- never derived from generic wall-candidate metadata,
floor area, or plan footprint:

* ``resolve_labeled_area_m2`` -- an explicit printed area annotation
  (e.g. ``"24.50 SM"``) near a family label (e.g. ``"CEILING"``,
  ``"ROOF"``). No floor area or footprint value is ever substituted.
* ``resolve_labeled_length_m`` -- a witness-bound (both endpoints) figured
  dimension near a family label (e.g. ``"EAVES"``, ``"OVERHANG"``),
  generalizing the proven F.23 witness-binding pattern.

Neither resolves a roof pitch angle: this module intentionally has no
angle-dimension evidence primitive. A printed degree figure with no
verified geometric (arc + leader) witness is not corroborated evidence --
see ``pb_roof_ceiling_authority`` for why ``ROOF_PITCH_DEG`` and
``ROOF_SURFACE_AREA`` always abstain rather than trust bare text.

OCR / raster-only pages fail closed. Ambiguity fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, List, Optional, Sequence, Tuple

from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import (
    BindingStatus,
    calibrate_dimension_layout,
    extract_dimension_evidence_bundle,
)
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    segment_page_viewports,
)

_ACCEPTED_BINDINGS = frozenset({BindingStatus.WITNESS_BOUND.value})
_AREA_UNIT_TOKENS = frozenset({"sm", "sqm", "m2", "m²", "sq.m", "sq.m."})
_AREA_VALUE_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*$")
_PLAN_VIEW_TYPES = frozenset({DrawingViewType.FLOOR_PLAN.value, DrawingViewType.ROOF_PLAN.value})
_DETAIL_VIEW_TYPES = frozenset(
    {DrawingViewType.ROOF_PLAN.value, DrawingViewType.ELEVATION.value, DrawingViewType.SECTION.value}
)


def _bbox_center(bbox: Sequence[float]) -> Tuple[float, float]:
    return (float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0


def _bbox_fully_inside(inner: Sequence[float], outer: Sequence[float], *, tolerance: float = 0.0) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _eligible_viewports(
    viewports: Sequence[SegmentedViewport], *, allowed_types: frozenset, allow_derived: bool
) -> List[SegmentedViewport]:
    allowed_status = {ViewportSegmentationStatus.RESOLVED.value}
    if allow_derived:
        allowed_status.add(ViewportSegmentationStatus.DERIVED.value)
    return [
        v
        for v in viewports
        if v.status in allowed_status and v.view_type in allowed_types and v.bounding_box is not None
    ]


def _label_words(page: Any, tokens: Sequence[str]) -> List[Tuple[Tuple[float, float, float, float], str]]:
    wanted = {t.strip().lower() for t in tokens}
    out: List[Tuple[Tuple[float, float, float, float], str]] = []
    for word in page.get_text("words"):
        text = str(word[4]).strip().lower().strip(".,:;")
        if text in wanted:
            out.append(((float(word[0]), float(word[1]), float(word[2]), float(word[3])), text))
    return out


def _unique_anchor(
    page: Any, *, viewports: Sequence[SegmentedViewport], tokens: Sequence[str]
) -> Optional[Tuple[Tuple[float, float, float, float], str, SegmentedViewport]]:
    labels = _label_words(page, tokens)
    if not labels:
        return None
    anchors = []
    for label_bbox, label_text in labels:
        owners = [v for v in viewports if _bbox_fully_inside(label_bbox, v.bounding_box)]
        if len(owners) == 1:
            anchors.append((label_bbox, label_text, owners[0]))
    if not anchors:
        return None
    distinct_view_ids = {v.view_id for _b, _t, v in anchors}
    if len(distinct_view_ids) > 1 or len(anchors) > 1:
        return None
    return anchors[0]


# --------------------------------------------------------------------------
# Explicit printed area annotation near a family label.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LabeledAreaEvidence:
    label_text: str
    area_m2: float
    view_id: str
    view_status: str
    source_page: int
    label_bbox: Tuple[float, float, float, float]
    notes: Tuple[str, ...] = field(default_factory=tuple)


def _area_value_words(page: Any) -> List[Tuple[Tuple[float, float, float, float], float]]:
    words = list(page.get_text("words"))
    out: List[Tuple[Tuple[float, float, float, float], float]] = []
    for index, word in enumerate(words):
        text = str(word[4]).strip()
        if not _AREA_VALUE_RE.match(text):
            continue
        if index + 1 >= len(words):
            continue
        next_word = words[index + 1]
        unit_text = str(next_word[4]).strip().lower().rstrip(".,:;")
        if unit_text not in _AREA_UNIT_TOKENS:
            continue
        value_bbox = (float(word[0]), float(word[1]), float(word[2]), float(word[3]))
        unit_bbox = (float(next_word[0]), float(next_word[1]), float(next_word[2]), float(next_word[3]))
        combined = (
            min(value_bbox[0], unit_bbox[0]),
            min(value_bbox[1], unit_bbox[1]),
            max(value_bbox[2], unit_bbox[2]),
            max(value_bbox[3], unit_bbox[3]),
        )
        try:
            value = float(text)
        except ValueError:
            continue
        if not (math.isfinite(value) and value > 0.0):
            continue
        out.append((combined, value))
    return out


def resolve_labeled_area_m2(
    page: Any,
    *,
    page_num: int,
    family_tokens: Sequence[str],
) -> Optional[LabeledAreaEvidence]:
    """Resolve one explicit printed area near a unique family label.

    Never derives area from wall-candidate metadata, floor area, or plan
    footprint -- only from an actual printed ``<number> <area unit>``
    annotation. Returns ``None`` on ambiguity or missing evidence.
    """
    all_viewports = segment_page_viewports(page, page_number=page_num)
    for allow_derived in (False, True):
        viewports = _eligible_viewports(all_viewports, allowed_types=_PLAN_VIEW_TYPES, allow_derived=allow_derived)
        anchor = _unique_anchor(page, viewports=viewports, tokens=family_tokens)
        if anchor is None:
            continue
        label_bbox, label_text, viewport = anchor

        layout = calibrate_dimension_layout(page)
        proximity_tol = max(layout.median_word_height_pt * 4.0, layout.witness_endpoint_distance_pt * 1.5)
        label_center = _bbox_center(label_bbox)

        candidates: List[Tuple[float, Tuple[float, float, float, float]]] = []
        for area_bbox, value in _area_value_words(page):
            if not _bbox_fully_inside(area_bbox, viewport.bounding_box, tolerance=layout.median_word_height_pt):
                continue
            area_center = _bbox_center(area_bbox)
            if math.hypot(area_center[0] - label_center[0], area_center[1] - label_center[1]) > proximity_tol:
                continue
            candidates.append((value, area_bbox))

        if not candidates:
            continue
        distinct = {round(v, 3) for v, _b in candidates}
        if len(distinct) > 1:
            continue

        value, _bbox = candidates[0]
        return LabeledAreaEvidence(
            label_text=label_text,
            area_m2=round(value, 3),
            view_id=viewport.view_id,
            view_status=viewport.status,
            source_page=page_num,
            label_bbox=label_bbox,
            notes=(f"labeled_area label={label_text}",),
        )
    return None


# --------------------------------------------------------------------------
# Witness-bound figured dimension near a family label (e.g. eaves overhang).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LabeledLengthEvidence:
    label_text: str
    length_m: float
    view_id: str
    view_status: str
    source_page: int
    chain_id: str
    label_bbox: Tuple[float, float, float, float]
    binding_status: str = ""


def _resolve_length_near_label(
    page: Any,
    *,
    page_num: int,
    viewport: SegmentedViewport,
    label_bbox: Tuple[float, float, float, float],
) -> Optional[Tuple[float, str, str]]:
    layout = calibrate_dimension_layout(page)
    proximity_tol = max(layout.median_word_height_pt * 4.0, layout.witness_endpoint_distance_pt * 1.5)

    bundle = extract_dimension_evidence_bundle(
        page, page_num=page_num, view_id=viewport.view_id, view_type=viewport.view_type,
    )
    binding_by_id = {b.observation_id: b.status for b in bundle.bindings}
    label_center = _bbox_center(label_bbox)

    candidates: List[Tuple[float, str, str]] = []
    for observation in bundle.observations:
        if observation.bbox is None:
            continue
        if not _bbox_fully_inside(observation.bbox, viewport.bounding_box, tolerance=layout.median_word_height_pt):
            continue
        status = binding_by_id.get(observation.dimension_id, BindingStatus.UNSUPPORTED.value)
        if status not in _ACCEPTED_BINDINGS:
            continue
        obs_center = _bbox_center(observation.bbox)
        if math.hypot(obs_center[0] - label_center[0], obs_center[1] - label_center[1]) > proximity_tol:
            continue
        try:
            value_m = float(observation.value_m)
        except (TypeError, ValueError):
            continue
        if not (value_m > 0.0):
            continue
        candidates.append((value_m, observation.dimension_id, status))

    if not candidates:
        return None
    distinct = {round(v, 3) for v, _id, _st in candidates}
    if len(distinct) > 1:
        return None
    value_m, dimension_id, status = min(candidates, key=lambda c: (round(c[0], 3), c[1]))
    return round(value_m, 3), dimension_id, status


def resolve_labeled_length_m(
    page: Any,
    *,
    page_num: int,
    family_tokens: Sequence[str],
) -> Optional[LabeledLengthEvidence]:
    """Resolve one witness-bound length near a unique family label on a
    roof-plan, elevation or section viewport. Returns ``None`` on ambiguity
    or missing evidence -- there is no fallback to wall/perimeter geometry.
    """
    all_viewports = segment_page_viewports(page, page_number=page_num)
    for allow_derived in (False, True):
        viewports = _eligible_viewports(all_viewports, allowed_types=_DETAIL_VIEW_TYPES, allow_derived=allow_derived)
        anchor = _unique_anchor(page, viewports=viewports, tokens=family_tokens)
        if anchor is None:
            continue
        label_bbox, label_text, viewport = anchor
        resolved = _resolve_length_near_label(page, page_num=page_num, viewport=viewport, label_bbox=label_bbox)
        if resolved is None:
            continue
        length_m, dimension_id, binding_status = resolved
        return LabeledLengthEvidence(
            label_text=label_text,
            length_m=length_m,
            view_id=viewport.view_id,
            view_status=viewport.status,
            source_page=page_num,
            chain_id=dimension_id,
            label_bbox=label_bbox,
            binding_status=binding_status,
        )
    return None


__all__ = [
    "LabeledAreaEvidence",
    "LabeledLengthEvidence",
    "resolve_labeled_area_m2",
    "resolve_labeled_length_m",
]
