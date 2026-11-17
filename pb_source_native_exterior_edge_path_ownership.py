"""Shadow: unique-or-abstain native path owners of footprint-first exterior edges.

Consumes GPT1 ``ExternalFootprintTrace`` polygons and the existing layered
wall-run / doorway-ring producer. It does not edit the raster collector, mint
walls, close unproved gaps, or issue quantities. Morphological red contours
are never walls.

Observed (not inferred): the raster tracer records ``page_drawings_examined=0``.
Proposed: bind each contour edge to original native path indices, or ABSTAIN.
Benchmark scores and project names are not inputs.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus

# Association window only. Not a geometry snap that invents ink, and not the
# 0.05 pt representation-noise test used inside native wall runs.
_EDGE_SEARCH_PT = 2.5
_AXIS_PT = 2.0
_DIAGONAL_PT = 2.0
_MIN_OWNER_SPAN_PT = 8.0
_SHORT_CONTOUR_PT = 8.0
_GRAZE_EDGE_PT = 24.0


def _dashed(row: Mapping[str, Any]) -> bool:
    token = "".join(str(row.get("dashes") or "").split())
    return token not in {"", "[]0"}


def _xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def _finite_width(row: Mapping[str, Any]) -> float | None:
    width = row.get("width")
    if type(width) is bool or type(width) not in (int, float):
        return None
    value = float(width)
    return value if math.isfinite(value) else None


def _rect_edges(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    lo_x, hi_x = (x0, x1) if x0 <= x1 else (x1, x0)
    lo_y, hi_y = (y0, y1) if y0 <= y1 else (y1, y0)
    return (
        ((lo_x, lo_y), (hi_x, lo_y)),
        ((hi_x, lo_y), (hi_x, hi_y)),
        ((hi_x, hi_y), (lo_x, hi_y)),
        ((lo_x, hi_y), (lo_x, lo_y)),
    )


def _dark_original_ink(rgb: Any) -> bool:
    """Original PDF ink color, not raster-inferred physical wall authority.

    Pale background fills and mid-grey design guide lines may draw geometric
    edges but are not physical black wall ink. Even a dark path needs later
    original-source physical-wall authority before any customer quantity.
    """
    if not isinstance(rgb, (tuple, list)) or len(rgb) != 3:
        return False
    if any(type(v) is bool or type(v) not in (int, float) for v in rgb):
        return False
    values = tuple(float(v) for v in rgb)
    return all(math.isfinite(v) and 0.0 <= v <= 0.4 for v in values)


def _visible_native_dark_wall_ink(row: Mapping[str, Any]) -> bool:
    """Respect rendered stroke/fill mode; a pale PDF fill is not a wall."""
    kind = str(row.get("type") or "")
    if kind == "s":
        return _dark_original_ink(row.get("color"))
    if kind == "f":
        return _dark_original_ink(row.get("fill"))
    if kind == "fs":
        return (_dark_original_ink(row.get("color"))
                or _dark_original_ink(row.get("fill")))
    # Some synthetic producer records have no PyMuPDF type, but still provide
    # actual ink colors. Never treat missing RGB as a black source stroke.
    return (_dark_original_ink(row.get("color"))
            or _dark_original_ink(row.get("fill")))


def _native_line_segments(
    drawings: Sequence[Mapping[str, Any] | object],
) -> tuple[tuple[int, tuple[float, float], tuple[float, float], Mapping[str, Any]], ...]:
    """Original ``l`` / ``re`` / ``qu`` edges. Bezier door swings are not walls."""
    out: list[tuple[int, tuple[float, float], tuple[float, float], Mapping[str, Any]]] = []
    for index, raw in enumerate(drawings):
        if not isinstance(raw, Mapping):
            continue
        if _dashed(raw) or not _visible_native_dark_wall_ink(raw):
            continue
        for item in raw.get("items") or ():
            if not item:
                continue
            kind = item[0]
            edges: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = ()
            if kind == "l" and len(item) >= 3:
                edges = ((_xy(item[1]), _xy(item[2])),)
            elif kind == "re" and len(item) >= 2:
                rect = item[1]
                try:
                    edges = _rect_edges(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
                except (AttributeError, TypeError, ValueError):
                    continue
            elif kind == "qu" and len(item) >= 2:
                quad = item[1]
                try:
                    pts = (_xy(quad.ul), _xy(quad.ur), _xy(quad.lr), _xy(quad.ll))
                except (AttributeError, TypeError, ValueError):
                    continue
                edges = tuple((pts[i], pts[(i + 1) % 4]) for i in range(4))
            for start, end in edges:
                if not all(math.isfinite(v) for v in (*start, *end)):
                    continue
                if max(abs(start[0] - end[0]), abs(start[1] - end[1])) <= NOISE_PT:
                    continue
                out.append((index, start, end, raw))
    return tuple(out)


def _polygon_signed_area(points: Sequence[tuple[float, float]]) -> float:
    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _is_diagonal(start: tuple[float, float], end: tuple[float, float]) -> bool:
    return abs(start[0] - end[0]) > _DIAGONAL_PT and abs(start[1] - end[1]) > _DIAGONAL_PT


def _axis_aligned(start: tuple[float, float], end: tuple[float, float]) -> bool:
    return abs(start[0] - end[0]) <= _AXIS_PT or abs(start[1] - end[1]) <= _AXIS_PT


def _overlap_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    lo0, hi0 = (a0, a1) if a0 <= a1 else (a1, a0)
    lo1, hi1 = (b0, b1) if b0 <= b1 else (b1, b0)
    return max(0.0, min(hi0, hi1) - max(lo0, lo1))


def _line_offset(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= NOISE_PT:
        return 0.0
    return ((point[0] - start[0]) * dy - (point[1] - start[1]) * dx) / length


@dataclass(frozen=True)
class ExteriorEdgeNativeOwnership:
    edge_index: int
    start_pdf_pts: tuple[float, float]
    end_pdf_pts: tuple[float, float]
    status: EvidenceResolutionStatus
    reason: str
    classification: str
    native_path_indices: tuple[int, ...]
    diagonal: bool
    topology_only: bool = True
    physical_wall_authenticated: bool = False
    can_issue_area: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_index": self.edge_index,
            "start_pdf_pts": list(self.start_pdf_pts),
            "end_pdf_pts": list(self.end_pdf_pts),
            "status": self.status.value,
            "reason": self.reason,
            "classification": self.classification,
            "native_path_indices": list(self.native_path_indices),
            "diagonal": self.diagonal,
            "topology_only": True,
            "physical_wall_authenticated": False,
            "can_issue_area": False,
            "commercial_publishable": False,
        }


@dataclass(frozen=True)
class OpenToExteriorSpanReceipt:
    horizontal: bool
    band_pdf_pts: tuple[float, float]
    gap_interval_pdf_pts: tuple[float, float]
    endpoints_pdf_pts: tuple[tuple[float, float], tuple[float, float]]
    adjacent_wall_native_path_indices: tuple[int, ...]
    left_wall_native_path_indices: tuple[int, ...]
    right_wall_native_path_indices: tuple[int, ...]
    source_path_side_partition_proven: bool
    layer_names: tuple[str, ...]
    stroke_widths: tuple[float, ...]
    dashed: bool
    swing_or_slider_or_stroke_witness: bool
    missing_jamb_opening_evidence: bool
    status: EvidenceResolutionStatus
    reason: str
    topology_only: bool = True
    physical_wall_authenticated: bool = False
    opening_authenticated: bool = False
    can_issue_area: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "horizontal": self.horizontal,
            "band_pdf_pts": list(self.band_pdf_pts),
            "gap_interval_pdf_pts": list(self.gap_interval_pdf_pts),
            "endpoints_pdf_pts": [list(p) for p in self.endpoints_pdf_pts],
            "adjacent_wall_native_path_indices": list(self.adjacent_wall_native_path_indices),
            "left_wall_native_path_indices": list(self.left_wall_native_path_indices),
            "right_wall_native_path_indices": list(self.right_wall_native_path_indices),
            "source_path_side_partition_proven": self.source_path_side_partition_proven,
            "layer_names": list(self.layer_names),
            "stroke_widths": list(self.stroke_widths),
            "dashed": self.dashed,
            "swing_or_slider_or_stroke_witness": self.swing_or_slider_or_stroke_witness,
            "missing_jamb_opening_evidence": self.missing_jamb_opening_evidence,
            "status": self.status.value,
            "reason": self.reason,
            "topology_only": True,
            "physical_wall_authenticated": False,
            "opening_authenticated": False,
            "can_issue_area": False,
        }


def own_exterior_contour_native_paths(
    drawings: Sequence[Mapping[str, Any] | object],
    trace: ExternalFootprintTrace,
    *,
    closures: Sequence[Any] = (),
) -> tuple[ExteriorEdgeNativeOwnership, ...]:
    """Bind each raster contour edge to unique native wall ink, or ABSTAIN.

    Dash-dotted site lines are dropped before matching. Diagonal morphological
    bridges without a unique axis-aligned native wall owner are classified as
    incorrect geometric bridges, not rooms or doors. A closure that already
    spans the interval stays topology-only.
    """
    if trace.status != "CANDIDATE" or len(trace.polygon_pdf_pts) < 4:
        return ()
    points = tuple((float(x), float(y)) for x, y in trace.polygon_pdf_pts)
    if not all(math.isfinite(v) for xy in points for v in xy):
        return ()
    winding = _polygon_signed_area(points)
    if abs(winding) <= NOISE_PT:
        return ()
    segments = _native_line_segments(drawings)
    owned: list[ExteriorEdgeNativeOwnership] = []
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        owned.append(_own_one_edge(
            edge_index, start, end, winding, segments, closures,
        ))
    return tuple(owned)


def _source_exact_collinear_chain(
    start: tuple[float, float],
    end: tuple[float, float],
    horizontal: bool,
    segments: Sequence[
        tuple[int, tuple[float, float], tuple[float, float], Mapping[str, Any]]
    ],
) -> tuple[str, tuple[int, ...], bool] | None:
    """Retain original touching CAD strokes, never use a 2.5pt wall join.

    This can only bind source ink to a review contour. Even an exact full
    stroke chain does not authenticate a physical wall or customer area.
    """
    axis = 1 if horizontal else 0
    along = 0 if horizontal else 1
    low, high = sorted((start[along], end[along]))
    length = high - low
    if length <= _SHORT_CONTOUR_PT:
        return None
    nearby = []
    for index, a, b, _row in segments:
        if abs(a[axis] - b[axis]) > NOISE_PT:
            continue
        coordinate = (a[axis] + b[axis]) / 2.0
        if max(abs(coordinate - start[axis]),
               abs(coordinate - end[axis])) > _EDGE_SEARCH_PT:
            continue
        sa, sb = sorted((a[along], b[along]))
        lo, hi = max(low, sa), min(high, sb)
        if hi - lo >= 1.0:
            nearby.append((coordinate, lo, hi, index))
    if len(nearby) < 2:
        return None
    # Nearby parallel wall faces are separate groups, not one inferred strip.
    buckets: list[tuple[float, list[tuple[float, float, int]]]] = []
    for coord, lo, hi, index in sorted(nearby):
        if buckets and abs(coord - buckets[-1][0]) <= NOISE_PT:
            buckets[-1][1].append((lo, hi, index))
        else:
            buckets.append((coord, [(lo, hi, index)]))
    runs = []
    for _coord, spans in buckets:
        current_lo = current_hi = None
        current_ids: set[int] = set()
        for lo, hi, index in sorted(spans):
            if current_lo is None:
                current_lo, current_hi, current_ids = lo, hi, {index}
            elif lo <= current_hi + NOISE_PT:
                current_hi = max(current_hi, hi)
                current_ids.add(index)
            else:
                runs.append((current_hi - current_lo, current_lo,
                             current_hi, tuple(sorted(current_ids))))
                current_lo, current_hi, current_ids = lo, hi, {index}
        if current_lo is not None:
            runs.append((current_hi - current_lo, current_lo,
                         current_hi, tuple(sorted(current_ids))))
    plausible = [
        run for run in runs
        if run[0] >= 0.5 * length and len(run[3]) >= 2
    ]
    if not plausible:
        return None
    plausible.sort(key=lambda run: (-run[0], run[1], run[2], run[3]))
    if len(plausible) != 1:
        ids = tuple(sorted({i for run in plausible for i in run[3]}))
        return "ambiguous", ids, False
    _covered, first, last, ids = plausible[0]
    complete = first <= low + NOISE_PT and last >= high - NOISE_PT
    return ("complete" if complete else "incomplete"), ids, complete


def _own_one_edge(
    edge_index: int,
    start: tuple[float, float],
    end: tuple[float, float],
    winding: float,
    segments: Sequence[tuple[int, tuple[float, float], tuple[float, float], Mapping[str, Any]]],
    closures: Sequence[Any],
) -> ExteriorEdgeNativeOwnership:
    diagonal = _is_diagonal(start, end)
    if diagonal or not _axis_aligned(start, end):
        return ExteriorEdgeNativeOwnership(
            edge_index, start, end, EvidenceResolutionStatus.ABSTAINED,
            "incorrect_geometric_bridge_no_native_wall_owner",
            "incorrect_geometric_bridge", (), True,
        )
    edge_len = math.hypot(end[0] - start[0], end[1] - start[1])
    if edge_len < _SHORT_CONTOUR_PT:
        return ExteriorEdgeNativeOwnership(
            edge_index, start, end, EvidenceResolutionStatus.ABSTAINED,
            "no_native_path_owner_for_morphological_edge",
            "unmatched_contour_segment", (), False,
        )
    if _closure_covers_edge(start, end, closures):
        return ExteriorEdgeNativeOwnership(
            edge_index, start, end, EvidenceResolutionStatus.ABSTAINED,
            "exterior_edge_topology_only_opening_closure",
            "topology_only_opening_closure", (), False,
        )
    horizontal = abs(start[1] - end[1]) <= _AXIS_PT
    hits: list[tuple[float, int]] = []
    min_overlap = max(_MIN_OWNER_SPAN_PT, 0.35 * edge_len)
    for index, a, b, _row in segments:
        native_len = math.hypot(b[0] - a[0], b[1] - a[1])
        if native_len > 4.0 * edge_len and edge_len < _GRAZE_EDGE_PT:
            continue
        if horizontal:
            if abs(a[1] - b[1]) > _AXIS_PT:
                continue
            overlap = _overlap_1d(start[0], end[0], a[0], b[0])
            offset = max(
                abs(a[1] - start[1]), abs(a[1] - end[1]),
                abs(b[1] - start[1]), abs(b[1] - end[1]),
            )
        else:
            if abs(a[0] - b[0]) > _AXIS_PT:
                continue
            overlap = _overlap_1d(start[1], end[1], a[1], b[1])
            offset = max(
                abs(a[0] - start[0]), abs(a[0] - end[0]),
                abs(b[0] - start[0]), abs(b[0] - end[0]),
            )
        if overlap < min_overlap or offset > _EDGE_SEARCH_PT:
            continue
        signed = _line_offset(a, start, end)
        # Positive winding is CCW: interior is to the left of each edge.
        outward = -signed if winding > 0 else signed
        hits.append((round(outward, 3), index))
    if not hits:
        chain = _source_exact_collinear_chain(start, end, horizontal, segments)
        if chain is not None:
            kind, ids, complete = chain
            if kind == "ambiguous":
                return ExteriorEdgeNativeOwnership(
                    edge_index, start, end, EvidenceResolutionStatus.ABSTAINED,
                    "ambiguous_competing_native_path_owners",
                    "competing_source_ink_chains", ids, diagonal,
                )
            return ExteriorEdgeNativeOwnership(
                edge_index, start, end,
                EvidenceResolutionStatus.CANDIDATE if complete
                else EvidenceResolutionStatus.ABSTAINED,
                ("native_exact_source_chain_needs_physical_wall_proof"
                 if complete else "native_source_chain_has_unwitnessed_contour_endpoint"),
                ("source_native_wall_ink_chain_candidate"
                 if complete else "incomplete_source_native_wall_ink_chain"),
                ids, diagonal,
            )
        return ExteriorEdgeNativeOwnership(
            edge_index, start, end, EvidenceResolutionStatus.ABSTAINED,
            "no_native_path_owner_for_morphological_edge",
            "unmatched_contour_segment", (), diagonal,
        )
    outermost = max(offset for offset, _index in hits)
    cluster = tuple(sorted({index for offset, index in hits if offset == outermost}))
    rival_offsets = {offset for offset, _index in hits if offset != outermost}
    if rival_offsets and any(abs(outermost - other) <= NOISE_PT for other in rival_offsets):
        return ExteriorEdgeNativeOwnership(
            edge_index, start, end, EvidenceResolutionStatus.ABSTAINED,
            "ambiguous_competing_native_path_owners",
            "competing_exterior_path_owners", cluster, diagonal,
        )
    return ExteriorEdgeNativeOwnership(
        edge_index, start, end, EvidenceResolutionStatus.CANDIDATE,
        "unique_outer_native_path_owner_needs_physical_wall_proof",
        "source_native_wall_ink_candidate", cluster, diagonal,
    )


def _closure_covers_edge(
    start: tuple[float, float],
    end: tuple[float, float],
    closures: Sequence[Any],
    *,
    horizontal_witness: bool | None = None,
) -> bool:
    if not closures:
        return False
    # A source gap's endpoint pair can span opposite faces of a thick wall.
    # Its orientation belongs to the original ring witness, not an inferred
    # centerline axis. Keep the old inference for standalone diagnostic calls.
    horizontal = (
        horizontal_witness
        if horizontal_witness is not None
        else abs(start[1] - end[1]) <= _AXIS_PT
    )
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    for closure in closures:
        lo, hi = closure.gap_interval
        band0, band1 = closure.band
        if not all(math.isfinite(float(v)) for v in (lo, hi, band0, band1)):
            continue
        if bool(closure.horizontal) != horizontal:
            continue
        # The 2.5-pt path SEARCH radius is not source closure authority:
        # parallel physical wall faces can be inside that radius.
        # Require the SAME band to touch within 0.05-pt representation noise.
        low_band, high_band = sorted((band0, band1))
        if horizontal:
            on_band = low_band - NOISE_PT <= mid[1] <= high_band + NOISE_PT
            span0, span1 = sorted((start[0], end[0]))
        else:
            on_band = low_band - NOISE_PT <= mid[0] <= high_band + NOISE_PT
            span0, span1 = sorted((start[1], end[1]))
        # A closure touching only the middle of a longer missing span
        # cannot authenticate the entire opening. Preserve the source
        # tolerance, but require BOTH native gap ends to be witnessed by
        # this same closure. Never union unrelated partial closures.
        on_span = lo - NOISE_PT <= span0 and span1 <= hi + NOISE_PT
        if on_band and on_span:
            return True
    return False


def first_unsupported_open_to_exterior_span(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_sha256: str,
    page_index: int,
    sliding_leaf_frame_closure: bool = False,
    dark_painted_wall_source: bool = False,
    source_heavy_stroke_wall_bands: bool = False,
) -> OpenToExteriorSpanReceipt | None:
    """First unresolved collinear gap in existing ring topology; never a door.

    Length is reported. It is not a close/open threshold. Missing swing, slider
    or source-stroke jamb evidence keeps the span ABSTAINED.
    """
    result = build_layered_wall_doorway_room_rings(
        drawings, source_sha256=source_sha256, page_index=page_index,
        sliding_leaf_frame_closure=sliding_leaf_frame_closure,
        dark_painted_wall_source=dark_painted_wall_source,
        source_heavy_stroke_wall_bands=source_heavy_stroke_wall_bands,
    )
    if not result.unresolved_gap_witnesses:
        return None
    witness = result.unresolved_gap_witnesses[0]
    return enrich_open_to_exterior_span(
        drawings, witness, closures=result.closures,
    )


def enrich_open_to_exterior_span(
    drawings: Sequence[Mapping[str, Any] | object],
    witness: Mapping[str, Any],
    *,
    closures: Sequence[Any] = (),
) -> OpenToExteriorSpanReceipt:
    horizontal = bool(witness["horizontal"])
    band = (float(witness["band_pdf_pts"][0]), float(witness["band_pdf_pts"][1]))
    interval = (
        float(witness["gap_interval_pdf_pts"][0]),
        float(witness["gap_interval_pdf_pts"][1]),
    )
    if horizontal:
        endpoints = ((interval[0], band[0]), (interval[1], band[1]))
    else:
        endpoints = ((band[0], interval[0]), (band[1], interval[1]))
    adjacent = tuple(int(i) for i in witness.get("adjacent_wall_native_path_indices") or ())
    left = tuple(int(i) for i in witness.get("left_wall_native_path_indices") or ())
    right = tuple(int(i) for i in witness.get("right_wall_native_path_indices") or ())
    layers: list[str] = []
    widths: list[float] = []
    dashed = False
    for index in adjacent:
        if index < 0 or index >= len(drawings):
            continue
        row = drawings[index]
        if not isinstance(row, Mapping):
            continue
        layers.append(str(row.get("layer") or ""))
        width = _finite_width(row)
        if width is not None:
            widths.append(width)
        dashed = dashed or _dashed(row)
    covered = _closure_covers_edge(
        endpoints[0], endpoints[1], closures, horizontal_witness=horizontal,
    )
    missing = not covered
    reason = (
        "open_to_exterior_span_missing_jamb_or_opening_witness"
        if missing else
        "open_to_exterior_span_has_topology_only_closure"
    )
    return OpenToExteriorSpanReceipt(
        horizontal=horizontal,
        band_pdf_pts=band,
        gap_interval_pdf_pts=interval,
        endpoints_pdf_pts=endpoints,
        adjacent_wall_native_path_indices=adjacent,
        left_wall_native_path_indices=left,
        right_wall_native_path_indices=right,
        source_path_side_partition_proven=bool(
            witness.get("source_path_side_partition_proven")
        ),
        layer_names=tuple(layers),
        stroke_widths=tuple(widths),
        dashed=dashed,
        swing_or_slider_or_stroke_witness=covered,
        missing_jamb_opening_evidence=missing,
        status=EvidenceResolutionStatus.ABSTAINED,
        reason=reason,
    )
