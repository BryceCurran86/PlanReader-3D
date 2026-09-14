"""Shadow validation of the wall-linear authority bridge on real drawings.

Diagnostic only. Does not invent scale, height, thickness, or whole-building
perimeter. Does not compare against BOQ. Does not publish quantities.
"""
from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_canonical_wall_room_evidence_model import resolve_wall_physical_evidence
from pb_migration_contracts import DocumentEvidence, EvidenceResolutionStatus, ViewportEvidence, ViewportResolutionStatus
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_existence_authority import (
    adapt_wall_candidate_to_entity_evidence,
    wall_physical_existence_status,
)
from pb_vector_geometry_v130 import detect_wall_pairs, extract_native_page
from pb_wall_length_quantity import build_wall_length_quantity
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import GRAPH_ATOMS_KEY, attach_typed_semantic_evidence
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates

SOURCES_DIR = REPO_ROOT / "benchmarks" / "sources"

# Region clips are diagnostic windows, not whole-building scope.
DRAWINGS = [
    {"label": "Baghau", "pdf": SOURCES_DIR / "bq_and_drawing_1747803602496.pdf", "page_0based": 35, "region": (350.0, 350.0, 950.0, 850.0)},
    {"label": "Lamu", "pdf": SOURCES_DIR / "lamu-ishakani-ecd-classrooms-boq.pdf", "page_0based": 40, "region": (100.0, 20.0, 750.0, 380.0)},
    {"label": "Dungicha", "pdf": SOURCES_DIR / "dungicha_3classrooms.pdf", "page_0based": 133, "region": (0.0, 550.0, 900.0, 950.0)},
    {"label": "KSTVET", "pdf": SOURCES_DIR / "1727358888238-bq-nd-drawing.pdf", "page_0based": 53, "region": (150.0, 300.0, 750.0, 800.0)},
]


def _overlaps_region(bbox, region) -> bool:
    bx0, by0, bx1, by1 = bbox
    rx0, ry0, rx1, ry1 = region
    return not (bx1 < rx0 or bx0 > rx1 or by1 < ry0 or by0 > rx1)


def _region_segments(spec) -> List[Dict[str, Any]]:
    doc = fitz.open(str(spec["pdf"]))
    try:
        native = extract_native_page(doc[spec["page_0based"]])
    finally:
        doc.close()
    region = spec["region"]
    return [
        s for s in native["segments"]
        if _overlaps_region(
            (min(s["x1"], s["x2"]), min(s["y1"], s["y2"]), max(s["x1"], s["x2"]), max(s["y1"], s["y2"])),
            region,
        )
    ]


def _shadow_one(spec: Dict[str, Any]) -> Dict[str, Any]:
    source_sha256 = hashlib.sha256(spec["pdf"].read_bytes()).hexdigest()
    document_id = f"doc-{source_sha256[:16]}"
    page_id = f"page-{spec['page_0based']}"
    viewport_id = f"vp-{spec['page_0based']}"
    page_no = int(spec["page_0based"]) + 1

    segments = _region_segments(spec)
    graph = build_wall_graph_for_viewport(segments)
    graph = attach_typed_semantic_evidence(
        graph,
        document_id=document_id,
        page_id=page_id,
        viewport_id=viewport_id,
    )
    junctions, relationships = classify_junctions(
        graph,
        document_id=document_id,
        page_id=page_id,
        viewport_id=viewport_id,
    )
    walls, _edge_id_to_wall_id = assemble_wall_candidates(
        graph, junctions, relationships, viewport_id=viewport_id
    )
    pairs = detect_wall_pairs(segments)
    resolved, minted = resolve_wall_physical_evidence(
        walls,
        graph=graph,
        document_id=document_id,
        page_id=page_id,
        paired_wall_faces=pairs,
    )

    semantic_atoms = list(graph.get(GRAPH_ATOMS_KEY) or [])
    catalog = [*semantic_atoms, *minted]
    evidence_ids = tuple(
        dict.fromkeys(
            str(a.get("evidence_id") if isinstance(a, dict) else a.evidence_id)
            for a in catalog
            if (a.get("evidence_id") if isinstance(a, dict) else a.evidence_id)
        )
    )
    document = DocumentEvidence(
        document_id=document_id,
        source_sha256=source_sha256,
        page_count=1,
        page_ids=(page_id,),
        evidence_ids=evidence_ids,
    )
    viewport = ViewportEvidence(
        viewport_id=viewport_id,
        document_id=document_id,
        page_id=page_id,
        bbox=tuple(spec["region"]),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )
    context = ProviderContext(
        run_id="wall-linear-shadow",
        workspace_id="shadow",
        project_id="shadow",
        document_id=document_id,
        source_sha256=source_sha256,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(spec["page_0based"],),
        owned_viewport_ids=(viewport_id,),
        evidence_snapshot_id="shadow-ev",
        owned_page_numbers=(page_no,),
        viewport_page_ownership=((viewport_id, page_no),),
    )

    existence_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    abstentions: Counter[str] = Counter()
    firm_lengths = 0
    missing_entity = 0

    for wall in resolved:
        existence = wall_physical_existence_status(
            wall,
            evidence_atoms=catalog,
            document=document,
            viewport=viewport,
        )
        existence_counts[existence.value] += 1
        entity = adapt_wall_candidate_to_entity_evidence(
            wall,
            evidence_atoms=catalog,
            document=document,
            viewport=viewport,
            context=context,
        )
        if entity is None:
            missing_entity += 1
            entity_counts["unavailable"] += 1
            abstentions["physical_wall_entity_evidence_unavailable"] += 1
            continue
        entity_counts[entity.status.value] += 1
        qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            page_no=page_no,
            scale_calibration=None,
        )
        if qty.abstained:
            for reason in qty.blocking_reasons:
                abstentions[reason] += 1
        else:
            firm_lengths += 1

    return {
        "label": spec["label"],
        "page_0based": spec["page_0based"],
        "region": spec["region"],
        "canonical_walls_considered": len(resolved),
        "physical_existence_corroborated": existence_counts.get("corroborated", 0),
        "entity_evidence_corroborated": entity_counts.get("corroborated", 0),
        "firm_scale_available": False,
        "firm_wall_length_quantities": firm_lengths,
        "existence_status_counts": dict(existence_counts),
        "entity_status_counts": dict(entity_counts),
        "missing_entity_evidence": missing_entity,
        "abstentions_by_reason": dict(abstentions),
        "notes": (
            "Region-scoped diagnostic window only. Partial walls are not a "
            "whole-building perimeter. Scale was not invented."
        ),
    }


def available_drawings() -> List[Dict[str, Any]]:
    return [spec for spec in DRAWINGS if spec["pdf"].exists()]


def run_shadow() -> List[Dict[str, Any]]:
    return [_shadow_one(spec) for spec in available_drawings()]


def main() -> None:
    found = available_drawings()
    if not found:
        print("SKIP: no real-drawing PDFs present under benchmarks/sources")
        return
    for result in run_shadow():
        print(f"\n=== {result['label']} page={result['page_0based']} region={result['region']} ===")
        for key, value in result.items():
            if key == "label":
                continue
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
