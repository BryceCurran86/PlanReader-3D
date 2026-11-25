"""U1 review: real-drawing lineage trace + Stage-A performance comparison.

Diagnostic/research only. Does not touch benchmark gold, does not judge U1
by quantity movement. Traces plural-parent lineage, recursive merges,
snap-collapse, and metadata conflicts on real native-vector drawings, and
measures the wall-clock cost of the new source-recovery pass against the
pre-U1 baseline (same region, lineage disabled) to check for an unwanted
new O(n^2) regression.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_vector_geometry_v130 import extract_native_page
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    filter_structural_segments,
    _point_pairs_to_segment_dicts,
    _segments_to_point_pairs,
)
from pb_accuracy_v13_engines_v145 import split_segments_at_intersections
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY

SOURCES_DIR = REPO_ROOT / "benchmarks" / "sources"

PROJECTS = [
    {
        "name": "Baghau",
        "pdf": SOURCES_DIR / "bq_and_drawing_1747803602496.pdf",
        "page_0based": 35,
        "region": (350.0, 350.0, 950.0, 850.0),
    },
    {
        "name": "Lamu",
        "pdf": SOURCES_DIR / "lamu-ishakani-ecd-classrooms-boq.pdf",
        "page_0based": 40,
        "region": (100.0, 20.0, 750.0, 380.0),
    },
    {
        "name": "Dungicha",
        "pdf": SOURCES_DIR / "dungicha_3classrooms.pdf",
        "page_0based": 133,
        "region": (0.0, 550.0, 900.0, 950.0),
    },
    {
        "name": "KSTVET",
        "pdf": SOURCES_DIR / "1727358888238-bq-nd-drawing.pdf",
        "page_0based": 53,
        "region": (150.0, 300.0, 750.0, 800.0),
    },
]


def _overlaps_region(bbox, region) -> bool:
    bx0, by0, bx1, by1 = bbox
    rx0, ry0, rx1, ry1 = region
    return not (bx1 < rx0 or bx0 > rx1 or by1 < ry0 or by0 > ry1)


def _region_segments(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    doc = fitz.open(str(spec["pdf"]))
    try:
        page = doc[spec["page_0based"]]
        native = extract_native_page(page)
    finally:
        doc.close()
    region = spec["region"]
    return [
        s
        for s in native["segments"]
        if _overlaps_region(
            (min(s["x1"], s["x2"]), min(s["y1"], s["y2"]), max(s["x1"], s["x2"]), max(s["y1"], s["y2"])),
            region,
        )
    ]


def _time_stage_a_with_and_without_lineage(segments: List[Dict[str, Any]]) -> Tuple[float, float]:
    """Compare wall-clock cost of the U1 source-recovery pass against the
    pre-U1 shape (no source_segments passed to _point_pairs_to_segment_dicts,
    i.e. the exact old fabricated-sentinel path)."""
    structural, _ = filter_structural_segments(segments)
    point_pairs = _segments_to_point_pairs(structural)
    split_pairs = split_segments_at_intersections(point_pairs)

    t0 = time.perf_counter()
    _point_pairs_to_segment_dicts(split_pairs)  # legacy path, source_segments=None
    without_lineage = time.perf_counter() - t0

    t0 = time.perf_counter()
    _point_pairs_to_segment_dicts(split_pairs, source_segments=structural)  # U1 path
    with_lineage = time.perf_counter() - t0

    return without_lineage, with_lineage


def _find_examples(graph: Dict[str, Any], structural_count: int) -> Dict[str, Any]:
    edges = [e for e in graph["edges"] if not e.get("_removed")]
    examples: Dict[str, Any] = {}

    # B: 2+ sources -> one edge (plural direct lineage)
    plural = [e for e in edges if len(e.get(LINEAGE_KEY, {}).get("source_primitive_ids", [])) >= 2]
    if plural:
        e = min(plural, key=lambda e: len(e[LINEAGE_KEY]["source_primitive_ids"]))
        examples["plural_parent_edge"] = {
            "edge_id": e.get("id"),
            "coords": (e["x1"], e["y1"], e["x2"], e["y2"]),
            "source_primitive_ids": e[LINEAGE_KEY]["source_primitive_ids"],
            "attribute_status": e[LINEAGE_KEY]["attribute_status"],
        }

    # C: recursive collinear merge with 3+ leaf parents
    recursive = [e for e in edges if len(e.get("collinear_merge_leaf_edge_ids") or []) >= 3]
    if recursive:
        e = max(recursive, key=lambda e: len(e["collinear_merge_leaf_edge_ids"]))
        examples["recursive_merge_edge"] = {
            "edge_id": e.get("id"),
            "coords": (e["x1"], e["y1"], e["x2"], e["y2"]),
            "leaf_edge_ids": e["collinear_merge_leaf_edge_ids"],
            "primitive_lineage_ids": e.get(LINEAGE_KEY, {}).get("source_primitive_ids", []),
        }

    # E: metadata conflict
    conflicted = [e for e in edges if e.get(LINEAGE_KEY, {}).get("attribute_conflicts")]
    if conflicted:
        e = conflicted[0]
        examples["metadata_conflict_edge"] = {
            "edge_id": e.get("id"),
            "coords": (e["x1"], e["y1"], e["x2"], e["y2"]),
            "conflicts": e[LINEAGE_KEY]["attribute_conflicts"],
            "records": [
                {"id": r.get("id"), "width": r.get("width"), "layer": r.get("layer")}
                for r in e[LINEAGE_KEY]["source_records"]
            ],
        }

    # D: snap-collapsed fragment
    collapsed = graph.get("snap_collapsed_fragments") or []
    if collapsed:
        c = collapsed[0]
        examples["snap_collapsed"] = {
            "fragment_id": c.get("id"),
            "coords": (c.get("x1"), c.get("y1"), c.get("x2"), c.get("y2")),
            "source_primitive_ids": c[LINEAGE_KEY]["source_primitive_ids"],
        }

    # A: one source split into several derived fragments
    from collections import Counter

    source_to_fragments: Dict[str, int] = Counter()
    for e in edges:
        for sid in e.get(LINEAGE_KEY, {}).get("source_primitive_ids", []):
            source_to_fragments[sid] += 1
    multi_fragment_sources = {sid: n for sid, n in source_to_fragments.items() if n >= 2}
    if multi_fragment_sources:
        sid = max(multi_fragment_sources, key=multi_fragment_sources.get)
        contributing = [
            e.get("id")
            for e in edges
            if sid in e.get(LINEAGE_KEY, {}).get("source_primitive_ids", [])
        ]
        examples["one_source_many_fragments"] = {
            "source_id": sid,
            "fragment_count": multi_fragment_sources[sid],
            "fragment_edge_ids": contributing,
        }

    examples["summary_counts"] = {
        "structural_segments": structural_count,
        "graph_edges": len(edges),
        "plural_parent_edges": len(plural),
        "recursive_merge_3plus_edges": len(recursive),
        "metadata_conflict_edges": len(conflicted),
        "snap_collapsed_fragments": len(collapsed),
    }
    return examples


def main() -> None:
    for spec in PROJECTS:
        if not spec["pdf"].exists():
            print(f"SKIP {spec['name']}: source not present")
            continue
        segments = _region_segments(spec)
        without_s, with_s = _time_stage_a_with_and_without_lineage(segments)
        graph = build_wall_graph_for_viewport(segments)

        print(f"\n=== {spec['name']} (page {spec['page_0based'] + 1}, region {spec['region']}) ===")
        print(f"  raw region segments: {len(segments)}")
        print(f"  Stage-A rebuild time WITHOUT lineage: {without_s*1000:.2f}ms")
        print(f"  Stage-A rebuild time WITH lineage:    {with_s*1000:.2f}ms")
        ratio = (with_s / without_s) if without_s > 0 else float("inf")
        print(f"  overhead ratio: {ratio:.2f}x")

        examples = _find_examples(graph, len(segments))
        print(f"  summary: {examples['summary_counts']}")
        for key in (
            "one_source_many_fragments",
            "plural_parent_edge",
            "recursive_merge_edge",
            "snap_collapsed",
            "metadata_conflict_edge",
        ):
            if key in examples:
                print(f"  [{key}] {examples[key]}")
            else:
                print(f"  [{key}] none found in this region")


if __name__ == "__main__":
    main()
