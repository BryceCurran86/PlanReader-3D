"""Read-only census: why a layered CAD floor plan yields no authenticated room face.

Counts only. No words, coordinates, room names, quantities or benchmark values are
printed, so the output is safe to quote publicly for a private source.

It answers two independent questions about one original PDF page:

1. Which native drawing layers carry the page's linework, and how much of it do the
   EXISTING W2 layer rules (``is_structural_candidate_segment``) already exclude?
2. How many authenticated native figured dimensions have BOTH extents on a vertical or
   horizontal face of a wall-layer polygon? (A scale-free tie between a printed
   figure and a physical face; it is corroboration only, never a measurement.)

This module changes no production behavior and grants no authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import fitz

from pb_wall_room_topology_stage_a import is_structural_candidate_segment

# Layer tokens that name wall linework in the source's own metadata. This is a
# census predicate for the diagnostic only; it is not wall authority.
_WALL_TOKEN = "wall"


def layer_census(drawings: Sequence[dict]) -> dict[str, dict[str, int]]:
    """Per native layer: drawing count and how many existing W2 rules would exclude."""
    totals: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    for row in drawings:
        layer = str(row.get("layer") or "")
        totals[layer] += 1
        keep, _reasons = is_structural_candidate_segment({"layer": layer})
        if not keep:
            excluded[layer] += 1
    return {
        layer: {"drawings": totals[layer], "excluded_by_existing_w2_layer_rules": excluded[layer]}
        for layer in sorted(totals)
    }


def is_wall_layer(layer: object) -> bool:
    # Substring, not token: CAD layer names are CamelCase, so lower-casing first
    # would glue "WallExternal" into one token. Census predicate only.
    return _WALL_TOKEN in str(layer or "").lower()


def wall_layer_axis_faces(
    drawings: Sequence[dict],
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Axis-aligned faces of filled wall-layer rectangles/quads.

    Returns (vertical_faces, horizontal_faces) as (coordinate, low, high). Only the
    native rectangle (``re``), quad (``qu``) and straight-line (``l``) items of a FILLED
    path on a wall layer are used, so an unfilled centreline, an annotation or a door
    swing arc never becomes a face.
    """
    vertical: list[tuple[float, float, float]] = []
    horizontal: list[tuple[float, float, float]] = []
    for row in drawings:
        if not is_wall_layer(row.get("layer")) or row.get("fill") is None:
            continue
        for item in row.get("items", ()):
            kind = item[0]
            if kind == "re":
                rect = item[1]
                corners = [(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)]
                edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
            elif kind == "qu":
                quad = item[1]
                corners = [(quad.ul.x, quad.ul.y), (quad.ur.x, quad.ur.y), (quad.lr.x, quad.lr.y), (quad.ll.x, quad.ll.y)]
                edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
            elif kind == "l":
                edges = [((item[1].x, item[1].y), (item[2].x, item[2].y))]
            else:
                continue
            for (x0, y0), (x1, y1) in edges:
                if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                    continue
                if x0 == x1 and y0 != y1:
                    vertical.append((float(x0), min(y0, y1), max(y0, y1)))
                elif y0 == y1 and x0 != x1:
                    horizontal.append((float(y0), min(x0, x1), max(x0, x1)))
    return vertical, horizontal


def coordinate_on_face(
    coordinate: float, faces: Iterable[tuple[float, float, float]], *, tolerance_pt: float,
) -> bool:
    return any(abs(coordinate - face[0]) <= tolerance_pt for face in faces)


def figured_dimension_face_ties(
    dimensions: Sequence[Any],
    vertical_faces: Sequence[tuple[float, float, float]],
    horizontal_faces: Sequence[tuple[float, float, float]],
    *, tolerance_pt: float,
) -> dict[str, int]:
    """How many figured dimensions have both extents on a wall-layer face."""
    tied = 0
    for dimension in dimensions:
        (ax, ay), (bx, by) = dimension.endpoints_pt
        if dimension.orientation == "horizontal":
            ok = coordinate_on_face(ax, vertical_faces, tolerance_pt=tolerance_pt) and coordinate_on_face(
                bx, vertical_faces, tolerance_pt=tolerance_pt)
        elif dimension.orientation == "vertical":
            ok = coordinate_on_face(ay, horizontal_faces, tolerance_pt=tolerance_pt) and coordinate_on_face(
                by, horizontal_faces, tolerance_pt=tolerance_pt)
        else:
            ok = False
        tied += 1 if ok else 0
    return {"figured_dimensions": len(dimensions), "both_extents_on_wall_layer_face": tied}


def ring_figured_box_ties(rings: Sequence[Any], dimensions: Sequence[Any], *, tolerance_pt: float) -> dict[str, int]:
    """For each ring: how many authenticated (horizontal, vertical) figured pairs have exactly the
    ring's bounding box as their witness box. Counts only; corroboration, never a measurement."""
    horizontals = []
    verticals = []
    for dimension in dimensions:
        (ax, ay), (bx, by) = dimension.endpoints_pt
        if dimension.orientation == "horizontal":
            horizontals.append(tuple(sorted((ax, bx))))
        elif dimension.orientation == "vertical":
            verticals.append(tuple(sorted((ay, by))))
    unique = competing = none = 0
    for ring in rings:
        x0, y0, x1, y1 = ring.bbox_pdf_pts
        h = {span for span in horizontals if abs(span[0] - x0) <= tolerance_pt and abs(span[1] - x1) <= tolerance_pt}
        v = {span for span in verticals if abs(span[0] - y0) <= tolerance_pt and abs(span[1] - y1) <= tolerance_pt}
        pairs = len(h) * len(v)
        if pairs == 1:
            unique += 1
        elif pairs > 1:
            competing += 1
        else:
            none += 1
    return {"rings": len(rings), "unique_figured_box_pair": unique, "competing_figured_box_pairs": competing, "no_figured_box_pair": none}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-index", required=True, type=int, help="0-based original page")
    parser.add_argument("--with-dimensions", action="store_true",
                        help="also ingest the page and tie authenticated figured dimensions to wall faces")
    parser.add_argument("--rings", action="store_true",
                        help="also build the doorway-closed room rings (shadow) and, with --with-dimensions, tie them to figured boxes")
    args = parser.parse_args()
    payload = args.pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        drawings = document[args.page_index].get_drawings()
    finally:
        document.close()
    vertical, horizontal = wall_layer_axis_faces(drawings)
    result: dict[str, Any] = {
        "source_sha256": sha,
        "page_index": args.page_index,
        "drawings": len(drawings),
        "layers": layer_census(drawings),
        "wall_layer_drawings": sum(1 for row in drawings if is_wall_layer(row.get("layer"))),
        "wall_layer_vertical_faces": len(vertical),
        "wall_layer_horizontal_faces": len(horizontal),
    }
    rings_result = None
    if args.rings:
        from collections import Counter as _Counter
        from pb_layered_wall_doorway_room_ring_shadow import build_layered_wall_doorway_room_rings

        rings_result = build_layered_wall_doorway_room_rings(drawings, source_sha256=sha, page_index=args.page_index)
        result["doorway_closed_rings"] = {
            "result_status": rings_result.status.value,
            "wall_strips": rings_result.wall_strip_count,
            "wall_gaps": rings_result.wall_gap_count,
            "collinear_unresolved_gaps": rings_result.unresolved_gap_count,
            "closures_by_kind": dict(_Counter(c.kind for c in rings_result.closures)),
            "swing_unplaced": rings_result.unplaced_swing_count,
            "swing_ambiguous": rings_result.ambiguous_swing_count,
            "sliver_regions": rings_result.sliver_region_count,
            "rings_by_status": dict(_Counter(r.status.value for r in rings_result.rings)),
        }
    if args.with_dimensions:
        from pb_cross_view_room_area_authority import _trusted_native_dimensions_for_page
        from pb_drawing_evidence_binding import DrawingViewType
        from pb_source_visibility_authority import SourceVisibilityProducer

        page_id = str(args.page_index + 1)
        source = SourceVisibilityProducer(producer_method="layered-floor-plan-first-gate", producer_version="1")
        published = source.ingest_native_pdf_bytes(
            document_id=f"live-source:{sha[:32]}", source_bytes=payload,
            source_locator="memory://layered-floor-plan-first-gate.pdf", page_ids=(page_id,),
        )
        dimensions = _trusted_native_dimensions_for_page(
            source, revision_id=published.revision.revision_id, page_id=page_id,
            candidate_lines=(), view_type=DrawingViewType.FLOOR_PLAN.value,
        )
        if rings_result is not None:
            result["doorway_closed_rings"]["figured_box_ties_candidate_rings"] = ring_figured_box_ties(
                [r for r in rings_result.rings if r.status.value == "candidate"], dimensions, tolerance_pt=0.5)
            result["doorway_closed_rings"]["figured_box_ties_all_rings"] = ring_figured_box_ties(
                list(rings_result.rings), dimensions, tolerance_pt=0.5)
        result["figured_dimension_face_ties"] = {
            f"tolerance_{tolerance}pt": figured_dimension_face_ties(
                dimensions, vertical, horizontal, tolerance_pt=tolerance)
            for tolerance in (0.05, 0.5)
        }
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
