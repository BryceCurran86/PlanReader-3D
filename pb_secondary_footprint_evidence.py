"""Viewport-scoped secondary-footprint width evidence (PlanReader F.23).

Resolves a secondary strip width (e.g. verandah depth) only when:

* a unique secondary-space label sits in one eligible F.07 floor-plan viewport;
* the label is adjacent to a safe physical-role edge: any RESOLVED frame edge,
  or (for the existing DERIVED depth-only contract) only an edge coincident
  with the source page boundary — never an interior title-grid separator;
* a figured dimension is **fully witness-bound** (both endpoints) inside that
  viewport with orientation **orthogonal to that adjoining edge**;
* no competing orthogonal depth values remain.
* one-sided / partial witness bindings fail closed — depth needs both the
  main-building boundary witness and the outer verandah boundary witness.

Top/bottom verandah → vertical depth evidence.
Left/right verandah → horizontal depth evidence.

Parallel-to-edge figures (typical wall-thickness marks along a verandah
front) are rejected by orientation/role, never by a hardcoded magnitude
blacklist.

Does **not** broaden F.15's horizontal-chain extractor. Depth uses
``pb_figured_dimension_evidence.extract_dimension_evidence_bundle``.

OCR / raster-only pages fail closed. Ambiguity fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pb_dimension_graph_constraint_engine import DimensionOrientation
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

_SECONDARY_SPACE_LABELS = ("verandah", "veranda")
_EDGE_BAND_FRACTION = 0.25

# Depth must be perpendicular to the verandah's adjoining building edge.
_DEPTH_ORIENTATION_FOR_EDGE = {
    "top": DimensionOrientation.VERTICAL.value,
    "bottom": DimensionOrientation.VERTICAL.value,
    "left": DimensionOrientation.HORIZONTAL.value,
    "right": DimensionOrientation.HORIZONTAL.value,
}

# Depth requires both witness endpoints (main-boundary + outer-boundary).
# PARTIAL_WITNESS / LINE_BOUND alone are not enough for secondary footprint.
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
class SecondaryFootprintEvidence:
    """A resolved secondary-footprint width, fully traceable to its source."""

    label_text: str
    width_m: float
    view_id: str
    view_status: str
    source_page: int
    edge: str  # "top" | "bottom" | "left" | "right"
    chain_id: str  # evidence id (figured dimension_id)
    label_bbox: Tuple[float, float, float, float]
    notes: Tuple[str, ...] = field(default_factory=tuple)
    depth_orientation: str = ""
    binding_status: str = ""


def _label_words(page: Any) -> List[Tuple[Tuple[float, float, float, float], str]]:
    out: List[Tuple[Tuple[float, float, float, float], str]] = []
    for word in page.get_text("words"):
        text = str(word[4]).strip().lower().strip(".,:;")
        if text in _SECONDARY_SPACE_LABELS:
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


def _edge_is_physical_role_safe(
    page: Any,
    viewport: SegmentedViewport,
    edge: str,
) -> bool:
    """Whether a viewport edge may establish secondary-strip depth role.

    RESOLVED viewport edges are source-backed physical frame evidence.

    DERIVED title partitions are weaker: their internal cell/grid separators
    are document-layout constructs, not drawn building boundaries. Existing
    F.23/Item-29 contracts still permit a witness-bound depth at an outer page
    edge, where the partition edge coincides with the source page boundary.
    An interior derived separator may never decide whether a secondary strip
    is left/right/top/bottom of the plan.
    """
    if viewport.status == ViewportSegmentationStatus.RESOLVED.value:
        return True
    if viewport.status != ViewportSegmentationStatus.DERIVED.value:
        return False
    if viewport.bounding_box is None:
        return False

    vx0, vy0, vx1, vy1 = (float(v) for v in viewport.bounding_box)
    rect = page.rect
    tol = 1.0
    return {
        "left": abs(vx0 - float(rect.x0)) <= tol,
        "right": abs(vx1 - float(rect.x1)) <= tol,
        "top": abs(vy0 - float(rect.y0)) <= tol,
        "bottom": abs(vy1 - float(rect.y1)) <= tol,
    }.get(edge, False)

def _label_edge(
    label_center: Tuple[float, float],
    viewport_bbox: Sequence[float],
) -> Optional[Tuple[str, float]]:
    vx0, vy0, vx1, vy1 = (float(v) for v in viewport_bbox)
    v_width = vx1 - vx0
    v_height = vy1 - vy0
    if v_width <= 0 or v_height <= 0:
        return None
    edge_fractions: Dict[str, float] = {
        "top": (label_center[1] - vy0) / v_height,
        "bottom": (vy1 - label_center[1]) / v_height,
        "left": (label_center[0] - vx0) / v_width,
        "right": (vx1 - label_center[0]) / v_width,
    }
    edge, fraction = min(edge_fractions.items(), key=lambda item: item[1])
    if fraction > _EDGE_BAND_FRACTION:
        return None
    return edge, fraction


def _observation_orientation(observation: Any) -> str:
    """Prefer endpoint-derived span axis when vector anchors exist."""
    endpoints = getattr(observation, "endpoints", None)
    if endpoints is not None and len(endpoints) == 2:
        (x0, y0), (x1, y1) = endpoints
        if abs(x1 - x0) >= abs(y1 - y0):
            return DimensionOrientation.HORIZONTAL.value
        return DimensionOrientation.VERTICAL.value
    return str(getattr(observation, "orientation", DimensionOrientation.UNKNOWN.value))


def _spatially_associated_with_edge(
    *,
    edge: str,
    label_center: Tuple[float, float],
    obs_center: Tuple[float, float],
    viewport_bbox: Sequence[float],
    along_tolerance_pt: float,
    depth_tolerance_pt: float,
) -> bool:
    """Require along-edge alignment and proximity in the depth direction."""
    vx0, vy0, vx1, vy1 = (float(v) for v in viewport_bbox)
    if edge in ("top", "bottom"):
        if abs(obs_center[0] - label_center[0]) > along_tolerance_pt:
            return False
        if abs(obs_center[1] - label_center[1]) > depth_tolerance_pt:
            return False
        # Stay inside the plan viewport (no title-block leakage below frame).
        if not (vy0 - depth_tolerance_pt <= obs_center[1] <= vy1 + depth_tolerance_pt):
            return False
        if not (vx0 <= obs_center[0] <= vx1):
            return False
        return True

    if abs(obs_center[1] - label_center[1]) > along_tolerance_pt:
        return False
    if abs(obs_center[0] - label_center[0]) > depth_tolerance_pt:
        return False
    if not (vx0 - depth_tolerance_pt <= obs_center[0] <= vx1 + depth_tolerance_pt):
        return False
    if not (vy0 <= obs_center[1] <= vy1):
        return False
    return True


def _resolve_orthogonal_depth(
    page: Any,
    *,
    page_num: int,
    viewport: SegmentedViewport,
    label_bbox: Tuple[float, float, float, float],
    edge: str,
) -> Optional[Tuple[float, str, str, Tuple[str, ...]]]:
    """Return (width_m, dimension_id, binding_status, notes) or None."""
    assert viewport.bounding_box is not None
    required_orientation = _DEPTH_ORIENTATION_FOR_EDGE[edge]
    layout = calibrate_dimension_layout(page)
    along_tol = max(layout.median_word_height_pt * 8.0, layout.chain_axis_tolerance_pt * 4.0)
    depth_tol = max(layout.median_word_height_pt * 10.0, layout.line_search_distance_pt)

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
        orientation = _observation_orientation(observation)
        if orientation != required_orientation:
            # Parallel-to-edge / unknown figures (e.g. wall-thickness marks
            # along a verandah front) cannot become depth.
            continue
        obs_center = _bbox_center(observation.bbox)
        if not _spatially_associated_with_edge(
            edge=edge,
            label_center=label_center,
            obs_center=obs_center,
            viewport_bbox=viewport.bounding_box,
            along_tolerance_pt=along_tol,
            depth_tolerance_pt=depth_tol,
        ):
            continue
        try:
            width_m = float(observation.value_m)
        except (TypeError, ValueError):
            continue
        if not (width_m > 0.0):
            continue
        candidates.append((width_m, observation.dimension_id, status))

    if not candidates:
        return None

    distinct = {round(w, 3) for w, _id, _st in candidates}
    if len(distinct) > 1:
        return None  # conflicting orthogonal depths

    width_m, dimension_id, status = min(candidates, key=lambda c: (round(c[0], 3), c[1]))
    notes = (
        f"orthogonal_depth edge={edge} orientation={required_orientation} "
        f"binding={status} via {dimension_id}",
        f"viewport {viewport.view_id} status={viewport.status}",
    )
    return round(width_m, 3), dimension_id, status, notes


def _resolve_for_viewports(
    page: Any,
    *,
    page_num: int,
    plan_viewports: Sequence[SegmentedViewport],
) -> Optional[SecondaryFootprintEvidence]:
    if not plan_viewports:
        return None

    labels = _label_words(page)
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
        return None

    label_bbox, label_text, viewport = anchors[0]
    assert viewport.bounding_box is not None
    label_center = _bbox_center(label_bbox)
    edge_info = _label_edge(label_center, viewport.bounding_box)
    if edge_info is None:
        return None
    edge, _fraction = edge_info
    if not _edge_is_physical_role_safe(page, viewport, edge):
        return None

    resolved = _resolve_orthogonal_depth(
        page,
        page_num=page_num,
        viewport=viewport,
        label_bbox=label_bbox,
        edge=edge,
    )
    if resolved is None:
        return None
    width_m, evidence_id, binding_status, notes = resolved

    return SecondaryFootprintEvidence(
        label_text=label_text,
        width_m=width_m,
        view_id=viewport.view_id,
        view_status=viewport.status,
        source_page=page_num,
        edge=edge,
        chain_id=evidence_id,
        label_bbox=label_bbox,
        notes=notes,
        depth_orientation=_DEPTH_ORIENTATION_FOR_EDGE[edge],
        binding_status=binding_status,
    )


def resolve_secondary_footprint_width_m(
    page: Any,
    *,
    page_num: int,
) -> Optional[SecondaryFootprintEvidence]:
    """Resolve one secondary-footprint width from orthogonal depth evidence.

    RESOLVED floor-plan frames are preferred. DERIVED title partitions remain
    eligible for the existing depth-only Item-29 contract, but an internal
    partition/grid separator cannot establish the physical edge role; for a
    DERIVED viewport the selected edge must coincide with the source page
    boundary. Returns None on ambiguity or missing safe edge authority so
    callers may retain their explicit source-text fallback.
    """
    viewports = segment_page_viewports(page, page_number=page_num)

    strict = _resolve_for_viewports(
        page,
        page_num=page_num,
        plan_viewports=_eligible_plan_viewports(viewports, allow_derived=False),
    )
    if strict is not None:
        return strict

    return _resolve_for_viewports(
        page,
        page_num=page_num,
        plan_viewports=_eligible_plan_viewports(viewports, allow_derived=True),
    )
