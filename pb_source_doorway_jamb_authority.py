"""Source-issued native doorway jamb endpoint chain, never a door quantity.

Uses original source path-item evidence, not plan-door label proximity.
A positive native contact witness shows two wall fragments terminate at two
distinct perpendicular jambs. It does NOT establish wall STRUCTURAL roles,
finished-face area, opening scheduled size, door count, W4 host topology or
room ring closure. Source issuer lineage is kept on every claim.
"""
from __future__ import annotations

from tools.diag_native_opposed_source_wall_ink_shadow import native_ink_record


def _near(a:float,b:float, tolerance:float) -> bool:
    return abs(a-b)<=tolerance


def audit_native_source_doorway_jamb_chain(
    page, *, left_wall_id:str, right_wall_id:str,
    left_jamb_id:str, right_jamb_id:str,
    exact_native_tolerance_pt:float=0.01,
) -> dict:
    """Bounded original strokes of one candidate wall interruption.

    Checks both positive wall-jamb terminators and matching other jamb
    endpoints in source space. Every implicit/weakening proximity snap is
    rejected: tolerance <0.01? allowed 0..0.01 only for representation noise.
    The physical snap contract of the construction producer is untouched.
    """
    ids=(left_wall_id,right_wall_id,left_jamb_id,right_jamb_id)
    if len(set(ids))!=4:
        raise ValueError("independent_original_wall_and_jamb_paths_required")
    if (type(exact_native_tolerance_pt) not in (int,float)
            or not 0<=exact_native_tolerance_pt<=.01):
        raise ValueError("strict_native_float_equality_scope_required")
    rows=[native_ink_record(page,x) for x in ids]
    base={
        "original_primitive_paths":dict(zip(
            ("left_wall","right_wall","left_jamb","right_jamb"),rows)),
        "native_ink_contact_proved":False,
        "original_structural_host_authenticated":False,
        "finished_wall_face_binding_proved":False,
        "opening_count_issuer_granted":False,
        "source_door_schedule_size_binding_granted":False,
        "source_physical_floor_ring_closed":False,
        "new_physical_opening_count":0,
        "new_quantities":0,
    }
    l,r,lj,rj=rows
    if (l["native_line_axis"]!="native_x" or
            r["native_line_axis"]!="native_x" or
            lj["native_line_axis"]!="native_y" or
            rj["native_line_axis"]!="native_y"):
        return {**base,"status":"original_native_axes_mismatch"}
    if not _near(l["native_axis_coordinate_pdf_pt"],
                 r["native_axis_coordinate_pdf_pt"],exact_native_tolerance_pt):
        return {**base,"status":"original_wall_run_ordinate_conflict"}
    left_x=l["native_interval_pdf_pts"][1]
    right_x=r["native_interval_pdf_pts"][0]
    if right_x<=left_x+exact_native_tolerance_pt:
        return {**base,"status":"no_original_positive_wall_opening_gap"}
    if not (
        _near(lj["native_axis_coordinate_pdf_pt"],left_x,exact_native_tolerance_pt)
        and _near(rj["native_axis_coordinate_pdf_pt"],right_x,exact_native_tolerance_pt)
    ):
        return {**base,"status":"native_jamb_not_exact_wall_terminator"}
    wall_y=l["native_axis_coordinate_pdf_pt"]
    if not (
        _near(lj["native_interval_pdf_pts"][1],wall_y,exact_native_tolerance_pt)
        and _near(rj["native_interval_pdf_pts"][1],wall_y,exact_native_tolerance_pt)
        and _near(lj["native_interval_pdf_pts"][0],rj["native_interval_pdf_pts"][0],
                  exact_native_tolerance_pt)
        and lj["native_interval_pdf_pts"][0]<wall_y
    ):
        return {**base,"status":"native_opposing_jamb_backface_conflict"}
    # Must retain original actual paint/widths.  Both walls and jambs are
    # black, with no faded drafting grid substituting a real jamb.
    originals=[x["original_color"] for x in rows]
    if not all(tuple(c)==(0.,0.,0.) for c in originals):
        return {**base,"status":"competing_nonstructural_paint_ink"}
    if not all(row["original_stroke_width_pdf_pt"]>0 for row in rows):
        return {**base,"status":"unpainted_primitive"}
    # Opposing source elements must have matching drawing roles: the two
    # wall fragments are one painted line family and the independent two
    # jamb returns are another. Sharing only black color is insufficient.
    if (not _near(l["original_stroke_width_pdf_pt"],
                  r["original_stroke_width_pdf_pt"],.001)
            or not _near(lj["original_stroke_width_pdf_pt"],
                         rj["original_stroke_width_pdf_pt"],.001)):
        return {**base,"status":"competing_source_stroke_role_mismatch"}
    return {
        **base,
        "status":"exact_original_native_jamb_endpoint_chain_candidate",
        "native_ink_contact_proved":True,
        "source_original_wall_axis_pdf_pt":wall_y,
        "source_native_unbridged_wall_gap_pdf_pts":[left_x,right_x],
        "source_native_jamb_crosswall_interval_pdf_pts":lj["native_interval_pdf_pts"],
        "source_native_jamb_separation_pdf_pt":right_x-left_x,
        "first_unresolved_authority":"W3_W4_physical_wall_host_and_door_jamb_structural_role",
    }
