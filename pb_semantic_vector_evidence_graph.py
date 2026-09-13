"""Shadow, provenance-preserving semantic evidence over Stage-A wall-graph
edges (Phase D of the autonomous foundation-work track).

STATUS: research / shadow only. Nothing in this module is imported by any
production path, any authority contract, any benchmark scorer, or any
published-quantity pipeline. It does not publish quantities, does not
promote itself to wall/room/opening authority, and does not treat its own
output as ground truth -- every result is an EVIDENCE bundle (a label, an
explicit strength tag, and the matched rule names that produced it), never
a bare "answer." Ambiguous or under-signalled primitives abstain
(SemanticClass.UNKNOWN) rather than guessing.

Objective (per the standing architecture): this is the first step toward

    PDF primitive -> provenance-preserving semantic evidence -> later
    wall/room/opening object

NOT

    PDF primitive -> BOQ quantity.

See docs/semantic_vector_evidence_graph_architecture.md for the intended
long-run shape of the full canonical building-evidence graph this module is
the first rung of.

Design choices
--------------
- Every feature is generic and project-agnostic: length, orientation,
  native layer/dash/width metadata, graph junction degree, local repetition
  density, and local parallel-partner geometry. No filename, project name,
  benchmark ID, expected quantity, or hand-tuned per-project threshold is
  used anywhere in this file.
- Where a Stage-A wall graph already computes a fact this module needs
  (`edge["length_pt"]`, `edge["angle_deg"]`, `node["degree"]`), it is read
  directly rather than recomputed, to stay consistent with the existing
  pipeline's own conventions and avoid a second, possibly-divergent
  definition of the same quantity.
- U1 primitive lineage (`primitive_lineage` on each edge, now merged to
  main) is used as the per-edge provenance/identity anchor and as a source
  of native per-parent metadata (`source_records`) -- this module reads it,
  never mutates it, and degrades gracefully (falls back to the edge's own
  fabricated-sentinel fields) on any edge that happens to carry no lineage
  (e.g. a graph built by an older caller that never wired the U1 pipeline).
- Rules are deliberately conservative and are documented individually with
  which real-drawing observation motivated them (see the architecture doc
  and this session's real-drawing validation script). This is a FIRST,
  intentionally simple deterministic pass, not a tuned or final
  classifier -- see the module-level TODO note near the bottom on ML.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

LINEAGE_KEY = "primitive_lineage"


class SemanticClass(str, Enum):
    PHYSICAL_WALL_PROBABLE = "physical_wall_probable"
    OPENING_GEOMETRY_PROBABLE = "opening_geometry_probable"
    DIMENSION_ANNOTATION = "dimension_annotation"
    HATCH = "hatch"
    GLAZING = "glazing"
    FURNITURE = "furniture"
    GRID = "grid"
    SYMBOL = "symbol"
    TABLE_OR_SCHEDULE = "table_or_schedule"
    UNKNOWN = "unknown"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class PrimitiveFeatures:
    primitive_id: str
    length_pt: float
    orientation_deg: float  # 0..180, direction-agnostic (matches Stage A's own convention)
    is_axis_aligned: bool
    native_layer: str
    native_dashes: str
    native_width: Optional[float]
    reason_codes: Tuple[str, ...]
    junction_degree_a: Optional[int]
    junction_degree_b: Optional[int]
    repetition_neighbor_count: int
    has_nearby_parallel_partner: bool
    nearest_parallel_offset_pt: Optional[float]
    source_primitive_count: Optional[int]


@dataclass(frozen=True)
class SemanticEvidence:
    primitive_id: str
    label: SemanticClass
    strength: EvidenceStrength
    matched_rules: Tuple[str, ...]
    features: PrimitiveFeatures


# ---------------------------------------------------------------------------
# Tunables -- all generic geometric defaults, none derived from or fitted to
# any specific project/benchmark drawing.
# ---------------------------------------------------------------------------

_AXIS_ALIGN_TOLERANCE_DEG = 3.0
_REPETITION_LENGTH_RELATIVE_TOLERANCE = 0.2
_REPETITION_ANGLE_TOLERANCE_DEG = 5.0
_REPETITION_NEIGHBORHOOD_PT = 60.0
_REPETITION_STRONG_THRESHOLD = 4
_REPETITION_WEAK_THRESHOLD = 2
_PARALLEL_PARTNER_ANGLE_TOLERANCE_DEG = 5.0
_PARALLEL_PARTNER_MIN_OFFSET_PT = 0.5
_PARALLEL_PARTNER_MAX_OFFSET_PT = 40.0
_PARALLEL_PARTNER_SEARCH_RADIUS_PT = 60.0
_GRID_MIN_LENGTH_PT = 120.0

# Real floor plans have a genuinely bimodal length distribution: a cluster
# of short primitives (hatch ticks, dimension marks, furniture symbols) and
# a cluster of long ones (walls, gridlines). Neither a population-median nor
# a population-maximum split is robust here: median is fragile to class
# imbalance (many more hatch ticks than wall lines pulls the median down
# INTO the tick cluster, so ticks stop reading as "short" relative to it --
# observed directly on a synthetic 12-tick/2-wall fixture), while a maximum-
# anchored split is fragile to a single long outlier (one page-spanning
# border/gridline can make every real wall read as "not long enough" --
# observed directly on real Baghau/Dungicha data). Otsu's method (a
# standard, parameter-light unsupervised threshold that maximizes between-
# class variance) is used instead: it is exactly the method built for
# splitting a bimodal distribution into two classes, is not fitted to any
# project's specific measurements, and is robust to both failure modes
# above by construction.
_LONG_SHORT_MARGIN_FRACTION = 0.1  # small dead zone around the computed
# threshold that counts as neither confidently short nor confidently long,
# consistent with this module's abstain-when-ambiguous stance.


def _otsu_threshold(values: Sequence[float]) -> Optional[float]:
    """Standard Otsu threshold over `values`, computed on log-length (real
    primitive lengths vary multiplicatively -- a 2pt hatch tick and a 200pt
    wall differ by two orders of magnitude -- so splitting on the raw scale
    would be dominated by the long cluster's own internal spread). Returns
    None when there are fewer than 2 distinct values (nothing to split)."""
    positive = sorted(v for v in values if v > 0)
    if len(positive) < 2:
        return None
    logs = [math.log(v) for v in positive]
    distinct = sorted(set(logs))
    if len(distinct) < 2:
        return None

    total = len(logs)
    total_sum = sum(logs)
    best_variance = -1.0
    best_log_threshold = distinct[0]
    running_count = 0
    running_sum = 0.0
    for candidate_idx, candidate in enumerate(distinct[:-1]):
        # advance past every value <= candidate into the "below" class
        while running_count < total and logs[running_count] <= candidate:
            running_sum += logs[running_count]
            running_count += 1
        if running_count == 0 or running_count == total:
            continue
        w0 = running_count / total
        w1 = 1.0 - w0
        mean0 = running_sum / running_count
        mean1 = (total_sum - running_sum) / (total - running_count)
        between_class_variance = w0 * w1 * (mean0 - mean1) ** 2
        if between_class_variance > best_variance:
            best_variance = between_class_variance
            # The decision boundary sits BETWEEN the two clusters, not AT
            # the top of the "below" cluster -- using `candidate` itself
            # would put every value exactly at the cluster's own length on
            # the wrong side of a tight below-threshold check downstream.
            best_log_threshold = (candidate + distinct[candidate_idx + 1]) / 2.0
    return math.exp(best_log_threshold)


def _angle_delta(a_deg: float, b_deg: float) -> float:
    d = abs(a_deg - b_deg) % 180.0
    return min(d, 180.0 - d)


def _midpoint(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _grid_cell(x: float, y: float, cell_size: float) -> Tuple[int, int]:
    return (int(math.floor(x / cell_size)), int(math.floor(y / cell_size)))


class _SpatialMidpointIndex:
    """Minimal uniform grid over segment midpoints, used only for bounded
    local-neighborhood queries (repetition density, parallel-partner
    search) -- not a general-purpose spatial index and not related to (or
    dependent on) the separate W2 splitter broad-phase work; this module's
    neighbor queries are a different, much smaller need (a handful of
    nearby-cell lookups per primitive, not exhaustive candidate-pair
    discovery for an O(n^2) predicate), so a small self-contained grid is
    kept local to this file rather than sharing code across the two
    independent research branches.
    """

    def __init__(self, midpoints: Sequence[Tuple[float, float]], cell_size: float):
        self._cell_size = cell_size
        self._grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for idx, (x, y) in enumerate(midpoints):
            self._grid[_grid_cell(x, y, cell_size)].append(idx)

    def neighbors_within(self, x: float, y: float, radius: float) -> List[int]:
        span = int(math.ceil(radius / self._cell_size)) + 1
        cx, cy = _grid_cell(x, y, self._cell_size)
        out: List[int] = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                out.extend(self._grid.get((cx + dx, cy + dy), ()))
        return out


@dataclass
class _EdgeGeometry:
    primitive_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    length_pt: float
    orientation_deg: float
    native_layer: str
    native_dashes: str
    native_width: Optional[float]
    reason_codes: Tuple[str, ...]
    junction_degree_a: Optional[int]
    junction_degree_b: Optional[int]
    source_primitive_count: Optional[int]


def _lineage_native_field(edge: Dict[str, Any], field_name: str, default: Any) -> Any:
    """Best-available native value for `field_name`: prefer U1 lineage's own
    per-source records (the fabricated post-split sentinel on the edge
    itself is never PDF-supplied evidence -- see pb_wall_room_topology_
    primitive_lineage's own field_is_present docstring), falling back to the
    edge's own field when no lineage is present at all (older/non-U1 graph).
    When multiple source records disagree, the first present value is used
    for *display* purposes only -- the classifier's own metadata-based rules
    below key off `attribute_status`/`reason_codes`, not off this value, so
    a conflict here does not silently become a false certainty in any rule.
    """
    lineage = edge.get(LINEAGE_KEY)
    if lineage and lineage.get("source_records"):
        for record in lineage["source_records"]:
            if record.get(f"{field_name}_present"):
                return record.get(field_name)
    return edge.get(field_name, default)


def _edge_geometry(edge: Dict[str, Any], nodes: Sequence[Dict[str, Any]]) -> _EdgeGeometry:
    lineage = edge.get(LINEAGE_KEY) or {}
    source_ids = lineage.get("source_primitive_ids") or []
    node_a = nodes[edge["a"]] if "a" in edge and edge["a"] < len(nodes) else None
    node_b = nodes[edge["b"]] if "b" in edge and edge["b"] < len(nodes) else None
    return _EdgeGeometry(
        primitive_id=str(edge.get("id")),
        x1=float(edge["x1"]), y1=float(edge["y1"]), x2=float(edge["x2"]), y2=float(edge["y2"]),
        length_pt=float(edge.get("length_pt", math.hypot(edge["x2"] - edge["x1"], edge["y2"] - edge["y1"]))),
        orientation_deg=float(edge.get("angle_deg", math.degrees(math.atan2(edge["y2"] - edge["y1"], edge["x2"] - edge["x1"])) % 180.0)),
        native_layer=str(_lineage_native_field(edge, "layer", "") or ""),
        native_dashes=str(_lineage_native_field(edge, "dashes", "") or ""),
        native_width=_lineage_native_field(edge, "width", None),
        reason_codes=tuple(edge.get("reason_codes") or ()),
        junction_degree_a=(node_a or {}).get("degree"),
        junction_degree_b=(node_b or {}).get("degree"),
        source_primitive_count=(len(source_ids) if lineage else None),
    )


def _excluded_segment_geometry(segment: Dict[str, Any]) -> _EdgeGeometry:
    x1, y1, x2, y2 = float(segment["x1"]), float(segment["y1"]), float(segment["x2"]), float(segment["y2"])
    return _EdgeGeometry(
        primitive_id=str(segment.get("id")),
        x1=x1, y1=y1, x2=x2, y2=y2,
        length_pt=math.hypot(x2 - x1, y2 - y1),
        orientation_deg=math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0,
        native_layer=str(segment.get("layer") or ""),
        native_dashes=str(segment.get("dashes") or ""),
        native_width=segment.get("width"),
        reason_codes=tuple(segment.get("reason_codes") or ()),
        junction_degree_a=None,
        junction_degree_b=None,
        source_primitive_count=None,
    )


def _compute_features(geoms: Sequence[_EdgeGeometry]) -> List[PrimitiveFeatures]:
    midpoints = [_midpoint(g.x1, g.y1, g.x2, g.y2) for g in geoms]
    index = _SpatialMidpointIndex(midpoints, cell_size=max(_REPETITION_NEIGHBORHOOD_PT, _PARALLEL_PARTNER_SEARCH_RADIUS_PT))

    features: List[PrimitiveFeatures] = []
    for i, g in enumerate(geoms):
        mx, my = midpoints[i]

        repetition_count = 0
        best_parallel_offset: Optional[float] = None
        for j in index.neighbors_within(mx, my, max(_REPETITION_NEIGHBORHOOD_PT, _PARALLEL_PARTNER_SEARCH_RADIUS_PT)):
            if j == i:
                continue
            other = geoms[j]
            angle_gap = _angle_delta(g.orientation_deg, other.orientation_deg)
            dist = math.hypot(midpoints[j][0] - mx, midpoints[j][1] - my)

            if dist <= _REPETITION_NEIGHBORHOOD_PT and angle_gap <= _REPETITION_ANGLE_TOLERANCE_DEG:
                if g.length_pt > 0 and abs(other.length_pt - g.length_pt) / g.length_pt <= _REPETITION_LENGTH_RELATIVE_TOLERANCE:
                    repetition_count += 1

            if dist <= _PARALLEL_PARTNER_SEARCH_RADIUS_PT and angle_gap <= _PARALLEL_PARTNER_ANGLE_TOLERANCE_DEG:
                offset = _perpendicular_offset(g, other)
                if offset is not None and _PARALLEL_PARTNER_MIN_OFFSET_PT <= offset <= _PARALLEL_PARTNER_MAX_OFFSET_PT:
                    if best_parallel_offset is None or offset < best_parallel_offset:
                        best_parallel_offset = offset

        features.append(
            PrimitiveFeatures(
                primitive_id=g.primitive_id,
                length_pt=g.length_pt,
                orientation_deg=g.orientation_deg,
                is_axis_aligned=min(g.orientation_deg % 90.0, 90.0 - (g.orientation_deg % 90.0)) <= _AXIS_ALIGN_TOLERANCE_DEG,
                native_layer=g.native_layer,
                native_dashes=g.native_dashes,
                native_width=g.native_width,
                reason_codes=g.reason_codes,
                junction_degree_a=g.junction_degree_a,
                junction_degree_b=g.junction_degree_b,
                repetition_neighbor_count=repetition_count,
                has_nearby_parallel_partner=best_parallel_offset is not None,
                nearest_parallel_offset_pt=best_parallel_offset,
                source_primitive_count=g.source_primitive_count,
            )
        )
    return features


def _perpendicular_offset(a: _EdgeGeometry, b: _EdgeGeometry) -> Optional[float]:
    """Perpendicular distance from segment b's midpoint to segment a's own
    infinite line, only when b's projection overlaps a's own span (so a
    perpendicular but spatially-unrelated segment several page-lengths away
    is never reported as a "parallel partner" merely for matching angle)."""
    dx, dy = a.x2 - a.x1, a.y2 - a.y1
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    ux, uy = dx / length, dy / length
    bmx, bmy = _midpoint(b.x1, b.y1, b.x2, b.y2)
    to_mid_x, to_mid_y = bmx - a.x1, bmy - a.y1
    projection = to_mid_x * ux + to_mid_y * uy
    if projection < -length * 0.25 or projection > length * 1.25:
        return None
    perpendicular = abs(to_mid_x * (-uy) + to_mid_y * ux)
    return perpendicular


# ---------------------------------------------------------------------------
# Deterministic rules
# ---------------------------------------------------------------------------

_METADATA_REASON_LABELS = {
    "dimension_layer_excluded": (SemanticClass.DIMENSION_ANNOTATION, EvidenceStrength.STRONG),
    "dashed_line_excluded": (SemanticClass.DIMENSION_ANNOTATION, EvidenceStrength.WEAK),
    "hatch_layer_excluded": (SemanticClass.HATCH, EvidenceStrength.STRONG),
}


def _classify_one(f: PrimitiveFeatures, length_split_threshold: Optional[float]) -> SemanticEvidence:
    matched: List[str] = []

    for code in f.reason_codes:
        if code in _METADATA_REASON_LABELS:
            label, strength = _METADATA_REASON_LABELS[code]
            return SemanticEvidence(f.primitive_id, label, strength, (f"metadata:{code}",), f)
        if code == "text_frame_layer_excluded":
            return SemanticEvidence(
                f.primitive_id, SemanticClass.UNKNOWN, EvidenceStrength.ABSTAIN,
                ("metadata:text_frame_layer_excluded_ambiguous_symbol_or_schedule",), f,
            )

    if length_split_threshold is None:
        is_short = is_long = False
    else:
        is_short = f.length_pt < length_split_threshold * (1.0 - _LONG_SHORT_MARGIN_FRACTION)
        is_long = f.length_pt >= length_split_threshold * (1.0 + _LONG_SHORT_MARGIN_FRACTION)

    if f.repetition_neighbor_count >= _REPETITION_STRONG_THRESHOLD and is_short:
        matched.append(f"repeated_short_neighbors>={_REPETITION_STRONG_THRESHOLD}")
        return SemanticEvidence(f.primitive_id, SemanticClass.HATCH, EvidenceStrength.STRONG, tuple(matched), f)

    if f.repetition_neighbor_count >= _REPETITION_STRONG_THRESHOLD and is_long and f.length_pt >= _GRID_MIN_LENGTH_PT:
        matched.append(f"repeated_long_regular_neighbors>={_REPETITION_STRONG_THRESHOLD}")
        return SemanticEvidence(f.primitive_id, SemanticClass.GRID, EvidenceStrength.WEAK, tuple(matched), f)

    if f.repetition_neighbor_count >= _REPETITION_WEAK_THRESHOLD and is_long and not f.has_nearby_parallel_partner:
        matched.append(f"repeated_long_neighbors_no_partner>={_REPETITION_WEAK_THRESHOLD}")
        return SemanticEvidence(f.primitive_id, SemanticClass.GLAZING, EvidenceStrength.WEAK, tuple(matched), f)

    if (
        f.has_nearby_parallel_partner
        and f.junction_degree_a == 2
        and f.junction_degree_b == 2
        and is_long
    ):
        matched.append("paired_parallel_partner_isolated_long_run")
        return SemanticEvidence(f.primitive_id, SemanticClass.PHYSICAL_WALL_PROBABLE, EvidenceStrength.STRONG, tuple(matched), f)

    if (
        f.junction_degree_a is not None and f.junction_degree_b is not None
        and f.junction_degree_a >= 3 and f.junction_degree_b >= 3
        and is_long
    ):
        matched.append("well_connected_network_long_run")
        return SemanticEvidence(f.primitive_id, SemanticClass.PHYSICAL_WALL_PROBABLE, EvidenceStrength.WEAK, tuple(matched), f)

    if f.repetition_neighbor_count >= _REPETITION_WEAK_THRESHOLD and is_short and not f.is_axis_aligned:
        matched.append(f"repeated_short_off_axis_neighbors>={_REPETITION_WEAK_THRESHOLD}")
        return SemanticEvidence(f.primitive_id, SemanticClass.FURNITURE, EvidenceStrength.WEAK, tuple(matched), f)

    return SemanticEvidence(f.primitive_id, SemanticClass.UNKNOWN, EvidenceStrength.ABSTAIN, ("no_rule_matched",), f)


def classify_wall_graph_evidence(graph: Dict[str, Any]) -> List[SemanticEvidence]:
    """Deterministic semantic evidence for every (non-removed) edge in an
    already-built Stage-A wall graph (pb_wall_room_topology_stage_a.
    build_wall_graph_for_viewport's own output). Read-only: does not mutate
    the graph, does not feed any authority path. See module docstring."""
    edges = [e for e in graph.get("edges", []) if not e.get("_removed")]
    nodes = graph.get("nodes", [])
    geoms = [_edge_geometry(e, nodes) for e in edges]
    features = _compute_features(geoms)
    threshold = _otsu_threshold([g.length_pt for g in geoms])
    return [_classify_one(f, threshold) for f in features]


def classify_excluded_segment_evidence(excluded_segments: Sequence[Dict[str, Any]]) -> List[SemanticEvidence]:
    """Deterministic semantic evidence for the population Stage A's own
    Section 6.11 pre-filter excluded (graph["excluded_segments"]). These
    carry no graph-junction context (they never entered the graph), so
    junction-degree-based rules always abstain for this population; the
    metadata-reason rules and repetition/parallel geometric rules still
    apply using only the segments' own coordinates and reason_codes."""
    geoms = [_excluded_segment_geometry(s) for s in excluded_segments]
    features = _compute_features(geoms)
    threshold = _otsu_threshold([g.length_pt for g in geoms])
    return [_classify_one(f, threshold) for f in features]


# ---------------------------------------------------------------------------
# ML strategy note (deliberately not started -- see architecture doc and the
# standing instruction: "First build a deterministic feature graph + shadow
# evidence interface. Only after that should you assess whether a learned
# classifier is worthwhile.")
#
# This module IS that deterministic feature graph + shadow evidence
# interface. The next step, not started here, is to assess whether a
# learned classifier over `PrimitiveFeatures` (or a richer feature set)
# would out-perform these hand-written rules -- and if so, to source
# training data exclusively from public/synthetic/procedural drawings, never
# from the five development benchmark projects (Baghau, Lamu, Dungicha,
# KSTVET, and the fifth referenced in governance docs), which may only be
# used for qualitative development validation of whichever classifier is
# used, never for fitting its weights or thresholds.
# ---------------------------------------------------------------------------
