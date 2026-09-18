"""Source-backed wall-height dimension evidence (PlanReader Item 17 hotfix).

Generalizes the proven F.23 witness-binding pattern
(``pb_secondary_footprint_evidence``) to an explicit wall-height callout: a
unique ``HEIGHT``/``HT`` label sitting in one elevation or section viewport,
with a witness-bound (both endpoints) figured dimension nearby. No wall
candidate, floor/ceiling datum, or gable/roof metadata is ever consulted --
if no such explicit callout exists, the resolver returns ``None`` and the
caller must abstain rather than assume a height.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
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

_HEIGHT_LABEL_TOKENS = ("height", "ht")
_ACCEPTED_BINDINGS = frozenset({BindingStatus.WITNESS_BOUND.value})
_DETAIL_VIEW_TYPES = frozenset({DrawingViewType.ELEVATION.value, DrawingViewType.SECTION.value})


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
    viewports: Sequence[SegmentedViewport], *, allow_derived: bool
) -> List[SegmentedViewport]:
    allowed_status = {ViewportSegmentationStatus.RESOLVED.value}
    if allow_derived:
        allowed_status.add(ViewportSegmentationStatus.DERIVED.value)
    return [
        v
        for v in viewports
        if v.status in allowed_status and v.view_type in _DETAIL_VIEW_TYPES and v.bounding_box is not None
    ]


def _label_words(page: Any) -> List[Tuple[Tuple[float, float, float, float], str]]:
    wanted = set(_HEIGHT_LABEL_TOKENS)
    out: List[Tuple[Tuple[float, float, float, float], str]] = []
    for word in page.get_text("words"):
        text = str(word[4]).strip().lower().strip(".,:;")
        if text in wanted:
            out.append(((float(word[0]), float(word[1]), float(word[2]), float(word[3])), text))
    return out


@dataclass(frozen=True)
class WallHeightDimensionEvidence:
    label_text: str
    height_m: float
    view_id: str
    view_status: str
    source_page: int
    chain_id: str
    label_bbox: Tuple[float, float, float, float]
    binding_status: str = ""


def _resolve_height_near_label(
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


def resolve_wall_height_dimension_m(
    page: Any,
    *,
    page_num: int,
) -> Optional[WallHeightDimensionEvidence]:
    """Resolve one witness-bound wall height near a unique HEIGHT/HT label
    on an elevation or section viewport. Returns ``None`` on ambiguity or
    missing evidence -- never falls back to a plan/floor-datum quantity.
    """
    all_viewports = segment_page_viewports(page, page_number=page_num)
    for allow_derived in (False, True):
        viewports = _eligible_viewports(all_viewports, allow_derived=allow_derived)
        labels = _label_words(page)
        if not labels:
            continue
        anchors = []
        for label_bbox, label_text in labels:
            owners = [v for v in viewports if _bbox_fully_inside(label_bbox, v.bounding_box)]
            if len(owners) == 1:
                anchors.append((label_bbox, label_text, owners[0]))
        if not anchors:
            continue
        distinct_view_ids = {v.view_id for _b, _t, v in anchors}
        if len(distinct_view_ids) > 1 or len(anchors) > 1:
            continue
        label_bbox, label_text, viewport = anchors[0]
        resolved = _resolve_height_near_label(page, page_num=page_num, viewport=viewport, label_bbox=label_bbox)
        if resolved is None:
            continue
        height_m, dimension_id, binding_status = resolved
        return WallHeightDimensionEvidence(
            label_text=label_text,
            height_m=height_m,
            view_id=viewport.view_id,
            view_status=viewport.status,
            source_page=page_num,
            chain_id=dimension_id,
            label_bbox=label_bbox,
            binding_status=binding_status,
        )
    return None


__all__ = [
    "WallHeightDimensionEvidence",
    "resolve_wall_height_dimension_m",
]
