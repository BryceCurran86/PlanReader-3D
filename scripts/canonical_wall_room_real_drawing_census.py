"""Real-drawing diagnostic census for the shadow canonical wall/room evidence
model. Research/diagnostic only -- does not compare against BOQ quantities,
does not publish anything, does not touch benchmark gold.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_vector_geometry_v130 import extract_native_page, detect_wall_pairs
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import attach_typed_semantic_evidence
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates
from pb_canonical_wall_room_evidence_model import (
    resolve_wall_physical_evidence,
    reconstruct_room_candidates_from_credible_walls,
)
from pb_migration_contracts import EvidenceResolutionStatus

SOURCES_DIR = REPO_ROOT / "benchmarks" / "sources"

PROJECTS = [
    {"name": "Baghau", "pdf": SOURCES_DIR / "bq_and_drawing_1747803602496.pdf", "page_0based": 35, "region": (350.0, 350.0, 950.0, 850.0)},
    {"name": "Lamu", "pdf": SOURCES_DIR / "lamu-ishakani-ecd-classrooms-boq.pdf", "page_0based": 40, "region": (100.0, 20.0, 750.0, 380.0)},
    {"name": "Dungicha", "pdf": SOURCES_DIR / "dungicha_3classrooms.pdf", "page_0based": 133, "region": (0.0, 550.0, 900.0, 950.0)},
    {"name": "KSTVET", "pdf": SOURCES_DIR / "1727358888238-bq-nd-drawing.pdf", "page_0based": 53, "region": (150.0, 300.0, 750.0, 800.0)},
]


def _overlaps_region(bbox, region) -> bool:
    bx0, by0, bx1, by1 = bbox
    rx0, ry0, rx1, ry1 = region
    return not (bx1 < rx0 or bx0 > rx1 or by1 < ry0 or by0 > ry1)


def _region_segments(spec) -> List[Dict[str, Any]]:
    doc = fitz.open(str(spec["pdf"]))
    try:
        native = extract_native_page(doc[spec["page_0based"]])
    finally:
        doc.close()
    region = spec["region"]
    return [
        s for s in native["segments"]
        if _overlaps_region((min(s["x1"], s["x2"]), min(s["y1"], s["y2"]), max(s["x1"], s["x2"]), max(s["y1"], s["y2"])), region)
    ]


def _census_one(spec) -> Dict[str, Any]:
    segments = _region_segments(spec)
    t0 = time.perf_counter()
    graph = build_wall_graph_for_viewport(segments)
    graph = attach_typed_semantic_evidence(graph, document_id=spec["name"], page_id=str(spec["page_0based"]), viewport_id=f"{spec['name']}_v1")
    junctions, relationships = classify_junctions(graph, document_id=spec["name"], page_id=str(spec["page_0based"]), viewport_id=f"{spec['name']}_v1")
    walls, edge_id_to_wall_id = assemble_wall_candidates(graph, junctions, relationships, viewport_id=f"{spec['name']}_v1")
    pairs = detect_wall_pairs(segments)
    resolved, minted = resolve_wall_physical_evidence(walls, graph=graph, document_id=spec["name"], page_id=str(spec["page_0based"]), paired_wall_faces=pairs)
    rooms_conservative = reconstruct_room_candidates_from_credible_walls(graph, resolved, edge_id_to_wall_id, document_id=spec["name"], viewport_id=f"{spec['name']}_v1", exclude_conflict=True)
    rooms_permissive = reconstruct_room_candidates_from_credible_walls(graph, resolved, edge_id_to_wall_id, document_id=spec["name"], viewport_id=f"{spec['name']}_v1", exclude_conflict=False)
    elapsed = time.perf_counter() - t0

    by_status: Dict[str, int] = {}
    by_existence: Dict[str, int] = {}
    for w in resolved:
        by_status[w.status.value] = by_status.get(w.status.value, 0) + 1
        pe = w.metadata.get("physical_evidence_status", "")
        by_existence[pe] = by_existence.get(pe, 0) + 1

    firm_rooms_conservative = [r for r in rooms_conservative if r.status != EvidenceResolutionStatus.ABSTAINED]

    # False-strong samples: CORROBORATED-top-level walls whose evidence should be double-checked.
    corroborated = [w for w in resolved if w.status == EvidenceResolutionStatus.CORROBORATED]
    existence_corroborated_capped = [w for w in resolved if w.metadata.get("physical_evidence_status") == "corroborated" and w.status != EvidenceResolutionStatus.CORROBORATED]

    return {
        "name": spec["name"],
        "elapsed_s": round(elapsed, 3),
        "raw_region_segments": len(segments),
        "stage_a_edges": len([e for e in graph["edges"] if not e.get("_removed")]),
        "excluded_segments": len(graph.get("excluded_segments", [])),
        "wall_hypotheses": len(walls),
        "wall_status_breakdown": by_status,
        "wall_existence_breakdown": by_existence,
        "wall_pairs_detected": len(pairs),
        "rooms_conservative_total": len(rooms_conservative),
        "rooms_conservative_firm": len(firm_rooms_conservative),
        "rooms_permissive_total": len(rooms_permissive),
        "corroborated_top_level_count": len(corroborated),
        "existence_corroborated_but_capped_count": len(existence_corroborated_capped),
        "corroborated_samples": [
            {
                "candidate_id": w.candidate_id,
                "length_pt": round(_chain_len(w), 2),
                "families": w.metadata.get("physical_evidence_families"),
                "supporting_evidence_ids": len(w.supporting_evidence_ids),
                "reason_codes": w.reason_codes,
            }
            for w in (corroborated + existence_corroborated_capped)[:8]
        ],
        "conflict_samples": [
            {
                "candidate_id": w.candidate_id,
                "length_pt": round(_chain_len(w), 2),
                "supporting": len(w.supporting_evidence_ids),
                "opposing": len(w.conflicting_evidence_ids),
            }
            for w in resolved if w.status == EvidenceResolutionStatus.CONFLICT
        ][:5],
    }


def _chain_len(wall) -> float:
    pts = wall.centerline_pts
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        total += ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5
    return total


def main() -> None:
    results = []
    for spec in PROJECTS:
        if not spec["pdf"].exists():
            print(f"SKIP {spec['name']}: source not present")
            continue
        result = _census_one(spec)
        results.append(result)
        print(f"\n=== {result['name']} (region-scoped) ===")
        for key, value in result.items():
            if key in ("corroborated_samples", "conflict_samples"):
                continue
            print(f"  {key}: {value}")
        print("  corroborated_samples:")
        for sample in result["corroborated_samples"]:
            print(f"    {sample}")
        print("  conflict_samples:")
        for sample in result["conflict_samples"]:
            print(f"    {sample}")

    out_path = REPO_ROOT / "scripts" / "canonical_wall_room_census_output.json"
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
