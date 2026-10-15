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
    # Diagnostic quantisation only; never input to W2 or source identity.
    return (round(p[0], 4), round(p[1], 4))

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
    return {
        "status": "SOURCE_COMPONENT_CANDIDATE",
        "seed": seed,
        "role_granted": False,
        "structural_role": "UNRESOLVED",
        "annotation_role": "UNRESOLVED",
        "complete_exact_cycle": closed_simple_cycle,
        "component_edges": sorted(visited),
        "component_edge_count": len(visited),
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
