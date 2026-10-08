"""Exact source-endpoint connected components with linear incidence scanning.

No coordinate snapping, proximity tolerance, or inferred geometry.
"""
from collections import defaultdict
from collections.abc import Mapping, Sequence


def exact_endpoint_components(
    wall_ids: Sequence[str],
    endpoints_by_wall: Mapping[str, set[tuple[float, float]]],
) -> dict[str, frozenset[str]]:
    ids = tuple(wall_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate wall identities")
    parent = {wall_id: wall_id for wall_id in ids}

    def find(wall_id: str) -> str:
        while parent[wall_id] != wall_id:
            parent[wall_id] = parent[parent[wall_id]]
            wall_id = parent[wall_id]
        return wall_id

    first_owner = {}
    for wall_id in ids:
        for point in endpoints_by_wall[wall_id]:
            previous = first_owner.setdefault(point, wall_id)
            left, right = find(previous), find(wall_id)
            if left != right:
                parent[max(left, right)] = min(left, right)

    groups = defaultdict(set)
    for wall_id in ids:
        groups[find(wall_id)].add(wall_id)
    return {root: frozenset(members) for root, members in groups.items()}
