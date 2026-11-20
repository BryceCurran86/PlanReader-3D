"""Shadow #4549-06..10: dual-dwelling shell, party length, opening bridges.

- 06 one outer shell with two independent internal dwelling graphs
- 07 party wall kept internal; exterior length excludes party
- 08 window-gap bridge retains outer path without inventing wall material
- 09 sliding / cavity-slider topology closure retains the door object
- 10 swing-door threshold bridge retains swing orientation

Topology / review only — never FIRM, customer, or frozen120 authority.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TopologyEdge:
    edge_id: int
    start_pdf_pts: tuple[float, float]
    end_pdf_pts: tuple[float, float]
    role: str = "external"  # external | party | internal | opening_bridge
    kind: str = "wall"  # wall | window | sliding | swing | post
    swing_orientation: str | None = None  # cw | ccw | None
    retained_object_id: int | None = None


def _length(edge: TopologyEdge) -> float:
    return math.hypot(
        edge.end_pdf_pts[0] - edge.start_pdf_pts[0],
        edge.end_pdf_pts[1] - edge.start_pdf_pts[1],
    )


@dataclass(frozen=True)
class DualDwellingTopologyReceipt:
    status: str
    reason: str
    outer_shell_edge_ids: tuple[int, ...] = ()
    dwelling_a_edge_ids: tuple[int, ...] = ()
    dwelling_b_edge_ids: tuple[int, ...] = ()
    party_wall_edge_ids: tuple[int, ...] = ()
    outer_shell_length_pt: float = 0.0
    party_length_excluded_from_outer_pt: float = 0.0
    window_bridges: tuple[int, ...] = ()
    sliding_closures: tuple[int, ...] = ()
    swing_closures: tuple[dict[str, object], ...] = ()
    posts_refused_as_walls: tuple[int, ...] = ()
    topology_only: bool = True
    measurement_authorized: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "outer_shell_edge_ids": list(self.outer_shell_edge_ids),
            "dwelling_a_edge_ids": list(self.dwelling_a_edge_ids),
            "dwelling_b_edge_ids": list(self.dwelling_b_edge_ids),
            "party_wall_edge_ids": list(self.party_wall_edge_ids),
            "outer_shell_length_pt": self.outer_shell_length_pt,
            "party_length_excluded_from_outer_pt": (
                self.party_length_excluded_from_outer_pt
            ),
            "window_bridges": list(self.window_bridges),
            "sliding_closures": list(self.sliding_closures),
            "swing_closures": [dict(s) for s in self.swing_closures],
            "posts_refused_as_walls": list(self.posts_refused_as_walls),
            "tasks_covered": ["06", "07", "08", "09", "10"],
            "topology_only": True,
            "doorway_closure_is_not_physical_wall": True,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "official_frozen120_score_change": 0,
        }


def _closed_loop(edge_ids: Sequence[int], edges: dict[int, TopologyEdge]) -> bool:
    if len(edge_ids) < 3:
        return False
    tips: list[tuple[float, float]] = []
    for eid in edge_ids:
        e = edges[eid]
        tips.extend((e.start_pdf_pts, e.end_pdf_pts))
    # Each endpoint degree should be even for a single closed walk; unique tips
    # must repeat — simple check: first start matches a free tip of last.
    counts: dict[tuple[float, float], int] = {}
    for tip in tips:
        key = (round(tip[0], 3), round(tip[1], 3))
        counts[key] = counts.get(key, 0) + 1
    return bool(counts) and all(v % 2 == 0 for v in counts.values())


def build_dual_dwelling_opening_topology(
    edges: Sequence[TopologyEdge],
    *,
    dwelling_a_edge_ids: Sequence[int],
    dwelling_b_edge_ids: Sequence[int],
) -> DualDwellingTopologyReceipt:
    """Assemble dual-dwelling outer shell + opening topology receipts."""
    by_id = {e.edge_id: e for e in edges}
    if len(by_id) != len(edges):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "duplicate_topology_edge_ids",
        )
    for eid in (*dwelling_a_edge_ids, *dwelling_b_edge_ids):
        if eid not in by_id:
            return DualDwellingTopologyReceipt(
                "ABSTAINED", "dwelling_edge_id_unknown",
            )

    posts = tuple(
        e.edge_id for e in edges if e.kind == "post" or e.role == "post"
    )
    # Posts never enter shell/dwelling graphs.
    party = tuple(
        sorted(
            e.edge_id for e in edges
            if e.role == "party" and e.edge_id not in posts
        )
    )
    external = tuple(
        sorted(
            e.edge_id for e in edges
            if e.role == "external" and e.kind == "wall" and e.edge_id not in posts
        )
    )
    window_bridges = tuple(
        sorted(e.edge_id for e in edges if e.kind == "window" and e.role == "opening_bridge")
    )
    sliding = tuple(
        sorted(e.edge_id for e in edges if e.kind == "sliding" and e.role == "opening_bridge")
    )
    swing_edges = [
        e for e in edges if e.kind == "swing" and e.role == "opening_bridge"
    ]
    swing_closures = tuple(
        {
            "edge_id": e.edge_id,
            "retained_object_id": e.retained_object_id,
            "swing_orientation": e.swing_orientation,
            "physical_wall_authenticated": False,
        }
        for e in swing_edges
        if e.retained_object_id is not None and e.swing_orientation in {"cw", "ccw"}
    )
    if any(
        e.retained_object_id is None or e.swing_orientation not in {"cw", "ccw"}
        for e in swing_edges
    ):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "swing_bridge_missing_retained_orientation",
            posts_refused_as_walls=posts,
        )
    if any(e.retained_object_id is None for e in edges if e.kind == "sliding"):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "sliding_bridge_missing_retained_door_object",
            posts_refused_as_walls=posts,
        )

    a_ids = tuple(sorted(set(dwelling_a_edge_ids) - set(posts)))
    b_ids = tuple(sorted(set(dwelling_b_edge_ids) - set(posts)))
    if not party:
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "dual_dwelling_requires_authenticated_party_wall",
            posts_refused_as_walls=posts,
        )
    if set(a_ids) & set(b_ids) - set(party):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "dwelling_graphs_share_non_party_edges",
            posts_refused_as_walls=posts,
        )
    if not (set(party) <= set(a_ids) and set(party) <= set(b_ids)):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "party_wall_must_bound_both_dwelling_graphs",
            posts_refused_as_walls=posts,
        )
    if not _closed_loop(a_ids, by_id) or not _closed_loop(b_ids, by_id):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "dwelling_graph_not_closed",
            party_wall_edge_ids=party,
            posts_refused_as_walls=posts,
        )

    # Outer shell = external walls (+ window/sliding/swing bridges that keep
    # the footprint continuous). Party walls are explicitly excluded.
    shell_ids = tuple(
        sorted(
            set(external)
            | set(window_bridges)
            | set(sliding)
            | {e.edge_id for e in swing_edges}
        )
    )
    if any(pid in shell_ids for pid in party):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "party_wall_leaked_into_outer_shell",
            party_wall_edge_ids=party,
            posts_refused_as_walls=posts,
        )
    if not _closed_loop(shell_ids, by_id):
        return DualDwellingTopologyReceipt(
            "ABSTAINED", "outer_shell_not_closed",
            outer_shell_edge_ids=shell_ids,
            party_wall_edge_ids=party,
            posts_refused_as_walls=posts,
        )

    outer_len = round(sum(_length(by_id[i]) for i in shell_ids), 4)
    party_len = round(sum(_length(by_id[i]) for i in party), 4)
    # Double-count guard: party length must not be embedded in outer length.
    # (Shell edges are disjoint from party by construction above.)
    return DualDwellingTopologyReceipt(
        status="CANDIDATE",
        reason="dual_dwelling_shell_with_opening_topology_bridges",
        outer_shell_edge_ids=shell_ids,
        dwelling_a_edge_ids=a_ids,
        dwelling_b_edge_ids=b_ids,
        party_wall_edge_ids=party,
        outer_shell_length_pt=outer_len,
        party_length_excluded_from_outer_pt=party_len,
        window_bridges=window_bridges,
        sliding_closures=sliding,
        swing_closures=swing_closures,
        posts_refused_as_walls=posts,
    )
