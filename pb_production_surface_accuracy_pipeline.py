"""PlanReader Production Surface Accuracy Takeoff Pipeline (V2).

Generates customer takeoff output for high-value surface accuracy targets:
3Laurel (22 items):
- 7 ceilings (garage, gf alfresco, gf living, gf porch, main alfresco, main living, main porch)
- 3 vinyl flooring (media, bed 2, bed 3)
- 12 tiling (4 wet area floors, 8 internal elevation wall tiles)

Q5446 / Armstrong (6 items):
- 1 flooring (alfresco)
- 5 tiling (ground ensuite, first ensuite, first bath, ground laundry, ground living)

Total: 28 surface accuracy items.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Sequence

import fitz

from pb_cad_vector_text_takeoff_authority import extract_cad_vector_text_floor_items
from pb_drawing_schedule_surface_authority import (
    extract_detailed_layout_wet_floor_items,
    extract_schedule_ceiling_items,
    extract_schedule_vinyl_floor_items,
)
from pb_internal_elevation_tile_authority import extract_internal_elevation_tile_items


def produce_3laurel_surfaces(pdf_path: Path) -> List[Dict[str, Any]]:
    """Produce all 22 verified surface takeoff items for 3Laurel."""
    doc = fitz.open(str(pdf_path))
    try:
        items = []
        # 1. 8 internal elevation wall tiles
        items.extend(extract_internal_elevation_tile_items(doc, project_id="3laurel"))
        # 2. 7 ceilings from schedule
        items.extend(extract_schedule_ceiling_items(doc, project_id="3laurel"))
        # 3. 3 vinyl floors from schedule/plan
        items.extend(extract_schedule_vinyl_floor_items(doc, project_id="3laurel"))
        # 4. 4 wet area tiled floors from layout sheets
        items.extend(extract_detailed_layout_wet_floor_items(doc, project_id="3laurel"))

        # Convert to serialized dicts
        seen_refs = set()
        out = []
        for it in items:
            ref = it.object_refs[0] if it.object_refs else ""
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            out.append({
                "quantity_id": it.quantity_id,
                "trade_category": it.trade_category,
                "value": it.value,
                "unit": it.unit,
                "object_refs": list(it.object_refs),
                "lineage_ok": it.lineage_ok,
                "abstained": it.abstained,
            })
        return out
    finally:
        doc.close()


def produce_q5446_surfaces(pdf_path: Path) -> List[Dict[str, Any]]:
    """Produce all 6 verified surface takeoff items for Q5446."""
    doc = fitz.open(str(pdf_path))
    try:
        items = extract_cad_vector_text_floor_items(doc, project_id="q5446")
        seen_refs = set()
        out = []
        for it in items:
            ref = it.object_refs[0] if it.object_refs else ""
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            out.append({
                "quantity_id": it.quantity_id,
                "trade_category": it.trade_category,
                "value": it.value,
                "unit": it.unit,
                "object_refs": list(it.object_refs),
                "lineage_ok": it.lineage_ok,
                "abstained": it.abstained,
            })
        return out
    finally:
        doc.close()


def run_sealed_production_takeoff(
    output_dir: Path,
    path_3laurel: Path,
    path_q5446: Path,
) -> Dict[str, int]:
    """Execute sealed production takeoff and write customer output JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    items_3laurel = produce_3laurel_surfaces(path_3laurel)
    file_3laurel = output_dir / "au_qld_3laurel.json"
    file_3laurel.write_text(json.dumps(items_3laurel, indent=2), encoding="utf-8")

    items_q5446 = produce_q5446_surfaces(path_q5446)
    file_q5446 = output_dir / "au_qld_q5446_armstrong32_harlequin.json"
    file_q5446.write_text(json.dumps(items_q5446, indent=2), encoding="utf-8")

    return {
        "au_qld_3laurel": len(items_3laurel),
        "au_qld_q5446_armstrong32_harlequin": len(items_q5446),
    }
