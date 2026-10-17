"""Exact original-source wall-ink correspondence across two pages.

Read-only, caller-supplied candidate path/item identities. A matched source
stroke is not a structural wall, closing doorway, finished face or an area.
All original candidates and gaps remain owned by their original page.
"""
from __future__ import annotations
import hashlib
import math
import re
import fitz

_ID=re.compile(r"^d([0-9]+)i([0-9]+)$")
_ROLES=("left","right","bottom","top_partial")


def _line(drawings, identity):
    match=_ID.fullmatch(identity) if type(identity) is str else None
    if match is None:
        raise ValueError("original_native_path_item_id_required")
    pi,ii=map(int,match.groups())
    if pi>=len(drawings) or ii>=len(drawings[pi].get("items",())):
        raise ValueError("original_native_path_item_missing")
    entry=drawings[pi]
    item=entry["items"][ii]
    if len(item)<3 or item[0]!="l":
        raise ValueError("actual_original_straight_line_required")
    x,y,X,Y=(round(float(z),3) for point in item[1:3] for z in point)
    if not all(math.isfinite(q) for q in (x,y,X,Y)):
        raise ValueError("finite_original_source_line_required")
    ends=sorted(((x,y),(X,Y)))
    color=entry.get("color")
    width=entry.get("width")
    opacity=entry.get("stroke_opacity")
    dashes=entry.get("dashes")
    painting=entry.get("type")
    if (color is None or width is None or opacity is None
            or type(dashes) is not str or type(painting) is not str):
        raise ValueError("native_source_ink_style_required")
    try:
        color_values=tuple(float(v) for v in color)
        width_value=float(width)
        opacity_value=float(opacity)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("native_source_ink_style_required") from None
    # A fill-only, dashed or transparent construction path is not a
    # rendered continuous physical edge, regardless of endpoint match.
    if (not color_values or any(not math.isfinite(v) or not 0<=v<=1
                                for v in color_values)
            or not math.isfinite(width_value) or width_value<=0
            or not math.isfinite(opacity_value) or not 0<opacity_value<=1
            or "s" not in painting or "".join(dashes.split()) not in {"[]0",""}):
        raise ValueError("unrendered_or_dashed_original_source_edge")
    return {
        "identity":identity,"ends":ends,
        "stroke_width":round(width_value,3),
        "source_color":tuple(round(v,5) for v in color_values),
        "stroke_opacity":round(opacity_value,6),
        "source_paint_type":painting,
        "original_source_continuous_painted_stroke":True,
    }


def audit_source_enclosure_correspondence(
    original_pdf_bytes:bytes, *, expected_sha256:str,
    floor_page_1_based:int, finish_page_1_based:int,
    original_side_pairs:dict[str,tuple[str,str]],
    expected_translation_pdf_pts:tuple[float,float],
    max_native_paths:int=120000,
)->dict:
    if type(original_pdf_bytes) is not bytes or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256:
        raise ValueError("original_source_sha_mismatch")
    if (type(original_side_pairs) is not dict
            or set(original_side_pairs)!=set(_ROLES)
            or any(type(v) is not tuple or len(v)!=2
                   for v in original_side_pairs.values())):
        raise ValueError("four_explicit_original_edge_pair_candidates_required")
    if (type(expected_translation_pdf_pts) is not tuple or len(expected_translation_pdf_pts)!=2
            or any(not isinstance(n,(int,float)) or not math.isfinite(n)
                   for n in expected_translation_pdf_pts)):
        raise ValueError("finite_source_translation_candidate_required")
    if len({a for v in original_side_pairs.values() for a in v})!=8:
        raise ValueError("distinct_source_path_item_owners_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as pdf:
        if (type(floor_page_1_based) is not int or type(finish_page_1_based) is not int
                or floor_page_1_based==finish_page_1_based
                or not 1<=floor_page_1_based<=len(pdf)
                or not 1<=finish_page_1_based<=len(pdf)):
            raise ValueError("distinct_original_source_pages_required")
        fa=pdf[floor_page_1_based-1].get_drawings()
        fb=pdf[finish_page_1_based-1].get_drawings()
        if len(fa)>max_native_paths or len(fb)>max_native_paths:
            return {"status":"source_path_cap_exceeded","room_authority_granted":False}
        pairs={}
        for side in _ROLES:
            a_id,b_id=original_side_pairs[side]
            a,b=_line(fa,a_id),_line(fb,b_id)
            dx,dy=expected_translation_pdf_pts
            translated=sorted((round(x+dx,3),round(y+dy,3)) for x,y in a["ends"])
            if (translated!=b["ends"] or a["source_color"]!=b["source_color"]
                    or a["stroke_width"]!=b["stroke_width"]
                    or a["stroke_opacity"]!=b["stroke_opacity"]):
                raise ValueError("source_side_ink_or_translation_conflict")
            pairs[side]={"floor_source":a,"finish_source":b,
                          "matched_original_ink_only":True,
                          "physical_wall_role_proven":False}
        left,right,bottom,top=(pairs[x]["floor_source"]["ends"] for x in _ROLES)
        if (left[0][0]!=left[1][0] or right[0][0]!=right[1][0]
                or bottom[0][1]!=bottom[1][1] or top[0][1]!=top[1][1]
                or left[0][0]>=right[0][0] or top[0][1]>=bottom[0][1]):
            raise ValueError("source_enclosure_side_orientation_conflict")
        x_left=left[0][0];x_right=right[0][0]
        y_top=top[0][1];y_bottom=bottom[0][1]
        if (left!=[(x_left,y_top),(x_left,y_bottom)]
                or right!=[(x_right,y_top),(x_right,y_bottom)]
                or bottom!=[(x_left,y_bottom),(x_right,y_bottom)]
                or top[1]!=(x_right,y_top)
                or not x_left<top[0][0]<x_right):
            raise ValueError("native_original_wall_side_or_doorway_gap_conflict")
        return {
            "status":"original_four_edge_ink_correspondence_with_unclosed_doorway",
            "original_floor_page_id":floor_page_1_based,
            "original_finish_page_id":finish_page_1_based,
            "source_translation_candidate_pdf_pts":list(expected_translation_pdf_pts),
            "original_witnesses":pairs,
            "original_top_gap_pdf_pts":[[x_left,y_top],[top[0][0],y_top]],
            "original_top_gap_is_a_door_without_jamb_proof":False,
            "canonical_cross_sheet_physical_room_equality_granted":False,
            "physical_wall_roles_verified":False,
            "source_finished_face_and_area_verified":False,
            "new_firm_quantities":0,
        }

def audit_competing_original_enclosure_registrations(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    floor_page_1_based: int, finish_page_1_based: int,
    candidates: tuple[dict, ...],
    max_native_paths: int = 120000,
) -> dict:
    """Compare ALL supplied source-side registration hypotheses, elect none.

    Every candidate contains explicit independent path-item owners and its
    original-source translation. The result is a negative-evidence ledger;
    even one source-ink winner does not grant W4 or physical room identity.
    """
    # Source integrity is global, not a rejected individual hypothesis.
    # No rival may turn a tampered original PDF into a legitimate empty
    # candidate set (which could otherwise silence a production audit).
    if (type(original_pdf_bytes) is not bytes or
            hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_source_sha_mismatch")
    if type(candidates) is not tuple or not candidates or len(candidates)>32:
        raise ValueError("bounded_explicit_source_registration_universe_required")
    seen=set()
    outcomes=[]
    for candidate in candidates:
        if type(candidate) is not dict or set(candidate)!={"side_pairs","translation"}:
            raise ValueError("exact_source_registration_candidate_fields_required")
        pairs=candidate["side_pairs"]
        translation=candidate["translation"]
        if type(pairs) is not dict or set(pairs)!=set(_ROLES):
            raise ValueError("four_explicit_original_edge_pair_candidates_required")
        if (type(translation) is not tuple or len(translation)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v)
                    for v in translation)):
            raise ValueError("finite_source_translation_candidate_required")
        key=(tuple((side,pairs[side]) for side in _ROLES),
             tuple(float(v) for v in translation))
        if key in seen:
            raise ValueError("duplicate_original_registration_candidate")
        seen.add(key)
        try:
            result=audit_source_enclosure_correspondence(
                original_pdf_bytes,expected_sha256=expected_sha256,
                floor_page_1_based=floor_page_1_based,
                finish_page_1_based=finish_page_1_based,
                original_side_pairs=pairs,
                expected_translation_pdf_pts=translation,
                max_native_paths=max_native_paths,
            )
        except ValueError as exc:
            # Preserve the rival and its first negative gate instead of
            # discarding it or swapping in the numerically nearest winner.
            result={"status":"source_registration_rejected",
                    "first_unclosed_gate":str(exc),"new_firm_quantities":0}
        outcomes.append({"original_candidate_index":len(outcomes),
                         "translation":translation,
                         "source_side_pairs":pairs,
                         "source_evidence":result})
    accepted=[row for row in outcomes if row["source_evidence"].get("status")==
              "original_four_edge_ink_correspondence_with_unclosed_doorway"]
    return {
        "status":("competing_original_source_registrations" if len(accepted)>1
                  else "one_original_ink_registration_candidate" if accepted
                  else "no_original_ink_registration_candidate"),
        "all_original_registration_evidence":outcomes,
        "source_ink_positive_candidate_count":len(accepted),
        "cross_sheet_physical_room_identity_issued":False,
        "original_source_structural_wall_issuer_granted":False,
        "original_source_door_gap_closed":False,
        "new_firm_quantities":0,
    }
