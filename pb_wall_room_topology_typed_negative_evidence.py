"""Shadow typed-negative semantic evidence over retained W2 edges (U2).

Perception nominates. Geometry relates. This module does not publish
quantities and does not delete graph edges. Existing W2 metadata exclusions
stay unchanged. Status never becomes CORROBORATED.

Reuses ``EvidenceAtom`` / ``EvidenceResolutionStatus`` / ``stable_contract_id``.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY

KIND_PHYSICAL_WALL = "physical_wall_linework"
KIND_DIMENSION = "dimension_annotation"
KIND_GLAZING = "glazing"
KIND_FURNITURE = "furniture"
KIND_TABLE = "table_or_schedule_frame"
KIND_GRID = "grid"
KIND_HATCH = "hatch_or_pattern"
KIND_SYMBOL = "symbol"
KIND_ANNOTATION_BORDER = "annotation_border"
KIND_UNKNOWN = "unknown"

POLARITY_SUPPORTING = "supporting"
POLARITY_OPPOSING = "opposing"
POLARITY_UNKNOWN = "unknown"

METHOD = "typed_negative_geometry_shadow"
GRAPH_ATOMS_KEY = "semantic_evidence_atoms"

_SUPPORTING_KINDS = frozenset({KIND_PHYSICAL_WALL})
_OPPOSING_KINDS = frozenset(
    {
        KIND_DIMENSION,
        KIND_GLAZING,
        KIND_FURNITURE,
        KIND_TABLE,
        KIND_GRID,
        KIND_HATCH,
        KIND_SYMBOL,
        KIND_ANNOTATION_BORDER,
    }
)

_ORTHO_DEG = 18.0
_PARALLEL_DEG = 12.0


def _lineage_ids(edge: Mapping[str, Any]) -> List[str]:
    payload = edge.get(LINEAGE_KEY) or {}
    ids = [str(item) for item in (payload.get("source_primitive_ids") or []) if item not in (None, "")]
    raw = edge.get("id")
    if raw not in (None, "") and str(raw) not in ids:
        ids.append(str(raw))
    return sorted(set(ids))


def _length(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0


def _angle_delta(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _mid(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _bbox(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float, float, float]:
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _point_to_seg(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _project_t(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return 0.0
    return ((px - x1) * dx + (py - y1) * dy) / denom


def _gaps_regular(values: Sequence[float]) -> bool:
    if len(values) < 2:
        return False
    ordered = sorted(values)
    gaps = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
    gaps = [g for g in gaps if g > 1e-6]
    if len(gaps) < 2:
        return False
    mid = sorted(gaps)[len(gaps) // 2]
    if mid <= 1e-6:
        return False
    return max(gaps) / mid <= 2.4 and min(gaps) / mid >= 0.4


def _as_geom(item: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        x1 = float(item["x1"])
        y1 = float(item["y1"])
        x2 = float(item["x2"])
        y2 = float(item["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    length = _length(x1, y1, x2, y2)
    if length <= 1e-9:
        return None
    return {
        "id": str(item.get("id") or ""),
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "length": length,
        "angle": _angle_deg(x1, y1, x2, y2),
        "mid": _mid(x1, y1, x2, y2),
        "source_primitive_ids": _lineage_ids(item),
        "raw": item,
    }


def _context_items(graph: Mapping[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        geom = _as_geom(edge)
        if geom:
            geom["retained"] = True
            items.append(geom)
    for segment in graph.get("excluded_segments") or []:
        geom = _as_geom(segment)
        if geom:
            geom["retained"] = False
            items.append(geom)
    items.sort(key=lambda item: (item["id"], item["x1"], item["y1"], item["x2"], item["y2"]))
    return items


def _word_inside(word: Mapping[str, Any], box: Tuple[float, float, float, float]) -> bool:
    bbox = word.get("bbox") or []
    if len(bbox) != 4:
        return False
    x0, y0, x1, y1 = (float(v) for v in bbox)
    return box[0] <= x0 and box[1] <= y0 and box[2] >= x1 and box[3] >= y1


def _rectangle_loops(graph: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]]) -> List[Tuple[str, ...]]:
    """Walk 4-cycles from Stage-A adjacency. Do not scan every 4-tuple of edges."""
    adjacency: Dict[int, List[Tuple[int, str]]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        edge_id = str(edge.get("id") or "")
        if edge_id not in by_id or "a" not in edge or "b" not in edge:
            continue
        a, b = int(edge["a"]), int(edge["b"])
        adjacency[a].append((b, edge_id))
        adjacency[b].append((a, edge_id))
    loops: List[Tuple[str, ...]] = []
    seen = set()
    for start in sorted(adjacency):
        for n1, e1 in adjacency[start]:
            for n2, e2 in adjacency[n1]:
                if n2 == start:
                    continue
                for n3, e3 in adjacency[n2]:
                    if n3 in {start, n1}:
                        continue
                    for n4, e4 in adjacency[n3]:
                        if n4 != start:
                            continue
                        members = tuple(sorted({e1, e2, e3, e4}))
                        if len(members) != 4 or members in seen:
                            continue
                        sides = [by_id[item] for item in members]
                        angles = [item["angle"] for item in sides]
                        ortho = 0
                        para = 0
                        for i, left in enumerate(angles):
                            for right in angles[i + 1 :]:
                                delta = _angle_delta(left, right)
                                if delta <= _PARALLEL_DEG:
                                    para += 1
                                elif abs(delta - 90.0) <= _ORTHO_DEG:
                                    ortho += 1
                        if para >= 2 and ortho >= 2:
                            seen.add(members)
                            loops.append(members)
    return loops


def _loop_bbox(loop: Sequence[str], by_id: Mapping[str, Mapping[str, Any]]) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for edge_id in loop:
        item = by_id[edge_id]
        xs.extend([item["x1"], item["x2"]])
        ys.extend([item["y1"], item["y2"]])
    return (min(xs), min(ys), max(xs), max(ys))


def _inside_box(item: Mapping[str, Any], box: Tuple[float, float, float, float], pad: float = 0.0) -> bool:
    x0, y0, x1, y1 = box
    return (
        x0 - pad <= item["x1"] <= x1 + pad
        and y0 - pad <= item["y1"] <= y1 + pad
        and x0 - pad <= item["x2"] <= x1 + pad
        and y0 - pad <= item["y2"] <= y1 + pad
    )


def _line_family_key(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    angle = round(item["angle"] / 6.0) * 6.0
    ux = math.cos(math.radians(angle))
    uy = math.sin(math.radians(angle))
    offset = item["x1"] * (-uy) + item["y1"] * ux
    return (round(ux, 2), round(uy, 2), round(offset, 1))


def _family_host(members: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    first = members[0]
    ux = math.cos(math.radians(first["angle"]))
    uy = math.sin(math.radians(first["angle"]))
    points = []
    for item in members:
        points.append((item["x1"], item["y1"]))
        points.append((item["x2"], item["y2"]))
    projections = [px * ux + py * uy for px, py in points]
    lo = min(projections)
    hi = max(projections)
    x1, y1 = lo * ux, lo * uy
    x2, y2 = hi * ux, hi * uy
    # Recover the offset so the reconstructed host sits on the family line.
    offset = first["x1"] * (-uy) + first["y1"] * ux
    x1, y1 = x1 + (-uy) * offset, y1 + ux * offset
    x2, y2 = x2 + (-uy) * offset, y2 + ux * offset
    host = {
        "id": "+".join(sorted(item["id"] for item in members)),
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "length": _length(x1, y1, x2, y2),
        "angle": first["angle"],
        "mid": _mid(x1, y1, x2, y2),
        "source_primitive_ids": sorted({pid for item in members for pid in item["source_primitive_ids"]}),
        "raw": members[0]["raw"],
        "member_ids": [item["id"] for item in members],
    }
    return host


def _array_nominations(
    host: Mapping[str, Any],
    context: Sequence[Mapping[str, Any]],
    family_len_by_id: Optional[Mapping[str, float]] = None,
) -> List[Dict[str, Any]]:
    host_len = host["length"]
    if host_len <= 1e-6:
        return []
    family_len_by_id = family_len_by_id or {}
    member_ids = set(host.get("member_ids") or [host["id"]])
    others = [item for item in context if item["id"] not in member_ids]
    near = [
        item
        for item in others
        if _point_to_seg(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        <= max(host_len * 0.12, 1e-6)
    ]
    nominations: List[Dict[str, Any]] = []
    ticks = [
        item
        for item in near
        if family_len_by_id.get(item["id"], item["length"]) / host_len <= 0.22
        and _angle_delta(item["angle"], host["angle"]) >= 90.0 - _ORTHO_DEG
    ]
    tick_ts = [
        _project_t(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        for item in ticks
    ]
    if len(ticks) >= 2 and (_gaps_regular(tick_ts) or len(ticks) >= 3):
        nominations.append(
            {
                "kind": KIND_DIMENSION,
                "polarity": POLARITY_OPPOSING,
                "confidence": 0.55,
                "reason_codes": ("perpendicular_tick_array",),
                "feature_basis": {"tick_count": len(ticks), "host_length": host_len},
            }
        )
    hatch = [
        item
        for item in near
        if family_len_by_id.get(item["id"], item["length"]) / host_len <= 0.28
    ]
    if len(hatch) >= 6:
        lengths = [item["length"] for item in hatch]
        mean = sum(lengths) / len(lengths)
        spread = max(abs(v - mean) for v in lengths) / max(mean, 1e-6)
        if spread <= 0.45:
            nominations.append(
                {
                    "kind": KIND_HATCH,
                    "polarity": POLARITY_OPPOSING,
                    "confidence": 0.5,
                    "reason_codes": ("dense_short_near_host",),
                    "feature_basis": {"near_short_count": len(hatch), "length_spread": spread},
                }
            )
    mullions = [
        item
        for item in others
        if 0.12 <= family_len_by_id.get(item["id"], item["length"]) / host_len <= 0.6
        and _angle_delta(item["angle"], host["angle"]) <= _PARALLEL_DEG
        and _point_to_seg(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        <= host_len * 0.2
    ]
    crossing_mullions = [
        item
        for item in others
        if 0.12 <= family_len_by_id.get(item["id"], item["length"]) / host_len <= 0.7
        and _angle_delta(item["angle"], host["angle"]) >= 90.0 - _ORTHO_DEG
        and _point_to_seg(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        <= host_len * 0.15
    ]
    mullion_pool = crossing_mullions or mullions
    mullion_ts = [
        _project_t(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        for item in mullion_pool
    ]
    if len(mullion_pool) >= 3 and _gaps_regular(mullion_ts) and len(hatch) < 6:
        nominations.append(
            {
                "kind": KIND_GLAZING,
                "polarity": POLARITY_OPPOSING,
                "confidence": 0.5,
                "reason_codes": ("regular_parallel_mullion_array",),
                "feature_basis": {"mullion_count": len(mullion_pool)},
            }
        )
    grid = [
        item
        for item in others
        if item["length"] / host_len >= 0.5
        and _angle_delta(item["angle"], host["angle"]) <= _PARALLEL_DEG
    ]
    grid_offsets = [
        (item["mid"][0] - host["mid"][0]) * math.sin(math.radians(host["angle"]))
        - (item["mid"][1] - host["mid"][1]) * math.cos(math.radians(host["angle"]))
        for item in grid
    ]
    if len(grid) >= 3 and _gaps_regular(grid_offsets):
        nominations.append(
            {
                "kind": KIND_GRID,
                "polarity": POLARITY_OPPOSING,
                "confidence": 0.5,
                "reason_codes": ("regular_long_parallels",),
                "feature_basis": {"parallel_count": len(grid)},
            }
        )
    table_cross = [
        item
        for item in others
        if 0.3 <= family_len_by_id.get(item["id"], item["length"]) / host_len <= 1.4
        and _angle_delta(item["angle"], host["angle"]) >= 90.0 - _ORTHO_DEG
        and _point_to_seg(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        <= host_len * 0.12
    ]
    table_ts = [
        _project_t(item["mid"][0], item["mid"][1], host["x1"], host["y1"], host["x2"], host["y2"])
        for item in table_cross
    ]
    if len(table_cross) >= 3 and _gaps_regular(table_ts) and len(hatch) < 6:
        nominations.append(
            {
                "kind": KIND_TABLE,
                "polarity": POLARITY_OPPOSING,
                "confidence": 0.5,
                "reason_codes": ("regular_long_crossers",),
                "feature_basis": {"crosser_count": len(table_cross)},
            }
        )
    return nominations


def _nominations_for_target(
    target: Mapping[str, Any],
    context: Sequence[Mapping[str, Any]],
    *,
    words: Sequence[Mapping[str, Any]],
    loops: Sequence[Tuple[str, ...]],
    by_id: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    host_len = target["length"]
    others = [item for item in context if item["id"] != target["id"]]
    near = [
        item
        for item in others
        if _point_to_seg(item["mid"][0], item["mid"][1], target["x1"], target["y1"], target["x2"], target["y2"])
        <= max(host_len * 0.12, 1e-6)
    ]
    nominations: List[Dict[str, Any]] = []
    crosses = [
        item
        for item in near
        if item["length"] / host_len <= 0.35
        and _angle_delta(item["angle"], target["angle"]) >= 90.0 - _ORTHO_DEG
        and abs(_project_t(item["mid"][0], item["mid"][1], target["x1"], target["y1"], target["x2"], target["y2"]) - 0.5)
        <= 0.2
    ]
    if 1 <= len(crosses) <= 2:
        nominations.append(
            {
                "kind": KIND_SYMBOL,
                "polarity": POLARITY_OPPOSING,
                "confidence": 0.4,
                "reason_codes": ("small_crossing_mark",),
                "feature_basis": {"cross_count": len(crosses)},
            }
        )

    target_loops = [loop for loop in loops if target["id"] in loop]
    for loop in target_loops:
        box = _loop_bbox(loop, by_id)
        interior = [
            item
            for item in others
            if item["id"] not in loop and _inside_box(item, box, pad=host_len * 0.02)
        ]
        interior_long = [item for item in interior if item["length"] > host_len * 0.25]
        word_hits = sum(1 for word in words if _word_inside(word, box))
        orientations = {0 if item["angle"] < 45 or item["angle"] > 135 else 1 for item in interior}
        if len(interior) >= 6 and len(orientations) >= 2:
            nominations.append(
                {
                    "kind": KIND_TABLE,
                    "polarity": POLARITY_OPPOSING,
                    "confidence": 0.5,
                    "reason_codes": ("rectangular_interior_grid",),
                    "feature_basis": {"loop": list(loop), "interior_count": len(interior)},
                }
            )
        if interior and not interior_long and (word_hits >= 1 or len(interior) >= 2):
            nominations.append(
                {
                    "kind": KIND_ANNOTATION_BORDER,
                    "polarity": POLARITY_OPPOSING,
                    "confidence": 0.45,
                    "reason_codes": ("outer_rectangle_enclosing_short_marks",),
                    "feature_basis": {"loop": list(loop), "word_hits": word_hits, "interior_count": len(interior)},
                }
            )
        if not interior_long:
            nominations.append(
                {
                    "kind": KIND_FURNITURE,
                    "polarity": POLARITY_OPPOSING,
                    "confidence": 0.45,
                    "reason_codes": ("closed_orthogonal_four_cycle",),
                    "feature_basis": {"loop": list(loop)},
                }
            )

    dashes = str((target["raw"].get(LINEAGE_KEY) or {}).get("source_records") or "")
    live_dashes = str(target["raw"].get("dashes") or "")
    solid = live_dashes in ("", "[] 0", "[]") and "dashed" not in dashes.lower()
    if host_len > 0 and solid:
        nominations.append(
            {
                "kind": KIND_PHYSICAL_WALL,
                "polarity": POLARITY_SUPPORTING,
                "confidence": 0.4,
                "reason_codes": ("solid_retained_stroke",),
                "feature_basis": {"length_pt": host_len},
            }
        )

    return nominations


def _atom(
    *,
    document_id: str,
    page_id: str,
    viewport_id: Optional[str],
    target: Mapping[str, Any],
    nomination: Mapping[str, Any],
) -> EvidenceAtom:
    payload = {
        "kind": nomination["kind"],
        "method": METHOD,
        "target_edge_id": target["id"],
        "source_primitive_ids": list(target["source_primitive_ids"]),
        "reason_codes": list(nomination["reason_codes"]),
        "feature_basis": nomination["feature_basis"],
        "polarity": nomination["polarity"],
    }
    return EvidenceAtom(
        evidence_id=stable_contract_id("ev", payload),
        document_id=document_id,
        page_id=page_id,
        kind=str(nomination["kind"]),
        method=METHOD,
        viewport_id=viewport_id or None,
        bbox=_bbox(target["x1"], target["y1"], target["x2"], target["y2"]),
        confidence=float(nomination["confidence"]),
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=tuple(nomination["reason_codes"]),
        metadata={
            "polarity": nomination["polarity"],
            "target_edge_id": target["id"],
            "source_primitive_ids": list(target["source_primitive_ids"]),
            "feature_basis": nomination["feature_basis"],
        },
    )


def bundle_status(atoms: Sequence[EvidenceAtom]) -> EvidenceResolutionStatus:
    kinds = {atom.kind for atom in atoms}
    polarities = {str((atom.metadata or {}).get("polarity") or "") for atom in atoms}
    if not atoms or kinds == {KIND_UNKNOWN}:
        return EvidenceResolutionStatus.ABSTAINED
    if POLARITY_SUPPORTING in polarities and POLARITY_OPPOSING in polarities:
        return EvidenceResolutionStatus.CONFLICT
    if len(kinds & _OPPOSING_KINDS) > 1:
        return EvidenceResolutionStatus.CONFLICT
    return EvidenceResolutionStatus.CANDIDATE


def collect_typed_semantic_evidence(
    graph: Mapping[str, Any],
    *,
    document_id: str,
    page_id: str,
    viewport_id: Optional[str] = None,
    words: Sequence[Mapping[str, Any]] = (),
) -> Tuple[EvidenceAtom, ...]:
    """Nominate supporting and opposing semantic atoms on retained edges only."""
    context = _context_items(graph)
    targets = [item for item in context if item.get("retained")]
    by_id = {item["id"]: item for item in context if item["id"]}
    loops = _rectangle_loops(graph, by_id)
    family_noms: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    families: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for target in targets:
        families[_line_family_key(target)].append(target)
    family_len_by_id = {
        item["id"]: _family_host(members)["length"]
        for members in families.values()
        for item in members
    }
    for members in families.values():
        host = _family_host(members)
        for nomination in _array_nominations(host, context, family_len_by_id):
            for member in members:
                family_noms[member["id"]].append(nomination)
    atoms: List[EvidenceAtom] = []
    for target in targets:
        nominations = list(family_noms.get(target["id"]) or [])
        nominations.extend(
            _nominations_for_target(target, context, words=words, loops=loops, by_id=by_id)
        )
        if not nominations:
            nominations = [
                {
                    "kind": KIND_UNKNOWN,
                    "polarity": POLARITY_UNKNOWN,
                    "confidence": 0.0,
                    "reason_codes": ("no_typed_semantic_feature",),
                    "feature_basis": {},
                }
            ]
        seen_kinds = set()
        for nomination in sorted(nominations, key=lambda item: (item["kind"], item["reason_codes"])):
            if nomination["kind"] in seen_kinds:
                continue
            seen_kinds.add(nomination["kind"])
            atoms.append(
                _atom(
                    document_id=document_id,
                    page_id=page_id,
                    viewport_id=viewport_id,
                    target=target,
                    nomination=nomination,
                )
            )
    atoms.sort(key=lambda atom: atom.evidence_id)
    return tuple(atoms)


def attach_typed_semantic_evidence(
    graph: Mapping[str, Any],
    *,
    document_id: str,
    page_id: str,
    viewport_id: Optional[str] = None,
    words: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Copy the graph and add a sidecar atom list. Geometry keys stay intact."""
    atoms = collect_typed_semantic_evidence(
        graph,
        document_id=document_id,
        page_id=page_id,
        viewport_id=viewport_id,
        words=words,
    )
    out = dict(graph)
    out[GRAPH_ATOMS_KEY] = [atom.to_dict() for atom in atoms]
    out["semantic_evidence_bundle_status"] = {
        edge_id: bundle_status(group).value
        for edge_id, group in _group_by_edge(atoms).items()
    }
    return out


def _group_by_edge(atoms: Sequence[EvidenceAtom]) -> Dict[str, List[EvidenceAtom]]:
    grouped: Dict[str, List[EvidenceAtom]] = defaultdict(list)
    for atom in atoms:
        grouped[str((atom.metadata or {}).get("target_edge_id") or "")].append(atom)
    return dict(grouped)


def census_semantic_evidence(atoms: Sequence[EvidenceAtom]) -> Dict[str, Any]:
    kinds = {kind: 0 for kind in sorted(_OPPOSING_KINDS | _SUPPORTING_KINDS | {KIND_UNKNOWN})}
    polarities = {POLARITY_SUPPORTING: 0, POLARITY_OPPOSING: 0, POLARITY_UNKNOWN: 0}
    for atom in atoms:
        kinds[atom.kind] = kinds.get(atom.kind, 0) + 1
        polarity = str((atom.metadata or {}).get("polarity") or POLARITY_UNKNOWN)
        polarities[polarity] = polarities.get(polarity, 0) + 1
    grouped = _group_by_edge(atoms)
    conflicts = sum(1 for group in grouped.values() if bundle_status(group) == EvidenceResolutionStatus.CONFLICT)
    abstained = sum(1 for group in grouped.values() if bundle_status(group) == EvidenceResolutionStatus.ABSTAINED)
    return {
        "atom_count": len(atoms),
        "kinds": kinds,
        "polarities": polarities,
        "conflict_edge_bundles": conflicts,
        "abstained_edge_bundles": abstained,
        "retained_edge_bundles": len(grouped),
    }


def assert_graph_geometry_unchanged(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    before_edges = list(before.get("edges") or [])
    after_edges = list(after.get("edges") or [])
    if len(before_edges) != len(after_edges):
        raise AssertionError("U2 must not add or delete Stage-A edges")
    for left, right in zip(before_edges, after_edges):
        for key in ("id", "x1", "y1", "x2", "y2", "a", "b"):
            if left.get(key) != right.get(key):
                raise AssertionError(f"U2 mutated edge geometry field {key}")
