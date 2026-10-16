"""Exact source interval partitioning for an explicitly isolated W2 experiment.

This represents coincident paint once with all its primitive ancestry. It does
not assert that the paint is a wall, merge physical identities or close gaps.
Every output endpoint already exists in the input. Binary float coordinates
are compared as exact rationals; no proximity, rounding or tolerance applies.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
import math

from pb_migration_contracts import stable_contract_id
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY, fabricated_live_fields, union_lineage


def partition_exact_collinear_fragments(fragments):
    """Partition overlapping prepared fragments, retaining plural source paint.

    Inputs are existing W2 split dictionaries, before snap/degree-two merge.
    The caller retains the original inputs and unchanged baseline experiment.
    New records use the existing lineage schema, including attribute conflicts.
    Emitting fragment addresses are additive diagnostics, never source parents.
    """
    groups = defaultdict(list)
    seen = set()
    for row in fragments:
        identity = row.get("id")
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError("exact interval partition needs unique fragment addresses")
        seen.add(identity)
        coords = tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2"))
        if not all(math.isfinite(v) for v in coords):
            raise ValueError("exact interval partition coordinates must be finite")
        a, b = sorted((coords[:2], coords[2:]))
        if a == b:
            raise ValueError("exact interval partition cannot authenticate a zero interval")
        lineage = row.get(LINEAGE_KEY)
        if not isinstance(lineage, dict) or not lineage.get("source_primitive_ids") or not lineage.get("source_records"):
            raise ValueError("exact interval partition needs original primitive lineage")
        x, y, u, v = map(Fraction, (*a, *b))
        key = (0, x) if u == x else (1, (v-y)/(u-x), y-((v-y)/(u-x))*x)
        groups[key].append((a, b, row))

    out = []
    for key in sorted(groups):
        events = defaultdict(lambda: [[], []])
        for i, (a, b, row) in enumerate(groups[key]):
            events[a][0].append(i)
            events[b][1].append(i)
        points = sorted(events)
        active = set()
        for a, b in zip(points, points[1:]):
            starts, ends = events[a]
            active.difference_update(ends)
            active.update(starts)
            if not active:
                continue
            owners = [groups[key][i][2] for i in sorted(active)]
            lineage = union_lineage(*(row[LINEAGE_KEY] for row in owners))
            # Prepared live fields are fabricated sentinels. Never elect an
            # original source's graphic state from competing source records.
            out.append({"id": stable_contract_id("w2-collinear-source-interval", {
                    "geometry": (*a, *b), "primitive_lineage": lineage}),
                "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                **fabricated_live_fields(), LINEAGE_KEY: deepcopy(lineage),
                "overlap_partition_emitter_fragment_ids": sorted(row["id"] for row in owners)})
    return out
