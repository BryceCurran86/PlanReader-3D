"""Source-backed wall-height evidence bound to exact registered wall geometry.

A wall-specific height is only eligible when:
1. the source page is an elevation/section viewport;
2. an explicit HEIGHT/HT label is near the exact registered target wall geometry;
3. a figured dimension near that label is WITNESS_BOUND at both endpoints.

This module does not accept a caller wall id and never establishes physical-wall
identity. Identity is supplied separately by producer-owned cross-sheet
registration in :mod:`pb_wall_height_authority`.
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
_DETAIL_VIEW_TYPES = frozenset(
    {DrawingViewType.ELEVATION.value, DrawingViewType.SECTION.value}
)


def _bbox_center(bbox: Sequence[float]) -> Tuple[float, float]:
    return (
        (float(bbox[0]) + float(bbox[2])) / 2.0,
        (float(bbox[1]) + float(bbox[3])) / 2.0,
    )


def _bbox_fully_inside(
    inner: Sequence[float], outer: Sequence[float], *, tolerance: float = 0.0
) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _point_to_bbox_distance(
    point: Tuple[float, float], bbox: Sequence[float]
) -> float:
    x, y = point
    x0, y0, x1, y1 = map(float, bbox)
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    return math.hypot(dx, dy)


def _eligible_viewports(
    viewports: Sequence[SegmentedViewport], *, allow_derived: bool
) -> List[SegmentedViewport]:
    allowed = {ViewportSegmentationStatus.RESOLVED.value}
    if allow_derived:
        allowed.add(ViewportSegmentationStatus.DERIVED.value)
    return [
        viewport
        for viewport in viewports
        if viewport.status in allowed
        and viewport.view_type in _DETAIL_VIEW_TYPES
        and viewport.bounding_box is not None
    ]


def _label_words(
    page: Any,
) -> List[Tuple[Tuple[float, float, float, float], str]]:
    wanted = set(_HEIGHT_LABEL_TOKENS)
    labels: List[Tuple[Tuple[float, float, float, float], str]] = []
    for word in page.get_text("words"):
        text = str(word[4]).strip().lower().strip(".,:;")
        if text in wanted:
            labels.append(
                (
                    (
                        float(word[0]),
                        float(word[1]),
                        float(word[2]),
                        float(word[3]),
                    ),
                    text,
                )
            )
    return labels


@dataclass(frozen=True)
class WallHeightDimensionEvidence:
    label_text: str
    height_m: float
    view_id: str
    view_status: str
    source_page: int
    chain_id: str
    label_bbox: Tuple[float, float, float, float]
    target_geometry_bbox: Tuple[float, float, float, float]
    binding_status: str = ""


def _resolve_height_near_label(
    page: Any,
    *,
    page_num: int,
    viewport: SegmentedViewport,
    label_bbox: Tuple[float, float, float, float],
) -> Optional[Tuple[float, str, str]]:
    layout = calibrate_dimension_layout(page)
    proximity_tol = max(
        layout.median_word_height_pt * 4.0,
        layout.witness_endpoint_distance_pt * 1.5,
    )
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
        if not _bbox_fully_inside(
            observation.bbox,
            viewport.bounding_box,
            tolerance=layout.median_word_height_pt,
        ):
            continue
        status = binding_by_id.get(
            observation.dimension_id, BindingStatus.UNSUPPORTED.value
        )
        if status not in _ACCEPTED_BINDINGS:
            continue
        obs_center = _bbox_center(observation.bbox)
        if (
            math.hypot(
                obs_center[0] - label_center[0],
                obs_center[1] - label_center[1],
            )
            > proximity_tol
        ):
            continue
        try:
            value_m = float(observation.value_m)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value_m) or value_m <= 0.0:
            continue
        candidates.append((value_m, observation.dimension_id, status))

    if not candidates:
        return None
    if len({round(v, 6) for v, _eid, _status in candidates}) != 1:
        return None
    value_m, dimension_id, status = min(
        candidates, key=lambda item: (round(item[0], 6), item[1])
    )
    return round(value_m, 6), dimension_id, status


def resolve_wall_height_dimension_m(
    page: Any,
    *,
    page_num: int,
    target_geometry_bbox: Sequence[float],
) -> Optional[WallHeightDimensionEvidence]:
    """Resolve one explicit height for one exact target geometry.

    The target geometry is producer-owned geometry from a cross-sheet-registered
    target wall. A HEIGHT/HT label must lie near that geometry and in the same
    elevation/section viewport. Ambiguous labels or dimensions fail closed.
    """
    target_bbox = tuple(float(v) for v in target_geometry_bbox)
    if len(target_bbox) != 4:
        return None

    all_viewports = segment_page_viewports(page, page_number=page_num)
    labels = _label_words(page)
    if not labels:
        return None

    for allow_derived in (False, True):
        viewports = _eligible_viewports(
            all_viewports, allow_derived=allow_derived
        )
        anchors = []
        for viewport in viewports:
            if not _bbox_fully_inside(
                target_bbox, viewport.bounding_box, tolerance=2.0
            ):
                continue
            layout = calibrate_dimension_layout(page)
            target_proximity = max(
                120.0,
                layout.median_word_height_pt * 8.0,
            )
            for label_bbox, label_text in labels:
                if not _bbox_fully_inside(
                    label_bbox, viewport.bounding_box
                ):
                    continue
                if (
                    _point_to_bbox_distance(
                        _bbox_center(label_bbox), target_bbox
                    )
                    > target_proximity
                ):
                    continue
                anchors.append((label_bbox, label_text, viewport))

        if len(anchors) != 1:
            continue

        label_bbox, label_text, viewport = anchors[0]
        resolved = _resolve_height_near_label(
            page,
            page_num=page_num,
            viewport=viewport,
            label_bbox=label_bbox,
        )
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
            target_geometry_bbox=target_bbox,
            binding_status=binding_status,
        )
    return None


__all__ = [
    "WallHeightDimensionEvidence",
    "resolve_wall_height_dimension_m",
]
