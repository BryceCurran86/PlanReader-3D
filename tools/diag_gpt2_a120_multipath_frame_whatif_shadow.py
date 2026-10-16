"""Default-unwired source-only F.07 what-if with a genuine multi-path CAD table.

Original F.07 resolution is recorded BEFORE any alternate interpretation.
The shadow separately considers every exact source-closed line-grid candidate
that contains one original semantic title, and rejects false repeated fixture
rectangles that have no physically shared native cell edges. No trust, room,
source viewport, ceiling, material, metric or customer authority can be minted.
The original F.07 result is never changed or replaced.

Uses repository-owned read-only diagnostic stage outputs. No expected object
identity, plan/project names, title string ranking, nearest matching, benchmark
quantity, source filename or thresholds derived from a project's target.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch


def _contains(a,b):
    return (
        a[0]<=b[0] and a[1]<=b[1]
        and a[2]>=b[2] and a[3]>=b[3]
    )


def _rows(views):
    return [
        {
            "reported_source_viewport_id":str(v.view_id),
            "source_viewport_type":str(v.view_type),
            "status":str(v.status),
            "source_native_bbox_pdf_pts":(
                list(v.bounding_box) if v.bounding_box else None
            ),
            "reported_separator_view_id":str(
                (v.provenance or {}).get("separator_view_id") or ""
            ),
            "view_is_a_new_source_authority":False,
            "quantity_or_material_granted":False,
        }
        for v in views
    ]


def audit_original_multipath_semantic_table_what_if(
    page:Any, *, page_number:int,
):
    """No caller-selected frame: enumerate all source-contiguous title owners."""
    if type(page_number) is not int or page_number<1:
        raise ValueError("original_one_based_page_required")
    import pb_viewport_segmentation as v
    from tools.diag_native_multipath_cad_grid_source_shadow import (
        audit_native_multipath_orthogonal_grid_components,
    )
    from tools.diag_source_connected_semantic_cell_shadow import (
        audit_source_rect_cell_lattice,
    )

    baseline=v.segment_page_viewports(page,page_number=page_number)
    native_grid=audit_native_multipath_orthogonal_grid_components(page)
    anchors=v.extract_view_title_anchors(page)
    frame_candidates=[]
    candidate_receipts=[]
    if native_grid["source_line_universe_complete"]:
        for grid in native_grid["candidate_native_grids"]:
            frame=tuple(grid["native_component_witness"]["native_bbox_pdf_pts"])
            matched=[
                (index,a)
                for index,a in enumerate(anchors)
                if a.view_type in v._SEMANTIC_TABLE_VIEW_TYPES
                and _contains(frame,a.bbox)
            ]
            candidate_receipts.append({
                "original_connected_line_grid_bbox_pdf_pts":list(frame),
                "original_native_path_item_ids":
                    list(grid["original_source_primitive_ids"]),
                "original_closed_line_grid_witness":
                    grid["native_component_witness"],
                "original_enclosed_semantic_title_candidates":[
                    {
                        "native_title_index":index,
                        "source_type_not_text_authority":str(a.view_type),
                        "original_title_bbox_pdf_pts":list(a.bbox),
                        "original_title_text_untrusted":str(a.text),
                    }
                    for index,a in matched
                ],
                "same_original_grid_title_owner_unambiguous_candidate_only":
                    len(matched)==1,
                "no_view_or_material_authority_granted":True,
            })
            if len(matched)==1:
                frame_candidates.append(frame)
    if not native_grid["source_line_universe_complete"]:
        return {
            "status":"source_original_multipath_grid_incomplete",
            "original_f07_viewports":_rows(baseline),
            "candidate_native_schedule_grids":candidate_receipts,
            "optin_simulated_f07_viewports":[],
            "simulation_universe_complete":False,
            "new_authoritative_viewports":0,
            "new_ceiling_material_or_m2":0,
        }

    original_extract=v.extract_vector_frames
    original_table=v._frame_looks_like_table
    table_firstgate_cache={}

    def filtered_native_cell_table(frame, current_page, calib,
                                   *, allow_line_grid_only=True):
        # Re-run exactly the producer's original predicate before any shadow.
        accepted=original_table(
            frame,current_page,calib,
            allow_line_grid_only=allow_line_grid_only,
        )
        if not accepted:
            return False
        # Keep the separate line-built schedule category as its own source
        # candidate. The existing F.07 line-grid test remains original.
        if (allow_line_grid_only
                and not original_table(
                    frame,current_page,calib,allow_line_grid_only=False
                )):
            return accepted
        key=tuple(frame)
        if key not in table_firstgate_cache:
            table_firstgate_cache[key]=audit_source_rect_cell_lattice(
                current_page,candidate_frame_bbox=frame,
            )
        return bool(
            table_firstgate_cache[key].get(
                "connected_cell_lattice_candidate_only",False
            )
        )

    def proposed_frames(current_page,calib):
        original=original_extract(current_page,calib)
        # Preserve original frame rivals; never prefer or remove by
        # nearest text or expected project identity.
        output=list(original)
        for frame in frame_candidates:
            if frame not in output:
                output.append(frame)
        return output

    with patch.object(v,"extract_vector_frames",side_effect=proposed_frames), \
         patch.object(v,"_frame_looks_like_table",
                      side_effect=filtered_native_cell_table):
        simulation=v.segment_page_viewports(page,page_number=page_number)

    return {
        "status":"read_only_source_f07_counterfactual_not_production",
        "original_f07_viewports":_rows(baseline),
        "candidate_native_schedule_grids":candidate_receipts,
        "candidate_source_grid_frame_count":len(frame_candidates),
        "original_false_rectangle_table_frame_diagnostics":[
            {
                "frame_native_bbox_pdf_pts":list(frame),
                "source_contiguous_cell_candidate_only":
                    result.get("connected_cell_lattice_candidate_only",False),
                "source_role_or_text_trust_granted":False,
            }
            for frame,result in table_firstgate_cache.items()
        ],
        "optin_simulated_f07_viewports":_rows(simulation),
        "simulated_result_does_not_replace_original_f07":True,
        "simulation_universe_complete":True,
        "new_authoritative_viewports":0,
        "new_ceiling_material_or_m2":0,
    }
