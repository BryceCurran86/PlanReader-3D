"""Original-app automatic preview: new native wall+doorway ring producer, never legacy envelope.

All paths, candidate strips and closure polygons come from the same native-source
producer used by PlanReader Next. No accepted quantities or commercial wall roles
are created by this preview.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz

from pb_next_wall_ring_preview import (
    _clip_drawing_items,
    _collect_dark_fill_strips,
    _collect_strips,
    _collect_stroke_pair_strips,
    _collect_source_heavy_stroke_strips,
    build_layered_wall_doorway_room_rings,
)
from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _source_wall_ink_candidate_drawings,
)
from pb_new_exterior_wall_preflight import (
    attempt_source_native_outer_wall_first,
)
from pb_new_typed_vector_ink_scope import scope_outlined_vector_lettering
from pb_new_numbered_space_key import (
    NumberedSpaceKeyResult,
    detect_numbered_space_key,
)


def _full_page_source_tiles(width: float, height: float, drawing_count: int):
    """Uniform bounded native-source viewports, not a heuristic footprint."""
    n = 3 if drawing_count <= 7000 else 4 if drawing_count <= 20000 else 5
    gap = 2.0  # overlap only for source-pane seams, not wall closure
    return tuple(
        (
            max(0.0, width * x / n - gap),
            max(0.0, height * y / n - gap),
            min(width, width * (x + 1) / n + gap),
            min(height, height * (y + 1) / n + gap),
        )
        for y in range(n) for x in range(n)
    )


def source_native_trace_preview(pdf_path: str | Path, page_index: int) -> tuple[dict, bytes]:
    """Return actual native-source trace evidence + PNG on the original PDF page.

    The function DOES NOT call legacy auto_detect_building_envelope or generate
    measurement_lines, m²/lm takeoff quantities, exterior walls or footprint.
    Source-endpoint connectivity and identity remain candidate until verified.
    """
    pdf_path = Path(pdf_path)
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("new_trace_original_pdf_required_no_legacy_fallback")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("new_trace_page_index_invalid")
    source_bytes = pdf_path.read_bytes()
    sha = hashlib.sha256(source_bytes).hexdigest()
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        if page_index >= len(document):
            raise ValueError("new_trace_original_page_index_invalid")
        page = document[page_index]
        drawings = page.get_drawings()
        rect = page.rect
        # Preflight source hygiene is not a physical tracing stage:
        # remove only source-proven non-wall vector glyphs and green ink,
        # keeping native path IDs and original bytes unchanged.
        vector_scope = scope_outlined_vector_lettering(page, drawings)
        wall_drawings, source_wall_ink_count, green_path_exclusions = (
            _source_wall_ink_candidate_drawings(vector_scope.drawings)
        )
        # MANDATORY FIRST GEOMETRY: try to trace the physical external walls
        # from source fill AND double-stroke pairs before any room operations.
        # This remains diagnostic-only until the source wall owner is proved.
        outer_wall = attempt_source_native_outer_wall_first(wall_drawings)
        # Room semantics are an automatic READ of source-printed numbered
        # key entries. This stage cannot draw walls, create areas, or override
        # a failed exterior trace. Missing key evidence is explicitly shown.
        try:
            space_key = detect_numbered_space_key(
                page, page_index=page_index, source_sha256=sha,
            )
        except Exception as exc:
            space_key = NumberedSpaceKeyResult(
                "ABSTAINED",
                "numbered_source_key_reader_failed:" + type(exc).__name__,
                page_index, sha,
            )
        panes = _full_page_source_tiles(rect.width, rect.height, len(drawings))
        # The new tracing producer reads the original native PDF paths, within
        # the unchanged 20,000 primitive cap per source-scope viewport.
        result = build_layered_wall_doorway_room_rings(
            wall_drawings,
            source_sha256=sha,
            page_index=page_index,
            sliding_leaf_frame_closure=True,
            panel_lift_label_closure=True,
            source_words=tuple(
                {
                    "text": str(w[4]),
                    "bbox_pdf_pts": tuple(float(v) for v in w[:4]),
                    "source_ref": f"native-word:p{page_index}:b{w[5]}:l{w[6]}:w{w[7]}",
                }
                for w in page.get_text("words")
            ),
            stroke_pair_wall_faces=True,
            wall_end_stroke_closures=False,
            viewport_pdf_pts=panes,
        )
        preview = fitz.open()
        canvas = preview.new_page(width=rect.width, height=rect.height)
        canvas.show_pdf_page(canvas.rect, document, page_index)
        native_wall_counts = {}
        seen = set()
        for pane in panes:
            clipped = _clip_drawing_items(wall_drawings, pane)
            filled, _other = _collect_strips(clipped)
            candidates = (
                ("source_filled", filled, (0.18, 0.50, 0.94)),
                ("stroke_pair", _collect_stroke_pair_strips(clipped), (0.0, 0.73, 0.80)),
                ("dark_fill", (
                    _collect_dark_fill_strips(clipped)
                    + _collect_dark_painted_source_wall_strips(clipped)
                ), (0.75, 0.20, 0.80)),
                ("source_heavy_stroke", _collect_source_heavy_stroke_strips(clipped), (0.93,0.3,0.12)),
            )
            for kind, strips, color in candidates:
                for strip in strips:
                    path_ids = strip.native_path_indices()
                    polygon = strip.polygon
                    if polygon is None or polygon.is_empty:
                        continue
                    key = (kind, path_ids, tuple(round(float(v), 2) for v in polygon.bounds))
                    if key in seen:
                        continue
                    seen.add(key)
                    native_wall_counts[kind] = native_wall_counts.get(kind, 0) + 1
                    try:
                        points = [fitz.Point(float(x), float(y)) for x, y in polygon.exterior.coords]
                        canvas.draw_polyline(points, color=color, width=1.7, stroke_opacity=0.78)
                    except (ValueError, TypeError, AttributeError):
                        continue
        # Show an outer boundary ONLY if the source actually traces a joined
        # wall-band perimeter. A boxed drawing/landscape hull is never shown.
        if outer_wall.polygon_pdf_pts:
            outer_pts = [
                fitz.Point(float(x), float(y))
                for x, y in outer_wall.polygon_pdf_pts
            ]
            canvas.draw_polyline(
                outer_pts + [outer_pts[0]],
                color=(0.95, 0.07, 0.13),
                width=2.8,
            )
        # Native source-backed FREE ENDPOINTS from the connected wall network
        # are diagnostic only, not authenticated openings or outside walls.
        # Do NOT render a bounding rectangle as the external wall footprint.
        for x, y in outer_wall.graph.largest_component_open_endpoints_pdf_pts[:300]:
            canvas.draw_circle(
                fitz.Point(x,y), radius=2.4,
                color=(.98,.12,.17), fill=(1.,.88,.07), width=0.8,
            )
        # Magenta: separate native wall components whose ORIGINAL endpoints
        # are near each other; NEVER an inferred physical wall or doorway.
        for hit in outer_wall.graph.endpoint_near_misses:
            canvas.draw_circle(
                fitz.Point(*hit.tip_pdf_pts), radius=4.0,
                color=(0.70, 0.08, 0.72), width=1.5,
            )
        for closure in result.closures:
            lo, hi = closure.gap_interval
            a, b = closure.band
            box = fitz.Rect(lo, a, hi, b) if closure.horizontal else fitz.Rect(a, lo, b, hi)
            if not box.is_empty:
                canvas.draw_rect(box, color=(1.0, 0.45, 0.0), fill=(1.0, 0.58, 0.0),
                                 fill_opacity=0.30, width=1.4)
        for ring in result.rings:
            if len(ring.polygon_pdf_pts) >= 3:
                points = [fitz.Point(float(x), float(y)) for x, y in ring.polygon_pdf_pts]
                canvas.draw_polyline(points + [points[0]], color=(0.01, 0.70, 0.15), width=3.0)
        zoom = min(1.2, 1800 / max(float(rect.width), float(rect.height)))
        png = canvas.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
        preview.close()
        summary = {
            "source_sha256": sha,
            "page_index": page_index,
            "producer": "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings",
            "legacy_envelope_used": False,
            "legacy_fallback_allowed": False,
            "stage_order": (
                "attempt_source_native_exterior_wall_trace_first",
                "trace_source_native_internal_wall_candidates",
                "temporarily_close_source_evidenced_doorways",
                "find_candidate_room_rings",
            ),
            "external_wall_trace_status": outer_wall.status,
            "external_wall_trace_reason": outer_wall.reason,
            "external_wall_native_source_paths": list(
                outer_wall.source_wall_path_ids
            ),
            "external_wall_band_candidates": outer_wall.source_wall_band_count,
            "external_wall_stroke_pair_candidates":
                outer_wall.source_stroke_pair_band_count,
            "external_wall_heavy_native_stroke_candidates":
                outer_wall.source_heavy_stroke_band_count,
            "external_wall_source_path_candidates":
                outer_wall.source_wall_path_count,
            "numbered_space_key": space_key.to_dict(),
            "exterior_source_wall_network": {
                "status": outer_wall.graph.connectivity_status,
                "connected_components": outer_wall.graph.component_count,
                "largest_source_wall_band_count":
                    outer_wall.graph.largest_component_band_count,
                "largest_network_source_path_ids": list(
                    outer_wall.graph.largest_component_source_paths
                ),
                "unjoined_native_wall_endpoints_pdf_pts": [
                    list(pt) for pt in outer_wall.graph.largest_component_open_endpoints_pdf_pts
                ],
                "outside_ink_filter_authorized": False,
                "source_endpoint_near_miss_total": (
                    outer_wall.graph.endpoint_near_miss_total
                ),
                "source_endpoint_near_misses": [
                    {
                        "tip_pdf_pts": list(hit.tip_pdf_pts),
                        "native_path_ids": list(hit.native_path_ids),
                        "nearby_native_path_ids": list(hit.nearby_native_path_ids),
                        "separation_pdf_pts": hit.separation_pdf_pts,
                        "physical_join_authenticated": False,
                        "measurement_authorized": False,
                    }
                    for hit in outer_wall.graph.endpoint_near_misses
                ],
            },
            "source_wall_ink_paths_retained": source_wall_ink_count,
            "green_source_paths_excluded": green_path_exclusions,
            "external_wall_path_points": [
                list(p) for p in outer_wall.polygon_pdf_pts
            ],
            "vector_ink_filter_applied": vector_scope.applied,
            "vector_ink_filter_reason": vector_scope.reason,
            "vector_ink_original_path_count": vector_scope.original_paths,
            "vector_ink_rejected_stroke_only_paths":
                vector_scope.discarded_simple_stroke_paths,
            "vector_ink_native_segments": vector_scope.native_line_segments,
            "vector_ink_retained_segments": vector_scope.kept_line_segments,
            "outside_ink_excluded_from_internal_wall_measurement": (
                outer_wall.internal_wall_filter_authorized
            ),
            "source_tile_count": len(panes),
            "primitive_cap_per_tile": 20000,
            "status": result.status.value,
            "reason_codes": list(result.reason_codes),
            "wall_strip_count": result.wall_strip_count,
            "wall_gap_count": result.wall_gap_count,
            "unresolved_wall_gap_count": result.unresolved_gap_count,
            "source_path_candidate_counts": native_wall_counts,
            "candidate_enclosed_regions": len(result.rings),
            "temporary_opening_closures": len(result.closures),
            "exterior_physical_wall_authenticated": False,
            "quantity_authorized": False,
            "commercial_publishable": False,
            "legend": {
                "blue": "source-filled native wall candidates",
                "cyan": "stroke-pair wall candidates; may include dimensions",
                "purple": "dark-fill wall candidates",
                "red_orange": "source-heavy black stroke wall candidate, not verified",
                "orange": "temporary topology-only doorway closures",
                "magenta": "near wall endpoints; unjoined and unverified",
                "green": "candidate room enclosure",
            },
        }
        return summary, png
