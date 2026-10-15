"""Shadow lineage helpers for W2 (U1).

This module does not invent geometry. Intersection splitting still belongs to
``pb_accuracy_v13_engines_v145.split_segments_at_intersections``. These helpers
only associate already-derived fragments with every source primitive that
geometrically contains them, preserve unknownness, and union lineage through
later W2 steps.

Live edge fields historically fabricated after the tuple round-trip
(``width=0.0``, ``layer=""``, ``dashes=""``, ``stroke=None``, ``fill=None``)
stay exactly those sentinels so existing W3–W10 readers are unchanged.
Truth lives in the additive ``primitive_lineage`` payload.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

Point = Tuple[float, float]
SegmentPair = Tuple[Point, Point]

LINEAGE_KEY = "primitive_lineage"
SNAP_COLLAPSE_REASON = "both_endpoints_snapped_to_same_node"

# Intersection points are rounded to 8 decimals by the existing splitter.
_CONTAINMENT_TOL_PT = 1e-5

_ATTRIBUTE_FIELDS = ("width", "stroke", "fill", "layer", "dashes", "clip")
_OWNERSHIP_FIELDS = ("document_id", "page_id", "viewport_id")
_PATH_INDEX_FIELDS = ("path_index", "item_index", "edge_index")
_PAGE_COORD_FIELDS = ("x1", "y1", "x2", "y2")

_ATTRIBUTE_UNKNOWN = "unknown"
_ATTRIBUTE_AGREED = "agreed"
_ATTRIBUTE_CONFLICT = "conflict"


def empty_lineage() -> Dict[str, Any]:
    return {
        "source_primitive_ids": [],
        "source_records": [],
        "attribute_status": {field: _ATTRIBUTE_UNKNOWN for field in _ATTRIBUTE_FIELDS},
        "attribute_conflicts": [],
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_default(item) for item in value]
    if isinstance(value, float):
        return value
    return str(value)


def _record_dedupe_key(record: Mapping[str, Any]) -> str:
    return json.dumps(dict(record), sort_keys=True, default=_json_default, separators=(",", ":"))


def _normalize_attr(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, (list, tuple)):
        return tuple(_normalize_attr(item) for item in value)
    return value


def _has_explicit_presence(segment: Mapping[str, Any], field: str) -> Optional[bool]:
    flag_key = f"{field}_present"
    if flag_key in segment:
        return bool(segment[flag_key])
    return None


def field_is_present(segment: Mapping[str, Any], field: str) -> bool:
    """Conservative presence: sentinels are unknown unless a caller flagged them.

    ``width=0.0``, ``layer=""``, and ``dashes=""`` are the historical extractor
    / split-rebuild sentinels. They must not become evidence that the PDF
    supplied those values. Explicit ``{field}_present`` wins when provided.
    """
    flagged = _has_explicit_presence(segment, field)
    if flagged is not None:
        return flagged
    if field not in segment:
        return False
    value = segment.get(field)
    if field == "width":
        if value is None:
            return False
        try:
            return float(value) != 0.0
        except (TypeError, ValueError):
            return True
    if field in ("layer", "dashes"):
        return str(value).strip() != ""
    if field in ("stroke", "fill", "clip", "kind"):
        return value not in (None, "")
    return value is not None


def source_record_from_segment(segment: Mapping[str, Any]) -> Dict[str, Any]:
    raw_id = segment.get("id")
    source_id = None if raw_id in (None, "") else str(raw_id)
    record: Dict[str, Any] = {
        "id": source_id,
        "kind": segment.get("kind") if field_is_present(segment, "kind") else None,
        "kind_present": field_is_present(segment, "kind"),
        "width": segment.get("width") if "width" in segment else None,
        "width_present": field_is_present(segment, "width"),
        "stroke": copy.deepcopy(segment.get("stroke")) if "stroke" in segment else None,
        "stroke_present": field_is_present(segment, "stroke"),
        "fill": copy.deepcopy(segment.get("fill")) if "fill" in segment else None,
        "fill_present": field_is_present(segment, "fill"),
        "layer": segment.get("layer") if "layer" in segment else None,
        "layer_present": field_is_present(segment, "layer"),
        "dashes": segment.get("dashes") if "dashes" in segment else None,
        "dashes_present": field_is_present(segment, "dashes"),
        "clip": copy.deepcopy(segment.get("clip")) if "clip" in segment else None,
        "clip_present": field_is_present(segment, "clip"),
    }
    # clip_known is additive and independent of clip_present: known-absent
    # (matched association, no active scissor) must not equal unknown
    # (extended API unavailable / missing / unmatched seqno).
    if "clip_known" in segment:
        record["clip_known"] = bool(segment["clip_known"])
    elif record["clip_present"]:
        record["clip_known"] = True
    # Priority-1: retain structured path indices and native page coordinates on
    # the source record so later snap/merge cannot erase native span provenance.
    for field in _PATH_INDEX_FIELDS:
        if field in segment and segment.get(field) is not None:
            try:
                record[field] = int(segment[field])
            except (TypeError, ValueError):
                record[field] = segment[field]
    coords_available = all(field in segment for field in _PAGE_COORD_FIELDS)
    page_coords_present = False
    if coords_available:
        all_finite = True
        for field in _PAGE_COORD_FIELDS:
            try:
                value = float(segment[field])
            except (TypeError, ValueError):
                record[field] = segment[field]
                all_finite = False
                continue
            # Never coerce non-finite geometry to zero; retain the value for
            # diagnostics but refuse page_coords_present authority.
            record[field] = value
            if not math.isfinite(value):
                all_finite = False
        page_coords_present = all_finite
    record["page_coords_present"] = page_coords_present
    for field in _OWNERSHIP_FIELDS:
        if field in segment:
            record[field] = copy.deepcopy(segment[field])
    return record


def _attribute_status_from_records(records: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, str], List[str]]:
    status = {}
    conflicts: List[str] = []
    for field in _ATTRIBUTE_FIELDS:
        present_values = []
        seen = set()
        for record in records:
            if not record.get(f"{field}_present"):
                continue
            normalized = _normalize_attr(record.get(field))
            marker = _record_dedupe_key({field: normalized})
            if marker in seen:
                continue
            seen.add(marker)
            present_values.append(normalized)
        if not present_values:
            status[field] = _ATTRIBUTE_UNKNOWN
        elif len(present_values) == 1:
            status[field] = _ATTRIBUTE_AGREED
        else:
            status[field] = _ATTRIBUTE_CONFLICT
            conflicts.append(field)
    return status, conflicts


def lineage_from_source_segments(segments: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    seen_keys = set()
    ids: List[str] = []
    seen_ids = set()
    for segment in segments:
        record = source_record_from_segment(segment)
        key = _record_dedupe_key(record)
        if key not in seen_keys:
            seen_keys.add(key)
            records.append(record)
        source_id = record.get("id")
        if source_id and source_id not in seen_ids:
            seen_ids.add(source_id)
            ids.append(source_id)
    records.sort(key=lambda item: (item.get("id") is None, str(item.get("id") or ""), _record_dedupe_key(item)))
    ids.sort()
    status, conflicts = _attribute_status_from_records(records)
    return {
        "source_primitive_ids": ids,
        "source_records": records,
        "attribute_status": status,
        "attribute_conflicts": conflicts,
    }


def union_lineage(*payloads: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    seen_keys = set()
    ids: List[str] = []
    seen_ids = set()
    for payload in payloads:
        if not payload:
            continue
        for record in payload.get("source_records") or []:
            copied = copy.deepcopy(dict(record))
            key = _record_dedupe_key(copied)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            records.append(copied)
        for source_id in payload.get("source_primitive_ids") or []:
            text = str(source_id)
            if text and text not in seen_ids:
                seen_ids.add(text)
                ids.append(text)
    records.sort(key=lambda item: (item.get("id") is None, str(item.get("id") or ""), _record_dedupe_key(item)))
    ids.sort()
    status, conflicts = _attribute_status_from_records(records)
    return {
        "source_primitive_ids": ids,
        "source_records": records,
        "attribute_status": status,
        "attribute_conflicts": conflicts,
    }


def lineage_from_edges(*edges: Mapping[str, Any]) -> Dict[str, Any]:
    return union_lineage(*(edge.get(LINEAGE_KEY) for edge in edges))


def collinear_merge_leaf_edge_ids(*edges: Mapping[str, Any]) -> List[str]:
    leaves: List[str] = []
    seen = set()
    for edge in edges:
        nested = edge.get("collinear_merge_leaf_edge_ids")
        candidates = list(nested) if nested else [edge.get("id")]
        for item in candidates:
            if item in (None, ""):
                continue
            text = str(item)
            if text not in seen:
                seen.add(text)
                leaves.append(text)
    leaves.sort()
    return leaves


def _point_on_segment(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    tol: float = _CONTAINMENT_TOL_PT,
) -> bool:
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= tol:
        return math.hypot(px - x1, py - y1) <= tol
    cross = abs((px - x1) * dy - (py - y1) * dx)
    if cross > tol * length:
        return False
    dot = (px - x1) * dx + (py - y1) * dy
    return -tol * length <= dot <= (length * length) + (tol * length)


def fragment_contained_in_segment(
    fragment: SegmentPair,
    segment: Mapping[str, Any],
    *,
    tol: float = _CONTAINMENT_TOL_PT,
) -> bool:
    (x1, y1), (x2, y2) = fragment
    if math.hypot(x2 - x1, y2 - y1) <= tol:
        return False
    sx1 = float(segment["x1"])
    sy1 = float(segment["y1"])
    sx2 = float(segment["x2"])
    sy2 = float(segment["y2"])
    return _point_on_segment(x1, y1, sx1, sy1, sx2, sy2, tol=tol) and _point_on_segment(
        x2, y2, sx1, sy1, sx2, sy2, tol=tol
    )


# Splitter residual slivers can be longer than the point-on-segment
# tolerance yet still have an unstable computed direction. Those fragments
# must not occupy a direction-keyed bucket that looks non-empty.
_UNSTABLE_DIRECTION_LENGTH_PT = 0.05
_BUCKET_ROUND_DECIMALS = 2
_BUCKET_STEP = 10.0 ** (-_BUCKET_ROUND_DECIMALS)
_BUCKET_NEIGHBOR_OFFSETS = (-_BUCKET_STEP, 0.0, _BUCKET_STEP)


def _line_bucket_key(x1: float, y1: float, x2: float, y2: float) -> Tuple[Any, ...]:
    """Group collinear strokes so extra-parent search is not a full fragment×source scan.

    Coarse 2-decimal cells plus neighbor lookup are required because two
    genuinely collinear parents can disagree in computed offset by ~3e-4.
    A 4-decimal single-cell lookup can return a non-empty incomplete set,
    so empty-only fallback never runs.
    """
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= _UNSTABLE_DIRECTION_LENGTH_PT:
        return ("point", round(x1, _BUCKET_ROUND_DECIMALS), round(y1, _BUCKET_ROUND_DECIMALS))
    ux, uy = dx / length, dy / length
    if ux < 0 or (ux == 0.0 and uy < 0):
        ux, uy = -ux, -uy
    offset = x1 * (-uy) + y1 * ux
    return (
        round(ux, _BUCKET_ROUND_DECIMALS),
        round(uy, _BUCKET_ROUND_DECIMALS),
        round(offset, _BUCKET_ROUND_DECIMALS),
    )


def source_line_bucket(segment: Mapping[str, Any]) -> Tuple[Any, ...]:
    return _line_bucket_key(
        float(segment["x1"]),
        float(segment["y1"]),
        float(segment["x2"]),
        float(segment["y2"]),
    )


def fragment_line_bucket(fragment: SegmentPair) -> Tuple[Any, ...]:
    (x1, y1), (x2, y2) = fragment
    return _line_bucket_key(x1, y1, x2, y2)


def fragment_line_bucket_neighbors(fragment: SegmentPair) -> List[Tuple[Any, ...]]:
    """Primary line bucket plus adjacent quantized cells.

    A matching source and fragment can land on opposite sides of one
    rounding boundary. Neighbor cells keep the exact containment test as
    the authority; this only widens the candidate set.
    """
    key = fragment_line_bucket(fragment)
    if key[0] == "point":
        return [key]
    kx, ky, koffset = key
    return [
        (
            round(kx + dx, _BUCKET_ROUND_DECIMALS),
            round(ky + dy, _BUCKET_ROUND_DECIMALS),
            round(koffset + doffset, _BUCKET_ROUND_DECIMALS),
        )
        for dx in _BUCKET_NEIGHBOR_OFFSETS
        for dy in _BUCKET_NEIGHBOR_OFFSETS
        for doffset in _BUCKET_NEIGHBOR_OFFSETS
    ]


def sources_for_fragment(
    fragment: SegmentPair,
    source_segments: Sequence[Mapping[str, Any]],
) -> List[Mapping[str, Any]]:
    """Return every source that can own this fragment. Never first/nearest/smallest."""
    return [segment for segment in source_segments if fragment_contained_in_segment(fragment, segment)]


# Candidate search only; the exact ownership decision remains
# ``fragment_contained_in_segment``. A source capable of containing a fragment
# must have an endpoint-expanded bounding box covering both fragment endpoints.
# Index those boxes once so bucket misses never fall back to a full source scan.
_CONTAINMENT_GRID_CELL_PT = 64.0
_CONTAINMENT_GRID_MAX_CELLS_PER_SOURCE = 4096


def _containment_grid_cell(point: Tuple[float, float]) -> Tuple[int, int]:
    return (
        math.floor(float(point[0]) / _CONTAINMENT_GRID_CELL_PT),
        math.floor(float(point[1]) / _CONTAINMENT_GRID_CELL_PT),
    )


def _build_source_containment_grid(
    source_segments: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[Tuple[int, int], set[int]], set[int]]:
    grid: Dict[Tuple[int, int], set[int]] = {}
    global_indexes: set[int] = set()
    cell = _CONTAINMENT_GRID_CELL_PT
    tol = _CONTAINMENT_TOL_PT
    for index, segment in enumerate(source_segments):
        x1 = float(segment["x1"])
        y1 = float(segment["y1"])
        x2 = float(segment["x2"])
        y2 = float(segment["y2"])
        min_x = math.floor((min(x1, x2) - tol) / cell)
        max_x = math.floor((max(x1, x2) + tol) / cell)
        min_y = math.floor((min(y1, y2) - tol) / cell)
        max_y = math.floor((max(y1, y2) + tol) / cell)
        cell_count = (max_x - min_x + 1) * (max_y - min_y + 1)
        if cell_count > _CONTAINMENT_GRID_MAX_CELLS_PER_SOURCE:
            # Pathological source spans stay globally eligible rather than being
            # dropped from the candidate set. This preserves exactness.
            global_indexes.add(index)
            continue
        for cell_x in range(min_x, max_x + 1):
            for cell_y in range(min_y, max_y + 1):
                grid.setdefault((cell_x, cell_y), set()).add(index)
    return grid, global_indexes


def _containment_grid_candidates(
    fragment: SegmentPair,
    source_segments: Sequence[Mapping[str, Any]],
    grid: Mapping[Tuple[int, int], set[int]],
    global_indexes: set[int],
) -> List[Mapping[str, Any]]:
    first_cell = _containment_grid_cell(fragment[0])
    second_cell = _containment_grid_cell(fragment[1])
    first = grid.get(first_cell, set())
    second = grid.get(second_cell, set())
    indexes = (
        set(first)
        if first_cell == second_cell
        else set(first).intersection(second)
    )
    indexes.update(global_indexes)
    return [source_segments[index] for index in sorted(indexes)]


def isolated_lineage(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return copy.deepcopy(payload) if payload else empty_lineage()


def isolate_graph_lineage(graph: Mapping[str, Any]) -> Dict[str, Any]:
    """Give every edge its own nested lineage container after shallow snap/merge copies."""
    for edge in graph.get("edges") or []:
        edge[LINEAGE_KEY] = isolated_lineage(edge.get(LINEAGE_KEY))
    return dict(graph)


def fabricated_live_fields() -> Dict[str, Any]:
    """Historical post-split sentinels. Not evidence that the PDF supplied them."""
    return {
        "kind": "line",
        "width": 0.0,
        "stroke": None,
        "fill": None,
        "layer": "",
        "dashes": "",
    }


# --------------------------------------------------------------------------------------------------------------------------
# Throughput helpers for ``attach_lineage_to_split_fragments``.  None of them changes WHICH sources own a fragment, the order in
# which owners are tried, or the emitted payload; they only avoid repeating work whose result is already determined.
# --------------------------------------------------------------------------------------------------------------------------

# A source passes ``fragment_contained_in_segment`` only if each fragment endpoint lies in the oriented rectangle
# [-tol, length + tol] x [-tol, +tol] around the source.  That rectangle's axis-aligned box extends beyond the source's own
# box by at most tol * (|ux| + |uy|) <= sqrt(2) * tol per side.  Four tolerances therefore leave a margin of more than 2.8 tol
# over the worst case and more than six orders of magnitude over double rounding for page coordinates, so the box test below can
# only discard candidates the exact predicate would also reject.  The exact predicate still makes every ownership decision.
_PREFILTER_MARGIN_PT = 4.0 * _CONTAINMENT_TOL_PT
_PREFILTER_MIN_CANDIDATES = 16
# 16x float overflow headroom for differences, dot/cross and squared length.
# Inputs outside this range are never discarded by the optional box filter:
# legacy _point_on_segment remains the sole parent authority, even on overflow.
_PREFILTER_SAFE_ABS_PT = math.sqrt(sys.float_info.max) / 16.0


class _BoxPrefilter:
    """Axis-aligned, margin-expanded boxes for one candidate list; ``select`` keeps list order."""

    __slots__ = ("_segments", "_bounds")

    def __init__(self, segments: Sequence[Mapping[str, Any]]) -> None:
        self._segments = segments
        self._bounds = None

    def _build(self):
        import numpy as np

        count = len(self._segments)
        columns = [
            np.fromiter((float(segment[field]) for segment in self._segments), dtype=float, count=count)
            for field in _PAGE_COORD_FIELDS
        ]
        x1, y1, x2, y2 = columns
        finite = np.isfinite(x1) & np.isfinite(y1) & np.isfinite(x2) & np.isfinite(y2)
        # A finite endpoint can still overflow the unchanged exact predicate's
        # subtraction, hypot, cross, dot or squared-length arithmetic. Those
        # parents must stay candidates, NEVER be AABB-pruned.
        safe = _PREFILTER_SAFE_ABS_PT
        finite &= (np.abs(x1) <= safe) & (np.abs(y1) <= safe)
        finite &= (np.abs(x2) <= safe) & (np.abs(y2) <= safe)
        margin = _PREFILTER_MARGIN_PT
        # a source with a non-finite coordinate is never discarded; the exact predicate decides
        self._bounds = (
            np.where(finite, np.minimum(x1, x2) - margin, -np.inf),
            np.where(finite, np.maximum(x1, x2) + margin, np.inf),
            np.where(finite, np.minimum(y1, y2) - margin, -np.inf),
            np.where(finite, np.maximum(y1, y2) + margin, np.inf),
        )
        return self._bounds

    def select(self, lo_x: float, hi_x: float, lo_y: float, hi_y: float) -> List[Mapping[str, Any]]:
        import numpy as np

        xmin, xmax, ymin, ymax = self._bounds or self._build()
        keep = (xmin <= lo_x) & (xmax >= hi_x) & (ymin <= lo_y) & (ymax >= hi_y)
        segments = self._segments
        return [segments[i] for i in np.flatnonzero(keep).tolist()]

    def select_indexes(self, indexes: Sequence[int], lo_x: float, hi_x: float, lo_y: float, hi_y: float) -> List[int]:
        """The members of ``indexes`` (positions in this prefilter's segment list) that may contain the fragment box, in order."""
        import numpy as np

        xmin, xmax, ymin, ymax = self._bounds or self._build()
        chosen = np.asarray(indexes, dtype=np.intp)
        keep = (xmin[chosen] <= lo_x) & (xmax[chosen] >= hi_x) & (ymin[chosen] <= lo_y) & (ymax[chosen] >= hi_y)
        return chosen[keep].tolist()


def _containment_grid_candidate_indexes(
    fragment: SegmentPair,
    grid: Mapping[Tuple[int, int], set[int]],
    global_indexes: set[int],
) -> List[int]:
    """Positions of ``_containment_grid_candidates`` (same selection, same ascending order)."""
    first_cell = _containment_grid_cell(fragment[0])
    second_cell = _containment_grid_cell(fragment[1])
    first = grid.get(first_cell, set())
    second = grid.get(second_cell, set())
    indexes = set(first) if first_cell == second_cell else set(first).intersection(second)
    indexes.update(global_indexes)
    return sorted(indexes)


def _fragment_box(pair: SegmentPair) -> Optional[Tuple[float, float, float, float]]:
    """Fragment AABB only when exact containment arithmetic has safe float headroom."""
    try:
        x1, y1 = float(pair[0][0]), float(pair[0][1])
        x2, y2 = float(pair[1][0]), float(pair[1][1])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) and abs(v) <= _PREFILTER_SAFE_ABS_PT for v in (x1, y1, x2, y2)):
        # Even finite 1e308 endpoints can cause legacy cross/dot overflow and
        # permit parents outside a finite AABB; do not prune them.
        return None
    return (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))


def _copy_json_like(value: Any) -> Any:
    """``copy.deepcopy`` for the plain dict/list/tuple/scalar structures a lineage payload is made of.

    Any other type is delegated to ``copy.deepcopy`` so the result is always what a deep copy would return.  Lineage payloads
    hold no shared or cyclic substructure, so the missing memo table cannot change the result.
    """
    kind = type(value)
    if kind is dict:
        return {key: _copy_json_like(item) for key, item in value.items()}
    if kind is list:
        return [_copy_json_like(item) for item in value]
    if kind is tuple:
        return tuple(_copy_json_like(item) for item in value)
    if kind in (str, int, float, bool, type(None)):
        return value
    return copy.deepcopy(value)


class _ParentLineageBuilder:
    """``lineage_from_source_segments`` with per-source work and per-parent-set results computed once per call.

    The payload is a function of the SET of parent segments only (records are de-duplicated by content and sorted by a total
    order; ids are de-duplicated and sorted), so equal parent sets share one payload.  Callers receive deep copies.
    """

    def __init__(self) -> None:
        self._source: Dict[int, Tuple[Dict[str, Any], str]] = {}
        self._payload: Dict[frozenset, Dict[str, Any]] = {}

    def _record(self, segment: Mapping[str, Any]) -> Tuple[Dict[str, Any], str]:
        entry = self._source.get(id(segment))
        if entry is None:
            record = source_record_from_segment(segment)
            entry = (record, _record_dedupe_key(record))
            self._source[id(segment)] = entry
        return entry

    def payload(self, parents: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        entries = [self._record(segment) for segment in parents]
        signature = frozenset(id(segment) for segment in parents)
        cached = self._payload.get(signature)
        if cached is not None:
            return cached
        records: List[Dict[str, Any]] = []
        keys: List[str] = []
        seen_keys = set()
        ids: List[str] = []
        seen_ids = set()
        for record, key in entries:
            if key not in seen_keys:
                seen_keys.add(key)
                records.append(record)
                keys.append(key)
            source_id = record.get("id")
            if source_id and source_id not in seen_ids:
                seen_ids.add(source_id)
                ids.append(source_id)
        order = sorted(
            range(len(records)),
            key=lambda i: (records[i].get("id") is None, str(records[i].get("id") or ""), keys[i]),
        )
        records = [records[i] for i in order]
        ids.sort()
        status, conflicts = _attribute_status_from_records(records)
        built = {
            "source_primitive_ids": ids,
            "source_records": records,
            "attribute_status": status,
            "attribute_conflicts": conflicts,
        }
        self._payload[signature] = built
        return built


def attach_lineage_to_split_fragments(
    split_pairs: Sequence[SegmentPair],
    source_segments: Sequence[Mapping[str, Any]],
    *,
    id_prefix: str = "split",
    source_parent_indexes: Sequence[int] | None = None,
) -> List[Dict[str, Any]]:
    """Rebuild the historical split-dict shape plus additive plural lineage.

    Official split geometry is caller-supplied. Extra parents are taken only
    from the same collinear bucket so this is not a second global n² pass.
    """
    if source_parent_indexes is not None and (
        not isinstance(source_parent_indexes, (list, tuple))
        or len(source_parent_indexes) != len(split_pairs)
        or any(type(i) is not int or not 0 <= i < len(source_segments)
               for i in source_parent_indexes)
    ):
        raise ValueError("exact split source parent inventory invalid")
    buckets: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = {}
    for segment in source_segments:
        buckets.setdefault(source_line_bucket(segment), []).append(segment)
    containment_grid, global_containment_indexes = _build_source_containment_grid(
        source_segments
    )

    prefilters: Dict[Tuple[Any, ...], _BoxPrefilter] = {}
    source_prefilter: Optional[_BoxPrefilter] = None
    lineage_builder = _ParentLineageBuilder()
    out: List[Dict[str, Any]] = []
    for idx, pair in enumerate(split_pairs):
        p1, p2 = pair
        seen_candidates: set[int] = set()
        candidates: List[Mapping[str, Any]] = []
        box = _fragment_box(pair)
        for neighbor_key in fragment_line_bucket_neighbors(pair):
            bucket = buckets.get(neighbor_key)
            if not bucket:
                continue
            if box is not None and len(bucket) >= _PREFILTER_MIN_CANDIDATES:
                prefilter = prefilters.get(neighbor_key)
                if prefilter is None:
                    prefilter = prefilters[neighbor_key] = _BoxPrefilter(bucket)
                bucket = prefilter.select(*box)
            for candidate in bucket:
                marker = id(candidate)
                if marker in seen_candidates:
                    continue
                seen_candidates.add(marker)
                candidates.append(candidate)
        # The endpoint grid is conservative and complete for the exact
        # containment predicate: every true parent must cover both endpoints
        # within the existing containment tolerance. Union it with the line
        # buckets, then retain the unchanged exact test below.
        grid_indexes = _containment_grid_candidate_indexes(
            pair, containment_grid, global_containment_indexes
        )
        if box is not None and len(grid_indexes) >= _PREFILTER_MIN_CANDIDATES:
            if source_prefilter is None:
                source_prefilter = _BoxPrefilter(source_segments)
            grid_indexes = source_prefilter.select_indexes(grid_indexes, *box)
        for candidate in (source_segments[index] for index in grid_indexes):
            marker = id(candidate)
            if marker in seen_candidates:
                continue
            seen_candidates.add(marker)
            candidates.append(candidate)
        parents = sources_for_fragment(pair, candidates)
        if source_parent_indexes is not None:
            # Shadow only: this parent is captured inside the splitter's own
            # source emission loop, never elected by geometry/proximity. The
            # unchanged endpoint predicate guards the rounded derived span;
            # other genuine plural parents remain retained above.
            origin = source_segments[source_parent_indexes[idx]]
            coords = (*p1, *p2)
            if (not all(math.isfinite(float(v)) for v in coords) or p1 == p2
                    or not all(_point_on_segment(
                        *point, *(float(origin[k]) for k in _PAGE_COORD_FIELDS)
                    ) for point in pair)):
                raise ValueError("exact split origin contradicts fragment geometry")
            if all(origin is not parent for parent in parents):
                parents.append(origin)
        fragment = {
            "id": f"{id_prefix}_{idx}",
            "x1": p1[0],
            "y1": p1[1],
            "x2": p2[0],
            "y2": p2[1],
            **fabricated_live_fields(),
            LINEAGE_KEY: _copy_json_like(lineage_builder.payload(parents)),
        }
        out.append(fragment)
    return out


def observe_snap_collapsed_fragments(
    split_fragments: Sequence[Mapping[str, Any]],
    snapped_graph: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    surviving_ids = {edge.get("id") for edge in snapped_graph.get("edges") or []}
    collapsed: List[Dict[str, Any]] = []
    for fragment in split_fragments:
        fragment_id = fragment.get("id")
        if fragment_id in surviving_ids:
            continue
        collapsed.append(
            {
                "id": fragment_id,
                "reason": SNAP_COLLAPSE_REASON,
                LINEAGE_KEY: isolated_lineage(fragment.get(LINEAGE_KEY)),
                "x1": fragment.get("x1"),
                "y1": fragment.get("y1"),
                "x2": fragment.get("x2"),
                "y2": fragment.get("y2"),
            }
        )
    return collapsed
