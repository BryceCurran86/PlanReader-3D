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
            # Some original A502 drafting faces terminate 1.2pt SHORT
            # of the adjacent face. The missing ink is a first failure to
            # retain, not permission to snap a corner or silently discard
            # a competing original wall-family.
            def corner_gaps(source,values):
                a,b=source["original_source_interval_pdf_pts"]
                return [round(max(a-v,0.,v-b),3) for v in values]
            gaps={
                "left":corner_gaps(faces["left"],(y0,y1)),
                "right":corner_gaps(faces["right"],(y0,y1)),
                "top":corner_gaps(faces["top"],(x0,x1)),
                "bottom":corner_gaps(faces["bottom"],(x0,x1)),
            }
            any_open=any(v>0 for gaps_for_role in gaps.values()
                         for v in gaps_for_role)
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
                "source_corner_unpainted_gaps_pdf_pts":gaps,
                "source_full_four_edge_ring_uninterrupted":not any_open,
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
        # Preserve both actually printed source text witnesses through the
        # intermediate wall-face ledger. Otherwise a downstream plan
        # candidate could quietly lose its independent FT2 mark provenance.
        "original_room_and_finish_mark_candidates":
            figure["original_room_and_finish_mark_candidates"],
        "original_source_candidate_face_families":tuple(candidates),
        "original_exact_figure_endpoint_family_count":len(matching),
        "original_source_figured_area_m2_candidate_not_signed":
            figure["candidate_orthogonal_area_m2_not_signed"],
        "first_unclosed_gate":"inner_vs_outer_finished_face_and_same_W4_room",
        "unique_finished_net_face_role_authenticated":False,
        "source_A502_to_A110_physical_room_issuer_granted":False,
        "new_firm_quantities":0,
    }


def audit_original_figured_wall_note_alignment(
    original_face_rivals: dict, original_dimension_chains: dict,
) -> dict:
    """Same-source original drawing's wall notes around the figured span.

    Independently drawn short end dimensions can tell us whether the
    printed long room dimension is bracketed by wall-build-up annotations.
    The numeric wall notes are NOT themselves verified wall type/finished
    surface. The outer source linework vs inner lining is not elected by
    lexical meaning, even when the first family matches all figured ends.
    """
    blocked={
        "status":"source_figured_wall_note_alignment_unresolved",
        "first_failure":"independent_original_figure_wall_note_source_unavailable",
        "source_net_finished_face_authenticated":False,
        "source_metric_floor_finish_area_issued":False,
        "new_firm_quantities":0,
    }
    if (type(original_face_rivals) is not dict or type(original_dimension_chains) is not dict or
            original_face_rivals.get("status")!="original_figured_face_source_rivals_only" or
            original_dimension_chains.get("status")!=
                "source_orthogonal_native_figured_chains_candidate_only" or
            original_face_rivals.get("original_source_sha256")!=
                original_dimension_chains.get("original_source_sha256") or
            original_face_rivals.get("original_detail_page_1_based")!=
                original_dimension_chains.get("original_detail_page_1_based")):
        return blocked
    chains=original_dimension_chains.get("native_printed_dimension_chains",{})
    try:
        x_chain=chains["horizontal"]
        y_chain=chains["vertical"]
        x_main=x_chain["original_source_records"]["main"]
        y_main=y_chain["original_source_records"]["main"]
        x_fig=tuple(float(n) for n in x_main["original_arrowhead_tips_pdf_pts"])
        y_fig=tuple(float(n) for n in y_main["original_arrowhead_tips_pdf_pts"])
    except (KeyError,TypeError,ValueError,OverflowError):
        return blocked
    # Both axes must have a typed, exact three-segment original annotation
    # chain: the near (wall) notes sit OUTSIDE the main dimension terminals.
    chain_roles={}
    for axis,chain in (("horizontal",x_chain),("vertical",y_chain)):
        try:
            b,m,a=(chain["original_source_records"][role]
                   for role in ("short_before","main","short_after"))
            bt=b["original_arrowhead_tips_pdf_pts"]
            mt=m["original_arrowhead_tips_pdf_pts"]
            at=a["original_arrowhead_tips_pdf_pts"]
            continuous=(bt[1]==mt[0] and mt[1]==at[0] and
                        bt[0]<bt[1]<mt[1]<at[1])
        except (KeyError,TypeError,ValueError,IndexError):
            return blocked
        if not continuous:
            return {**blocked,"first_failure":"source_original_wall_note_chain_has_uncovered_terminals"}
        chain_roles[axis]={
            "original_wall_note_before_mm":b["source_original_dimension_mm"],
            "original_main_figure_mm":m["source_original_dimension_mm"],
            "original_wall_note_after_mm":a["source_original_dimension_mm"],
            "original_wall_note_before_source_span_pdf_pts":bt,
            "original_main_figure_source_span_pdf_pts":mt,
            "original_wall_note_after_source_span_pdf_pts":at,
            "source_wall_note_labels_independently_printed":True,
            "source_wall_type_or_finished_face_role_granted":False,
        }
    candidates=[]
    for family in original_face_rivals.get("original_source_candidate_face_families",()):
        coords=family["original_source_native_bbox_pdf_pts"]
        x_residual=[round(coords[0]-x_fig[0],3),round(coords[2]-x_fig[1],3)]
        y_residual=[round(coords[1]-y_fig[0],3),round(coords[3]-y_fig[1],3)]
        candidates.append({
            "original_face_family_id":family["source_native_family_id_untrusted"],
            "original_source_face_bbox_pdf_pts":coords,
            "source_wall_note_to_figured_face_residual_x_pdf_pts":x_residual,
            "source_wall_note_to_figured_face_residual_y_pdf_pts":y_residual,
            "source_both_printed_long_figures_terminate_at_this_family":
                all(value==0 for value in (*x_residual,*y_residual)),
            "source_finished_face_role_proven":False,
        })
    if not candidates:
        return blocked
    return {
        **blocked,
        "status":"original_orthogonal_wall_note_and_face_rivals_candidate_only",
        "first_failure":"original_inset_main_room_W4_identity_and_finished_face_role",
        "original_source_sha256":original_face_rivals["original_source_sha256"],
        "original_page_1_based":original_face_rivals["original_detail_page_1_based"],
        "source_original_dimension_chains":chain_roles,
        "all_original_inner_outer_face_alignment_candidates":tuple(candidates),
        "original_figured_dimension_has_adjacent_wall_note_chains":True,
        "source_FT2_area_m2_candidate_not_signed":
            original_face_rivals["original_source_figured_area_m2_candidate_not_signed"],
    }



def audit_original_ft2_internal_wall_face_basis(
    original_face_rivals: dict, original_dimension_chains: dict,
) -> dict:
    """Explicit FT2 trade measurement rule: exposed floor up to wall faces.

    A502 prints 92 | main clear dimension | 92 on each axis. The short wall
    notes are OUTSIDE the middle figure: never include them in floor area and
    never subtract them a second time. Other secondary strokes INSIDE the
    figured box remain recorded as possible lining/face evidence, not an
    automatic offset to the measured internal wall boundary.

    This policy chooses WHAT physical surface to measure, not WHICH original
    W4-produced face is the finished wall. No signed customer quantity.
    """
    base={
        "status":"original_ft2_internal_wall_face_basis_unresolved",
        "first_failure":"original_internal_figure_or_ft2_source_not_authenticated",
        "measurement_surface":"exposed_ft2_floor_within_internal_finished_wall_faces",
        "include_area_under_walls":False,
        "deduct_the_92mm_walls_from_clear_room_figures":False,
        "add_the_92mm_walls_to_clear_room_figures":False,
        "do_not_elect_further_inset_stroke_as_finished_face_by_proximity":True,
        "d13_threshold_treatment_requires_source_boundary_proof":True,
        "source_finished_wall_face_role_authenticated":False,
        "source_W4_physical_room_identity_authenticated":False,
        "source_FT2_floor_finish_m2_signed":None,
        "new_firm_quantities":0,
    }
    mark=original_face_rivals.get("original_room_and_finish_mark_candidates")
    if (type(mark) not in (list,tuple) or len(mark)!=2
            or mark[0].get("original_literal_untrusted")!="PWD"
            or mark[1].get("original_literal_untrusted")!="FT2"):
        return base
    aligned=audit_original_figured_wall_note_alignment(
        original_face_rivals,original_dimension_chains)
    if aligned["status"]!="original_orthogonal_wall_note_and_face_rivals_candidate_only":
        return {**base,"first_failure":aligned["first_failure"]}
    ratios=aligned["source_original_dimension_chains"]
    try:
        vertical=ratios["vertical"]
        horizontal=ratios["horizontal"]
        long_mm=vertical["original_main_figure_mm"]
        width_mm=horizontal["original_main_figure_mm"]
        walls=(
            vertical["original_wall_note_before_mm"],
            vertical["original_wall_note_after_mm"],
            horizontal["original_wall_note_before_mm"],
            horizontal["original_wall_note_after_mm"],
        )
        face_candidates=aligned["all_original_inner_outer_face_alignment_candidates"]
    except (KeyError,TypeError):
        return base
    if (type(long_mm) is not int or type(width_mm) is not int
            or long_mm<=0 or width_mm<=0 or
            not all(type(x) is int and x>0 for x in walls)):
        return base
    # Original figured spans must terminate at ONE genuinely drawn source
    # face family. Even that figure-bound family is not thereby certified a
    # finished-face W4 wall: original multiple source layers can coexist.
    fig_bound=[
        family for family in face_candidates
        if family["source_both_printed_long_figures_terminate_at_this_family"]
    ]
    if len(fig_bound)!=1 or len(face_candidates)<2:
        return {
            **base,
            "first_failure":"clear_inside_figure_face_missing_or_competing",
            "source_original_face_family_candidates":tuple(face_candidates),
        }
    area=round(long_mm*width_mm/1_000_000,9)
    if area!=aligned["source_FT2_area_m2_candidate_not_signed"]:
        return {
            **base,"first_failure":"original_figure_area_receipt_conflict",
        }
    return {
        **base,
        "status":"original_ft2_clear_internal_wall_face_area_candidate",
        "first_failure":"original_figured_face_W4_finished_surface_and_D13_threshold",
        "original_source_sha256":aligned["original_source_sha256"],
        "original_page_1_based":aligned["original_page_1_based"],
        "source_original_figured_internal_length_mm":long_mm,
        "source_original_figured_internal_width_mm":width_mm,
        "source_wall_notes_outside_clear_dimensions_mm":walls,
        "source_original_figure_bound_face_family":
            fig_bound[0]["original_face_family_id"],
        "source_all_face_family_candidates":tuple(face_candidates),
        "source_ft2_clear_room_rectangle_area_m2_candidate_not_signed":area,
        "source_rectangular_area_not_a_sealed_finished_floor_polygon":True,
        "source_floor_finish_occurrence_authority_issued":False,
    }
