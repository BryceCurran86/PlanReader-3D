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
                or bottom!=[(x_left,y_bottom),(x_right,y_bottom)]):
            raise ValueError("native_original_wall_side_or_doorway_gap_conflict")
        # Two actual original A110/A140 orientations occur: OFFICE has a
        # right-anchored top partial wall (open on the left); PWD has a
        # left-anchored top partial wall (open on the right). Never assume
        # the first endpoint of the partial stroke is the doorway endpoint.
        if (top[1]==(x_right,y_top) and x_left<top[0][0]<x_right):
            gap=[[x_left,y_top],[top[0][0],y_top]]
            anchor="right"
        elif (top[0]==(x_left,y_top) and x_left<top[1][0]<x_right):
            gap=[[top[1][0],y_top],[x_right,y_top]]
            anchor="left"
        else:
            raise ValueError("native_original_wall_side_or_doorway_gap_conflict")
        return {
            "status":"original_four_edge_ink_correspondence_with_unclosed_doorway",
            "original_floor_page_id":floor_page_1_based,
            "original_finish_page_id":finish_page_1_based,
            # Every positive candidate carries its immutable original source
            # root. Path-item IDs are sheet-local and cannot be joined to
            # similarly numbered paths in an independently issued PDF.
            "original_source_sha256":expected_sha256,
            "source_original_page_pair_ids":[floor_page_1_based,finish_page_1_based],
            "source_translation_candidate_pdf_pts":list(expected_translation_pdf_pts),
            "original_witnesses":pairs,
            "original_top_gap_pdf_pts":gap,
            "original_top_partial_wall_anchor":anchor,
            "original_top_gap_is_a_door_without_jamb_proof":False,
            "canonical_cross_sheet_physical_room_equality_granted":False,
            "physical_wall_roles_verified":False,
            "source_finished_face_and_area_verified":False,
            "new_firm_quantities":0,
        }

def audit_source_painted_enclosure_correspondence_shadow(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    floor_page_1_based: int, finish_page_1_based: int,
    original_side_pairs: dict[str, tuple[str, str]],
    expected_translation_pdf_pts: tuple[float, float],
    max_native_paths: int = 120000,
) -> dict:
    """Prove *source-painted* endpoint contact, not a canonical closed room.

    Exact original PDF native black painted strokes can terminate one full
    stroke-width apart and still touch at their real paint boundaries.
    This is NOT a 2.5pt W2 snap, a missing wall, a physical room equivalence,
    a finished-face offset or a finish area.
    """
    if (type(original_pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest() != expected_sha256):
        raise ValueError("original_source_sha_mismatch")
    if (type(original_side_pairs) is not dict
            or set(original_side_pairs) != set(_ROLES)
            or any(type(pair) is not tuple or len(pair) != 2
                   or any(type(identity) is not str or not identity
                          or identity != identity.strip()
                          for identity in pair)
                   for pair in original_side_pairs.values())):
        raise ValueError("four_exact_original_ink_side_pairs_required")
    if len({identity for pair in original_side_pairs.values()
            for identity in pair}) != 8:
        raise ValueError("distinct_original_native_wall_ink_source_ids_required")
    if (type(expected_translation_pdf_pts) is not tuple
            or len(expected_translation_pdf_pts) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in expected_translation_pdf_pts)):
        raise ValueError("independently_proven_finite_source_translation_required")
    if type(max_native_paths) is not int or max_native_paths <= 0:
        raise ValueError("original_native_path_safety_cap_required")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as doc:
        if (type(floor_page_1_based) is not int
                or type(finish_page_1_based) is not int
                or min(floor_page_1_based, finish_page_1_based) <= 0
                or floor_page_1_based == finish_page_1_based
                or max(floor_page_1_based, finish_page_1_based) > len(doc)):
            raise ValueError("distinct_original_source_pages_required")
        native = {
            floor_page_1_based: doc[floor_page_1_based - 1].get_drawings(),
            finish_page_1_based: doc[finish_page_1_based - 1].get_drawings(),
        }
    if any(len(drawings) > max_native_paths for drawings in native.values()):
        raise ValueError("original_source_native_path_safety_bound_exceeded")
    dx, dy = map(float, expected_translation_pdf_pts)
    all_source_sides = {floor_page_1_based: {}, finish_page_1_based: {}}
    pairs = {}
    for role in _ROLES:
        floor_id, finish_id = original_side_pairs[role]
        left = _line(native[floor_page_1_based], floor_id)
        right = _line(native[finish_page_1_based], finish_id)
        # Both original line interpretations must be the SAME paint, not just
        # the same centreline; dashes/white ink/opacity remain barred by _line.
        for field in ("stroke_width", "source_color", "stroke_opacity",
                      "source_paint_type"):
            if left[field] != right[field]:
                raise ValueError("original_side_ink_style_conflict")
        if left["source_color"] != (0., 0., 0.):
            raise ValueError("original_source_black_structural_ink_required")
        shifted = sorted((round(x + dx, 3), round(y + dy, 3))
                         for x, y in left["ends"])
        if shifted != right["ends"]:
            raise ValueError("original_source_translation_ink_pair_conflict")
        all_source_sides[floor_page_1_based][role] = left
        all_source_sides[finish_page_1_based][role] = right
        pairs[role] = {
            "floor_source": left,
            "finish_source": right,
            "matched_original_paint_only": True,
            "structural_wall_role_authenticated": False,
        }

    def ring_audit(source_roles):
        vertical_left = source_roles["left"]["ends"]
        vertical_right = source_roles["right"]["ends"]
        bottom = source_roles["bottom"]["ends"]
        top = source_roles["top_partial"]["ends"]
        if (vertical_left[0][0] != vertical_left[1][0]
                or vertical_right[0][0] != vertical_right[1][0]
                or bottom[0][1] != bottom[1][1]
                or top[0][1] != top[1][1]):
            raise ValueError("original_source_four_sides_not_orthogonal")
        x0, x1 = vertical_left[0][0], vertical_right[0][0]
        yt, yb = vertical_left[0][1], vertical_left[1][1]
        if (x0 >= x1 or yt >= yb
                or vertical_right != [(x1, yt), (x1, yb)]
                or bottom[0] != (x0, yb)
                or top[0][1] != yt
                or not x0 < top[0][0] < x1
                or bottom[1][0] > x1 or top[1][0] > x1):
            raise ValueError("native_original_room_wall_side_or_gap_conflict")
        # Source-native .001pt rounding belongs only to the ink audit.
        # Two opaque strokes can touch if their actual half-width paint
        # envelopes touch; a larger deficit is a REAL unclosed corner.
        gaps = {
            "bottom_right": round(x1 - bottom[1][0], 3),
            "top_right": round(x1 - top[1][0], 3),
        }
        for side, gap in gaps.items():
            horizontal_role = "bottom" if side == "bottom_right" else "top_partial"
            max_painted_reach = (
                source_roles[horizontal_role]["stroke_width"] / 2
                + source_roles["right"]["stroke_width"] / 2
            )
            if gap < 0 or gap > max_painted_reach + .001:
                raise ValueError("original_painted_corner_contact_unproven")
        return {
            "original_source_ink_bbox_pdf_pts": (x0, yt, x1, yb),
            "original_source_raw_endpoint_deficits_pdf_pts": gaps,
            "original_source_top_virtual_door_gap_pdf_pts":
                ((x0, yt), (top[0][0], yt)),
            "source_horizontal_stroke_endpoint_paint_reach_proven": True,
            "source_virtual_door_gap_is_structural_wall": False,
            "source_finished_wall_face_offset_authenticated": False,
        }

    floor = ring_audit(all_source_sides[floor_page_1_based])
    finish = ring_audit(all_source_sides[finish_page_1_based])
    translated_floor = tuple(round(value + shift, 3)
                             for value, shift in zip(
                                 floor["original_source_ink_bbox_pdf_pts"],
                                 (dx, dy, dx, dy)))
    if translated_floor != finish["original_source_ink_bbox_pdf_pts"]:
        raise ValueError("original_painted_enclosure_cross_page_bbox_conflict")
    return {
        "status": "original_painted_wall_ink_correspondence_candidate_only",
        "original_source_sha256": expected_sha256,
        "original_floor_page_1_based": floor_page_1_based,
        "original_finish_page_1_based": finish_page_1_based,
        "independent_source_translation_candidate_pdf_pts": (dx, dy),
        "original_four_side_ink_witnesses": pairs,
        "source_floor_painted_corner_evidence": floor,
        "source_finish_painted_corner_evidence": finish,
        "source_original_paint_contact_not_W2_endpoint_snap": True,
        "source_authenticated_structural_room_or_wall": False,
        "source_cross_page_physical_room_equality_authenticated": False,
        "source_finished_face_or_finish_threshold_authenticated": False,
        "new_firm_quantities": 0,
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
