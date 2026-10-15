"""Read-only source-native cycle census. Never classifies walls or issues quantities.

This diagnostic deliberately takes an indexed native seed and original document bytes.
It reports exact closed-component evidence and all conflicting endpoint owners,
without choosing a structural or annotation role.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

def _point(p):
    return (float(p.x), float(p.y))

def _key(p):
    # Source-native exact endpoint equality: never quantise a real source gap
    # into an invented junction or erase a tiny genuine indexed line.
    # W2 retains its separate production snap authority and 2.5pt tolerance.
    return (float(p[0]), float(p[1]))

def _edge_biconnected_blocks(visited, selected):
    """Enumerate every exact native edge block, never choose a symbol role.

    Blocks separate true cycles sharing a junction while preserving ambiguous
    chords, parallel edges, spurs and all indexed source-line ownership.
    """
    graph = defaultdict(list)
    for name in sorted(visited):
        item = selected[name]
        a, b = _key(item["a"]), _key(item["b"])
        graph[a].append((b, name))
        graph[b].append((a, name))

    discovery, low, stack, blocks = {}, {}, [], []
    clock = 0

    def visit(vertex, parent_edge=None):
        nonlocal clock
        clock += 1
        discovery[vertex] = low[vertex] = clock
        for neighbour, edge_id in sorted(graph[vertex]):
            if edge_id == parent_edge:
                continue
            if neighbour not in discovery:
                stack.append(edge_id)
                visit(neighbour, edge_id)
                low[vertex] = min(low[vertex], low[neighbour])
                if low[neighbour] >= discovery[vertex]:
                    block = []
                    while stack:
                        member = stack.pop()
                        block.append(member)
                        if member == edge_id:
                            break
                    blocks.append(sorted(block))
            elif discovery[neighbour] < discovery[vertex]:
                stack.append(edge_id)
                low[vertex] = min(low[vertex], discovery[neighbour])

    for vertex in sorted(graph):
        if vertex not in discovery:
            visit(vertex)
    output = []
    for members in sorted(blocks):
        local_degrees = defaultdict(int)
        for member in members:
            item = selected[member]
            local_degrees[_key(item["a"])] += 1
            local_degrees[_key(item["b"])] += 1
        simple = (
            len(members) >= 3 and len(local_degrees) == len(members)
            and all(degree == 2 for degree in local_degrees.values())
        )
        output.append({
            "source_edge_ids": members,
            "source_edge_count": len(members),
            "complete_exact_cycle": simple,
            "no_role_granted": True,
        })
    # Integrity: no indexed member is silently lost or double-counted.
    assert sorted(edge for block in output for edge in block["source_edge_ids"]) == sorted(visited)
    return output


def _simple_cycles_containing_seed(visited, selected, seed, *, state_limit=20000,
                                   cycle_limit=500):
    """Bounded exact source-endpoint paths closing the selected native edge.

    Does not elect a symbol or a wall. If boundedness is reached, fail closed
    with INCOMPLETE and retain the already discovered source candidates.
    """
    exemplar = selected[seed]
    first, last = _key(exemplar["a"]), _key(exemplar["b"])
    graph = defaultdict(list)
    for name in sorted(visited):
        if name == seed:
            continue
        item = selected[name]
        a, b = _key(item["a"]), _key(item["b"])
        graph[a].append((b, name))
        graph[b].append((a, name))
    for rows in graph.values():
        rows.sort(key=lambda x: (x[1], x[0]))

    frontier = [(first, frozenset({first}), ())]
    seen = set()
    states = 0
    truncated = False
    while frontier:
        if states >= state_limit or len(seen) >= cycle_limit:
            truncated = True
            break
        vertex, nodes, edges = frontier.pop()
        states += 1
        for adjacent, edge_id in graph.get(vertex, ()):
            if adjacent == last:
                if len(edges) >= 1:
                    cycle = frozenset((seed, edge_id, *edges))
                    if len(cycle) >= 3:
                        seen.add(cycle)
                continue
            if adjacent in nodes:
                continue
            frontier.append((adjacent, nodes | {adjacent}, (*edges, edge_id)))
    records = [
        {"source_edge_ids": sorted(cycle),
         "source_edge_count": len(cycle),
         "role_granted": False}
        for cycle in seen
    ]
    records.sort(key=lambda d: (d["source_edge_count"], d["source_edge_ids"]))
    return {
        "status": ("INCOMPLETE_SAFETY_BOUND" if truncated else "COMPLETE_EXACT_SOURCE_PATH_CENSUS"),
        "search_states": states,
        "source_seed_cycle_count": len(records),
        "source_seed_cycles": records,
        "annotation_or_structural_role_granted": False,
    }


def inspect_native_component(page, seed: str):
    """Return candidate component and raw source receipts, not an authority grant."""
    segments = {}
    for path_id, drawing in enumerate(page.get_drawings()):
        for item_id, item in enumerate(drawing.get("items", ())):
            if not item or item[0] != "l" or len(item) < 3:
                continue
            a, b = _point(item[1]), _point(item[2])
            if not all(math.isfinite(v) for v in (*a, *b)) or _key(a) == _key(b):
                continue
            name = f"d{path_id}i{item_id}"
            segments[name] = {
                "id": name, "a": a, "b": b,
                "stroke": tuple(drawing.get("color") or ()),
                "fill": tuple(drawing.get("fill") or ()),
                "width": drawing.get("width"),
                "layer": drawing.get("layer"),
                "dashes": drawing.get("dashes"),
                "type": drawing.get("type"),
            }
    if seed not in segments:
        return {"status": "SEED_NOT_FOUND", "seed": seed, "role_granted": False}
    # Never aggregate by style alone: only identically painted source lines
    # meeting at exact original endpoints can enter this candidate component.
    exemplar = segments[seed]
    style_fields = ("stroke", "fill", "width", "layer", "dashes", "type")
    selected = {k: v for k, v in segments.items()
                if all(v[f] == exemplar[f] for f in style_fields)}
    adjacency = defaultdict(set)
    for name, item in selected.items():
        adjacency[_key(item["a"])].add(name)
        adjacency[_key(item["b"])].add(name)
    visited = set()
    frontier = [seed]
    while frontier:
        name = frontier.pop()
        if name in visited:
            continue
        visited.add(name)
        item = selected[name]
        for endpoint in (_key(item["a"]), _key(item["b"])):
            frontier.extend(adjacency[endpoint] - visited)
    degrees = defaultdict(int)
    for name in visited:
        item = selected[name]
        degrees[_key(item["a"])] += 1
        degrees[_key(item["b"])] += 1
    closed_simple_cycle = len(visited) >= 3 and all(n == 2 for n in degrees.values()) and len(degrees) == len(visited)
    source_blocks = _edge_biconnected_blocks(visited, selected)
    seed_cycle_census = _simple_cycles_containing_seed(visited, selected, seed)
    return {
        "status": "SOURCE_COMPONENT_CANDIDATE",
        "seed": seed,
        "role_granted": False,
        "structural_role": "UNRESOLVED",
        "annotation_role": "UNRESOLVED",
        "complete_exact_cycle": closed_simple_cycle,
        "component_edges": sorted(visited),
        "component_edge_count": len(visited),
        "exact_native_edge_blocks": source_blocks,
        "exact_simple_cycle_block_count": sum(b["complete_exact_cycle"] for b in source_blocks),
        "seed_incident_exact_cycle_census": seed_cycle_census,
        "component_role_ambiguous": True,
        "endpoint_degrees": [{"point": list(p), "degree": n} for p, n in sorted(degrees.items())],
        "source_segments": [selected[k] for k in sorted(visited)],
        "all_original_seed_endpoint_owners": {
            str(p): sorted(k for k, item in segments.items()
                           if _key(item["a"]) == p or _key(item["b"]) == p)
            for p in (_key(exemplar["a"]), _key(exemplar["b"]))
        },
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page", type=int, required=True, help="1-based original PDF page")
    parser.add_argument("--seed", required=True, help="original d<path>i<item> indexed segment")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = Path(args.pdf).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest.lower() != args.sha256.lower():
        raise SystemExit("SOURCE_SHA_MISMATCH")
    import fitz
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        if not 1 <= args.page <= pdf.page_count:
            raise SystemExit("INVALID_PAGE")
        result = inspect_native_component(pdf.load_page(args.page - 1), args.seed)
    finally:
        pdf.close()
    result.update({"source_sha256": digest, "page": args.page,
                   "publication": "READ_ONLY_NO_AUTHORITY",
                   "quantity_granted": False, "room_granted": False})
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")

if __name__ == "__main__":
    main()
