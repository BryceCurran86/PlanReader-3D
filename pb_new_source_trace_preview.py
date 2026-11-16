"""Original-app automatic preview: new native wall+doorway ring producer, never legacy envelope.

All paths, candidate strips and closure polygons come from the same native-source
producer used by PlanReader Next. No accepted quantities or commercial wall roles
are created by this preview.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path

import fitz

from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _source_wall_ink_candidate_drawings,
)
from pb_new_exterior_wall_preflight import (
    SourceNativeOuterWallAttempt,
    attempt_source_native_outer_wall_first,
)
from pb_new_numbered_space_key import (
    NumberedSpaceKeyResult,
    detect_numbered_space_key,
)
from pb_new_raster_source_wall_trace import (
    RasterSourceSegmentTrace,
    trace_source_raster_wall_lines,
)
from pb_new_source_dark_ink_scope import include_source_neutral_dark_strokes
from pb_new_source_modality_router import classify_source_page_modality
from pb_new_typed_vector_ink_scope import scope_outlined_vector_lettering
from pb_next_wall_ring_preview import (
    _clip_drawing_items,
    _collect_cavity_multi_face_strips,
    _collect_dark_fill_strips,
    _collect_monotonic_source_stroke_pairs,
    _collect_source_heavy_stroke_strips,
    _collect_source_wide_face_pairs,
    _collect_strips,
    _collect_stroke_pair_strips,
    build_layered_wall_doorway_room_rings,
)
from pb_source_ocr_glyph_fastpath import get_source_words_with_glyph_fastpath


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


def _draw_unsealed_source_ring_preview(canvas, outside_walk) -> bool:
    """Dashed amber review aid only; never a physical/quantity footprint.

    The canonical walker may have two closed occupied source regions yet
    still reject outside page components. Keep authoritative ring fields
    empty, and make the unresolved shape visually unmistakable.
    """
    if (
        outside_walk is None
        or outside_walk.status != "ABSTAINED"
        or outside_walk.reason != "source_other_structural_walls_outside_candidate"
        or outside_walk.measurement_authorized
        or outside_walk.building_footprint_authenticated
    ):
        return False
    ring = outside_walk.diagnostic_unsealed_ring_pdf_pts
    if not 5 <= len(ring) <= 20_000 or ring[0] != ring[-1]:
        return False
    try:
        coords = [(float(x), float(y)) for x, y in ring]
    except (ValueError, TypeError, OverflowError):
        return False
    if not all(math.isfinite(x) and math.isfinite(y) for x, y in coords):
        return False
    points = [fitz.Point(x, y) for x, y in coords]
    canvas.draw_polyline(
        points, color=(0.92, 0.58, 0.08),
        dashes="[6 4] 0", width=2.2, stroke_opacity=0.88,
    )
    return True


def source_native_trace_preview(
    pdf_path: str | Path,
    page_index: int,
    *,
    viewport_pdf_pts: tuple[float, float, float, float] | Sequence[tuple[float, float, float, float]] | None = None,
) -> tuple[dict, bytes]:
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
        # Source representation must be checked BEFORE choosing a physical
        # tracing lane. A full tiled raster architectural page does not gain
        # physical wall authority from its unrelated vector dimensions.
        source_modality = classify_source_page_modality(
            page, vector_path_count=len(drawings),
        )
        raster_trace = RasterSourceSegmentTrace(
            "ABSTAINED", "not_raster_source_page", page_index, 0.,
        )
        # Preflight source hygiene is not a physical tracing stage:
        # remove only source-proven non-wall vector glyphs and green ink,
        # keeping native path IDs and original bytes unchanged.
        vector_scope = scope_outlined_vector_lettering(page, drawings)
        wall_drawings, source_wall_ink_count, green_path_exclusions = (
            _source_wall_ink_candidate_drawings(vector_scope.drawings)
        )
        # Preserve the immutable strict black source mask. Near-black paths
        # must ADD candidates, not erase earlier valid pair witnesses.
        strict_wall_drawings = wall_drawings
        wall_drawings, neutral_dark_added = include_source_neutral_dark_strokes(
            vector_scope.drawings, wall_drawings,
        )
        if source_modality.route == "tiled_raster_underlay":
            # First geometry is from raster SOURCE PIXELS. Do not silently
            # misclassify native dimension overlays as architectural walls.
            raster_trace = trace_source_raster_wall_lines(
                page,source_page_index=page_index,
                source_raster_xrefs=source_modality.raster_unique_xrefs,
            )
            # Preserve every native path offset, but mask ALL native-vector
            # wall candidates for this image-backed plan page.
            blank = {"layer":"","fill":None,"color":None,"items":()}
            wall_drawings = tuple(blank for _ in wall_drawings)
            strict_wall_drawings = wall_drawings
            source_wall_ink_count = 0
            neutral_dark_added = 0
            outer_wall = SourceNativeOuterWallAttempt(
                "ABSTAINED", "source_raster_exterior_wall_not_authenticated",
            )
        else:
            source_words = get_source_words_with_glyph_fastpath(
                page, page_index=page_index,
            )
            # MANDATORY FIRST GEOMETRY on native-vector source: structural
            # wall-band outer attempt before internal wall/room work.
            outer_wall = attempt_source_native_outer_wall_first(
                wall_drawings,
                baseline_source_drawings=(
                    strict_wall_drawings if neutral_dark_added else None
                ),
                source_ink_already_scoped=True,
                source_words=source_words,
                window_source_drawings=drawings,
                source_page_index=page_index,
                viewport_pdf_pts=viewport_pdf_pts,
            )
        # Room semantics are an automatic READ of source-printed numbered
        # key entries. This stage cannot draw walls, create areas, or override
        # a failed exterior trace. Missing key evidence is explicitly shown.
        try:
            space_key = detect_numbered_space_key(
                page, page_index=page_index, source_sha256=sha,
            )
        except (AttributeError, KeyError, IndexError, TypeError, ValueError, RuntimeError, OSError) as exc:
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
                    "source_ref": f"source-word:p{page_index}:w{i}",
                }
                for i, w in enumerate(
                    source_words
                    if source_modality.route != "tiled_raster_underlay"
                    else page.get_text("words")
                )
            ),
            stroke_pair_wall_faces=True,
            source_pair_baseline_drawings=(
                strict_wall_drawings if neutral_dark_added else None
            ),
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
            clipped_baseline = (
                _clip_drawing_items(strict_wall_drawings, pane)
                if neutral_dark_added else None
            )
            filled, _other = _collect_strips(clipped)
            candidates = (
                ("source_filled", filled, (0.18, 0.50, 0.94)),
                ("stroke_pair", _collect_monotonic_source_stroke_pairs(
                    clipped, clipped_baseline,
                ), (0.0, 0.73, 0.80)),
                ("dark_fill", (
                    _collect_dark_fill_strips(clipped)
                    + _collect_dark_painted_source_wall_strips(clipped)
                ), (0.75, 0.20, 0.80)),
                ("source_heavy_stroke", _collect_source_heavy_stroke_strips(clipped), (0.93,0.3,0.12)),
                ("source_cavity_multi_face", _collect_cavity_multi_face_strips(clipped), (0.46,0.29,0.87)),
                ("source_wide_face_pair", _collect_source_wide_face_pairs(clipped), (0.59,0.4,0.93)),
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
        # Raster branch shows actual source image line-candidate geometry,
        # not any native-vector page furniture or old envelope contour.
        # The render is a diagnostic: magenta may include dimension lines.
        for x0,y0,x1,y1 in raster_trace.candidate_axis_segments_pdf_pts[:1200]:
            canvas.draw_line(
                fitz.Point(x0,y0),fitz.Point(x1,y1),
                color=(.88,.07,.55),width=.75,stroke_opacity=.68,
            )
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
        # Blue spans are native window aperture CONTINUITY of the footprint,
        # not solid walls or customer-measurable material.
        for bridge in outer_wall.window_footprint_bridges:
            canvas.draw_rect(
                fitz.Rect(*bridge.bounds_pdf_pts),
                color=(0.0, 0.43, 0.95), fill=(0.15, 0.7, 1.0),
                fill_opacity=0.25, width=2.2,
            )
        # Orange denotes a hosted garage panel-lift aperture. Its 2D
        # boundary continues across the door, but it is never wall material.
        for bridge in outer_wall.garage_door_footprint_bridges:
            canvas.draw_rect(
                fitz.Rect(*bridge.bounds_pdf_pts),
                color=(0.96, 0.48, 0.02), fill=(1., 0.64, 0.08),
                fill_opacity=0.17, width=2.2,
            )
        # Magenta is a native hosted swing DOOR aperture between real
        # exterior wall ends. Its arc and both jamb caps are source-owned.
        # It is not a full-depth physical wall or a billable wall face.
        for bridge in outer_wall.swing_door_footprint_bridges:
            canvas.draw_rect(
                fitz.Rect(*bridge.bounds_pdf_pts),
                color=(0.74, 0.05, 0.56), fill=(0.95, 0.31, 0.72),
                fill_opacity=0.20, width=2.2,
            )
        # Indigo denotes native ASD/SGD SLIDING doors: verified jamb
        # caps + track path receipts, never billable wall/door quantities.
        for bridge in outer_wall.sliding_door_footprint_bridges:
            canvas.draw_rect(
                fitz.Rect(*bridge.bounds_pdf_pts),
                color=(0.30, 0.23, 0.87), fill=(0.48, 0.43, 0.99),
                fill_opacity=0.19, width=2.2,
            )
        # Gold = actual original neutral-grey wall seam paint between
        # source-owned black exterior host faces; this is NOT a blind snap
        # or an authenticated/billable physical wall quantity.
        for seam in outer_wall.neutral_wall_seams:
            canvas.draw_rect(
                fitz.Rect(*seam.bounds_pdf_pts),
                color=(0.77, 0.50, 0.03), fill=(0.99, 0.79, 0.21),
                fill_opacity=0.22, width=2.2,
            )
        # Purple identifies an original annotated PARTY wall candidate.
        # This can separate two dwelling rooms INSIDE ONE building envelope;
        # its inside-face loop MUST NOT become the outside footprint.
        # Native wall ink + nearby PARTY WALL annotation + occupied zones
        # on BOTH sides are required; still no authoritative building ring.
        for divider in outer_wall.shared_dwelling_divider_candidates:
            canvas.draw_rect(
                fitz.Rect(*divider.wall_bounds_pdf_pts),
                color=(0.55, 0.11, 0.77),
                fill=(0.68, 0.34, 0.91),
                fill_opacity=0.13,
                width=2.8,
            )
        # The TRUE outside-facing walk can enclose multiple dwellings while
        # the internally shared PARTY wall remains purple. Draw blue only
        # after both source dwelling regions are demonstrably enclosed.
        outside_walk = outer_wall.source_outside_face_walk
        if outside_walk is not None and outside_walk.status == "CANDIDATE":
            polyline = [
                fitz.Point(float(x), float(y))
                for x, y in outside_walk.clockwise_pdf_pts
            ]
            if len(polyline) >= 5:
                canvas.draw_polyline(
                    polyline, color=(0.02, 0.42, 0.97), width=3.0,
                )
        # Do NOT turn unresolved components into a blue/firm footprint.
        # Amber dashed tracing is the exact-source unsealed review receipt.
        _draw_unsealed_source_ring_preview(canvas, outside_walk)
        # Proposed 0.5pt joins are SMALL CYAN dots/segments only; never
        # applied to native geometry and never counted as physical walls.
        for ax,ay,bx,by,distance in (
            outer_wall.graph.second_stage_05pt_join_proposals[:128]
        ):
            canvas.draw_line(
                fitz.Point(ax,ay),fitz.Point(bx,by),
                color=(0.,.95,.95),width=1.8,
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
        if outer_wall.viewport_pdf_pts:
            for vp_box in outer_wall.viewport_pdf_pts:
                canvas.draw_rect(
                    fitz.Rect(*vp_box),
                    color=(0.10, 0.75, 0.75),
                    dashes="[5 3] 0",
                    width=1.5,
                )
        zoom = min(1.2, 1800 / max(float(rect.width), float(rect.height)))
        png = canvas.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
        preview.close()
        summary = {
            "source_sha256": sha,
            "page_index": page_index,
            "producer": "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings",
            "legacy_envelope_used": False,
            "legacy_fallback_allowed": False,
            "source_modality": source_modality.to_dict(),
            "raster_source_trace": raster_trace.to_dict(),
            "stage_order": (
                "attempt_raster_source_walls_first"
                if source_modality.route == "tiled_raster_underlay"
                else "attempt_source_native_exterior_wall_trace_first",
                "trace_source_native_internal_wall_candidates",
                "temporarily_close_source_evidenced_doorways",
                "find_candidate_room_rings",
            ),
            "external_wall_trace_status": outer_wall.status,
            "external_wall_trace_reason": outer_wall.reason,
            "viewport_pdf_pts": (
                [list(vp) for vp in outer_wall.viewport_pdf_pts]
                if outer_wall.viewport_pdf_pts is not None
                else None
            ),
            "viewport_scoped_closure_enabled": outer_wall.viewport_pdf_pts is not None,
            # Diagnostic owner census only. A rejected small ring is NEVER
            # the physical building footprint or a customer quantity.
            "external_candidate_closed_wall_loop_count":
                outer_wall.diagnostic_closed_wall_loop_count,
            "external_rejected_loop_bbox_pdf_pts": (
                list(outer_wall.diagnostic_rejected_loop_bbox_pdf_pts)
                if outer_wall.diagnostic_rejected_loop_bbox_pdf_pts is not None
                else None
            ),
            "external_wall_bands_outside_rejected_loop":
                outer_wall.diagnostic_wall_bands_outside_loop,
            # One source building may contain multiple dwellings; a party
            # wall is NOT the outside boundary of the shared envelope.
            "building_scope": "one_building_multiple_dwelling_zones_candidate"
            if outer_wall.shared_dwelling_divider_candidates
            else "unresolved",
            "source_shared_dwelling_divider_candidate_count": len(
                outer_wall.shared_dwelling_divider_candidates
            ),
            "source_shared_dwelling_divider_candidates": [
                divider.to_dict()
                for divider in outer_wall.shared_dwelling_divider_candidates
            ],
            "source_party_wall_bounded_unit_loop_count": outer_wall.diagnostic_party_wall_bounded_unit_loops,
            "source_unbounded_outside_face_walk": (
                outer_wall.source_outside_face_walk.to_dict()
                if outer_wall.source_outside_face_walk is not None else None
            ),
            # Raw wall-ink graph endpoints are not necessarily missing
            # structural walls: windows/doors interrupt the painted ink.
            # This read-only ledger distinguishes source-hosted EXISTING
            # aperture terminals from residual unmatched/ambiguous tips.
            "source_wall_endpoint_aperture_review": (
                outer_wall.source_wall_endpoint_aperture_review.to_dict()
            ),
            "shared_dwelling_building_footprint_authenticated": False,
            "shared_dwelling_party_wall_billing_authorized": False,
            "external_source_path_ids_outside_rejected_loop_sample": list(
                outer_wall.diagnostic_outside_source_path_sample
            ),
            "source_window_footprint_continuity_count": len(outer_wall.window_footprint_bridges),
            "source_garage_door_footprint_continuity_count": len(outer_wall.garage_door_footprint_bridges),
            "source_swing_door_footprint_continuity_count": len(outer_wall.swing_door_footprint_bridges),
            "source_sliding_door_footprint_continuity_count": len(
                outer_wall.sliding_door_footprint_bridges
            ),
            "source_sliding_door_footprint_continuity": [
                bridge.to_dict() for bridge in outer_wall.sliding_door_footprint_bridges
            ],
            "source_sliding_door_continuity_billing_authorized": False,
            "source_neutral_wall_seam_count": len(outer_wall.neutral_wall_seams),
            "source_neutral_grey_wall_seam_count": len(outer_wall.neutral_wall_seams),
            "source_neutral_wall_seams": [
                seam.to_dict() for seam in outer_wall.neutral_wall_seams
            ],
            "source_neutral_wall_seam_billing_authorized": False,
            "source_neutral_grey_wall_seam_billing_authorized": False,
            "source_swing_door_footprint_continuity": [
                bridge.to_dict() for bridge in outer_wall.swing_door_footprint_bridges
            ],
            "source_swing_door_continuity_billing_authorized": False,
            "source_garage_door_footprint_continuity": [
                bridge.to_dict() for bridge in outer_wall.garage_door_footprint_bridges
            ],
            "source_window_footprint_continuity": [
                bridge.to_dict() for bridge in outer_wall.window_footprint_bridges
            ],
            "window_continuity_billing_authorized": False,
            "external_wall_native_source_paths": list(
                outer_wall.source_wall_path_ids
            ),
            "external_wall_band_candidates": outer_wall.source_wall_band_count,
            "external_wall_stroke_pair_candidates":
                outer_wall.source_stroke_pair_band_count,
            "external_wall_heavy_native_stroke_candidates":
                outer_wall.source_heavy_stroke_band_count,
            "external_wall_cavity_multi_face_candidates":
                outer_wall.source_cavity_multi_face_band_count,
            "external_wall_wide_native_face_pair_candidates":
                outer_wall.source_wide_face_pair_band_count,
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
                "stage_two_0_5pt_join_proposals": [
                    list(pt) for pt in outer_wall.graph.second_stage_05pt_join_proposals
                ],
                "stage_two_join_source_paths": [
                    [list(a),list(b)]
                    for a,b in outer_wall.graph.second_stage_join_source_paths
                ],
                "stage_two_join_applied": False,
                "source_endpoint_near_miss_total": (
                    outer_wall.graph.endpoint_near_miss_total
                ),
                "source_endpoint_near_misses": [
                    {
                        "tip_pdf_pts": list(hit.tip_pdf_pts),
                        "native_path_ids": list(hit.native_path_ids),
                        "nearby_native_path_ids": list(hit.nearby_native_path_ids),
                        "separation_pdf_pts": hit.separation_pdf_pts,
                        "native_source_layers": list(hit.native_source_layers),
                        "nearby_source_layers": list(hit.nearby_source_layers),
                        "same_painted_exterior_layer_hint": (
                            hit.same_painted_exterior_layer_hint
                        ),
                        "physical_join_authenticated": False,
                        "measurement_authorized": False,
                    }
                    for hit in outer_wall.graph.endpoint_near_misses
                ],
            },
            "source_wall_ink_paths_retained": source_wall_ink_count,
            "green_source_paths_excluded": green_path_exclusions,
            "source_neutral_dark_stroke_paths_added": neutral_dark_added,
            "source_stroke_pair_strict_count": (
                len(_collect_stroke_pair_strips(strict_wall_drawings))
                if neutral_dark_added else None
            ),
            "source_stroke_pair_expanded_count": (
                len(_collect_stroke_pair_strips(wall_drawings))
                if neutral_dark_added else None
            ),
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
                "magenta": "tiled raster original-source candidate ink, not physical wall",
                "violet": "three/four native CAD parallel-face wall candidates only",
                "lavender": "two isolated native faces 8–16 PDF pt apart; candidates only",
                "light_cyan": "proposed source 0.5pt CAD connection; not applied",
                "orange": "temporary topology-only doorway closures",
                "magenta_circle": "native wall endpoint near misses, not verified",
                "green": "candidate room enclosure",
            },
        }
        return summary, png
