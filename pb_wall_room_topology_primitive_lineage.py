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


def _lineage_from_single_source_segment(segment: Mapping[str, Any]) -> Dict[str, Any]:
    """Exact one-record lineage without generic dedupe / JSON canonicalization."""
    record = source_record_from_segment(segment)
    source_id = record.get("id")
    status = {
        field: (
            _ATTRIBUTE_AGREED
            if record.get(f"{field}_present")
            else _ATTRIBUTE_UNKNOWN
        )
        for field in _ATTRIBUTE_FIELDS
    }
    return {
        "source_primitive_ids": [str(source_id)] if source_id else [],
        "source_records": [record],
        "attribute_status": status,
        "attribute_conflicts": [],
    }


def lineage_from_source_segments(segments: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if len(segments) == 1:
        return _lineage_from_single_source_segment(segments[0])
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
            copied = _clone_source_record(record)
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


_IMMUTABLE_LINEAGE_SCALARS = (str, bytes, int, float, bool, type(None))


def _clone_lineage_value(value: Any) -> Any:
    """Clone mutable lineage containers while sharing proven-immutable leaves."""
    value_type = type(value)
    if value_type in _IMMUTABLE_LINEAGE_SCALARS:
        return value
    if value_type is tuple:
        # The production source-record tuples are numeric/color tuples. Share
        # them when every child is an exact immutable scalar; otherwise recurse
        # so extension tuples containing mutable children remain isolated.
        if all(type(item) in _IMMUTABLE_LINEAGE_SCALARS for item in value):
            return value
        return tuple(_clone_lineage_value(item) for item in value)
    if value_type is list:
        # Lists themselves must never alias, but the overwhelmingly common clip
        # coordinate lists contain only immutable scalars and can be copied in C.
        if all(type(item) in _IMMUTABLE_LINEAGE_SCALARS for item in value):
            return list(value)
        return [_clone_lineage_value(item) for item in value]
    if value_type is dict:
        if all(type(item) in _IMMUTABLE_LINEAGE_SCALARS for item in value.values()):
            return dict(value)
        return {key: _clone_lineage_value(item) for key, item in value.items()}
    if value_type is set:
        if all(type(item) in _IMMUTABLE_LINEAGE_SCALARS for item in value):
            return set(value)
        return {_clone_lineage_value(item) for item in value}
    # Preserve subclass / extension semantics exactly as the defensive fallback.
    if isinstance(value, _IMMUTABLE_LINEAGE_SCALARS):
        return value
    if isinstance(value, tuple):
        return tuple(_clone_lineage_value(item) for item in value)
    if isinstance(value, list):
        return [_clone_lineage_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _clone_lineage_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return {_clone_lineage_value(item) for item in value}
    return copy.deepcopy(value)


def _clone_source_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: _clone_lineage_value(value)
        for key, value in record.items()
    }


def isolated_lineage(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return empty_lineage()
    return {
        "source_primitive_ids": [
            _clone_lineage_value(value)
            for value in (payload.get("source_primitive_ids") or ())
        ],
        "source_records": [
            _clone_source_record(record)
            for record in (payload.get("source_records") or ())
        ],
        "attribute_status": dict(payload.get("attribute_status") or {}),
        "attribute_conflicts": [
            _clone_lineage_value(value)
            for value in (payload.get("attribute_conflicts") or ())
        ],
    }


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


def attach_lineage_to_split_fragments(
    split_pairs: Sequence[SegmentPair],
    source_segments: Sequence[Mapping[str, Any]],
    *,
    id_prefix: str = "split",
    primary_source_indexes: Optional[Sequence[int]] = None,
    isolate_lineage: bool = True,
) -> List[Dict[str, Any]]:
    """Rebuild the historical split-dict shape plus additive plural lineage.

    Official split geometry is caller-supplied. Extra parents are taken only
    from the same collinear bucket so this is not a second global n² pass.
    When the splitter supplies the source index that emitted each fragment,
    that guaranteed parent is preserved instead of being rediscovered.
    """
    if primary_source_indexes is not None and len(primary_source_indexes) != len(split_pairs):
        raise ValueError("primary_source_indexes must align 1:1 with split_pairs")

    buckets: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = {}
    source_bounds: Dict[int, Tuple[float, float, float, float]] = {}
    single_source_lineage: Dict[int, Dict[str, Any]] = {}
    multi_source_lineage: Dict[Tuple[int, ...], Dict[str, Any]] = {}
    for segment in source_segments:
        buckets.setdefault(source_line_bucket(segment), []).append(segment)
        sx1 = float(segment["x1"])
        sy1 = float(segment["y1"])
        sx2 = float(segment["x2"])
        sy2 = float(segment["y2"])
        source_bounds[id(segment)] = (
            min(sx1, sx2),
            min(sy1, sy2),
            max(sx1, sx2),
            max(sy1, sy2),
        )

    out: List[Dict[str, Any]] = []
    for idx, pair in enumerate(split_pairs):
        p1, p2 = pair
        fragment_bounds = (
            min(float(p1[0]), float(p2[0])),
            min(float(p1[1]), float(p2[1])),
            max(float(p1[0]), float(p2[0])),
            max(float(p1[1]), float(p2[1])),
        )
        seen_candidates: set[int] = set()
        candidates: List[Mapping[str, Any]] = []
        if primary_source_indexes is not None:
            primary_index = int(primary_source_indexes[idx])
            if primary_index < 0 or primary_index >= len(source_segments):
                raise ValueError("primary source index is outside source_segments")
            primary = source_segments[primary_index]
            marker = id(primary)
            seen_candidates.add(marker)
            candidates.append(primary)
        for neighbor_key in fragment_line_bucket_neighbors(pair):
            for candidate in buckets.get(neighbor_key, ()):
                marker = id(candidate)
                if marker in seen_candidates:
                    continue
                seen_candidates.add(marker)
                sx0, sy0, sx1, sy1 = source_bounds[marker]
                fx0, fy0, fx1, fy1 = fragment_bounds
                # Necessary condition only: every true segment parent must
                # contain both fragment endpoints, therefore its AABB must
                # contain the fragment AABB within the exact containment
                # tolerance.  The authoritative geometric predicate below is
                # unchanged and still decides every surviving candidate.
                if (
                    sx0 - _CONTAINMENT_TOL_PT > fx0
                    or sy0 - _CONTAINMENT_TOL_PT > fy0
                    or sx1 + _CONTAINMENT_TOL_PT < fx1
                    or sy1 + _CONTAINMENT_TOL_PT < fy1
                ):
                    continue
                candidates.append(candidate)
        parents = sources_for_fragment(pair, candidates)
        if not parents:
            # Splitter endpoints are rounded to 8 decimals. A fragment can
            # leave its source's coarse line bucket while still lying on the
            # source. Scan sources only for that miss — not every fragment.
            parents = sources_for_fragment(pair, source_segments)
        if len(parents) == 1 and primary_source_indexes is not None:
            marker = id(parents[0])
            cached = single_source_lineage.get(marker)
            if cached is None:
                cached = lineage_from_source_segments((parents[0],))
                single_source_lineage[marker] = cached
            lineage = isolated_lineage(cached) if isolate_lineage else cached
        else:
            parent_key = tuple(sorted(id(parent) for parent in parents))
            derived_lineage = multi_source_lineage.get(parent_key)
            if derived_lineage is None:
                derived_lineage = lineage_from_source_segments(parents)
                multi_source_lineage[parent_key] = derived_lineage
            lineage = (
                isolated_lineage(derived_lineage)
                if isolate_lineage
                else derived_lineage
            )
        fragment = {
            "id": f"{id_prefix}_{idx}",
            "x1": p1[0],
            "y1": p1[1],
            "x2": p2[0],
            "y2": p2[1],
            **fabricated_live_fields(),
            LINEAGE_KEY: lineage,
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
