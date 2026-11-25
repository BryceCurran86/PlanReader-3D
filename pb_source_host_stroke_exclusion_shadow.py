"""Item 24: Source opening host-stroke exclusion shadow.

Filters candidate vector strokes around a physical opening aperture so that
annotation leaders, dimension rails, extension/witness lines, dashed overhead
projections, and cross-layer or cross-viewport strokes are explicitly rejected
from opening host-wall evidence.

All geometric checks use coordinate-frame-invariant Euclidean dot/cross
products so classifications are invariant under arbitrary rotation and
translation. Shadow-only; contains zero job-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Sequence


_NON_WALL_LAYER_RE = re.compile(
    r"(?:^|[\-_./\s])("
    r"anno|annot|annotation|dim|dims|dimension|dimensions|leader|leaders|"
    r"text|txt|note|notes|callout|callouts|label|labels|tag|tags|symbol|symbols|"
    r"furn|furniture|joinery|cabinet|millwork|fixture|fixtures|sanitary|"
    r"elec|electrical|light|lighting|plumb|plumbing|mech|mechanical|hvac|hyd|"
    r"grid|grids|axis|axes|hatch|fill|pattern|roof|eave|eaves|fascia|gutter|"
    r"drain|drainage|stormwater|site|landscape|tree|vehicle|car|demo|demolition|"
    r"title|border|viewport|vport|defpoints|xref"
    r")(?:$|[\-_./\s])",
    re.IGNORECASE,
)

_WALL_LAYER_HINT_RE = re.compile(
    r"(?:^|[\-_./\s])(wall|walls|masonry|blockwork|brick|stud|partition|struct|structural)(?:$|[\-_./\s])",
    re.IGNORECASE,
)

_NUMERIC_DIM_TEXT_RE = re.compile(
    r"^\s*\d{2,5}(?:\.\d{1,2})?\s*(?:mm|m)?\s*$",
    re.IGNORECASE,
)

_CALLOUT_LABEL_RE = re.compile(
    r"[A-Za-z]{1,4}\s*[\-_]?\s*\d{1,4}|\b(?:door|window|opening|glaz|lintel|head|sill|panel|roller|sliding)\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_to_segment_distance(
    pt: tuple[float, float],
    seg_a: tuple[float, float],
    seg_b: tuple[float, float],
) -> float:
    vx = seg_b[0] - seg_a[0]
    vy = seg_b[1] - seg_a[1]
    l2 = vx * vx + vy * vy
    if l2 <= 1e-12:
        return _dist(pt, seg_a)
    t = max(0.0, min(1.0, ((pt[0] - seg_a[0]) * vx + (pt[1] - seg_a[1]) * vy) / l2))
    proj = (seg_a[0] + t * vx, seg_a[1] + t * vy)
    return _dist(pt, proj)


def _point_to_bbox_distance(
    pt: tuple[float, float],
    bbox: tuple[float, float, float, float],
) -> float:
    x0, y0, x1, y1 = min(bbox[0], bbox[2]), min(bbox[1], bbox[3]), max(bbox[0], bbox[2]), max(bbox[1], bbox[3])
    dx = max(x0 - pt[0], 0.0, pt[0] - x1)
    dy = max(y0 - pt[1], 0.0, pt[1] - y1)
    return math.hypot(dx, dy)


def _segment_unit(p0: tuple[float, float], p1: tuple[float, float]) -> tuple[float, float, float]:
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (0.0, 0.0, 0.0)
    return (dx / length, dy / length, length)


def _angle_deg_between_lines(u: tuple[float, float], v: tuple[float, float]) -> float:
    dot = abs(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))
    return math.degrees(math.acos(dot))


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class StrokeLineageRef:
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str

    def normalized_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            _clean(self.document_id),
            _clean(self.revision_id),
            _clean(self.source_sha256).lower(),
            _clean(self.page_id),
            _clean(self.viewport_id),
        )

    def is_valid(self) -> bool:
        return all(bool(v) for v in self.normalized_tuple())


@dataclass(frozen=True)
class ApertureHostCandidateContext:
    opening_id: str
    lineage: StrokeLineageRef
    aperture_center: tuple[float, float]
    aperture_axis_unit: tuple[float, float]
    aperture_half_span_pts: float
    wall_thickness_pts: float
    expected_host_layers: tuple[str, ...] = ()
    structural_wall_min_stroke_pts: float = 0.5


@dataclass(frozen=True)
class SourceVectorStroke:
    stroke_id: str
    p0: tuple[float, float]
    p1: tuple[float, float]
    stroke_width_pts: float
    layer: str
    lineage: StrokeLineageRef
    dashed: bool = False


@dataclass(frozen=True)
class SourceTextBox:
    text_id: str
    text: str
    bbox_pdf_pts: tuple[float, float, float, float]
    layer: str
    lineage: StrokeLineageRef


@dataclass(frozen=True)
class SourceMarkerPrimitive:
    marker_id: str
    kind: str  # "arrow" | "tick" | "slash" | "dot"
    tip_pt: tuple[float, float]
    layer: str
    lineage: StrokeLineageRef


@dataclass(frozen=True)
class HostStrokeEvaluation:
    stroke_id: str
    accepted_as_host_evidence: bool
    classification: str
    rejection_reasons: tuple[str, ...]
    layer: str
    stroke_length_pts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "stroke_id": self.stroke_id,
            "accepted_as_host_evidence": self.accepted_as_host_evidence,
            "classification": self.classification,
            "rejection_reasons": list(self.rejection_reasons),
            "layer": self.layer,
            "stroke_length_pts": round(self.stroke_length_pts, 4),
        }


@dataclass(frozen=True)
class OpeningHostStrokeFilterResult:
    opening_id: str
    accepted_stroke_ids: tuple[str, ...]
    rejected_stroke_ids: tuple[str, ...]
    evaluations: tuple[HostStrokeEvaluation, ...]
    rejection_counts_by_reason: dict[str, int]
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opening_id": self.opening_id,
            "accepted_stroke_ids": list(self.accepted_stroke_ids),
            "rejected_stroke_ids": list(self.rejected_stroke_ids),
            "evaluations": [e.to_dict() for e in self.evaluations],
            "rejection_counts_by_reason": dict(self.rejection_counts_by_reason),
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def _is_numeric_dim_text(text: str) -> bool:
    return bool(_NUMERIC_DIM_TEXT_RE.match(_clean(text)))


def _is_callout_text(text: str) -> bool:
    cleaned = _clean(text)
    return bool(cleaned) and not _is_numeric_dim_text(cleaned) and bool(_CALLOUT_LABEL_RE.search(cleaned))


def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) * 0.5, (bbox[1] + bbox[3]) * 0.5)


def _normalize_axis(axis: tuple[float, float]) -> tuple[float, float]:
    mag = math.hypot(axis[0], axis[1])
    if not math.isfinite(mag) or mag <= 1e-9:
        raise ValueError("aperture_axis_unit must be non-zero finite vector")
    return (axis[0] / mag, axis[1] / mag)


def filter_opening_host_wall_strokes_shadow(
    context: ApertureHostCandidateContext,
    strokes: Sequence[SourceVectorStroke],
    *,
    text_boxes: Sequence[SourceTextBox] = (),
    markers: Sequence[SourceMarkerPrimitive] = (),
) -> OpeningHostStrokeFilterResult:
    """Filter candidate vector strokes for opening host-wall evidence.

    Explicitly rejects:
    - Cross-lineage / cross-viewport strokes
    - Non-wall layers and cross-layer strokes outside expected_host_layers
    - Dashed overhead/projection strokes
    - Annotation leader strokes (arrow/dot markers, oblique text pointers,
      or leader dogleg elbows touching a callout text box)
    - Dimension rails (thin lines carrying numeric dimension text and/or
      dual tick/slash/arrow markers)
    - Dimension extension/witness lines (perpendicular thin lines meeting a
      detected dimension rail endpoint/tick)
    - Non-coplanar / detached strokes outside the host-wall geometric envelope
    """
    opening_id = _clean(context.opening_id)
    if not opening_id:
        raise ValueError("opening_id is required")
    if not context.lineage.is_valid():
        raise ValueError("context.lineage must have all non-empty lineage fields")

    axis = _normalize_axis(context.aperture_axis_unit)
    normal = (-axis[1], axis[0])
    ctx_lineage = context.lineage.normalized_tuple()
    expected_layers_norm = frozenset(_clean(l).casefold() for l in context.expected_host_layers if _clean(l))

    # Filter text & markers to same lineage/viewport
    local_texts = [t for t in text_boxes if t.lineage.normalized_tuple() == ctx_lineage]
    local_markers = [m for m in markers if m.lineage.normalized_tuple() == ctx_lineage]
    numeric_texts = [t for t in local_texts if _is_numeric_dim_text(t.text)]
    callout_texts = [t for t in local_texts if _is_callout_text(t.text)]

    # Precompute stroke geometry
    stroke_geom: dict[str, tuple[tuple[float, float], float]] = {}
    for s in strokes:
        ux, uy, length = _segment_unit(s.p0, s.p1)
        stroke_geom[s.stroke_id] = ((ux, uy), length)

    # First pass: identify dimension rails and leader segments so connected
    # extension lines and leader landing shelves can also be rejected cleanly.
    dim_rail_ids: set[str] = set()
    dim_rail_endpoints: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = []
    leader_core_ids: set[str] = set()
    leader_endpoints: list[tuple[float, float]] = []

    marker_snap_tol = 4.0
    text_snap_tol = 10.0

    for s in strokes:
        if s.lineage.normalized_tuple() != ctx_lineage:
            continue
        unit, length = stroke_geom[s.stroke_id]
        if length <= 1e-6:
            continue
        is_thin = float(s.stroke_width_pts) <= max(0.45, context.structural_wall_min_stroke_pts * 0.85)

        # Check markers near p0 and p1
        m_p0 = [m for m in local_markers if _dist(m.tip_pt, s.p0) <= marker_snap_tol]
        m_p1 = [m for m in local_markers if _dist(m.tip_pt, s.p1) <= marker_snap_tol]
        tick_kinds = {"tick", "slash", "arrow", "dot"}
        has_dual_dim_markers = any(m.kind in tick_kinds for m in m_p0) and any(
            m.kind in tick_kinds for m in m_p1
        )
        has_single_arrow_or_dot = (
            any(m.kind in {"arrow", "dot"} for m in m_p0) ^ any(m.kind in {"arrow", "dot"} for m in m_p1)
        )

        # Check numeric dimension text positioned near and parallel along the stroke
        has_numeric_dim_text = False
        for t in numeric_texts:
            tc = _bbox_center(t.bbox_pdf_pts)
            d_seg = _point_to_segment_distance(tc, s.p0, s.p1)
            # Project onto stroke to ensure text sits over the middle span
            proj = (tc[0] - s.p0[0]) * unit[0] + (tc[1] - s.p0[1]) * unit[1]
            if d_seg <= 14.0 and -4.0 <= proj <= length + 4.0:
                has_numeric_dim_text = True
                break

        if (has_dual_dim_markers and (is_thin or has_numeric_dim_text)) or (
            has_numeric_dim_text and is_thin
        ):
            dim_rail_ids.add(s.stroke_id)
            dim_rail_endpoints.append((s.p0, s.p1, unit))
            continue

        # Check annotation leader: single arrow/dot OR oblique line touching callout text
        angle_to_axis = _angle_deg_between_lines(unit, axis)
        angle_to_normal = _angle_deg_between_lines(unit, normal)
        is_oblique = min(angle_to_axis, angle_to_normal) > 12.0
        touches_callout = any(
            _point_to_bbox_distance(s.p0, t.bbox_pdf_pts) <= text_snap_tol
            or _point_to_bbox_distance(s.p1, t.bbox_pdf_pts) <= text_snap_tol
            for t in callout_texts
        )
        if has_single_arrow_or_dot or (is_oblique and touches_callout):
            leader_core_ids.add(s.stroke_id)
            leader_endpoints.extend((s.p0, s.p1))

    # Second pass: identify leader landing shelves connected to a leader core endpoint
    # and touching a callout text box, plus dimension extension lines meeting a dim rail.
    leader_shelf_ids: set[str] = set()
    dim_extension_ids: set[str] = set()

    for s in strokes:
        if s.lineage.normalized_tuple() != ctx_lineage:
            continue
        if s.stroke_id in dim_rail_ids or s.stroke_id in leader_core_ids:
            continue
        unit, length = stroke_geom[s.stroke_id]
        if length <= 1e-6:
            continue

        # Leader landing shelf: shares an endpoint with a leader core segment & touches callout text
        touches_leader = any(
            _dist(s.p0, lp) <= 2.5 or _dist(s.p1, lp) <= 2.5 for lp in leader_endpoints
        )
        touches_callout = any(
            _point_to_bbox_distance(s.p0, t.bbox_pdf_pts) <= text_snap_tol
            or _point_to_bbox_distance(s.p1, t.bbox_pdf_pts) <= text_snap_tol
            for t in callout_texts
        )
        if touches_leader and touches_callout:
            leader_shelf_ids.add(s.stroke_id)

        # Dimension extension/witness line: thin stroke perpendicular to a dimension rail
        # whose body or endpoint meets one of the dimension rail's endpoints.
        is_thin = float(s.stroke_width_pts) <= max(0.45, context.structural_wall_min_stroke_pts * 0.85)
        if is_thin:
            for r0, r1, r_unit in dim_rail_endpoints:
                if _angle_deg_between_lines(unit, r_unit) >= 75.0:
                    if (
                        _point_to_segment_distance(r0, s.p0, s.p1) <= 4.0
                        or _point_to_segment_distance(r1, s.p0, s.p1) <= 4.0
                    ):
                        dim_extension_ids.add(s.stroke_id)
                        break

    # Final classification pass
    evaluations: list[HostStrokeEvaluation] = []
    accepted_ids: list[str] = []
    rejected_ids: list[str] = []
    reason_counts: dict[str, int] = {}

    for s in strokes:
        reasons: list[str] = []
        unit, length = stroke_geom[s.stroke_id]
        layer_clean = _clean(s.layer)
        layer_cf = layer_clean.casefold()

        if not s.lineage.is_valid() or s.lineage.normalized_tuple() != ctx_lineage:
            reasons.append("cross_lineage_or_viewport_stroke_rejected")

        if length <= 1e-6:
            reasons.append("degenerate_zero_length_stroke_rejected")

        if s.dashed:
            reasons.append("dashed_non_host_projection_rejected")

        if layer_clean and _NON_WALL_LAYER_RE.search(layer_clean):
            reasons.append("non_wall_layer_stroke_rejected")

        if expected_layers_norm and layer_cf not in expected_layers_norm:
            reasons.append("cross_layer_host_mismatch")
        elif not expected_layers_norm and layer_clean and not _WALL_LAYER_HINT_RE.search(layer_clean):
            # If caller did not specify expected_host_layers and layer is named but
            # neither wall nor non-wall, mark ambiguous cross-layer stroke.
            if "non_wall_layer_stroke_rejected" not in reasons:
                reasons.append("unrecognized_non_wall_layer_rejected")

        if s.stroke_id in leader_core_ids or s.stroke_id in leader_shelf_ids:
            reasons.append("annotation_leader_stroke_rejected")

        if s.stroke_id in dim_rail_ids:
            reasons.append("dimension_rail_stroke_rejected")

        if s.stroke_id in dim_extension_ids:
            reasons.append("dimension_extension_line_rejected")

        # Geometric host-wall alignment check when not already disqualified by lineage/zero-length
        if length > 1e-6 and "cross_lineage_or_viewport_stroke_rejected" not in reasons:
            angle_axis = _angle_deg_between_lines(unit, axis)
            angle_norm = _angle_deg_between_lines(unit, normal)
            mid = ((s.p0[0] + s.p1[0]) * 0.5, (s.p0[1] + s.p1[1]) * 0.5)
            rel_x = mid[0] - context.aperture_center[0]
            rel_y = mid[1] - context.aperture_center[1]
            along = rel_x * axis[0] + rel_y * axis[1]
            perp = abs(rel_x * normal[0] + rel_y * normal[1])

            max_perp_wall = max(context.wall_thickness_pts * 0.75 + 2.0, 4.0)
            if angle_axis <= 5.0:
                # Host wall face parallel to aperture axis must lie within host-wall
                # thickness envelope (not far offset like an outer dimension rail).
                if perp > max_perp_wall:
                    reasons.append("off_axis_detached_stroke_rejected")
            elif angle_norm <= 5.0:
                # Jamb return stroke perpendicular to aperture axis must sit near a jamb
                # (|along| close to aperture_half_span_pts) and within wall thickness.
                jamb_delta = abs(abs(along) - context.aperture_half_span_pts)
                if jamb_delta > max(3.0, context.wall_thickness_pts * 0.6) or length > context.wall_thickness_pts * 1.5 + 2.0:
                    reasons.append("non_jamb_perpendicular_stroke_rejected")
            else:
                reasons.append("oblique_non_host_stroke_rejected")

            if float(s.stroke_width_pts) < context.structural_wall_min_stroke_pts:
                reasons.append("thin_non_structural_stroke_rejected")

        dedup = tuple(dict.fromkeys(reasons))
        if not dedup:
            accepted_ids.append(s.stroke_id)
            classification = "accepted_host_wall_stroke"
        else:
            rejected_ids.append(s.stroke_id)
            classification = dedup[0]
            for r in dedup:
                reason_counts[r] = reason_counts.get(r, 0) + 1

        evaluations.append(
            HostStrokeEvaluation(
                stroke_id=s.stroke_id,
                accepted_as_host_evidence=not dedup,
                classification=classification,
                rejection_reasons=dedup,
                layer=layer_clean,
                stroke_length_pts=length,
            )
        )

    payload = {
        "opening_id": opening_id,
        "accepted_stroke_ids": sorted(accepted_ids),
        "rejected_stroke_ids": sorted(rejected_ids),
        "rejection_counts_by_reason": dict(sorted(reason_counts.items())),
    }
    digest = _canonical_sha(payload)
    return OpeningHostStrokeFilterResult(
        opening_id=opening_id,
        accepted_stroke_ids=tuple(sorted(accepted_ids)),
        rejected_stroke_ids=tuple(sorted(rejected_ids)),
        evaluations=tuple(evaluations),
        rejection_counts_by_reason=dict(sorted(reason_counts.items())),
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
