"""Diagnostic-only source viewport inventory; cannot grant production authority."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from pathlib import Path
import fitz
from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport, segment_page_viewports,
    validate_non_overlapping_viewports,
    calibrate_viewport_layout, extract_vector_frames,
    extract_view_title_anchors, _frame_candidates_for_title,
    _frame_looks_like_table,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
if __name__ == "__main__":
    if not SOURCE.is_file():
        raise SystemExit(f"SOURCE PDF UNAVAILABLE: {SOURCE}")
    payload = SOURCE.read_bytes()
    doc = fitz.open(stream=payload, filetype="pdf")
    target_types = {
        DrawingViewType.REFLECTED_CEILING_PLAN.value,
        DrawingViewType.FLOOR_FINISH_PLAN.value,
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.LEGEND.value,
        DrawingViewType.SPECIFICATION.value,
    }
    results = []
    frame_diagnostics = []
    counts = Counter()
    for index in range(len(doc)):
        page_no = index + 1
        viewports = segment_page_viewports(doc[index], page_number=page_no)
        if page_no in (1, 9, 11, 30):
            page = doc[index]
            calibration = calibrate_viewport_layout(page)
            frames = extract_vector_frames(page, calibration)
            # Distinguish no source vectors from unsupported source paths;
            # this is diagnostic evidence only, never viewport authority.
            drawings = page.get_drawings()
            primitive_types = Counter(
                str(item[0])
                for drawing in drawings
                for item in drawing.get("items", []) or []
                if item
            )
            path_lengths = Counter(
                str(len(drawing.get("items", []) or []))
                for drawing in drawings
            )
            # Inspect genuine rectangle and four-edge paths BEFORE size/crop
            # filtering, never combine independent wall-line paths.
            raw_rectangles = []
            for path_index, drawing in enumerate(drawings):
                for item in drawing.get("items", []) or []:
                    if item and item[0] == "re":
                        rect = item[1]
                        raw_rectangles.append({
                            "path": path_index, "kind": "source_rectangle",
                            "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
                            "width": abs(rect.x1 - rect.x0),
                            "height": abs(rect.y1 - rect.y0),
                        })
            # Four-edge native paths are qualitatively different from loose
            # construction lines; inspect them as indivisible source paths.
            four_edge_paths = []
            for path_index, drawing in enumerate(drawings):
                items = drawing.get("items", []) or []
                if len(items) != 4:
                    continue
                edges = []
                for item in items:
                    if item and item[0] == "l":
                        a, b = item[1], item[2]
                        edges.append([[float(a.x), float(a.y)],
                                      [float(b.x), float(b.y)]])
                four_edge_paths.append({
                    "path": path_index, "source_edge_count": len(edges),
                    "bbox": tuple(drawing.get("rect") or ()),
                    "edges": edges,
                    "path_is_closed": bool(drawing.get("closePath")),
                })
            print("B01_SOURCE_FOUR_EDGE_PATHS", json.dumps({
                "page": page_no, "count": len(four_edge_paths),
                "first_30": four_edge_paths[:30],
            }, default=str, sort_keys=True))
            # Compact largest rectangles on the title-bearing sheets: this
            # reveals whether real producer geometry supplies usable borders.
            raw_rectangles.sort(
                key=lambda r: r["width"] * r["height"], reverse=True
            )
            print("B01_NATIVE_RECTANGLE_CANDIDATES", json.dumps({
                "page": page_no, "total": len(raw_rectangles),
                "largest_20": raw_rectangles[:20],
            }, sort_keys=True))
            print("B01_SOURCE_GEOMETRY_DIAGNOSTIC", json.dumps({
                "page": page_no, "drawings": len(drawings),
                "primitive_types": dict(primitive_types),
                "path_item_count_distribution": dict(path_lengths),
                "extracted_frames": len(frames),
            }, sort_keys=True))
            # PDF producer clipping/group objects may carry a boundary even
            # when ordinary drawing paths do not. Read-only, source-native
            # inspection; no clip is promoted to a viewport by this report.
            try:
                extended = page.get_drawings(extended=True)
            except (TypeError, ValueError, RuntimeError) as exc:
                extended = []
                print("B01_EXTENDED_DRAWINGS_UNAVAILABLE", str(exc))
            structural = []
            for path_index, drawing in enumerate(extended):
                kind = str(drawing.get("type") or "")
                if kind not in ("clip", "group"):
                    continue
                bbox = drawing.get("scissor") or drawing.get("rect")
                structural.append({
                    "index": path_index, "kind": kind,
                    "level": drawing.get("level"),
                    "bbox": tuple(bbox) if bbox is not None else None,
                    "items": len(drawing.get("items", []) or []),
                })
            try:
                images = page.get_images(full=True)
                placements = []
                for image in images[:40]:
                    for rect in page.get_image_rects(image[0])[:20]:
                        placements.append({"xref": image[0], "bbox": tuple(rect)})
            except (ValueError, RuntimeError) as exc:
                images, placements = [], []
                print("B01_IMAGE_PLACEMENTS_UNAVAILABLE", str(exc))
            print("B01_PRODUCER_CLIP_IMAGE_EVIDENCE", json.dumps({
                "page": page_no, "extended_count": len(extended),
                "clip_group_count": len(structural),
                "clip_groups_first_60": structural[:60],
                "image_count": len(images),
                "placements_first_40": placements[:40],
            }, default=str, sort_keys=True))
            # For each actual RCP/floor-finish title, report independently
            # existing clip/image regions containing it, and competing plan
            # titles within the same region. Never treat proximity as proof.
            anchors = extract_view_title_anchors(page)
            plan_kinds = {
                DrawingViewType.REFLECTED_CEILING_PLAN.value,
                DrawingViewType.FLOOR_FINISH_PLAN.value,
            }
            plan_anchors = [a for a in anchors if a.view_type in plan_kinds]
            region_rows = []
            clip_regions = [
                r for r in structural
                if r["bbox"] is not None and len(r["bbox"]) == 4
                and (r["bbox"][2] - r["bbox"][0]) >= calibration.minimum_frame_span_pt
                and (r["bbox"][3] - r["bbox"][1]) >= calibration.minimum_frame_span_pt
            ]
            for anchor in plan_anchors:
                center = (
                    (anchor.bbox[0] + anchor.bbox[2]) / 2,
                    (anchor.bbox[1] + anchor.bbox[3]) / 2,
                )
                owned = []
                for region in clip_regions:
                    b = region["bbox"]
                    if b[0] <= center[0] <= b[2] and b[1] <= center[1] <= b[3]:
                        competing = [
                            a.text for a in plan_anchors if a is not anchor
                            and b[0] <= (a.bbox[0]+a.bbox[2])/2 <= b[2]
                            and b[1] <= (a.bbox[1]+a.bbox[3])/2 <= b[3]
                        ]
                        owned.append({
                            "clip_index":region["index"],"bbox":b,
                            "other_plan_titles": competing,
                        })
                # A printed plan title may be outside its source clip.
                # Identify adjacent candidate regions only for diagnosis;
                # repeated/nested clips must NOT become viewport authority.
                adjacent = []
                for region in clip_regions:
                    b = region["bbox"]
                    width, height = b[2]-b[0], b[3]-b[1]
                    if width <= 0 or height <= 0:
                        continue
                    dx = max(b[0]-center[0], 0, center[0]-b[2])
                    dy = max(b[1]-center[1], 0, center[1]-b[3])
                    if dx > calibration.minimum_frame_span_pt or dy > calibration.minimum_frame_span_pt:
                        continue
                    competing = [
                        a.text for a in plan_anchors if a is not anchor
                        and max(b[0]-(a.bbox[0]+a.bbox[2])/2,0,(a.bbox[0]+a.bbox[2])/2-b[2]) <= calibration.minimum_frame_span_pt
                        and max(b[1]-(a.bbox[1]+a.bbox[3])/2,0,(a.bbox[1]+a.bbox[3])/2-b[3]) <= calibration.minimum_frame_span_pt
                    ]
                    adjacent.append({"clip_index":region["index"],"bbox":b,
                                     "distance_pt":round((dx*dx+dy*dy)**0.5,3),
                                     "competing_titles":competing})
                adjacent.sort(key=lambda v:(v["distance_pt"],v["clip_index"]))
                region_rows.append({
                    "title":anchor.text,"title_bbox":anchor.bbox,
                    "title_center":center,
                    "clip_regions_containing_title":owned[:20],
                    "total_containing":len(owned),
                    "adjacent_clip_count":len(adjacent),
                    "nearest_adjacent_clips":adjacent[:12],
                })
            print("B01_CLIP_TITLE_OWNERSHIP_PROBE", json.dumps({
                "page":page_no,"plan_titles":region_rows,
                "qualifying_clips":len(clip_regions),
            },default=str,sort_keys=True))
            for anchor in anchors:
                if anchor.view_type not in target_types:
                    continue
                candidates = _frame_candidates_for_title(
                    page, anchor, frames, calibration, anchors=anchors
                )
                frame_diagnostics.append({
                    'source_page': page_no, 'title': anchor.text,
                    'type': anchor.view_type, 'native_title_bbox': anchor.bbox,
                    'native_direction': anchor.direction,
                    'candidate_frames': candidates,
                    'candidate_table_proof': [
                        _frame_looks_like_table(frame, page, calibration)
                        for frame in candidates
                    ],
                    'native_frame_count': len(frames),
                    'calibrated_min_span_pt': calibration.minimum_frame_span_pt,
                })
        nonoverlap = validate_non_overlapping_viewports(viewports)
        for viewport in viewports:
            if viewport.view_type not in target_types:
                continue
            authoritative = (
                viewport.status == "resolved" and viewport.bounding_box is not None
            ) or is_authoritative_derived_viewport(viewport)
            counts[(viewport.view_type, viewport.status)] += 1
            results.append({
                "source_page": page_no,
                "view_id": viewport.view_id,
                "title": viewport.label,
                "view_type": viewport.view_type,
                "status": viewport.status,
                "authoritative": bool(authoritative and nonoverlap),
                "native_bbox": viewport.bounding_box,
                "notes": viewport.notes,
                "provenance": viewport.provenance,
                "page_viewport_nonoverlap": nonoverlap,
            })
    doc.close()
    report = {
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "page_count": page_no,
        "counts": [{"type": k[0], "status": k[1], "count": v} for k, v in sorted(counts.items())],
        "viewports": results,
        "target_page_frame_diagnostics": frame_diagnostics,
    }
    Path("maryborough_gpt2_source_viewport_inventory.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))
