"""Original-source ONLY first-gate receipt for native lines removed before W2.

Diagnostic/hand-off, not permission to restore filtered drafting primitives as
structural walls. Emits exact native identities and coordinates rather than
source-word/name or nearest-edge guessed lineage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_filtered_native_primitive_receipts import filtered_native_primitive_receipts
from pb_physical_wall_candidate_authority import (
    _filter_repeated_non_physical_drafting_primitives,
    _proven_filled_wall_strips,
    _filter_proven_wall_strip_geometry,
)
from pb_wall_room_topology_stage_a import (
    is_structural_candidate_segment,
    build_wall_graph_for_viewport,
)
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import (
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

SOURCE_PATH = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
PAGE_INDEX = 6
ORIGINAL_NATIVE_IDS = ("d50057i0", "d50507i0", "d50048i0")


def collect_page7_filtered_native_receipt(*, include_w2_graph: bool = False) -> dict[str, object]:
    payload = SOURCE_PATH.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != SOURCE_SHA:
        raise RuntimeError("original_maryborough_source_sha_conflict")
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        if pdf.page_count != 31:
            raise RuntimeError("original_maryborough_page_universe_conflict")
        page = pdf.load_page(PAGE_INDEX)
        native = extract_native_page(page)
        views = tuple(segment_page_viewports(page, page_number=7))
        if not validate_non_overlapping_viewports(views):
            raise RuntimeError("source_viewport_overlap")
        floor = tuple(
            v for v in views
            if v.view_type == DrawingViewType.FLOOR_PLAN.value
            and v.status == "resolved"
            and v.bounding_box is not None
        )
        if len(floor) != 1:
            raise RuntimeError("source_floor_viewport_unavailable")
        x0, y0, x1, y1 = map(float, floor[0].bounding_box)

        # Explicit producer-owned original source-line containment only.
        # This is a strict diagnostic subset of the authenticated viewport,
        # not a replacement for the W4 producer's own source partition.
        original = tuple(
            row for row in native["segments"]
            if x0 <= row["x1"] <= x1 and x0 <= row["x2"] <= x1
            and y0 <= row["y1"] <= y1 and y0 <= row["y2"] <= y1
        )
        retained = _filter_repeated_non_physical_drafting_primitives(
            original, page_width=page.rect.width, page_height=page.rect.height
        )
        excluded = filtered_native_primitive_receipts(original, retained)
        excluded_by_id = {item.source_id: item for item in excluded}
        original_by_id = {}
        for row in original:
            key = row.get("id")
            if type(key) is not str or not key or key in original_by_id:
                raise RuntimeError("native_original_source_identity_collision")
            original_by_id[key] = row
        retained_ids = {row["id"] for row in retained}
        if len(retained_ids) != len(retained):
            raise RuntimeError("native_retained_source_identity_collision")
        if (not retained_ids <= set(original_by_id)
                or len(excluded_by_id) != len(excluded)):
            raise RuntimeError("native_filter_receipt_unavailable")

        # Follow exact original source IDs through every lightweight gate
        # BEFORE W2 graph splitting. The whole graph can remain expensive,
        # but none of these stage receipts may mint missing W2 source edges.
        proven_strips = _proven_filled_wall_strips(retained)
        graph_inputs = _filter_proven_wall_strip_geometry(
            retained, proven_strips
        )
        graph_input_ids = {row["id"] for row in graph_inputs}
        if len(graph_input_ids) != len(graph_inputs):
            raise RuntimeError("native_graph_input_identity_collision")
        graph_input_by_id = {row["id"]: row for row in graph_inputs}
        if not graph_input_ids <= retained_ids:
            raise RuntimeError("native_graph_input_foreign_source_identity")

        targets = []
        for original_id in ORIGINAL_NATIVE_IDS:
            row = original_by_id.get(original_id)
            if row is None:
                raise RuntimeError("native_original_source_target_missing:" + original_id)
            if row.get("kind") != "line":
                raise RuntimeError("native_original_source_target_non_line:" + original_id)
            observed = excluded_by_id.get(original_id)
            status = (
                "EXCLUDED_NATIVE_CANDIDATE_ONLY" if observed is not None
                else ("RETAINED_AT_FIRST_FILTER" if original_id in retained_ids
                      else "REJECTED_NONCANDIDATE_AT_FIRST_FILTER")
            )
            graph_input = graph_input_by_id.get(original_id)
            is_stage_a_candidate = None
            stage_a_negative_reasons = []
            if graph_input is not None:
                is_stage_a_candidate, stage_a_negative_reasons = (
                    is_structural_candidate_segment(graph_input)
                )
            targets.append({
                "original_source_id": original_id,
                "source_path_index": row["path_index"],
                "exact_original_geometry": [
                    row["x1"], row["y1"], row["x2"], row["y2"]
                ],
                "original_stroke": row.get("stroke"),
                "original_width_pt": row.get("width"),
                "source_filter_disposition": status,
                "retained_by_first_filter": original_id in retained_ids,
                "retained_by_proven_filled_wall_strip_filter": (
                    original_id in graph_input_ids
                ),
                "stage_a_structural_candidate": is_stage_a_candidate,
                "stage_a_metadata_exclusion_reasons": stage_a_negative_reasons,
                "read_only_receipt_status": (
                    observed.status if observed is not None else None
                ),
                "physical_wall_proven": False,
                "two_sided_source_room_owner_proven": False,
                "new_firm_quantity_produced": False,
            })
        if include_w2_graph:
            # This is the real, unmodified Stage A source graph on the
            # original SHA-verified viewport input, not a new geometry guess.
            # Missing lineage is evidence of a possible W2 handoff dropout;
            # surviving lineage alone does not prove a W4 structural wall.
            if len(graph_inputs) > 20_000:
                raise RuntimeError("w2_source_segment_safety_bound")
            w2_graph = build_wall_graph_for_viewport(graph_inputs)
            source_index: dict[str, set[str]] = {
                source_id: set() for source_id in ORIGINAL_NATIVE_IDS
            }
            collapsed_index: dict[str, set[str]] = {
                source_id: set() for source_id in ORIGINAL_NATIVE_IDS
            }
            for edge in w2_graph.get("edges", ()):
                lineage = edge.get(LINEAGE_KEY) or {}
                parents = lineage.get("source_primitive_ids", ())
                edge_id = str(edge.get("id") or "")
                for parent in parents:
                    if parent in source_index and edge_id:
                        source_index[parent].add(edge_id)
            for fragment in w2_graph.get("snap_collapsed_fragments", ()):
                lineage = fragment.get(LINEAGE_KEY) or {}
                parents = lineage.get("source_primitive_ids", ())
                fragment_id = str(fragment.get("id") or "")
                for parent in parents:
                    if parent in collapsed_index and fragment_id:
                        collapsed_index[parent].add(fragment_id)
            for row in targets:
                source_id = row["original_source_id"]
                row["w2_source_descendant_edge_count"] = len(
                    source_index[source_id]
                )
                row["w2_source_descendant_edge_ids_sample"] = sorted(
                    source_index[source_id]
                )[:8]
                row["w2_snap_collapsed_source_fragment_count"] = len(
                    collapsed_index[source_id]
                )
                row["w2_graph_physical_wall_proven"] = False
            w2_counts = {
                "w2_graph_edge_count": len(w2_graph.get("edges", ())),
                "w2_snap_collapsed_total": len(
                    w2_graph.get("snap_collapsed_fragments", ())
                ),
                "w2_graph_lineage_proves_structural_wall": False,
            }
        else:
            w2_counts = {
                "w2_graph_executed": False,
                "w2_graph_lineage_proves_structural_wall": False,
            }
        return {
            **w2_counts,
            "source_sha256": sha,
            "original_page_number": 7,
            "authenticated_floor_viewport_id": floor[0].view_id,
            "source_native_original_viewport_segment_count": len(original),
            "source_filter_retained_segment_count": len(retained),
            "proven_filled_wall_strip_count": len(proven_strips),
            "w2_original_graph_input_segment_count": len(graph_inputs),
            "filtered_native_line_receipt_count": len(excluded),
            "targets": targets,
            "source_wall_role_authenticated_by_diagnostic": False,
            "source_room_geometry_published_by_diagnostic": False,
            "firm_quantity_published_by_diagnostic": False,
            "benchmark_accuracy_granted": False,
        }
    finally:
        pdf.close()


if __name__ == "__main__":
    import sys

    graph_arg = sys.argv[1:] == ["--w2-graph"]
    if sys.argv[1:] and not graph_arg:
        raise SystemExit("usage: diag_gpt2_filtered_native_page7.py [--w2-graph]")
    print(json.dumps(
        collect_page7_filtered_native_receipt(include_w2_graph=graph_arg),
        sort_keys=True,
    ))
