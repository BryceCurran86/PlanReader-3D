"""Read-only original W4 grid path census between competing native room labels.

An exact source-owned two-sided GRID adjacency can accidentally connect
different semantic rooms. This reports the W4 atomic edges on the shortest
*observed* path only. It neither cuts those walls nor grants any room/area.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any, Mapping

from pb_source_composite_room_face_authority import _edge_key

MAX_FACES = 5000
MAX_LINKS = 30000
MAX_COMPETITORS = 8
MAX_ROUTE_EDGES = 256


def _id(value: Any) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def inspect_exact_grid_competing_label_paths(
    adjacency: Mapping[str, Any], *,
    source_face_records: Any,
    seed_face_ids: Any,
    competitor_receipts: Any,
) -> dict[str, Any]:
    """Census existing exact source W4 paths, never elect a room separator."""
    answer = {
        "status": "unavailable",
        "diagnostic_only_no_wall_cut_or_room_publication": True,
        "authenticated_physical_boundary_or_room_recovered": False,
        "original_source_room_face_universe_proven_complete": False,
        "route_is_not_a_room_boundary": True,
        "routes": [],
        "competitor_receipts_truncated": False,
    }
    if not isinstance(adjacency, Mapping) or not isinstance(
        seed_face_ids, (tuple, list)
    ) or not isinstance(competitor_receipts, (tuple, list)):
        answer["status"] = "invalid_source_inputs"
        return answer
    seeds = tuple(seed_face_ids)
    faces = tuple(source_face_records or ())
    if (not seeds or len(seeds) > 8 or any(not _id(s) for s in seeds)
            or len(set(seeds)) != len(seeds)
            or len(faces) > MAX_FACES or len(adjacency) > MAX_FACES):
        answer["status"] = "source_universe_or_identity_safety_bound"
        return answer
    names = [getattr(x, "face_id", None) for x in faces]
    receipts = [getattr(x, "record_id", None) for x in faces]
    if (any(not _id(x) for x in names + receipts)
            or any(n != 1 for n in Counter(names).values())
            or any(n != 1 for n in Counter(receipts).values())):
        answer["status"] = "source_face_identity_ambiguous"
        return answer
    known = set(names)
    if any(x not in known for x in seeds):
        answer["status"] = "source_seed_face_missing"
        return answer
    routes = {}
    link_count = 0
    for source, neighbours in adjacency.items():
        if not _id(source) or source not in known or not isinstance(
            neighbours, (tuple, list)
        ):
            answer["status"] = "source_grid_adjacency_malformed"
            return answer
        normalized = []
        for item in neighbours:
            if not isinstance(item, (tuple, list)) or len(item) != 3:
                answer["status"] = "source_grid_adjacency_malformed"
                return answer
            other, wall, raw_edge = item
            edge = _edge_key(raw_edge)
            if (not _id(other) or other not in known or not _id(wall)
                    or edge is None or other == source):
                answer["status"] = "source_grid_adjacency_malformed"
                return answer
            normalized.append((other, wall, edge))
            link_count += 1
            if link_count > MAX_LINKS:
                answer["status"] = "source_grid_path_safety_bound"
                return answer
        if len(set(normalized)) != len(normalized):
            answer["status"] = "duplicate_source_grid_edges"
            return answer
        routes[source] = tuple(sorted(normalized))
    # Refuse unilateral GRID adjacency (a source-owned two-sided original
    # W4 separator must be attested at BOTH faces with the same atomic edge).
    for source, neighbouring in routes.items():
        for other, wall, edge in neighbouring:
            if (source, wall, edge) not in routes.get(other, ()):
                answer["status"] = "source_grid_edge_not_two_sided"
                return answer
    if len(competitor_receipts) > MAX_COMPETITORS:
        answer["competitor_receipts_truncated"] = True
    selected = tuple(competitor_receipts[:MAX_COMPETITORS])
    for receipt in selected:
        if not isinstance(receipt, dict):
            answer["status"] = "competing_label_receipt_invalid"
            answer["routes"] = []
            return answer
        label = receipt.get("native_room_label")
        face_ids = receipt.get("competing_source_face_ids")
        if (not _id(label) or not isinstance(face_ids, (tuple, list))
                or not face_ids or any(not _id(x) for x in face_ids)
                or len(set(face_ids)) != len(face_ids)):
            answer["status"] = "competing_label_receipt_invalid"
            answer["routes"] = []
            return answer
        if any(x not in known for x in face_ids):
            answer["status"] = "competing_label_face_missing"
            answer["routes"] = []
            return answer
    if answer["competitor_receipts_truncated"]:
        answer["status"] = "competitor_universe_truncated"
        return answer

    starts = sorted(seeds)
    parent = {seed: None for seed in starts}
    pending = deque(starts)
    while pending:
        source = pending.popleft()
        for other, wall, edge in routes.get(source, ()):
            if other not in parent:
                parent[other] = (source, wall, edge)
                pending.append(other)

    for receipt in selected:
        targets = sorted(receipt["competing_source_face_ids"])
        reachable = [x for x in targets if x in parent]
        if not reachable:
            answer["routes"].append({
                "competing_native_room_label": receipt["native_room_label"],
                "status": "no_exact_source_grid_path_observed",
                "observed_route": [],
                "no_room_boundary_selected": True,
            })
            continue
        target = min(reachable, key=lambda x: (
            _parent_depth(x, parent), x
        ))
        path = []
        position = target
        while parent[position] is not None:
            prior, wall, edge = parent[position]
            path.append({
                "from_source_face_id": prior,
                "to_source_face_id": position,
                "original_w4_wall_id": wall,
                "original_atomic_edge_pdf_pts": [list(x) for x in edge],
                "physical_room_separator_role_proven": False,
            })
            position = prior
            if len(path) > MAX_ROUTE_EDGES:
                answer["status"] = "source_grid_route_safety_bound"
                answer["routes"] = []
                return answer
        answer["routes"].append({
            "competing_native_room_label": receipt["native_room_label"],
            "status": "exact_source_grid_path_observed_not_room_authority",
            "observed_route": list(reversed(path)),
            "route_edge_count": len(path),
            "no_room_boundary_selected": True,
        })
    answer["status"] = "original_source_grid_competing_label_paths_observed"
    return answer


def _parent_depth(value: str, parent: dict) -> int:
    depth = 0
    while parent[value] is not None:
        depth += 1
        value = parent[value][0]
    return depth
