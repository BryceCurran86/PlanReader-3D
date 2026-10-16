"""Read-only annotation-cycle census for one original PDF.

The classifier lives in pb_annotation_cycle_shadow. This tool does not write
production geometry, quantities, or source files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from pb_annotation_cycle_shadow import (
    classify_exact_annotation_cycles,
    shadow_annotation_cycle_topology,
)
from pb_vector_geometry_v130 import extract_native_page

SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _words(page) -> list[dict]:
    return [
        {"text": word[4], "x0": word[0], "y0": word[1], "x1": word[2], "y1": word[3]}
        for word in page.get_text("words")
        if word[4]
    ]


def _summary(result: dict) -> dict:
    proven = [
        cycle for cycle in result["cycles"]
        if cycle["status"] == "source_proven_annotation_cycle"
    ]
    failures: dict[str, int] = {}
    for cycle in result["cycles"]:
        for reason in cycle["failed_gates"]:
            failures[reason] = failures.get(reason, 0) + 1
    return {
        "proven_cycle_count": len(proven),
        "quarantined_primitive_count": len(result["quarantined_primitive_ids"]),
        "contained_text": sorted({
            item["text"]
            for cycle in proven
            for item in cycle["contained_source_text"]
        }),
        "rejected_gate_counts": failures,
        "diagnostic_only": True,
        "quantity_or_metric_area_published": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pages", default="7,11")
    parser.add_argument(
        "--page-11-plan-bbox",
        default="251.52,471.2,1195.44,1946.48",
        help="Source floor-finish plan box already measured for page 11",
    )
    args = parser.parse_args()
    payload = args.pdf.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != SOURCE_SHA:
        raise SystemExit("original source PDF SHA mismatch")
    pages = tuple(int(item) for item in args.pages.split(",") if item)
    plan_box = tuple(float(item) for item in args.page_11_plan_bbox.split(","))
    report = {"source_sha256": digest, "pages": []}
    with fitz.open(stream=payload, filetype="pdf") as document:
        for page_number in pages:
            page = document[page_number - 1]
            segments = extract_native_page(page)["segments"]
            bounds = page.rect
            page_box = (bounds.x0, bounds.y0, bounds.x1, bounds.y1)
            span = min(bounds.width, bounds.height)
            page_result = classify_exact_annotation_cycles(
                segments, _words(page), page_span=span, viewport_bbox=page_box,
            )
            row = {
                "page": page_number,
                "page_partition": _summary(page_result),
                "quarantined_primitive_ids": page_result["quarantined_primitive_ids"],
            }
            if page_number == 11:
                view_result = classify_exact_annotation_cycles(
                    segments, _words(page), page_span=span, viewport_bbox=plan_box,
                )
                row["floor_finish_plan_partition"] = _summary(view_result)
                row["d26362i0_quarantined_in_plan_view"] = (
                    "d26362i0" in view_result["quarantined_primitive_ids"]
                )
                local_ids = set(view_result["quarantined_primitive_ids"]) | {"d1288i0", "d1308i0"}
                local = [segment for segment in segments if segment["id"] in local_ids]
                shadow = shadow_annotation_cycle_topology(
                    local, _words(page), page_span=span, viewport_bbox=plan_box,
                    document_id="annotation-cycle-shadow", page_id="11",
                    viewport_id="source_plan_view_c57aa3592e81d66ad2fa5a92",
                )
                row["local_w2_w4_shadow"] = {
                    "quarantined_count": len(shadow["classification"]["quarantined_primitive_ids"]),
                    "d26362i0_withheld": "d26362i0" in shadow["classification"]["quarantined_primitive_ids"],
                    "unaffected_grid_edge_geometry_unchanged": shadow[
                        "unaffected_non_annotation_edge_geometry_unchanged"
                    ],
                    "baseline_nodes": shadow["baseline"]["w2_nodes"],
                    "shadow_nodes": shadow["shadow_with_proven_cycles_withheld_from_snap_input"]["w2_nodes"],
                    "shadow_w4_primitive_ids": shadow[
                        "shadow_with_proven_cycles_withheld_from_snap_input"
                    ]["w4_source_primitive_ids"],
                    "quantity_or_metric_area_published": False,
                }
            report["pages"].append(row)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
