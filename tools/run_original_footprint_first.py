"""Read-only original PlanReader footprint-first source-tracing diagnostic.

No customer quantities, benchmark, private-source upload or automatic FIRM.
Use: py -3.13 tools/run_original_footprint_first.py --pdf house.pdf --page 1 --out-dir C:\\private\\test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_gpt1_acacia_source_packet import (
    inspect_acacia_original_bytes,
)
from pb_gpt1_acacia_cross_sheet_review import (
    ROOM_KEY, SCHEDULE_CODES, review_acacia_finishes,
    review_acacia_legend_room,
)
from pb_external_footprint_first_trace import (  # noqa: E402
    bound_native_drawings_to_footprint,
    refine_external_footprint_against_wall_ink,
    trace_external_footprint_first,
)
from pb_layered_wall_doorway_room_ring_shadow import (  # noqa: E402
    _source_wall_ink_candidate_drawings,
    build_layered_wall_doorway_room_rings,
)
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
from pb_source_native_exterior_edge_path_ownership import (  # noqa: E402
    own_exterior_contour_native_paths,
)
from pb_source_native_wall_body_junction_graph_shadow import (  # noqa: E402
    build_source_native_wall_body_junction_graph,
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


def _acacia_source_scope_review(packet, outer_review):
    """Original Acacia legend/schedule exceptions, with no commercial authority.

    A sheet key, GFA note or 16 schedule prototypes never substitute for a
    physical room polygon, finished face, hosted installed door or window.
    """
    room_reviews = [
        review_acacia_legend_room(packet, key)
        for key in sorted(ROOM_KEY)
    ]
    finish_status, finish_reason = review_acacia_finishes(packet)
    return {
        "source_scope_status": "ORIGINAL_ACACIA_SOURCE_REVIEW_ONLY",
        "original_source_roles_verified": packet.original_byte_roles_verified,
        "indoor_candidate_key_ids": [
            r.legend_id for r in room_reviews if r.scope == "interior_candidate"
        ],
        "outdoor_or_service_excluded_key_ids": [
            r.legend_id for r in room_reviews
            if r.status == "EXCLUDED_FROM_ENCLOSED_FINISH"
        ],
        "scheduled_prototype_codes_not_installed_count": list(SCHEDULE_CODES),
        "source_exterior_first_failing_gate": (
            "outside_original_wall_ink_not_physically_accepted"
            if not outer_review.get("physical_wall_authenticated", False)
            else "finished_inside_face_and_opening_host_not_verified"
        ),
        "material_finish_status": finish_status,
        "material_finish_reason": finish_reason,
        "printed_gfa_note_is_not_a_measured_finished_area": True,
        "installed_opening_instances_count_verified": False,
        "physical_room_face_authorized": False,
        "floor_wall_ceiling_finish_authorized": False,
        "commercial_quantity_rows": 0,
        "official_frozen120_score_change": 0,
    }


def _original_source_native_outer_wall_review(drawings, words, page_index):
    """Read-only original-native evidence; never upgrade raster to a wall.

    Use the existing outside-facing walker and wall/opening graph. Missing
    ownership or a nearby source stroke may guide review, but cannot grant
    an invented seam, snapped corner, measurement or customer publication.
    """
    try:
        proof = attempt_source_native_outer_wall_first(
            drawings, source_words=words, source_page_index=page_index,
        )
        graph = proof.graph
        misses = tuple(graph.endpoint_near_misses)
        return {
            "status": proof.status,
            "reason": proof.reason,
            "source_wall_band_count": proof.source_wall_band_count,
            "connected_native_wall_components": graph.component_count,
            "source_endpoint_near_miss_count": len(misses),
            "near_miss_witnesses_sample": [
                {
                    "tip_pdf_pts": list(w.tip_pdf_pts),
                    "nearby_native_path_ids": list(w.nearby_native_path_ids),
                    "separation_pdf_pts": w.separation_pdf_pts,
                    "physical_join_authenticated": False,
                }
                for w in misses[:8]
            ],
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    except (RuntimeError, ValueError, TypeError, OverflowError, IndexError):
        return {
            "status": "ABSTAINED",
            "reason": "original_native_outer_source_review_unavailable",
            "source_wall_band_count": 0,
            "connected_native_wall_components": 0,
            "source_endpoint_near_miss_count": 0,
            "near_miss_witnesses_sample": [],
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def _enforce_original_source_sha_pin(actual_sha: str, expected_sha256: str | None) -> bool:
    """Fail before any geometry or output if the regional original is wrong.

    A Brisbane acceptance run must not silently use the similar Sydney or
    Melbourne Acacia PDF. No PDF bytes, source paths, or quantities are changed.
    """
    if expected_sha256 is None:
        return False
    if (type(expected_sha256) is not str or len(expected_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_sha256)):
        raise ValueError("original_footprint_expected_sha256_invalid")
    if actual_sha != expected_sha256:
        raise ValueError("original_footprint_source_sha256_mismatch")
    return True


def _verify_original_drawing_title(source_bytes: bytes, page_index: int,
                                   expected_title: str | None) -> bool:
    """Optional page-identity gate: never mistake site/roof for floor plan."""
    if expected_title is None:
        return False
    if (type(expected_title) is not str or not expected_title.strip()
            or len(expected_title) > 100):
        raise ValueError("original_footprint_expected_page_title_invalid")
    import fitz

    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        if type(page_index) is not int or not 0 <= page_index < len(document):
            raise ValueError("original_footprint_original_page_index_invalid")
        # Source title blocks may wrap a single drawing title across PDF
        # lines (Acacia p10: "Window" / "and Door Schedule"). Whitespace
        # layout is not part of the drawing's semantic title identity.
        import re

        source_title_text = " ".join(document[page_index].get_text().split())
        normalized_expected_title = " ".join(expected_title.split())
        # A cover sheet's drawing INDEX can mention "Floor Plan" without
        # itself being that sheet (original 3Laurel A0.1 versus A0.3).
        # Require one explicit title-block field, not arbitrary page text.
        # Title/metadata may wrap across multiple PDF text lines.
        titles = re.findall(
            r"\bDrawing\s+(?:title|name)\s*:\s*(.*?)\s*"
            r"(?=\bScale\s*:|\bPaper\s+size\s*:|"
            r"\bDrawing\s+number\s*:|\bDate\s+issued\s*:|"
            r"\bProject\s+stage\s*:|$)",
            source_title_text,
            flags=re.IGNORECASE,
        )
        if (len(titles) != 1
                or " ".join(titles[0].split()).casefold()
                != normalized_expected_title.casefold()):
            raise ValueError("original_footprint_original_page_title_mismatch")
    return True


def run(pdf: Path, page_index: int, out_dir: Path, *,
        expected_sha256: str | None = None,
        expected_drawing_title: str | None = None,
        acacia_region: str | None = None):
    import fitz

    original_bytes = pdf.read_bytes()
    acacia_package = None
    if acacia_region is not None:
        # In Acacia-specific replay, prevent p1 site/cover, foreign regional
        # source and wrong section/setout/schedule variants from reaching
        # geometry. Generic projects retain their existing input contract.
        acacia_package = inspect_acacia_original_bytes(
            original_bytes, expected_region=acacia_region,
        )
        if not acacia_package.original_byte_roles_verified:
            raise ValueError("original_footprint_acacia_role_packet_unverified")
        if page_index != 1:
            raise ValueError("original_footprint_acacia_floor_page_required")
    sha = hashlib.sha256(original_bytes).hexdigest()
    sha_pin_verified = _enforce_original_source_sha_pin(sha, expected_sha256)
    # Reject invalid original sheet identities before source-native geometry tracing.
    with fitz.open(stream=original_bytes, filetype="pdf") as source_pages:
        if type(page_index) is not int or not 0 <= page_index < len(source_pages):
            raise ValueError("original_footprint_original_page_index_invalid")
    title_verified = _verify_original_drawing_title(
        original_bytes, page_index, expected_drawing_title,
    )
    (outer,) = trace_external_footprint_first(
        original_bytes, source_sha256=sha, page_indices=(page_index,),
    )
    with fitz.open(stream=original_bytes, filetype="pdf") as source:
        drawings = tuple(source[page_index].get_drawings())
        source_native_outer_review = _original_source_native_outer_wall_review(
            drawings, source[page_index].get_text("words"), page_index,
        )
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
            "source_sha_pin_verified": sha_pin_verified,
            "source_page_title_verified": title_verified,
            "acacia_four_role_original_source_review": (
                acacia_package.to_dict() if acacia_package else None
            ),
            "acacia_room_opening_and_finish_source_review": (
                _acacia_source_scope_review(
                    acacia_package, source_native_outer_review,
                ) if acacia_package else None
            ),
            "page_index_0based": page_index,
            "stage_order": [
                "source_hashed_exterior_ink_contour",
                "preserve_original_native_path_scope",
                "dark_wall_and_doorway_ring_topology",
                "physical_wall_metric_and_customer_UNAUTHORIZED",
            ],
            "exterior": outer.to_dict(),
            "source_native_outer_wall_review": source_native_outer_review,
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
                "gap_review_performed": ring is not None,
                "unresolved_collinear_gap_count": ring.unresolved_gap_count if ring else None,
                "source_gap_witness_count": ring.unresolved_gap_witness_count if ring else None,
                "source_gap_witnesses_sample": [
                    dict(w) for w in ring.unresolved_gap_witnesses
                ] if ring else [],
                "wall_strip_count": ring.wall_strip_count if ring else 0,
                "merged_collinear_dark_face_strip_count": (
                    ring.merged_collinear_dark_face_strip_count if ring else 0
                ),
                "free_space_part_count": ring.free_space_part_count if ring else 0,
                "free_space_exterior_touching_count": (
                    ring.free_space_exterior_touching_count if ring else 0
                ),
                "free_space_enclosed_part_count": (
                    ring.free_space_enclosed_part_count if ring else 0
                ),
                "free_space_max_enclosed_area_pt2": (
                    ring.free_space_max_enclosed_area_pt2 if ring else 0.0
                ),
                "ring_area_tier_lt_100_count": (
                    ring.ring_area_tier_lt_100_count if ring else 0
                ),
                "ring_area_tier_100_to_1000_count": (
                    ring.ring_area_tier_100_to_1000_count if ring else 0
                ),
                "ring_area_tier_ge_1000_count": (
                    ring.ring_area_tier_ge_1000_count if ring else 0
                ),
                "drafting_pocket_sliver_count": (
                    ring.drafting_pocket_sliver_count if ring else 0
                ),
                "commercial_publishable": False,
                "room_quantity_authorized": False,
            },
            "commercial_quantity_rows": 0,
            "official_frozen120_score_change": 0,
        }
        if scope.status == "CANDIDATE":
            owned = own_exterior_contour_native_paths(
                scope.drawings, outer, closures=() if ring is None else ring.closures,
            )
            class_counts: dict[str, int] = {}
            for edge in owned:
                class_counts[edge.classification] = class_counts.get(edge.classification, 0) + 1
            chain_edges = [
                edge for edge in owned
                if edge.classification in {
                    "source_native_wall_ink_chain_candidate",
                    "incomplete_source_native_wall_ink_chain",
                }
            ]
            unique_edges = [
                edge for edge in owned
                if edge.classification == "source_native_wall_ink_candidate"
            ]
            result["exterior_edge_ownership"] = {
                "classification_counts": class_counts,
                "edge_count": len(owned),
                "unmatched_or_incomplete": sum(
                    1 for edge in owned
                    if edge.classification in {
                        "unmatched_contour_segment",
                        "incomplete_source_native_wall_ink_chain",
                        "incorrect_geometric_bridge",
                        "competing_exterior_path_owners",
                        "competing_source_ink_chains",
                    }
                ),
                "complete_source_chain_count": sum(
                    1 for edge in owned
                    if edge.classification == "source_native_wall_ink_chain_candidate"
                ),
                "incomplete_source_chain_count": sum(
                    1 for edge in owned
                    if edge.classification == "incomplete_source_native_wall_ink_chain"
                ),
                "chain_endpoint_shortfalls_pt": [
                    {
                        "edge_index": edge.edge_index,
                        "classification": edge.classification,
                        "start_shortfall_pt": edge.chain_start_shortfall_pt,
                        "end_shortfall_pt": edge.chain_end_shortfall_pt,
                        "association_pt": edge.contour_endpoint_association_pt,
                        "native_path_indices": list(edge.native_path_indices),
                    }
                    for edge in chain_edges
                ],
                "unique_owner_coverage": [
                    {
                        "edge_index": edge.edge_index,
                        "native_path_indices": list(edge.native_path_indices),
                        "overlap_fraction": edge.unique_owner_overlap_fraction,
                        "uncovered_start_pt": edge.unique_owner_uncovered_start_pt,
                        "uncovered_end_pt": edge.unique_owner_uncovered_end_pt,
                        "competing_incomplete_chain_path_count": len(
                            edge.competing_incomplete_chain_path_indices
                        ),
                        "competing_incomplete_chain_coverage_fraction": (
                            edge.competing_incomplete_chain_coverage_fraction
                        ),
                    }
                    for edge in unique_edges
                ],
                "physical_wall_authenticated": False,
                "commercial_publishable": False,
            }
            graph = build_source_native_wall_body_junction_graph(
                drawings,
                page_index=page_index,
                # Optional Acacia host-stroke audit filter only; never a join.
                focus_native_path_ids=(4000, 4002, 5862, 5848, 5849),
            )
            result["junction_graph_summary"] = {
                "exterior_preflight_status": graph.get("exterior_preflight_status"),
                "exterior_preflight_reason": graph.get("exterior_preflight_reason"),
                "exterior_preflight_connectivity_status": graph.get(
                    "exterior_preflight_connectivity_status"
                ),
                "junction_disposition_counts": graph.get("junction_disposition_counts"),
                "endpoint_near_miss_count": graph.get("endpoint_near_miss_count"),
                "focus_path_near_miss_count": graph.get("focus_path_near_miss_count"),
                "focus_path_near_misses": graph.get("focus_path_near_misses"),
                "open_endpoint_disposition_counts": graph.get(
                    "open_endpoint_disposition_counts"
                ),
                "window_continuity_disposition_counts": graph.get(
                    "window_continuity_disposition_counts"
                ),
                "physical_wall_authenticated": False,
                "commercial_publishable": False,
            }
            # Longest unique/chain edges — west face audit without hardcoding IDs.
            longest_edges = sorted(
                owned,
                key=lambda edge: math.hypot(
                    edge.end_pdf_pts[0] - edge.start_pdf_pts[0],
                    edge.end_pdf_pts[1] - edge.start_pdf_pts[1],
                ),
                reverse=True,
            )[:6]
            result["exterior_edge_ownership"]["longest_edge_sample"] = [
                {
                    "edge_index": edge.edge_index,
                    "classification": edge.classification,
                    "start_pdf_pts": list(edge.start_pdf_pts),
                    "end_pdf_pts": list(edge.end_pdf_pts),
                    "native_path_indices": list(edge.native_path_indices),
                    "overlap_fraction": edge.unique_owner_overlap_fraction,
                    "chain_start_shortfall_pt": edge.chain_start_shortfall_pt,
                    "chain_end_shortfall_pt": edge.chain_end_shortfall_pt,
                }
                for edge in longest_edges
            ]
            result["layered_ring_authority"] = {
                "ring_count": 0 if ring is None else len(ring.rings),
                "commercial_projection_allowed": False,
                "takeoff_eligible": False,
                "metric_area_issued": False,
                "physical_room_identity_issued": False,
                "free_space_enclosed_part_count": (
                    0 if ring is None else ring.free_space_enclosed_part_count
                ),
                "merged_collinear_dark_face_strip_count": (
                    0 if ring is None else ring.merged_collinear_dark_face_strip_count
                ),
                "rings": [
                    {
                        "record_id": rec.record_id,
                        "status": rec.status.value,
                        "area_pt2": rec.area_pt2,
                        "commercial_projection_allowed": False,
                        "takeoff_eligible": False,
                        "metric_area_issued": False,
                        "physical_room_identity_issued": False,
                    }
                    for rec in (() if ring is None else ring.rings)
                ],
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
    parser.add_argument("--expected-sha256",
                        help="Exact SHA256 of the intended original drawing")
    parser.add_argument("--expected-drawing-title",
                        help="Require drawing-title field of the intended page")
    parser.add_argument("--acacia-region",
                        choices=("Sydney", "Melbourne", "Brisbane"),
                        help="Require four exact original Acacia source pages on floor p2")
    arguments = parser.parse_args()
    result, js, png = run(
        arguments.pdf, arguments.page, arguments.out_dir,
        expected_sha256=arguments.expected_sha256,
        expected_drawing_title=arguments.expected_drawing_title,
        acacia_region=arguments.acacia_region,
    )
    print(json.dumps({
        "source_sha_pin_verified": result["source_sha_pin_verified"],
        "source_page_title_verified": result["source_page_title_verified"],
        "exterior_status": result["exterior"]["status"],
        "source_native_ink_primitives": result["bounded_source"]["candidate_wall_native_primitives"],
        "room_topology_status": result["topology"]["status"],
        "room_topology_reasons": result["topology"]["reason_codes"],
        "rooms": result["topology"]["candidate_room_rings"],
        "closures": result["topology"]["temporary_doorway_closures"],
        "json": str(js), "overlay": str(png),
    }, indent=2))
