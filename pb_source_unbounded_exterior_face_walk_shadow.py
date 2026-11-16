"""Shadow: walk the unbounded exterior face around a shared building.

OBSERVED: the unique closed painted ring can follow an internal PARTY wall
and miss genuine outer walls of a second dwelling in the same footprint.
INFERRED: faces that bound the unbounded outside region, and not a
conditioned dwelling on both sides, are the building's outer face.
PROPOSED: unique-or-abstain walk of those faces; opening bridges are
topology-only; never snap, hull, or bill.
BENCHMARK: frozen 120 / BED2 / BED5 / expected BOQ are not inputs.

Layer names are not wall roles. A PARTY divider on Enclosure_WallExternal
stays interior. Alfresco/porch/post leave the envelope only with source
proof. This module never sets measurement_authorized.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_exterior_endpoint_authority_shadow import CONTACT_PT
from pb_source_native_wall_body_junction_graph_shadow import _unique_source_wall_bars
from pb_source_outer_house_continuity_shadow import bar_proven_outside_envelope
from pb_source_spatial_subdivision_shadow import (
    build_source_spatial_subdivision,
)

try:
    from pb_source_shared_dwelling_envelope_shadow import (
        detect_native_shared_dwelling_dividers,
    )
except ImportError:  # #4389 consumed when present; never reimplemented here.
    def detect_native_shared_dwelling_dividers(*_args, **_kwargs):
        return ()


ROLE_EXTERIOR_FACE = "unbounded_exterior_face_candidate"
ROLE_INTERIOR_DIVIDER = "interior_dwelling_divider_not_building_outer"
ROLE_EXCLUDED = "source_named_outdoor_or_post_excluded"
ROLE_UNPROVEN = "unproven_not_unbounded_exterior_face"

REASON_CYCLE = "source_unbounded_exterior_face_cycle_candidate_not_physical_authority"
REASON_UNCLOSED = "source_unbounded_exterior_face_unclosed"
REASON_BRANCH = "source_unbounded_exterior_face_branch_not_unique"
REASON_LEFTOVER = "source_unbounded_exterior_face_incomplete_leftover_ink"
REASON_MISSING = "source_unbounded_exterior_face_not_found"
REASON_AMBIGUOUS = "source_unbounded_exterior_face_components_not_unique"

_CONDITIONED_TOKENS = (
    " LIVING ", " MEDIA ", " DINING ", " KITCHEN ", " KIT ",
    " BED ", " BEDROOM ", " STUDY ", " OFFICE ", " BATH ",
    " BATHROOM ", " LAUNDRY ", " WC ", " WIR ", " WIP ",
    " MASTER ", " ENTRY ", " GARAGE ", " FAMILY ", " LOUNGE ",
    " THEATRE ", " RUMPUS ",
)
_ALONG_PAD_PT = 3.0
_NORMAL_LABEL_PT = 180.0


@dataclass(frozen=True)
class ExteriorFaceBar:
    bar_index: int
    native_path_ids: tuple[int, ...]
    bounds_pdf_pts: tuple[float, float, float, float]
    role: str
    reason: str
    house_label_side_count: int


def _path_ids(bar: Any) -> tuple[int, ...]:
    return tuple(sorted({int(v) for v in bar.native_path_indices()}))


def _padded_name(text: str) -> str:
    return " " + re.sub(r"[^A-Z0-9 ]", " ", str(text).upper()) + " "


def _is_conditioned_name(text: str) -> bool:
    padded = _padded_name(text)
    if any(token in padded for token in _CONDITIONED_TOKENS):
        return True
    compact = re.sub(r"[^A-Z0-9]", "", str(text).upper())
    return compact == "BED" or (compact.startswith("BED") and compact[3:].isdigit())


def _word_points(
    words: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> tuple[tuple[str, float, float], ...]:
    out = []
    for word in words:
        try:
            if isinstance(word, Mapping):
                raw = str(word.get("text") or "")
                bounds = tuple(float(v) for v in (word.get("bbox_pdf_pts") or word.get("bbox") or ()))
            else:
                raw = str(word[4])
                bounds = tuple(float(v) for v in word[:4])
            if len(bounds) != 4 or not all(map(math.isfinite, bounds)):
                continue
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                continue
            out.append((raw, (bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return tuple(out)


def _as_word_rows(
    words: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> tuple[Sequence[Any], ...]:
    rows = []
    for word in words:
        if isinstance(word, Mapping):
            bounds = word.get("bbox_pdf_pts") or word.get("bbox")
            if bounds is None:
                continue
            rows.append((*tuple(float(v) for v in bounds), str(word.get("text") or "")))
        else:
            rows.append(word)
    return tuple(rows)


def _labels_on_sides(
    bar: Any,
    points: Sequence[tuple[str, float, float]],
    predicate,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    x0, y0, x1, y1 = (float(v) for v in bar.polygon.bounds)
    vertical = (y1 - y0) >= (x1 - x0)
    mid = (x0 + x1) / 2.0 if vertical else (y0 + y1) / 2.0
    low, high = (y0, y1) if vertical else (x0, x1)
    side_a, side_b = [], []
    for text, rx, ry in points:
        if not predicate(text):
            continue
        along = ry if vertical else rx
        normal = rx if vertical else ry
        if not (low - _ALONG_PAD_PT <= along <= high + _ALONG_PAD_PT):
            continue
        if abs(normal - mid) > _NORMAL_LABEL_PT:
            continue
        if normal < mid - 1.0:
            side_a.append(text)
        elif normal > mid + 1.0:
            side_b.append(text)
    return tuple(side_a), tuple(side_b)


def _party_path_ids(drawings, source_words, source_page_index: int) -> frozenset[int]:
    if not source_words:
        return frozenset()
    found = detect_native_shared_dwelling_dividers(
        drawings, source_words, source_page_index=source_page_index,
    )
    return frozenset(
        int(path)
        for item in found
        for path in getattr(item, "wall_native_path_ids", ())
    )


def classify_exterior_face_bars(
    bars: Sequence[Any],
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
    *,
    source_page_index: int = -1,
) -> tuple[ExteriorFaceBar, ...]:
    points = _word_points(source_words)
    party_paths = _party_path_ids(drawings, source_words, source_page_index)
    spatial = build_source_spatial_subdivision(
        drawings,
        bars=bars,
        text_words=_as_word_rows(source_words) or None,
    )
    spatial_faces = {
        tuple(sorted(int(v) for v in face.native_path_ids)): face
        for face in spatial.boundary_faces
    }
    records = []
    for index, bar in enumerate(bars):
        if getattr(bar, "polygon", None) is None or bar.polygon.is_empty:
            continue
        paths = _path_ids(bar)
        bounds = tuple(round(float(v), 3) for v in bar.polygon.bounds)
        face = spatial_faces.get(paths)
        house_a, house_b = _labels_on_sides(bar, points, _is_conditioned_name)
        house_count = int(bool(house_a)) + int(bool(house_b))
        if bar_proven_outside_envelope(bar, drawings, source_words):
            records.append(ExteriorFaceBar(
                index, paths, bounds, ROLE_EXCLUDED, "unique_source_outdoor_or_post", 0,
            ))
            continue
        if party_paths.intersection(paths) or house_count == 2:
            records.append(ExteriorFaceBar(
                index, paths, bounds, ROLE_INTERIOR_DIVIDER,
                "source_party_or_two_sided_dwelling_labels", house_count,
            ))
            continue
        if face is not None and face.is_interior_partition:
            records.append(ExteriorFaceBar(
                index, paths, bounds, ROLE_INTERIOR_DIVIDER,
                "spatial_interior_partition_not_unbounded_face", house_count,
            ))
            continue
        if (face is not None and face.is_exterior_envelope) or house_count == 1:
            records.append(ExteriorFaceBar(
                index, paths, bounds, ROLE_EXTERIOR_FACE,
                "unbounded_or_one_sided_dwelling_outer_face", house_count,
            ))
            continue
        records.append(ExteriorFaceBar(
            index, paths, bounds, ROLE_UNPROVEN,
            "neither_unbounded_exterior_nor_two_sided_dwelling", house_count,
        ))
    divider_paths = {
        path for rec in records if rec.role == ROLE_INTERIOR_DIVIDER for path in rec.native_path_ids
    }
    if not divider_paths:
        return tuple(records)
    demoted = []
    for rec in records:
        if rec.role == ROLE_EXTERIOR_FACE and divider_paths.intersection(rec.native_path_ids):
            demoted.append(ExteriorFaceBar(
                rec.bar_index, rec.native_path_ids, rec.bounds_pdf_pts,
                ROLE_INTERIOR_DIVIDER, "composite_bar_shares_interior_divider_path",
                rec.house_label_side_count,
            ))
        else:
            demoted.append(rec)
    return tuple(demoted)


def _topology_host_pairs(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> frozenset[frozenset[int]]:
    pairs: set[frozenset[int]] = set()
    if not source_words:
        return frozenset()

    def _add(left, right) -> None:
        try:
            a, b = int(left), int(right)
        except (TypeError, ValueError):
            return
        if a != b:
            pairs.add(frozenset((a, b)))

    from pb_source_garage_door_footprint_continuity import (
        detect_exterior_garage_door_footprint_bridges,
    )
    from pb_source_neutral_wall_seam_continuity import detect_source_neutral_wall_seams
    from pb_source_swing_door_footprint_continuity import (
        detect_exterior_swing_door_footprint_bridges,
    )
    from pb_source_window_footprint_continuity import (
        detect_exterior_window_footprint_bridges,
    )
    try:
        from pb_source_sliding_door_footprint_continuity import (
            detect_exterior_sliding_door_footprint_bridges,
        )
    except ImportError:
        def detect_exterior_sliding_door_footprint_bridges(*_a, **_k):
            return ()

    for bridge in detect_exterior_window_footprint_bridges(drawings, source_words):
        _add(bridge.left_host_path_id, bridge.right_host_path_id)
    for bridge in detect_exterior_garage_door_footprint_bridges(drawings, source_words):
        _add(bridge.start_host_path_id, bridge.end_host_path_id)
    for bridge in detect_exterior_swing_door_footprint_bridges(drawings, source_words):
        _add(bridge.first_host_path_id, bridge.second_host_path_id)
    for bridge in detect_exterior_sliding_door_footprint_bridges(drawings, source_words):
        _add(
            getattr(bridge, "first_host_path_id", None),
            getattr(bridge, "second_host_path_id", None),
        )
    for seam in detect_source_neutral_wall_seams(drawings, page_index=-1):
        _add(getattr(seam, "first_host_path_id", None), getattr(seam, "second_host_path_id", None))
    return frozenset(pairs)


def _paths_touch(
    left: Sequence[int],
    right: Sequence[int],
    pairs: frozenset[frozenset[int]],
) -> bool:
    left_set, right_set = set(left), set(right)
    for pair in pairs:
        if len(pair) != 2:
            continue
        a, b = tuple(pair)
        if (a in left_set and b in right_set) or (b in left_set and a in right_set):
            return True
    return False


def _neighbor_graph(
    bars: Sequence[Any],
    exterior_indices: Sequence[int],
    topology_pairs: frozenset[frozenset[int]],
) -> dict[int, tuple[tuple[int, str, float], ...]]:
    graph: dict[int, list[tuple[int, str, float]]] = {i: [] for i in exterior_indices}
    for pos, i in enumerate(exterior_indices):
        for j in exterior_indices[pos + 1:]:
            dist = float(bars[i].polygon.distance(bars[j].polygon))
            if not math.isfinite(dist):
                continue
            kind = None
            if dist <= CONTACT_PT:
                kind = "representation_contact"
            elif _paths_touch(_path_ids(bars[i]), _path_ids(bars[j]), topology_pairs):
                kind = "opening_topology_continuity_only"
            if kind is None:
                continue
            graph[i].append((j, kind, dist))
            graph[j].append((i, kind, dist))
    return {i: tuple(sorted(neigh, key=lambda row: (row[2], row[0]))) for i, neigh in graph.items()}


def _connected(graph: Mapping[int, Sequence[tuple[int, str, float]]]) -> list[set[int]]:
    unseen = set(graph)
    parts = []
    while unseen:
        seed = min(unseen)
        stack = [seed]
        seen: set[int] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(neigh[0] for neigh in graph[node])
        unseen -= seen
        parts.append(seen)
    return parts


def _walk_unique(graph: Mapping[int, Sequence[tuple[int, str, float]]]) -> tuple[tuple[int, ...], str]:
    if not graph:
        return (), REASON_MISSING
    degrees = {i: len(neigh) for i, neigh in graph.items()}
    if any(deg > 2 for deg in degrees.values()):
        return (), REASON_BRANCH
    if len(_connected(graph)) != 1:
        return (), REASON_AMBIGUOUS
    ends = sorted(i for i, deg in degrees.items() if deg == 1)
    loops = [i for i, deg in degrees.items() if deg == 2]
    if ends:
        if len(ends) != 2 or len(ends) + len(loops) != len(graph):
            return (), REASON_UNCLOSED
        start = ends[0]
        expected_kind = "path"
    else:
        if len(loops) != len(graph) or len(graph) < 3:
            return (), REASON_UNCLOSED
        start = min(graph)
        expected_kind = "cycle"
    order = [start]
    prev = None
    current = start
    while True:
        nxt = [n for n, _kind, _d in graph[current] if n != prev]
        if expected_kind == "cycle" and prev is None:
            nxt = sorted(n for n, _kind, _d in graph[current])
        if not nxt:
            break
        if expected_kind == "cycle" and prev is None and len(nxt) == 2:
            choice = nxt[0]
        elif len(nxt) != 1:
            return (), REASON_BRANCH
        else:
            choice = nxt[0]
        if choice == start and expected_kind == "cycle" and prev is not None:
            break
        if choice in order:
            return (), REASON_BRANCH
        order.append(choice)
        prev, current = current, choice
        if expected_kind == "path" and current in ends and current != start:
            break
        if len(order) > len(graph) + 1:
            return (), REASON_BRANCH
    if set(order) != set(graph):
        return (), REASON_LEFTOVER
    return tuple(order), expected_kind


def walk_unbounded_exterior_face(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
    page_index: int = -1,
    bars: Sequence[Any] | None = None,
) -> dict[str, object]:
    """Follow the unbounded outer face around every dwelling in one building.

    A closed walk is still only a candidate. Party / two-sided dwelling
    walls are never outer. Distance is never a 2.5 pt join.
    """
    if bars is None:
        bars = _unique_source_wall_bars(drawings)
    bars = tuple(bars)
    records = classify_exterior_face_bars(
        bars, drawings, source_words, source_page_index=page_index,
    )
    divider_paths = {
        path for rec in records if rec.role == ROLE_INTERIOR_DIVIDER for path in rec.native_path_ids
    }
    exterior_indices = [
        rec.bar_index for rec in records
        if rec.role == ROLE_EXTERIOR_FACE and not divider_paths.intersection(rec.native_path_ids)
    ]
    topology_pairs = _topology_host_pairs(drawings, source_words)
    graph = _neighbor_graph(bars, exterior_indices, topology_pairs)
    order, walk_kind = _walk_unique(graph)
    if order:
        exterior_ids = [list(_path_ids(bars[j])) for j in order]
    else:
        exterior_ids = [list(_path_ids(bars[i])) for i in exterior_indices]
    closed = walk_kind == "cycle"
    leftover = _leftover_structural(records, bars, order, exterior_indices)
    if leftover and closed:
        closed = False
        walk_kind = REASON_LEFTOVER
    if not exterior_indices:
        status, reason = EvidenceResolutionStatus.ABSTAINED, REASON_MISSING
    elif walk_kind in {REASON_BRANCH, REASON_LEFTOVER, REASON_AMBIGUOUS, REASON_UNCLOSED, REASON_MISSING}:
        status, reason = EvidenceResolutionStatus.ABSTAINED, walk_kind
    elif closed:
        status, reason = EvidenceResolutionStatus.CANDIDATE, REASON_CYCLE
    else:
        status, reason = EvidenceResolutionStatus.ABSTAINED, REASON_UNCLOSED
    first_open = None
    if status is EvidenceResolutionStatus.ABSTAINED:
        tip = bars[order[-1]] if order else (bars[exterior_indices[0]] if exterior_indices else None)
        if tip is not None:
            first_open = {
                "native_path_ids": list(_path_ids(tip)),
                "bounds_pdf_pts": [round(float(v), 3) for v in tip.polygon.bounds],
                "reason": reason,
            }
    party_module = getattr(detect_native_shared_dwelling_dividers, "__module__", "")
    return {
        "page_index": page_index,
        "status": status.value,
        "reason": reason,
        "walk_kind": walk_kind if walk_kind in {"cycle", "path"} else "none",
        "closed_shared_envelope_candidate": closed,
        "exterior_face_count": len(exterior_indices),
        "interior_divider_count": sum(1 for rec in records if rec.role == ROLE_INTERIOR_DIVIDER),
        "excluded_outdoor_or_post_count": sum(1 for rec in records if rec.role == ROLE_EXCLUDED),
        "unproven_count": sum(1 for rec in records if rec.role == ROLE_UNPROVEN),
        "exterior_path_id_sequence": exterior_ids,
        "interior_divider_path_ids": sorted({
            path for rec in records if rec.role == ROLE_INTERIOR_DIVIDER for path in rec.native_path_ids
        }),
        "face_records": [
            {
                "native_path_ids": list(rec.native_path_ids),
                "bounds_pdf_pts": list(rec.bounds_pdf_pts),
                "role": rec.role,
                "reason": rec.reason,
                "house_label_side_count": rec.house_label_side_count,
            }
            for rec in records
        ],
        "first_unclosed_exterior_endpoint": first_open,
        "topology_continuity_pair_count": len(topology_pairs),
        "party_module_present": party_module.endswith("pb_source_shared_dwelling_envelope_shadow"),
        "layer_name_is_not_outer_role": True,
        "snap_join_applied": False,
        "convex_hull_applied": False,
        "naive_x_filter_applied": False,
        "physical_wall_authenticated": False,
        "building_footprint_authenticated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "can_issue_area": False,
        "official_frozen120_score_change": 0,
    }


def _leftover_structural(
    records: Sequence[ExteriorFaceBar],
    bars: Sequence[Any],
    order: Sequence[int],
    exterior_indices: Sequence[int],
) -> bool:
    walked = set(order)
    if any(index not in walked for index in exterior_indices) and walked:
        return True
    if not walked:
        return False
    walked_geom = unary_union([bars[i].polygon for i in walked])
    for rec in records:
        if rec.role != ROLE_UNPROVEN:
            continue
        bar = bars[rec.bar_index]
        if walked_geom.distance(bar.polygon) > CONTACT_PT:
            return True
    return False
