"""Shadow-only evidence: paired-face linework of OTHER ink classes that is attached to the structural wall network.

Why this exists. ``pb_structural_wall_ink_shadow`` proves only the darkest ink present on a page, on purpose: it is an
ordinal on the page's own strokes, not a threshold. Plans that draw external walls heavier than internal partitions keep the
partitions at ``UNPROVEN`` (``lighter_than_darkest_present_ink``), so rooms cannot be separated from one another. Pairing every
lighter class instead is not safe: a floor-finish plank or tile pattern is also made of parallel lines within wall-thickness
of each other and touches every wall.

What it does. From the same native segments and the structural report, it keeps the solid strokes that are not already
``WALL_NETWORK_INK_CANDIDATE`` or ``NOT_WALL_INK`` and applies two relational tests only:

* ladder rejection: a stroke that has a parallel same-class partner within wall-thickness on BOTH sides is a member of a field of
  regularly spaced parallel lines (hatch, planks, tiles), never a wall face; so is a stroke whose only partners are such members
  (the outer line of the field). Typed negatives, retained with their reasons;
* attachment: the remaining strokes are re-read, as one ink with the structural candidates, by the unchanged structural
  classifier. A stroke is a ``PARTITION_INK_CANDIDATE`` only when it is a paired-face member of a network that also contains
  structural candidates (it is drawn like a wall AND it stands on the wall network). Detached paired groups stay ``UNPROVEN``.

It also returns the opening-gap evidence of that joint reading, so an internal doorway between two attached faces is typed
like an external one.

What it deliberately does not do. It does not use a numeric stroke weight, a colour list, a layer name, a project name, a
page number or any expected quantity. It does not filter, merge, snap or re-key anything, it raises no authority, it is not
called by a live path, and no primitive is dropped: every considered stroke gets a decision. Fixtures and joinery that stand
on a wall and are drawn as a double line are not separated from partitions here (an open gate, as in the structural report).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from pb_structural_wall_ink_shadow import (
    ANGLE_TOL_RAD,
    MAX_FACE_GAP_PT,
    MIN_FACE_ASPECT,
    MIN_FACE_OFFSET_PT,
    MIN_RUN_LENGTH_PT,
    NOT_WALL_INK,
    UNPROVEN,
    WALL_NETWORK_INK_CANDIDATE,
    InkClassRow,
    OpeningGapCandidate,
    StructuralWallInkReport,
    _GRID_CELL_PT,
    _angle,
    _color,
    _endpoints,
    _length,
    _luminance,
    _num,
    classify_structural_wall_ink,
)

PARTITION_INK_SCHEMA_VERSION = "1.0.0"

PARTITION_INK_CANDIDATE = "partition_ink_candidate"
NOT_PARTITION_INK = "not_partition_ink"

REASON_ATTACHED_PAIRED_NETWORK = "paired_face_network_attached_to_structural_candidates"
REASON_PARALLEL_LADDER = "regularly_spaced_parallel_ladder"
REASON_PARALLEL_LADDER_EDGE = "edge_of_a_regularly_spaced_parallel_ladder"
REASON_NOT_PAIRED_OR_NOT_ATTACHED = "not_a_paired_face_member_of_an_attached_network"
REASON_NO_STRUCTURAL_CANDIDATES = "no_structural_candidates_to_attach_to"

_PAPER_LUMINANCE = 0.999


@dataclass(frozen=True)
class PartitionInkDecision:
    source_primitive_id: str
    classification: str                 # PARTITION_INK_CANDIDATE | NOT_PARTITION_INK | UNPROVEN
    reason_codes: Tuple[str, ...]
    ink_class: Tuple[Any, ...]          # (stroke width, stroke colour)


@dataclass(frozen=True)
class PartitionInkReport:
    decisions: Tuple[PartitionInkDecision, ...]
    class_table: Tuple[InkClassRow, ...]
    opening_gaps: Tuple[OpeningGapCandidate, ...]
    reason_codes: Tuple[str, ...] = ()
    schema_version: str = PARTITION_INK_SCHEMA_VERSION
    shadow_only: bool = True
    live_effect: bool = False
    wall_authority_granted: bool = False

    def ids_with(self, classification: str) -> Tuple[str, ...]:
        return tuple(d.source_primitive_id for d in self.decisions if d.classification == classification)


def _ladder_members(considered: Sequence[Tuple[str, Tuple[float, float, float, float], Tuple[Any, ...]]]) -> Tuple[set, set]:
    """Ids of strokes with a parallel same-class partner within wall-thickness on both sides of them, and the ids of
    strokes whose only partners are such members (the outer lines of a field of parallel lines)."""
    by_class: Dict[Tuple[Any, ...], List[Tuple[str, Tuple[float, float, float, float]]]] = defaultdict(list)
    for ident, p, klass in considered:
        by_class[klass].append((ident, p))
    out: set = set()
    edges: set = set()
    for klass in sorted(by_class, key=repr):
        members = sorted(by_class[klass])
        geo = []
        grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for k, (ident, p) in enumerate(members):
            a = _angle(p)
            ux, uy = math.cos(a), math.sin(a)
            cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
            half = _length(p) / 2
            geo.append((a, ux, uy, -uy, ux, cx, cy, half))
            x0, x1 = sorted((p[0], p[2]))
            y0, y1 = sorted((p[1], p[3]))
            for gx in range(int((x0 - MAX_FACE_GAP_PT) // _GRID_CELL_PT), int((x1 + MAX_FACE_GAP_PT) // _GRID_CELL_PT) + 1):
                for gy in range(int((y0 - MAX_FACE_GAP_PT) // _GRID_CELL_PT), int((y1 + MAX_FACE_GAP_PT) // _GRID_CELL_PT) + 1):
                    grid[(gx, gy)].append(k)
        two_sided: set = set()
        partners: Dict[int, List[int]] = defaultdict(list)
        for k, (ident, p) in enumerate(members):
            a, ux, uy, nx, ny, cx, cy, half = geo[k]
            x0, x1 = sorted((p[0], p[2]))
            y0, y1 = sorted((p[1], p[3]))
            seen: set = set()
            sides: set = set()
            for gx in range(int(x0 // _GRID_CELL_PT), int(x1 // _GRID_CELL_PT) + 1):
                for gy in range(int(y0 // _GRID_CELL_PT), int(y1 // _GRID_CELL_PT) + 1):
                    for q in grid.get((gx, gy), ()):
                        if q == k or q in seen:
                            continue
                        seen.add(q)
                        qa, _, _, _, _, qx, qy, qhalf = geo[q]
                        d = abs(qa - a)
                        if min(d, math.pi - d) > ANGLE_TOL_RAD:
                            continue
                        off = (qx - cx) * nx + (qy - cy) * ny
                        if abs(off) < MIN_FACE_OFFSET_PT or abs(off) > MAX_FACE_GAP_PT:
                            continue
                        mid = (qx - cx) * ux + (qy - cy) * uy
                        overlap = min(half, mid + qhalf) - max(-half, mid - qhalf)
                        if overlap >= 0.5 * min(2 * half, 2 * qhalf) and overlap >= MIN_FACE_ASPECT * abs(off):
                            sides.add(1 if off > 0 else -1)
                            partners[k].append(q)
            if len(sides) == 2:
                two_sided.add(k)
        for k in two_sided:
            out.add(members[k][0])
        for k, others in partners.items():
            if k not in two_sided and others and all(q in two_sided for q in others):
                edges.add(members[k][0])
    return out, edges


def classify_attached_partition_ink(
    segments: Sequence[Mapping[str, Any]],
    report: StructuralWallInkReport,
    *,
    page_width: float,
    page_height: float,
) -> PartitionInkReport:
    """See the module docstring. Pure, deterministic, input-order invariant; never mutates its inputs."""
    keyed: List[Tuple[str, Mapping[str, Any]]] = []
    for position, segment in enumerate(segments):
        ident = str(segment.get("id") if segment.get("id") not in (None, "") else f"anon:{position}")
        keyed.append((ident, segment))
    keyed.sort(key=lambda item: item[0])
    if len({k for k, _ in keyed}) != len(keyed):
        raise ValueError("source primitive ids must be unique")
    byid = dict(keyed)

    tier0 = set(report.ids_with(WALL_NETWORK_INK_CANDIDATE))
    negatives = set(report.ids_with(NOT_WALL_INK))
    if not tier0 <= set(byid):
        raise ValueError("the structural report names primitives that are not in these segments")
    ink = report.darkest_ink_color
    if ink is None or not tier0:
        return PartitionInkReport((), (), (), (REASON_NO_STRUCTURAL_CANDIDATES,))

    considered: List[Tuple[str, Tuple[float, float, float, float], Tuple[Any, ...]]] = []
    for ident, segment in keyed:
        if ident in tier0 or ident in negatives:
            continue
        if not segment.get("stroke_present", segment.get("stroke") is not None):
            continue
        colour = _color(segment.get("stroke"))
        width = _num(segment.get("width"))
        p = _endpoints(segment)
        if colour is None or p is None or width is None or width <= 0.0:
            continue
        if _luminance(colour) >= _PAPER_LUMINANCE or _length(p) < MIN_RUN_LENGTH_PT:
            continue
        considered.append((ident, p, (round(width, 3), colour)))

    ladder, ladder_edges = _ladder_members(considered)
    survivors = {ident for ident, _, _ in considered if ident not in ladder and ident not in ladder_edges}

    joint: List[Dict[str, Any]] = []
    for ident in sorted(tier0):
        joint.append(dict(byid[ident]))
    for ident in sorted(survivors):
        reread = dict(byid[ident])
        reread["stroke"] = tuple(ink)           # one ink with the structural candidates: the unchanged classifier reads pairing
        joint.append(reread)
    again = classify_structural_wall_ink(joint, page_width=page_width, page_height=page_height)

    anchored = {d.network_id for d in again.decisions if d.source_primitive_id in tier0 and d.network_id is not None}
    verdict = {d.source_primitive_id: d for d in again.decisions}
    decisions: List[PartitionInkDecision] = []
    table: Dict[Tuple[Any, ...], List[float]] = defaultdict(lambda: [0, 0.0, 0])
    for ident, p, klass in considered:
        if ident in ladder or ident in ladder_edges:
            reason = REASON_PARALLEL_LADDER if ident in ladder else REASON_PARALLEL_LADDER_EDGE
            decisions.append(PartitionInkDecision(ident, NOT_PARTITION_INK, (reason,), klass))
            candidate = False
        else:
            d = verdict[ident]
            candidate = d.classification == WALL_NETWORK_INK_CANDIDATE and d.network_id in anchored
            if candidate:
                decisions.append(PartitionInkDecision(ident, PARTITION_INK_CANDIDATE, (REASON_ATTACHED_PAIRED_NETWORK,), klass))
            else:
                decisions.append(PartitionInkDecision(
                    ident, UNPROVEN, tuple(sorted(set(d.reason_codes) | {REASON_NOT_PAIRED_OR_NOT_ATTACHED})), klass))
        row = table[klass]
        row[0] += 1
        row[1] += _length(p)
        row[2] += 1 if candidate else 0
    class_table = tuple(
        InkClassRow(k, int(v[0]), round(v[1], 3), int(v[2])) for k, v in sorted(table.items(), key=lambda kv: (-kv[1][1], repr(kv[0])))
    )
    return PartitionInkReport(tuple(decisions), class_table, again.opening_gaps)
