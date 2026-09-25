from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import fitz

from pb_physical_wall_identity import collect_physical_wall_identities, resolve_physical_wall_equivalence
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import assemble_wall_topology

PAGE = 54
TARGETS = {
    "external_wall_band": (648.1, 480.4),
    "internal_wall_band": (270.1, 622.0),
}
RADIUS = 8.0


def _inside(seg, bbox):
    x0, y0, x1, y1 = bbox
    return (
        x0 <= float(seg["x1"]) <= x1
        and y0 <= float(seg["y1"]) <= y1
        and x0 <= float(seg["x2"]) <= x1
        and y0 <= float(seg["y2"]) <= y1
    )


def _intersects_box(seg, cx, cy, r):
    x1, y1, x2, y2 = (float(seg[k]) for k in ("x1", "y1", "x2", "y2"))
    xmin, xmax, ymin, ymax = cx - r, cx + r, cy - r, cy + r
    if xmin <= x1 <= xmax and ymin <= y1 <= ymax:
        return True
    if xmin <= x2 <= xmax and ymin <= y2 <= ymax:
        return True
    dx, dy = x2 - x1, y2 - y1
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x1 - xmin), (dx, xmax - x1), (-dy, y1 - ymin), (dy, ymax - y1)):
        if abs(p) <= 1e-12:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0:
            if t > hi:
                return False
            lo = max(lo, t)
        else:
            if t < lo:
                return False
            hi = min(hi, t)
    return lo <= hi


def _seg_meta(seg):
    return {
        "id": seg.get("id"),
        "path_index": seg.get("path_index"),
        "item_index": seg.get("item_index"),
        "edge_index": seg.get("edge_index"),
        "kind": seg.get("kind"),
        "layer": seg.get("layer"),
        "width": seg.get("width"),
        "dashes": seg.get("dashes"),
        "stroke": seg.get("stroke"),
        "fill": seg.get("fill"),
        "geometry": [seg.get("x1"), seg.get("y1"), seg.get("x2"), seg.get("y2")],
    }


def main(path: Path):
    doc = fitz.open(path)
    page = doc.load_page(PAGE - 1)
    native = extract_native_page(page)
    viewports = tuple(segment_page_viewports(page, page_number=PAGE))
    non_overlap = validate_non_overlapping_viewports(viewports)
    eligible = [
        v for v in viewports
        if v.bounding_box is not None
        and (
            v.status == ViewportSegmentationStatus.RESOLVED.value
            or (non_overlap and is_authoritative_derived_viewport(v))
        )
    ]

    drawings = page.get_drawings() or []

    def path_summary(path_index):
        if path_index is None or not (0 <= int(path_index) < len(drawings)):
            return None
        drawing = drawings[int(path_index)]
        items = []
        for item in drawing.get("items") or ():
            if not item:
                continue
            vals = []
            for value in item[1:]:
                if hasattr(value, "x") and hasattr(value, "y"):
                    vals.append([float(value.x), float(value.y)])
                elif all(hasattr(value, key) for key in ("x0", "y0", "x1", "y1")):
                    vals.append([float(value.x0), float(value.y0), float(value.x1), float(value.y1)])
                else:
                    vals.append(str(value))
            items.append([str(item[0]), *vals])
        rect = drawing.get("rect")
        return {
            "path_index": int(path_index),
            "layer": str(drawing.get("layer") or drawing.get("oc") or ""),
            "type": drawing.get("type"),
            "seqno": drawing.get("seqno"),
            "width": drawing.get("width"),
            "color": drawing.get("color"),
            "fill": drawing.get("fill"),
            "rect": None if rect is None else [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
            "items": items,
        }

    out = {"targets": {}}
    for name, (cx, cy) in TARGETS.items():
        owners = [
            v for v in eligible
            if v.bounding_box[0] <= cx <= v.bounding_box[2]
            and v.bounding_box[1] <= cy <= v.bounding_box[3]
        ]
        if len(owners) != 1:
            out["targets"][name] = {"center": [cx, cy], "viewport_owner_count": len(owners)}
            continue
        viewport = owners[0]
        segments = [dict(s) for s in native.get("segments") or () if _inside(s, viewport.bounding_box)]
        graph = build_wall_graph_for_viewport(segments)
        junctions, rels = classify_junctions(
            graph,
            document_id="diag:kstvet",
            page_id=str(PAGE),
            viewport_id=str(viewport.view_id),
        )
        walls, _ = assemble_wall_topology(graph, junctions, rels, viewport_id=str(viewport.view_id))
        identities = collect_physical_wall_identities(walls, graph)
        eq = resolve_physical_wall_equivalence(
            tuple(identities[w.candidate_id] for w in walls if w.candidate_id in identities),
            walls_by_id={w.candidate_id: w for w in walls},
        )
        by_raw = {str(s.get("id")): s for s in segments if s.get("id")}
        raw_hits = sorted(
            str(s["id"]) for s in segments
            if s.get("id") and _intersects_box(s, cx, cy, RADIUS)
        )
        raw_set = set(raw_hits)
        matches = []
        touched_paths = set()
        for wall in sorted(walls, key=lambda w: w.candidate_id):
            identity = identities.get(wall.candidate_id)
            if identity is None or not (raw_set & set(identity.source_primitive_ids)):
                continue
            prims = [_seg_meta(by_raw[rid]) for rid in identity.source_primitive_ids if rid in by_raw]
            touched_paths.update(p.get("path_index") for p in prims if p.get("path_index") is not None)
            matches.append({
                "wall_candidate_id": wall.candidate_id,
                "centerline_pts": [list(p) for p in wall.centerline_pts],
                "junction_types": [j.value for j in wall.junction_types],
                "source_primitive_ids": list(identity.source_primitive_ids),
                "path_fingerprint": [list(p) for p in (identity.path_fingerprint or ())],
                "source_primitives": prims,
            })
        raw_meta = [_seg_meta(by_raw[rid]) for rid in raw_hits if rid in by_raw]
        touched_paths.update(p.get("path_index") for p in raw_meta if p.get("path_index") is not None)
        out["targets"][name] = {
            "center": [cx, cy],
            "viewport": {
                "id": viewport.view_id,
                "label": viewport.label,
                "view_type": viewport.view_type,
                "bbox": list(viewport.bounding_box),
                "status": viewport.status,
            },
            "wall_count": len(walls),
            "equivalence_groups": [list(g) for g in eq.equivalence_groups],
            "raw_hits": raw_meta,
            "matching_walls": matches,
            "path_summaries": [
                summary for summary in (path_summary(idx) for idx in sorted(touched_paths))
                if summary is not None
            ],
        }
    print("ITEM19B_WALL_PROVENANCE " + json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: wall_provenance_kstvet_probe.py <kstvet.pdf>")
    main(Path(sys.argv[1]))
