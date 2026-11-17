"""Read-only original PlanReader footprint-first source-tracing diagnostic.

No customer quantities, benchmark, private-source upload or automatic FIRM.
Use: py -3.13 tools/run_original_footprint_first.py --pdf house.pdf --page 1 --out-dir C:\\private\\test
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_external_footprint_first_trace import (  # noqa: E402
    bound_native_drawings_to_footprint,
    refine_external_footprint_against_wall_ink,
    trace_external_footprint_first,
)
from pb_layered_wall_doorway_room_ring_shadow import (  # noqa: E402
    _source_wall_ink_candidate_drawings,
    build_layered_wall_doorway_room_rings,
)


def _draw_source_overlay(page, original, trace, scope, ring):
    """Colour legend: red unverified outer, blue candidate ink, orange closures."""
    import fitz

    page.show_pdf_page(page.rect, original, trace.page_index)
    candidate_count = 0
    if scope.status == "CANDIDATE":
        # One shape/commit for source-candidate diagnostics. Repeated
        # page.draw_line() rebuilt the PDF content stream 1,600 times on a
        # typical A0 drawing and dominated debug rendering time.
        blue_shape = page.new_shape()
        filtered, _count, _greens = _source_wall_ink_candidate_drawings(
            scope.drawings
        )
        for row in filtered:
            for item in row.get("items", ()):
                if not item or item[0] != "l":
                    continue
                p, q = item[1], item[2]
                if abs(p.x - q.x) <= .01 and abs(p.y - q.y) <= .01:
                    continue
                # Keep the visual legible, without altering diagnostic scope.
                if abs(p.x - q.x) > .1 and abs(p.y - q.y) > .1:
                    continue
                if max(abs(p.x - q.x), abs(p.y - q.y)) < 9.0:
                    continue
                if candidate_count >= 1600:
                    break
                blue_shape.draw_line(p, q)
                candidate_count += 1
            if candidate_count >= 1600:
                break
        if candidate_count:
            blue_shape.finish(color=(.0, .2, .9), width=.4,
                              stroke_opacity=.55)
            blue_shape.commit()
    if ring is not None:
        for closure in ring.closures:
            lo, hi = closure.gap_interval
            band0, band1 = closure.band
            rect = (fitz.Rect(lo, band0, hi, band1) if closure.horizontal
                    else fitz.Rect(band0, lo, band1, hi))
            page.draw_rect(rect, color=(1., .45, 0.), width=1.0)
    if ring is not None:
        # Magenta is an UNRESOLVED original-wall-run interruption, never a
        # filled closure. Show at most a small deterministic diagnostic sample.
        for witness in ring.unresolved_gap_witnesses[:24]:
            lo, hi = witness["gap_interval_pdf_pts"]
            band0, band1 = witness["band_pdf_pts"]
            rect = (fitz.Rect(lo, band0, hi, band1) if witness["horizontal"]
                    else fitz.Rect(band0, lo, band1, hi))
            page.draw_rect(rect, color=(.7, .0, .65), width=.75)
    if trace.polygon_pdf_pts:
        points = [fitz.Point(x, y) for x, y in trace.polygon_pdf_pts]
        if len(points) >= 3:
            shape = page.new_shape()
            shape.draw_polyline(points + [points[0]])
            shape.finish(color=(1., 0., 0.), width=2.2)
            shape.commit()
    # No heading overlay over the actual building; legend left in JSON.
    return candidate_count


def run(pdf: Path, page_index: int, out_dir: Path):
    import fitz

    original_bytes = pdf.read_bytes()
    sha = hashlib.sha256(original_bytes).hexdigest()
    (outer,) = trace_external_footprint_first(
        original_bytes, source_sha256=sha, page_indices=(page_index,),
    )
    with fitz.open(stream=original_bytes, filetype="pdf") as source:
        drawings = tuple(source[page_index].get_drawings())
        outer, detour_receipt = refine_external_footprint_against_wall_ink(
            outer, drawings,
        )
        scope = bound_native_drawings_to_footprint(
            drawings, trace=outer, expected_source_sha256=sha,
        )
        ring = None
        if scope.status == "CANDIDATE":
            ring = build_layered_wall_doorway_room_rings(
                scope.drawings,
                source_sha256=sha,
                page_index=page_index,
                sliding_leaf_frame_closure=True,
                dark_painted_wall_source=True,
                wall_end_stroke_closures=False,
            )
        result = {
            "source_sha256": sha,
            "page_index_0based": page_index,
            "stage_order": [
                "source_hashed_exterior_ink_contour",
                "preserve_original_native_path_scope",
                "dark_wall_and_doorway_ring_topology",
                "physical_wall_metric_and_customer_UNAUTHORIZED",
            ],
            "exterior": outer.to_dict(),
            "unsupported_rectangular_detour": dict(detour_receipt),
            "bounded_source": {
                "status": scope.status,
                "reason": scope.reason,
                "source_total_paths": scope.source_total_paths,
                "retained_path_count": len(scope.selected_source_path_indices),
                "candidate_wall_native_primitives": scope.wall_native_primitive_count,
                "source_path_indices_preserved": True,
                "source_primitive_cap": 20_000,
            },
            "topology": {
                "status": (str(ring.status.value) if ring else "ABSTAINED"),
                "reason_codes": list(ring.reason_codes) if ring else [
                    "source_bounded_scope_unavailable"
                ],
                "candidate_room_rings": len(ring.rings) if ring else 0,
                "temporary_doorway_closures": len(ring.closures) if ring else 0,
                "unresolved_collinear_gap_count": ring.unresolved_gap_count if ring else 0,
                "source_gap_witness_count": ring.unresolved_gap_witness_count if ring else 0,
                "source_gap_witnesses_sample": [
                    dict(w) for w in ring.unresolved_gap_witnesses
                ] if ring else [],
                "commercial_publishable": False,
                "room_quantity_authorized": False,
            },
            "commercial_quantity_rows": 0,
            "official_frozen120_score_change": 0,
        }
        canvas = fitz.open()
        layer = canvas.new_page(width=source[page_index].rect.width,
                                height=source[page_index].rect.height)
        shown = _draw_source_overlay(layer, source, outer, scope, ring)
        result["overlay"] = {
            "legend": {
                "red": "unverified external contour candidate",
                "blue": "raw dark ink candidate line, not proven internal wall",
                "orange": "topology-only temporary doorway closure",
                "magenta": "source-indexed UNRESOLVED gap; never an accepted wall/closure",
            },
            "wall_ink_segments_shown": shown,
            "all_segments_shown": shown < 1600,
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        json_file = out_dir / f"page_{page_index+1}_footprint_first.json"
        png_file = out_dir / f"page_{page_index+1}_footprint_first.png"
        # No source PDF is ever copied or added to the repo.
        with json_file.open("x", encoding="utf8") as target:
            json.dump(result, target, indent=2)
        with png_file.open("xb") as target:
            target.write(layer.get_pixmap(
                matrix=fitz.Matrix(1.2, 1.2), alpha=False).tobytes("png")
            )
        canvas.close()
    return result, json_file, png_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True,
                        help="0-based page index")
    parser.add_argument("--out-dir", type=Path, required=True)
    arguments = parser.parse_args()
    result, js, png = run(arguments.pdf, arguments.page, arguments.out_dir)
    print(json.dumps({
        "exterior_status": result["exterior"]["status"],
        "source_native_ink_primitives": result["bounded_source"]["candidate_wall_native_primitives"],
        "room_topology_status": result["topology"]["status"],
        "room_topology_reasons": result["topology"]["reason_codes"],
        "rooms": result["topology"]["candidate_room_rings"],
        "closures": result["topology"]["temporary_doorway_closures"],
        "json": str(js), "overlay": str(png),
    }, indent=2))
