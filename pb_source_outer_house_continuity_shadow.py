"""Shadow: outer-house / garage continuity without discarding structural ink.

The unique closed painted ring can be only a left/central fragment. Bars
outside that ring keep native path IDs and PDF-point bounds. Proven ALFRESCO /
PORCH / POST source labels may leave the thermal envelope; Living / Bed / garage
structure may not. Near-miss component seams are unique-or-abstain. Distance
is never a 2.5 pt commercial snap.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import box
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from pb_new_wall_graph_diagnostic import inspect_native_wall_graph
from pb_source_native_exterior_endpoint_authority_shadow import (
    CONTACT_PT,
    REASON_NEAR_MISS,
    ROLE_EXCLUSION,
    ROLE_EXTERIOR_OUTER_FACE,
    ROLE_INTERNAL_WALL,
    authenticate_external_wall_junction,
    classify_source_native_path_role,
)
from pb_source_native_wall_body_junction_graph_shadow import _unique_source_wall_bars
from pb_source_spatial_subdivision_shadow import _is_outdoor_name

ROLE_STRUCTURAL = "structural_house_or_garage_candidate"
ROLE_OUTDOOR = "source_named_outdoor_excluded_from_envelope"
ROLE_POST = "source_named_isolated_post_not_wall"
ROLE_UNPROVEN = "outside_bar_unproven_keep_structural"
SNAP_PT = 2.5
_HOUSE_TOKENS = (
    " BED ", " BEDROOM ", " LIVING ", " LOUNGE ", " GARAGE ", " KITCHEN ",
    " DINING ", " FAMILY ", " RUMPUS ", " THEATRE ", " STUDY ",
)
_POST_TOKENS = (" POST ", " TIMBER POST ", " COLUMN ", " PIER ")


def _path_ids(bar: Any) -> tuple[int, ...]:
    return tuple(sorted({int(v) for v in bar.native_path_indices()}))


def _word_records(
    words: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> tuple[tuple[str, tuple[float, float, float, float]], ...]:
    out = []
    for word in words:
        try:
            if isinstance(word, Mapping):
                raw = str(word.get("text") or "")
                bounds = tuple(float(v) for v in word["bbox_pdf_pts"])
            else:
                raw = str(word[4])
                bounds = tuple(float(v) for v in word[:4])
            if len(bounds) != 4 or not all(map(math.isfinite, bounds)):
                continue
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                continue
            out.append((raw, bounds))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return tuple(out)


def _padded_name(text: str) -> str:
    import re
    return " " + re.sub(r"[^A-Z ]", " ", str(text).upper()) + " "


def _is_house_name(text: str) -> bool:
    padded = _padded_name(text)
    return any(token in padded for token in _HOUSE_TOKENS)


def _is_post_name(text: str) -> bool:
    padded = _padded_name(text)
    return any(token in padded for token in _POST_TOKENS)


def _overlapping_names(bar: Any, records: Sequence[tuple[str, tuple[float, float, float, float]]]) -> tuple[str, ...]:
    geom = bar.polygon.buffer(CONTACT_PT * 4)
    hits = []
    for text, bounds in records:
        if geom.intersects(box(*bounds)):
            hits.append(text)
    return tuple(hits)


def classify_outside_envelope_role(
    bar: Any,
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
) -> tuple[str, str]:
    """Unique source labels only. X-thresholds and largest-polygon are not roles."""
    paths = _path_ids(bar)
    # A composite wall strip can have several original PDF path owners.
    # A nearby printed PORCH/ALFRESCO label is a *space* semantic, not proof
    # that any independently painted physical wall beside it is disposable.
    owner_roles = {
        classify_source_native_path_role(drawings[idx])
        for idx in paths if 0 <= idx < len(drawings)
    }
    names = _overlapping_names(bar, _word_records(source_words))
    outdoor = tuple(name for name in names if _is_outdoor_name(name))
    house = tuple(name for name in names if _is_house_name(name))
    post = tuple(name for name in names if _is_post_name(name))
    bounds = bar.polygon.bounds
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    compact_post = (
        width > 0 and height > 0
        and max(width, height) / min(width, height) <= 1.7
    )
    if house and outdoor:
        return ROLE_STRUCTURAL, "shared_house_outdoor_wall_kept_as_envelope"
    # A uniquely marked compact post is a discrete element, not a long
    # masonry wall crossing a PORCH/POST annotation.
    if len(set(map(_padded_name, post))) == 1 and not house and compact_post:
        return ROLE_POST, "source_named_compact_post_not_wall"
    if (
        ROLE_EXTERIOR_OUTER_FACE in owner_roles
        or ROLE_INTERNAL_WALL in owner_roles
    ):
        return ROLE_STRUCTURAL, "original_source_wall_kept_despite_outdoor_text"
    # Genuine green/site/roof/hatch exclusion is independently source-owned.
    # Mixed source roles cannot use one excluded component to drop another.
    if owner_roles == {ROLE_EXCLUSION} and not house:
        return ROLE_OUTDOOR, "source_exclusion_site_roof_hatch_title_green"
    if outdoor:
        return ROLE_UNPROVEN, "outdoor_name_alone_does_not_exclude_wall"
    return ROLE_UNPROVEN, "outside_structural_ink_not_droppable"


def bar_proven_outside_envelope(
    bar: Any,
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
) -> bool:
    role, _reason = classify_outside_envelope_role(bar, drawings, source_words)
    return role in {ROLE_OUTDOOR, ROLE_POST}


def authenticate_outer_house_seams(
    bars: Sequence[Any],
    drawings: Sequence[Mapping[str, Any] | object],
) -> tuple[dict[str, object], ...]:
    """Inter-component near-misses. Representation contact only; no snap."""
    valid = [
        bar for bar in bars
        if getattr(bar, "polygon", None) is not None and not bar.polygon.is_empty
    ]
    if len(valid) < 2:
        return ()
    buffered = [bar.polygon.buffer(CONTACT_PT, join_style=2) for bar in valid]
    tree = STRtree(buffered)
    parent = list(range(len(valid)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i, geom in enumerate(buffered):
        for j in tree.query(geom, predicate="intersects"):
            j = int(j)
            if i == j:
                continue
            a, b = find(i), find(j)
            if a != b:
                parent[max(a, b)] = min(a, b)
    receipts = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for i, left in enumerate(valid):
        for j in range(i + 1, len(valid)):
            if find(i) == find(j):
                continue
            a, b = nearest_points(left.polygon, valid[j].polygon)
            sep = float(a.distance(b))
            if not math.isfinite(sep) or sep > SNAP_PT:
                continue
            left_ids, right_ids = _path_ids(left), _path_ids(valid[j])
            pair = tuple(sorted((left_ids, right_ids)))
            if pair in seen:
                continue
            seen.add(pair)
            status, reason = authenticate_external_wall_junction(
                native_path_ids=left_ids,
                nearby_native_path_ids=right_ids,
                separation_pdf_pts=sep,
                drawings=drawings,
            )
            receipts.append({
                "left_path_ids": list(left_ids),
                "right_path_ids": list(right_ids),
                "separation_pdf_pts": round(sep, 4),
                "contact_pdf_pts": [round((a.x + b.x) / 2.0, 3), round((a.y + b.y) / 2.0, 3)],
                "status": status.value,
                "reason": reason,
                "physical_join_authenticated": False,
                "measurement_authorized": False,
                "snap_join_applied": False,
                "naive_x_filter_applied": False,
            })
    receipts.sort(key=lambda row: (
        float(row["separation_pdf_pts"]),
        row["left_path_ids"],
        row["right_path_ids"],
    ))
    return tuple(receipts)


def census_source_outside_candidate(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
    page_index: int = -1,
) -> dict[str, object]:
    """Keep right-house/garage owners. Do not hull or x-crop the leftover ink."""
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first

    attempt = attempt_source_native_outer_wall_first(
        drawings,
        source_words=source_words,
        window_source_drawings=drawings,
    )
    bars = _unique_source_wall_bars(drawings)
    graph = inspect_native_wall_graph(bars, source_drawings=drawings)
    closed = None
    if attempt.polygon_pdf_pts and len(attempt.polygon_pdf_pts) >= 4:
        closed = box(*_bounds_of(attempt.polygon_pdf_pts))
    elif attempt.rejected_candidate_bbox_pdf_pts:
        closed = box(*attempt.rejected_candidate_bbox_pdf_pts)
    elif attempt.diagnostic_rejected_loop_bbox_pdf_pts:
        closed = box(*attempt.diagnostic_rejected_loop_bbox_pdf_pts)
    if closed is None:
        closed = _unique_closed_union_fragment(bars)
    outside = []
    for bar in bars:
        if closed is not None and closed.buffer(0.05).covers(bar.polygon):
            continue
        role, reason = classify_outside_envelope_role(bar, drawings, source_words)
        bounds = tuple(round(float(v), 3) for v in bar.polygon.bounds)
        outside.append({
            "native_path_ids": list(_path_ids(bar)),
            "bounds_pdf_pts": list(bounds),
            "envelope_role": role,
            "reason": reason,
            "centroid_pdf_pts": [
                round((bounds[0] + bounds[2]) / 2.0, 3),
                round((bounds[1] + bounds[3]) / 2.0, 3),
            ],
            "proven_outside_envelope": role in {ROLE_OUTDOOR, ROLE_POST},
        })
    seams = authenticate_outer_house_seams(bars, drawings)
    near_miss_receipts = []
    for miss in graph.endpoint_near_misses:
        status, reason = authenticate_external_wall_junction(
            native_path_ids=miss.native_path_ids,
            nearby_native_path_ids=miss.nearby_native_path_ids,
            separation_pdf_pts=miss.separation_pdf_pts,
            drawings=drawings,
        )
        near_miss_receipts.append({
            "left_path_ids": list(miss.native_path_ids),
            "right_path_ids": list(miss.nearby_native_path_ids),
            "separation_pdf_pts": miss.separation_pdf_pts,
            "tip_pdf_pts": list(miss.tip_pdf_pts),
            "status": status.value,
            "reason": reason,
            "physical_join_authenticated": False,
            "measurement_authorized": False,
            "snap_join_applied": False,
        })
    structural_outside = [
        row for row in outside if row["envelope_role"] in {ROLE_STRUCTURAL, ROLE_UNPROVEN}
    ]
    return {
        "page_index": page_index,
        "preflight_status": attempt.status,
        "preflight_reason": attempt.reason,
        "component_count": graph.component_count,
        "body_count": len(bars),
        "outside_bar_count": len(outside),
        "structural_outside_count": len(structural_outside),
        "proven_outdoor_or_post_count": sum(
            1 for row in outside if row["proven_outside_envelope"]
        ),
        "outside_bars": outside,
        "outer_house_seams": list(seams),
        "endpoint_near_miss_receipts": near_miss_receipts,
        "near_miss_seam_count": sum(1 for row in seams if row["reason"] == REASON_NEAR_MISS),
        "joined_seam_count": sum(1 for row in seams if row["status"] == "candidate"),
        "rejected_candidate_bbox_pdf_pts": (
            list(closed.bounds) if closed is not None else None
        ),
        "naive_x_filter_applied": False,
        "snap_join_applied": False,
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "can_issue_area": False,
        "official_frozen120_score_change": 0,
        "sliding_bridge_count": len(getattr(attempt, "sliding_door_footprint_bridges", ()) or ()),
        "neutral_grey_seam_count": len(getattr(attempt, "neutral_wall_seams", ()) or ()),
        "window_bridge_count": len(attempt.window_footprint_bridges),
        "swing_bridge_count": len(attempt.swing_door_footprint_bridges),
        "garage_bridge_count": len(attempt.garage_door_footprint_bridges),
        "diagnostic_closed_wall_loop_count": attempt.diagnostic_closed_wall_loop_count,
        "diagnostic_wall_bands_outside_loop": attempt.diagnostic_wall_bands_outside_loop,
        "diagnostic_outside_source_path_sample": list(
            attempt.diagnostic_outside_source_path_sample
        ),
        "left_only_closed_loop_rejected": (
            attempt.reason == "source_exterior_other_wall_ink_outside_candidate"
            and attempt.diagnostic_closed_wall_loop_count == 1
            and attempt.diagnostic_wall_bands_outside_loop > 0
        ),
    }


def _bounds_of(points: Sequence[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _unique_closed_union_fragment(bars: Sequence[Any]):
    geoms = [bar.polygon for bar in bars if getattr(bar, "polygon", None) is not None]
    if not geoms:
        return None
    union = unary_union(geoms)
    parts = list(union.geoms) if hasattr(union, "geoms") else [union]
    closed = [
        part for part in parts
        if part.geom_type == "Polygon" and part.is_valid and len(part.interiors) >= 1
    ]
    if len(closed) != 1:
        return None
    return closed[0]
