"""W2 order-free endpoint snapping (shadow, default off).

The ordinary W2 snap (pb_wall_room_topology_stage_a._snap_geometry_indexed)
walks the endpoints in input order and moves each node to the running mean of
whatever joined it.  Which node an endpoint joins, and where that node ends up,
therefore depend on the order the segments arrive in, and a stub no longer than
the tolerance can pull the corner of two long lines sideways and tilt a wall.

This option decides both from the geometry alone, with the same tolerance:

* only endpoints of pieces longer than the tolerance place a node.  They group
  by complete linkage (every pair in a group is within the tolerance); equally
  close groupings merge only when the whole union still fits, otherwise they
  stay apart rather than being settled by order;
* endpoints of shorter pieces join the single nearest such node within the
  tolerance without moving it (an exact tie between two nodes is not joined),
  and otherwise group among themselves by the same rule;
* a node sits at the mean of the endpoints that place it (exactly on them when
  they coincide).

No new threshold and no wall, room, measurement or quantity authority.
"""
from __future__ import annotations

import heapq
import math
from collections.abc import Sequence
from typing import Any

ORDER_FREE_SNAP_SHADOW_VERSION = "order-free-snap-1.0.0"
# Float noise only: translated or rotated sources must make the same decisions.
_NOISE_PT = 1e-6

Point = tuple[float, float]


def _root(parent: dict[int, int], key: int) -> int:
    while parent.setdefault(key, key) != key:
        parent[key] = parent[parent[key]]
        key = parent[key]
    return key


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mean(points: Sequence[Point]) -> Point:
    first = points[0]
    if all(point == first for point in points):
        return first
    return (
        math.fsum(point[0] for point in points) / len(points),
        math.fsum(point[1] for point in points) / len(points),
    )


def _grid(points: Sequence[Point], cell: float) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = {}
    for index, (x, y) in enumerate(points):
        grid.setdefault((math.floor(x / cell), math.floor(y / cell)), []).append(index)
    return grid


def _near(grid: dict[tuple[int, int], list[int]], point: Point, cell: float) -> list[int]:
    cx, cy = math.floor(point[0] / cell), math.floor(point[1] / cell)
    return [index for dx in (-1, 0, 1) for dy in (-1, 0, 1) for index in grid.get((cx + dx, cy + dy), ())]


def _complete_linkage(points: Sequence[Point], limit: float) -> tuple[list[list[int]], int]:
    """Order-free groups whose members are all pairwise within ``limit``."""
    cell = limit + _NOISE_PT
    grid = _grid(points, cell)
    members: dict[int, list[int]] = {index: [index] for index in range(len(points))}
    linked: dict[int, set] = {index: set() for index in range(len(points))}
    heap: list[tuple[float, int, int]] = []
    for index, point in enumerate(points):
        for other in _near(grid, point, cell):
            if other > index:
                apart = _distance(point, points[other])
                if apart <= limit + _NOISE_PT:
                    heap.append((apart, index, other))
                    linked[index].add(other)
                    linked[other].add(index)
    heapq.heapify(heap)
    next_key = len(points)
    refused = 0
    while heap:
        level = heap[0][0]
        batch = []
        while heap and heap[0][0] <= level + _NOISE_PT:
            _apart, first, second = heapq.heappop(heap)
            if first in members and second in members:
                batch.append((first, second))
        # Equally close pairs are settled together, never one before another.
        parent: dict[int, int] = {}
        for first, second in batch:
            parent[_root(parent, first)] = _root(parent, second)
        together: dict[int, list[int]] = {}
        for key in list(parent):
            together.setdefault(_root(parent, key), []).append(key)
        for group in together.values():
            union = [site for key in group for site in members[key]]
            if any(_distance(points[p], points[q]) > limit + _NOISE_PT
                   for position, p in enumerate(union) for q in union[position + 1:]):
                refused += 1
                continue
            neighbours = set().union(*(linked[key] for key in group)) - set(group)
            for key in group:
                del members[key]
            members[next_key] = union
            linked[next_key] = set()
            for other in neighbours:
                if other not in members:
                    continue
                far = max(_distance(points[p], points[q]) for p in union for q in members[other])
                if far <= limit + _NOISE_PT:
                    heapq.heappush(heap, (far, next_key, other))
                    linked[next_key].add(other)
                    linked[other].add(next_key)
            next_key += 1
    return list(members.values()), refused


def order_free_snap_geometry(
    segments: Sequence[dict[str, Any]],
    tolerance_pt: float,
    *,
    include_endpoint_assignments: bool = False,
) -> dict[str, Any]:
    """Same output shape as the ordinary W2 snap, decided from geometry only."""
    if not (math.isfinite(tolerance_pt) and tolerance_pt > 0):
        raise ValueError("order-free snap requires a positive finite tolerance")
    # One site per distinct endpoint coordinate; each remembers its occurrences.
    site_of: dict[tuple[float, float], int] = {}
    placing: list[list[Point]] = []
    every: list[list[Point]] = []
    coordinates: list[Point] = []
    ends: list[tuple[int, int]] = []
    for segment in segments:
        a = (float(segment["x1"]), float(segment["y1"]))
        b = (float(segment["x2"]), float(segment["y2"]))
        if not all(math.isfinite(value) for value in (*a, *b)):
            raise ValueError("order-free snap source must be finite")
        long_piece = _distance(a, b) > tolerance_pt + _NOISE_PT
        pair = []
        for point in (a, b):
            key = (round(point[0], 6), round(point[1], 6))
            site = site_of.get(key)
            if site is None:
                site = site_of[key] = len(coordinates)
                coordinates.append(point)
                placing.append([])
                every.append([])
            every[site].append(point)
            if long_piece:
                placing[site].append(point)
            pair.append(site)
        ends.append((pair[0], pair[1]))
    # A site's coordinate must not depend on which end came first (they differ by float noise at most).
    for site, points in enumerate(every):
        coordinates[site] = min(points)

    strong = [site for site in range(len(coordinates)) if placing[site]]
    groups, refused = _complete_linkage([coordinates[site] for site in strong], tolerance_pt)
    clusters: list[list[int]] = [[strong[index] for index in group] for group in groups]
    positions: list[Point] = [
        _mean(sorted(point for site in cluster for point in placing[site])) for cluster in clusters
    ]
    cell = tolerance_pt + _NOISE_PT
    position_grid = _grid(positions, cell)
    joined = ambiguous = 0
    leftover: list[int] = []
    attached: dict[int, list[int]] = {}
    for site in range(len(coordinates)):
        if placing[site]:
            continue
        reach = sorted(
            (_distance(coordinates[site], positions[index]), index)
            for index in _near(position_grid, coordinates[site], cell)
            if _distance(coordinates[site], positions[index]) <= tolerance_pt + _NOISE_PT
        )
        if reach and (len(reach) == 1 or reach[1][0] - reach[0][0] > _NOISE_PT):
            attached.setdefault(reach[0][1], []).append(site)
            joined += 1
        else:
            ambiguous += bool(reach)
            leftover.append(site)
    for index, sites in attached.items():
        clusters[index] = clusters[index] + sites
    weak_groups, weak_refused = _complete_linkage([coordinates[site] for site in leftover], tolerance_pt)
    for group in weak_groups:
        cluster = [leftover[index] for index in group]
        clusters.append(cluster)
        positions.append(_mean(sorted(point for site in cluster for point in every[site])))

    cluster_of = {site: index for index, cluster in enumerate(clusters) for site in cluster}
    # Node ids follow first appearance, like the ordinary snap; they only name.
    node_of: dict[int, int] = {}
    nodes: list[dict[str, Any]] = []
    for pair in ends:
        for site in pair:
            index = cluster_of[site]
            if index not in node_of:
                node_of[index] = len(nodes)
                nodes.append({
                    "id": len(nodes),
                    "x": positions[index][0],
                    "y": positions[index][1],
                    "samples": sum(len(every[member]) for member in clusters[index]),
                })
    edges: list[dict[str, Any]] = []
    assignments: dict[str, tuple[int, int]] = {}
    for segment, (first, second) in zip(segments, ends):
        a, b = node_of[cluster_of[first]], node_of[cluster_of[second]]
        if include_endpoint_assignments:
            segment_id = segment.get("id")
            if not isinstance(segment_id, str) or not segment_id or segment_id in assignments:
                raise ValueError("missing or duplicate split id in W2 endpoint trace")
            assignments[segment_id] = (a, b)
        if a == b:
            continue
        edge = dict(segment)
        edge.update({"a": a, "b": b})
        dx = float(segment["x2"]) - float(segment["x1"])
        dy = float(segment["y2"]) - float(segment["y1"])
        edge["length_pt"] = math.hypot(dx, dy)
        edge["angle_deg"] = math.degrees(math.atan2(dy, dx)) % 180.0
        edges.append(edge)
    adjacency: dict[int, list[int]] = {index: [] for index in range(len(nodes))}
    for edge_index, edge in enumerate(edges):
        adjacency[edge["a"]].append(edge_index)
        adjacency[edge["b"]].append(edge_index)
    for node in nodes:
        node["degree"] = len(adjacency[node["id"]])
    result: dict[str, Any] = {
        "nodes": nodes,
        "edges": edges,
        "adjacency": adjacency,
        "order_free_snap_shadow": {
            "enabled": True,
            "version": ORDER_FREE_SNAP_SHADOW_VERSION,
            "short_endpoint_sites_joined": joined,
            "short_endpoint_sites_equidistant": ambiguous,
            "equally_close_groupings_refused": refused + weak_refused,
            "source_wall_role_authenticated": False,
            "diagnostic_only": True,
        },
    }
    if include_endpoint_assignments:
        result["endpoint_snap_assignments"] = assignments
    return result
