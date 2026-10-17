"""Original figured-plan competing wall-face interpretations, no net-area grant.

An original printed dimension can terminate at independently painted OUTER
wall-face ink while INNER face ink is also present. Do not infer that a
dimension figure measures the net floor/ceiling surface, or correct an inner
face by the 2.5pt wall snap. Source-native PDF point geometry only.

Inputs are exact original path-item IDs with independently SHA-verified native
figured receipts; no frozen benchmark areas, labels or expected dimensions.
"""
from __future__ import annotations

import hashlib
import math

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line


def _axis_face(drawings, identity: str, axis: str) -> dict:
    source = _line(drawings, identity)
    a,b=source["ends"]
    if axis=="x":
        if a[0]!=b[0] or a[1]==b[1]:
            raise ValueError("original_candidate_not_vertical_wall_face")
        ordinate=a[0]
        interval=[min(a[1],b[1]),max(a[1],b[1])]
    elif axis=="y":
        if a[1]!=b[1] or a[0]==b[0]:
            raise ValueError("original_candidate_not_horizontal_wall_face")
        ordinate=a[1]
        interval=[min(a[0],b[0]),max(a[0],b[0])]
    else:
        raise ValueError("original_wall_face_axis_required")
    return {
        "original_native_source_id":identity,
        "original_source_coordinate_pdf_pt":ordinate,
        "original_source_interval_pdf_pts":interval,
        "original_native_stroke_width_pdf_pt":source["stroke_width"],
        "original_source_ink_color":source["source_color"],
        "original_source_paint_opacity":source["stroke_opacity"],
        "original_source_continuous_painted_stroke":
            source["original_source_continuous_painted_stroke"],
        "source_structural_wall_or_finished_face_role_proven":False,
    }


def audit_original_figured_detail_face_rivals(
    original_pdf: bytes, *, source_sha256: str,
    original_figure_receipt: dict, page_1_based: int,
    competing_original_wall_face_families: tuple[dict,...],
    max_source_paths: int=120000,
) -> dict:
    """Enumerate all competing original wall-face coordinate rectangles.

    A family is FOUR explicitly painted original path-item IDs:
    {"family_id":str,"left":dNNiM,"right":dNNiM,
     "top":dNNiM,"bottom":dNNiM}.
    These are just competing source paths; caller names such as "inner" and
    "outer" do not confer a wall role. The dimension arrow line itself
    independently names its figured original mm value.
    """
    if type(original_pdf) is not bytes or (
        hashlib.sha256(original_pdf).hexdigest()!=source_sha256
    ):
        raise ValueError("original_figured_faces_pdf_sha_mismatch")
    figure=original_figure_receipt
    if (type(figure) is not dict
            or figure.get("status")!=
                "original_figured_orthogonal_detail_area_candidate_only"
            or figure.get("original_source_sha256")!=source_sha256
            or figure.get("original_page_1_based")!=page_1_based):
        raise ValueError("sealed_original_figured_detail_receipt_required")
    if (type(competing_original_wall_face_families) is not tuple
            or len(competing_original_wall_face_families)<2
            or len(competing_original_wall_face_families)>32):
        raise ValueError("bounded_competing_original_face_families_required")
    if (type(max_source_paths) is not int or not
            8<=max_source_paths<=120000):
        raise ValueError("original_face_native_path_cap_invalid")
    dimensions=figure.get("original_figured_source_records")
    if (type(dimensions) not in (tuple,list) or len(dimensions)!=2
            or set(d.get("original_source_dimension_axis") for d in dimensions)
            !={"horizontal","vertical"}):
        raise ValueError("two_original_orthogonal_figured_dimensions_required")
    dx=next(d for d in dimensions
            if d["original_source_dimension_axis"]=="horizontal")
    dy=next(d for d in dimensions
            if d["original_source_dimension_axis"]=="vertical")
    deduced_x=tuple(sorted(
        float(p[0]) for p in dx["original_dimension_line_source_endpoints_pdf_pts"]))
    deduced_y=tuple(sorted(
        float(p[1]) for p in dy["original_dimension_line_source_endpoints_pdf_pts"]))
    names=set()
    native_ids=set()
    candidates=[]
    with fitz.open(stream=original_pdf,filetype="pdf") as pdf:
        if type(page_1_based) is not int or not 1<=page_1_based<=len(pdf):
            raise ValueError("original_detail_source_page_out_of_range")
        drawing=pdf[page_1_based-1].get_drawings()
        if len(drawing)>max_source_paths:
            raise ValueError("original_detail_source_wall_path_cap_exceeded")
        for candidate in competing_original_wall_face_families:
            if (type(candidate) is not dict or
                    set(candidate)!={"family_id","left","right","top","bottom"}
                    or type(candidate["family_id"]) is not str
                    or not candidate["family_id"]
                    or candidate["family_id"] in names):
                raise ValueError("distinct_original_face_family_required")
            names.add(candidate["family_id"])
            ids=tuple(candidate[role] for role in
                      ("left","right","top","bottom"))
            if len(set(ids))!=4 or any(id in native_ids for id in ids):
                raise ValueError("independent_competing_original_face_paths_required")
            native_ids.update(ids)
            faces={
                role:_axis_face(drawing,candidate[role],
                                "x" if role in ("left","right") else "y")
                for role in ("left","right","top","bottom")
            }
            x0=faces["left"]["original_source_coordinate_pdf_pt"]
            x1=faces["right"]["original_source_coordinate_pdf_pt"]
            y0=faces["top"]["original_source_coordinate_pdf_pt"]
            y1=faces["bottom"]["original_source_coordinate_pdf_pt"]
            if not (x0<x1 and y0<y1):
                raise ValueError("source_wall_face_competitor_rectangle_inverted")
            # Each source fragment should visibly reach a corner or side of
            # the proposed rectangle. An unrelated dimension/grid stroke
            # elsewhere on the page cannot own a boundary merely because
            # its x or y ordinate matches.
            def touches(source,values):
                a,b=source["original_source_interval_pdf_pts"]
                return any(a<=v<=b for v in values)
            if (not touches(faces["left"],(y0,y1))
                    or not touches(faces["right"],(y0,y1))
                    or not touches(faces["top"],(x0,x1))
                    or not touches(faces["bottom"],(x0,x1))):
                raise ValueError("source_face_role_intervals_not_connected_to_rectangle")
            interval_x=x1-x0
            interval_y=y1-y0
            residual_x=[
                round(x0-deduced_x[0],3),
                round(x1-deduced_x[1],3),
            ]
            residual_y=[
                round(y0-deduced_y[0],3),
                round(y1-deduced_y[1],3),
            ]
            matches_x=all(v==0 for v in residual_x)
            matches_y=all(v==0 for v in residual_y)
            candidates.append({
                "source_native_family_id_untrusted":candidate["family_id"],
                "original_page_1_based":page_1_based,
                "original_source_sha256":source_sha256,
                "source_original_four_face_records":faces,
                "original_source_native_bbox_pdf_pts":[x0,y0,x1,y1],
                "source_original_figure_endpoint_residual_x_pdf_pts":residual_x,
                "source_original_figure_endpoint_residual_y_pdf_pts":residual_y,
                "source_exact_printed_figure_endpoints_match":
                    matches_x and matches_y,
                "source_candidate_rectangle_pdf_pt2_not_metric_area":
                    round(interval_x*interval_y,6),
                "source_face_role_is_finished_internal":False,
                "source_face_role_is_outer_structural":False,
                "original_w4_physical_room_identity_proven":False,
                "new_firm_quantities":0,
            })
    matching=[c for c in candidates
              if c["source_exact_printed_figure_endpoints_match"]]
    # A single precise endpoint match does NOT elect it as the net finish.
    # The independent inner ink is an active competing interpretation.
    return {
        "status":"original_figured_face_source_rivals_only",
        "original_source_sha256":source_sha256,
        "original_detail_page_1_based":page_1_based,
        "original_source_candidate_face_families":tuple(candidates),
        "original_exact_figure_endpoint_family_count":len(matching),
        "original_source_figured_area_m2_candidate_not_signed":
            figure["candidate_orthogonal_area_m2_not_signed"],
        "first_unclosed_gate":"inner_vs_outer_finished_face_and_same_W4_room",
        "unique_finished_net_face_role_authenticated":False,
        "source_A502_to_A110_physical_room_issuer_granted":False,
        "new_firm_quantities":0,
    }
