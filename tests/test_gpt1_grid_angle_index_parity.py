"""Source-grid angular index must preserve every original legacy nomination."""
from collections import defaultdict
import math
import random

import pytest

import pb_wall_room_topology_typed_negative_evidence as u2


def _legacy(context, retained):
    families = defaultdict(list)
    for item in context:
        if bool(item.get("retained")) is bool(retained):
            families[u2._line_family_key(item)].append(item)
    output = {}
    for members in families.values():
        host = u2._family_host(members)
        host_len = host["length"]
        if host_len <= 1e-6:
            continue
        owned = set(host.get("member_ids") or [host["id"]])
        grid = [
            item for item in context
            if item["id"] not in owned
            and item["length"] / host_len >= 0.5
            and u2._angle_delta(item["angle"], host["angle"]) <= u2._PARALLEL_DEG
        ]
        offsets = [
            (item["mid"][0]-host["mid"][0])*math.sin(math.radians(host["angle"]))
            -(item["mid"][1]-host["mid"][1])*math.cos(math.radians(host["angle"]))
            for item in grid
        ]
        if len(grid) < 3 or not u2._gaps_regular(offsets):
            continue
        nomination = {
            "kind": u2.KIND_GRID,
            "polarity": u2.POLARITY_OPPOSING,
            "confidence": 0.5,
            "reason_codes": ("regular_long_parallels",),
            "feature_basis": {"parallel_count": len(grid)},
        }
        for member in members:
            output[member["id"]] = nomination
    return output


def _items(seed, count):
    rng = random.Random(seed)
    boundary_angles = (0, 0.01, 11.999999, 12, 12.000001, 90, 168, 179.999999)
    for i in range(count):
        angle = (boundary_angles[i % len(boundary_angles)]
                 if seed % 2 else rng.random()*180)
        x, y = rng.uniform(-1000, 1000), rng.uniform(-1000, 1000)
        length = rng.uniform(3, 60)
        x2 = x + length*math.cos(math.radians(angle))
        y2 = y + length*math.sin(math.radians(angle))
        yield {
            "id": f"edge-{i}",
            "x1": x, "y1": y, "x2": x2, "y2": y2,
            "length": math.hypot(x2-x, y2-y), "angle": angle,
            "mid": ((x+x2)/2,(y+y2)/2),
            "retained": i % 5 != 0, "source_primitive_ids": (f"source-{i}",),
            "raw": {},
        }


@pytest.mark.parametrize("seed", (11,12,13,14))
@pytest.mark.parametrize("count", (8,100,350))
@pytest.mark.parametrize("retained", (True, False))
def test_original_grid_opposition_exact_equal(seed, count, retained):
    source = tuple(_items(seed, count))
    original_ids = tuple((i["id"],i["angle"],i["length"]) for i in source)
    assert u2._generic_family_grid_nominations(
        source, retained=retained,
    ) == _legacy(source, retained)
    assert original_ids == tuple((i["id"],i["angle"],i["length"]) for i in source)
