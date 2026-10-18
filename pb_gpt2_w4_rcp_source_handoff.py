"""GPT2 W4 → original A120 RCP ceiling source-owner binding.

Ceiling measurements must come from the AUTHENTICATED reflected ceiling plan.
The physical room's p7 floor area is never copied as p9 ceiling square metres.
Both original view polygons and independent source-registration ancestry must
correspond exactly; even then GPT1 must own a genuine metric calibration and
ceiling lining quantity authority. This module publishes zero quantities.
"""
from __future__ import annotations
import math

from shapely.geometry import Polygon

from pb_gpt2_w4_original_floor_handoff import (
    audit_gpt2_w4_bound_original_floor,
)


def _valid_polygon(v):
    if type(v) not in (list,tuple) or len(v)<3:
        return None
    try:
        points=tuple((float(x),float(y)) for x,y in v)
        if any(not math.isfinite(x) or not math.isfinite(y) for x,y in points):
            return None
        polygon=Polygon(points)
    except (TypeError,ValueError,OverflowError):
        return None
    return polygon if polygon.is_valid and polygon.area>0 else None


def audit_gpt2_w4_original_rcp_ceiling_handoff(
    *, independently_registered_rcp: dict,
    original_rcp_ink: dict,
    original_rcp_material: dict,
    canonical_rooms,
    physical_room_id: str,
) -> dict:
    """Source-only A120 ceiling zone binding to a sealed W4 physical room.

    W4 result is expected to have been generated directly from the existing
    sealed room-face producer using audit_gpt2_w4_bound_original_floor; copied
    field matching does not independently authorize a commercial quantity.
    """
    blocked={
        "status":"original_W4_RCP_ceiling_handoff_abstained",
        "first_failure":"original_W4_room_or_RCP_source_unavailable",
        "ceiling_quantity_m2_issued":False,
        "floor_metric_area_copied_to_ceiling":False,
        "original_ceiling_measurement_source":"reflected_ceiling_plan",
        "new_firm_quantities":0,
    }
    # Re-execute the exact sealed W4 producer-face binding. A caller-made
    # dict with copied "W4 verified" booleans is never a valid W4 issuer.
    w4_room_result=audit_gpt2_w4_bound_original_floor(
        independently_registered_rcp,canonical_rooms=canonical_rooms,
        physical_room_id=physical_room_id)
    if (w4_room_result.get("status")!="source_original_floor_W4_face_candidate_only"
            or not w4_room_result.get("w4_room_face_source_identity_proven")
            or not w4_room_result.get("source_w4_wall_ownership_authenticated")):
        return {**blocked,"first_failure":w4_room_result.get("first_failure",
            "original_W4_room_not_independently_authenticated")}
    if (type(independently_registered_rcp) is not dict or
            independently_registered_rcp.get("status")!=
                "original_source_ink_ring_translation_candidate"
            or not independently_registered_rcp.get("geometric_ink_correspondence_only")
            or type(original_rcp_ink) is not dict or
            original_rcp_ink.get("status")!=
                "original_rcp_source_ink_ceiling_polygon_candidate"
            or type(original_rcp_material) is not dict or
            original_rcp_material.get("status")!=
                "original_rcp_material_in_ceiling_ink_candidate"):
        return {**blocked,"first_failure":"independent_original_A120_geometry_material_issuer_missing"}
    sha=w4_room_result["original_source_sha256"]
    if (sha!=independently_registered_rcp.get("original_source_sha256")
            or sha!=original_rcp_ink.get("original_source_sha256")
            or sha!=original_rcp_material.get("original_source_sha256")
            or str(independently_registered_rcp.get("original_floor_page"))!=
               str(w4_room_result.get("original_floor_page"))
            or independently_registered_rcp.get("original_finish_page")!=
               original_rcp_ink.get("original_rcp_page")):
        return {**blocked,"first_failure":"A120_source_root_or_original_page_mismatch"}
    if (w4_room_result.get("original_revision_id")!=
            original_rcp_ink.get("original_revision_id")
            or original_rcp_ink.get("original_revision_id")!=
               original_rcp_material.get("original_revision_id")
            or w4_room_result.get("original_snapshot_id")!=
               original_rcp_ink.get("original_snapshot_id")
            or original_rcp_ink.get("original_snapshot_id")!=
               original_rcp_material.get("original_snapshot_id")):
        return {**blocked,"first_failure":"W4_A120_source_revision_snapshot_disagreement"}
    if (not original_rcp_material.get("original_source_finish_record_ids")
            or not original_rcp_material.get("original_material_definition_record_id")
            or not original_rcp_material.get("original_rcp_scope_ownership_id")):
        return {**blocked,"first_failure":"A120_original_issuers_or_mark_missing"}
    registered_floor=_valid_polygon(
        independently_registered_rcp.get("source_floor_perimeter_polygon_pdf_pts"))
    registered_rcp=_valid_polygon(
        independently_registered_rcp.get("source_finishes_perimeter_polygon_pdf_pts"))
    w4_floor=_valid_polygon(
        w4_room_result.get("original_source_floor_polygon_pdf_pts"))
    rcp=_valid_polygon(original_rcp_ink.get("source_ceiling_ink_polygon_pdf_pts"))
    if not all((registered_floor,registered_rcp,w4_floor,rcp)):
        return {**blocked,"first_failure":"A120_source_perimeter_invalid"}
    if (not registered_floor.equals(w4_floor)
            or not registered_rcp.equals(rcp)):
        return {**blocked,"first_failure":"A120_ceiling_area_cannot_borrow_floor_perimeter"}
    translation=independently_registered_rcp.get(
        "source_cross_sheet_translation_pdf_pts")
    if type(translation) not in (list,tuple) or len(translation)!=2:
        return {**blocked,"first_failure":"original_floor_to_A120_registration_unavailable"}
    try:
        dx,dy=(float(v) for v in translation)
    except (TypeError,ValueError,OverflowError):
        return {**blocked,"first_failure":"original_floor_to_A120_registration_unavailable"}
    if not math.isfinite(dx) or not math.isfinite(dy):
        return {**blocked,"first_failure":"original_floor_to_A120_registration_unavailable"}
    from shapely.affinity import translate
    if not translate(registered_floor,xoff=dx,yoff=dy).equals(rcp):
        return {**blocked,"first_failure":"original_floor_to_A120_registration_conflict"}
    return {
        **blocked,
        "status":"original_A120_RCP_material_on_W4_room_candidate_for_GPT1",
        "first_failure":"GPT1_real_source_RCP_metric_ceiling_surface_measurement",
        "original_source_sha256":sha,
        "original_document_id":w4_room_result["original_document_id"],
        "original_revision_id":w4_room_result["original_revision_id"],
        "original_snapshot_id":w4_room_result["original_snapshot_id"],
        "original_physical_room_id":w4_room_result["original_physical_room_id"],
        "original_source_room_face_record_id":
            w4_room_result["original_source_room_face_record_id"],
        "original_rcp_viewport_id":original_rcp_ink["original_rcp_viewport_id"],
        "original_rcp_page":original_rcp_ink["original_rcp_page"],
        "original_rcp_code":original_rcp_material["original_source_finish_code"],
        "original_ceiling_material_definition_record_id":
            original_rcp_material["original_material_definition_record_id"],
        "original_ceiling_source_mark_ids":
            original_rcp_material["original_source_finish_record_ids"],
        "original_rcp_source_polygon_pdf_pts":
            original_rcp_ink["source_ceiling_ink_polygon_pdf_pts"],
        "source_original_rcp_polygon_pdf_pt2_not_m2":
            original_rcp_ink["source_ceiling_polygon_area_pdf_pt2_not_m2"],
    }
