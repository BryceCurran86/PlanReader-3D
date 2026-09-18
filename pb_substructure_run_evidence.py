"""Viewport-scoped substructure run-length evidence (PlanReader Item 30).

Generalizes the proven F.23 secondary-footprint depth pattern
(``pb_secondary_footprint_evidence``) to DPC / foundation-wall / strip-footing
run-length labels. Resolves a run length only when:

* a unique family label (e.g. "DPC", "FOUNDATION", "FOOTING") sits in one
  floor-plan viewport;
* a figured dimension is **fully witness-bound** (both endpoints) and lies
  within a tight proximity band of that label, inside the same viewport;
* no competing distinct length values remain near the label.

Ordinary wall-candidate length is never consulted. If no explicit,
witness-bound run-length callout exists next to the family label, this
resolver returns ``None`` -- there is no fallback to generic wall/perimeter
geometry.

OCR / raster-only pages fail closed. Ambiguity fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

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

# Depth requires both witness endpoints -- PARTIAL_WITNESS / LINE_BOUND alone
# are not enough to mint a substructure run-length proposition.
_ACCEPTED_BINDINGS = frozenset({BindingStatus.WITNESS_BOUND.value})


def _bbox_center(bbox: Sequence[float]) -> Tuple[float, float]:
    return (float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0


def _bbox_fully_inside(inner: Sequence[float], outer: Sequence[float], *, tolerance: float = 0.0) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


@dataclass(frozen=True)
class SubstructureRunEvidence:
    """A resolved substructure run length, fully traceable to its source."""

    label_text: str
    length_m: float
    view_id: str
    view_status: str
    source_page: int
    chain_id: str  # evidence id (figured dimension_id)
    label_bbox: Tuple[float, float, float, float]
    notes: Tuple[str, ...] = field(default_factory=tuple)
    binding_status: str = ""


def _label_words(page: Any, tokens: Sequence[str]) -> List[Tuple[Tuple[float, float, float, float], str]]:
    wanted = {t.strip().lower() for t in tokens}
    out: List[Tuple[Tuple[float, float, float, float], str]] = []
    for word in page.get_text("words"):
        text = str(word[4]).strip().lower().strip(".,:;")
        if text in wanted:
            out.append(((float(word[0]), float(word[1]), float(word[2]), float(word[3])), text))
    return out


def _eligible_plan_viewports(
    viewports: Sequence[SegmentedViewport], *, allow_derived: bool
) -> List[SegmentedViewport]:
    allowed = {ViewportSegmentationStatus.RESOLVED.value}
    if allow_derived:
        allowed.add(ViewportSegmentationStatus.DERIVED.value)
    return [
        v
        for v in viewports
        if v.status in allowed
        and v.view_type == DrawingViewType.FLOOR_PLAN.value
        and v.bounding_box is not None
    ]


def _resolve_length_near_label(
    page: Any,
    *,
    page_num: int,
    viewport: SegmentedViewport,
    label_bbox: Tuple[float, float, float, float],
) -> Optional[Tuple[float, str, str]]:
    """Return (length_m, dimension_id, binding_status) or None."""
    assert viewport.bounding_box is not None
    layout = calibrate_dimension_layout(page)
    proximity_tol = max(layout.median_word_height_pt * 4.0, layout.witness_endpoint_distance_pt * 1.5)

    bundle = extract_dimension_evidence_bundle(
        page,
        page_num=page_num,
        view_id=viewport.view_id,
        view_type=viewport.view_type,
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
        return None  # conflicting run-length values near the same label

    value_m, dimension_id, status = min(candidates, key=lambda c: (round(c[0], 3), c[1]))
    return round(value_m, 3), dimension_id, status


def _resolve_for_viewports(
    page: Any,
    *,
    page_num: int,
    plan_viewports: Sequence[SegmentedViewport],
    tokens: Sequence[str],
) -> Optional[SubstructureRunEvidence]:
    if not plan_viewports:
        return None

    labels = _label_words(page, tokens)
    if not labels:
        return None

    anchors: List[Tuple[Tuple[float, float, float, float], str, SegmentedViewport]] = []
    for label_bbox, label_text in labels:
        owners = [v for v in plan_viewports if _bbox_fully_inside(label_bbox, v.bounding_box)]
        if len(owners) == 1:
            anchors.append((label_bbox, label_text, owners[0]))

    if not anchors:
        return None

    distinct_view_ids = {viewport.view_id for _bbox, _text, viewport in anchors}
    if len(distinct_view_ids) > 1:
        return None
    if len(anchors) > 1:
        return None  # ambiguous: more than one matching label in scope

    label_bbox, label_text, viewport = anchors[0]
    resolved = _resolve_length_near_label(page, page_num=page_num, viewport=viewport, label_bbox=label_bbox)
    if resolved is None:
        return None
    length_m, dimension_id, binding_status = resolved

    return SubstructureRunEvidence(
        label_text=label_text,
        length_m=length_m,
        view_id=viewport.view_id,
        view_status=viewport.status,
        source_page=page_num,
        chain_id=dimension_id,
        label_bbox=label_bbox,
        notes=(f"substructure_run label={label_text} via {dimension_id}",),
        binding_status=binding_status,
    )


def resolve_substructure_run_length_m(
    page: Any,
    *,
    page_num: int,
    family_tokens: Sequence[str],
) -> Optional[SubstructureRunEvidence]:
    """Resolve one substructure run length from a witness-bound dimension.

    Tries ``RESOLVED`` floor-plan viewports first, then ``DERIVED``. Returns
    ``None`` on ambiguity or missing evidence -- there is no fallback to
    generic wall or perimeter geometry.
    """
    viewports = segment_page_viewports(page, page_number=page_num)

    strict = _resolve_for_viewports(
        page,
        page_num=page_num,
        plan_viewports=_eligible_plan_viewports(viewports, allow_derived=False),
        tokens=family_tokens,
    )
    if strict is not None:
        return strict

    return _resolve_for_viewports(
        page,
        page_num=page_num,
        plan_viewports=_eligible_plan_viewports(viewports, allow_derived=True),
        tokens=family_tokens,
    )


__all__ = [
    "SubstructureRunEvidence",
    "resolve_substructure_run_length_m",
]
