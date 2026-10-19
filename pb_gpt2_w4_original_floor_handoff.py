"""GPT2 → W4 source-room-face binding, read-only and quantity-free.

A PDF stroke graph is not a W4 wall or room. This adapter does not accept
caller-supplied truth flags: it replays the exact room-face authority retained
inside the producer-issued LiveCanonicalRoomComposition. Only a uniquely
published face with proven wall edge ownership and an exactly identical
source-floor polygon can become a measurement handoff CANDIDATE.

This adapter never signs quantities, invents scale, or promotes a finish mark.
"""
from __future__ import annotations

from collections import Counter
import math
from shapely.geometry import Polygon

from pb_migration_contracts import EvidenceResolutionStatus
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition, LiveCanonicalRoomObject,
)
from pb_source_room_face_authority import (
    SourceRoomFaceRecord, SourceRoomFaceSelector,
    OWNERSHIP_EVALUATION_EVALUATED,
)


def _polygon(value):
    if type(value) not in (tuple,list) or len(value)<3:
        return None
    try:
        coords=tuple((float(p[0]),float(p[1])) for p in value)
    except (TypeError,IndexError,ValueError,OverflowError):
        return None
    if (len(set(coords))<3 or not all(
            math.isfinite(x) and math.isfinite(y) for x,y in coords)):
        return None
    try:
        polygon=Polygon(coords)
        return polygon if polygon.is_valid and polygon.area>0 else None
    except (TypeError,ValueError,OverflowError):
        return None


def audit_gpt2_w4_bound_original_floor(
    source_correspondence: dict, *,
    canonical_rooms: LiveCanonicalRoomComposition,
    physical_room_id: str,
) -> dict:
    """Join exact original p7 ink to a **sealed** W4 published room-face record.

    The W4 owner alone is allowed to establish source room identity. A positive
    result only proves that the *candidate PDF path* describes that already
    published face. It cannot establish metric length, source material finish,
    wall thickness, ceiling zone, room rate, customer or benchmark quantity.
    """
    blocked={
        "status":"original_source_w4_room_binding_abstained",
        "first_failure":"canonical_source_room_authority_unavailable",
        "w4_room_face_source_identity_proven":False,
        "source_w4_wall_ownership_authenticated":False,
        "source_room_metric_area_issued":False,
        "floor_finish_quantity_issued":False,
        "new_firm_quantities":0,
    }
    if (type(canonical_rooms) is not LiveCanonicalRoomComposition
            or type(physical_room_id) is not str or not physical_room_id
            or physical_room_id!=physical_room_id.strip()):
        return blocked
    match=[room for room in canonical_rooms.rooms
           if type(room) is LiveCanonicalRoomObject
           and room.physical_room_id==physical_room_id]
    if len(match)!=1:
        return {**blocked,"first_failure":"original_physical_room_missing_or_duplicate"}
    room=match[0]
    if (type(source_correspondence) is not dict
            or source_correspondence.get("status")!=
                "original_source_ink_ring_translation_candidate"
            or not source_correspondence.get("geometric_ink_correspondence_only")
            or not isinstance(source_correspondence.get("original_floor_page"),int)
            or source_correspondence.get("original_source_sha256")!=room.source_sha256
            or str(source_correspondence["original_floor_page"])!=room.page_id):
        return {**blocked,"first_failure":"original_pdf_room_root_or_page_mismatch"}
    source_floor=_polygon(
        source_correspondence.get("source_floor_perimeter_polygon_pdf_pts"))
    existing_face=_polygon(room.polygon_pdf_pts)
    if (source_floor is None or existing_face is None
            or not existing_face.equals(source_floor)
            or abs(existing_face.area-room.area_page_pts2)>1e-6):
        return {**blocked,"first_failure":"source_floor_ink_vs_W4_face_geometry_conflict"}
    if (not room.geometry_complete or not room.wall_relationships_complete
            or room.coordinate_unit!="pdf_pt"
            or not room.source_room_face_record_id
            or not room.decision_scope_id
            or not room.snapshot_id
            or not room.bounding_wall_ids
            or len(set(room.bounding_wall_ids))!=len(room.bounding_wall_ids)
            or not room.canonical_bounding_wall_ids):
        return {**blocked,"first_failure":"published_W4_room_wall_binding_incomplete"}

    binding=canonical_rooms.room_face_authority_binding_for(room)
    if binding is None:
        return {**blocked,"first_failure":"sealed_W4_room_face_issuer_missing"}
    selector=SourceRoomFaceSelector(
        document_id=room.document_id,
        revision_id=room.revision_id,
        source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id,
        page_id=room.page_id,
        decision_scope_id=room.decision_scope_id,
    )
    scope=binding.authority.resolve_scope(selector)
    if (scope.status is not EvidenceResolutionStatus.CORROBORATED
            or scope.source_sha256!=room.source_sha256
            or scope.revision_id!=room.revision_id
            or scope.snapshot_id!=room.snapshot_id
            or scope.decision_scope_id!=room.decision_scope_id):
        return {**blocked,"first_failure":"sealed_W4_room_face_scope_not_correlated"}
    rows=[record for record in scope.records
          if type(record) is SourceRoomFaceRecord
          and record.record_id==room.source_room_face_record_id]
    if len(rows)!=1:
        return {**blocked,"first_failure":"W4_room_face_record_missing_or_competing"}
    record=rows[0]
    record_polygon=_polygon(record.polygon_pdf_pts)
    if (record_polygon is None or not existing_face.equals(record_polygon)
            or record.source_sha256!=room.source_sha256
            or record.snapshot_id!=room.snapshot_id
            or record.page_id!=room.page_id
            or record.decision_scope_id!=room.decision_scope_id
            or set(record.bounding_wall_ids)!=set(room.bounding_wall_ids)):
        return {**blocked,"first_failure":"W4_published_face_polygon_or_ancestry_conflict"}
    if (not scope.scope_complete
            and not (scope.ownership_evaluation.status==
                     OWNERSHIP_EVALUATION_EVALUATED
                     and scope.ownership_evaluation.is_face_ownership_clean(
                         record.face_id))):
        return {**blocked,"first_failure":"W4_room_face_local_contamination_unresolved"}
    edge_owners=record.boundary_wall_edges
    if (not edge_owners
            or any(type(owner) is not str or owner not in record.bounding_wall_ids
                   or type(edge) not in (tuple,list) or len(edge)!=2
                   for owner,edge in edge_owners)):
        return {**blocked,"first_failure":"W4_face_boundary_wall_owner_receipts_missing"}
    # Every W4-published wall must actually own source boundary edges.
    counts=Counter(owner for owner,_ in edge_owners)
    if set(counts)!=set(record.bounding_wall_ids):
        return {**blocked,"first_failure":"W4_bounding_wall_not_present_on_source_face"}
    return {
        **blocked,
        "status":"source_original_floor_W4_face_candidate_only",
        "first_failure":"independent_metric_measurement_and_finish_occurrence",
        "w4_room_face_source_identity_proven":True,
        "source_w4_wall_ownership_authenticated":True,
        "original_document_id":room.document_id,
        "original_source_sha256":room.source_sha256,
        "original_revision_id":room.revision_id,
        "original_snapshot_id":room.snapshot_id,
        "original_floor_page":room.page_id,
        "original_viewport_id":room.viewport_id,
        "original_decision_scope_id":room.decision_scope_id,
        "original_canonical_room_id":room.canonical_room_id,
        "original_physical_room_id":room.physical_room_id,
        "original_source_room_face_record_id":record.record_id,
        "original_source_w4_wall_ids":tuple(sorted(record.bounding_wall_ids)),
        "original_source_floor_polygon_pdf_pts":room.polygon_pdf_pts,
        "source_native_area_pdf_pt2_not_m2":record.area_page_pts2,
    }


def audit_gpt2_w4_material_to_gpt1(
    w4_result: dict, material_result: dict, *,
    source_room_area_quantity=None,
) -> dict:
    """Source-qualified handoff to GPT1, never reissues signed m2.

    The optional quantity is an ALREADY-ISSUED producer quantity, not an
    input for calculating area; this module deliberately does not parse it
    into its own physical floor finish m2. GPT1's existing authority must
    perform independent measurement and seal.
    """
    base={
        "status":"gpt2_source_to_gpt1_handoff_abstained",
        "first_failure":"W4_room_or_original_FT_occurrence_not_authenticated",
        "new_firm_quantities":0,
        "source_finish_area_quantity_issued":False,
    }
    if (type(w4_result) is not dict
            or w4_result.get("status")!="source_original_floor_W4_face_candidate_only"
            or not w4_result.get("w4_room_face_source_identity_proven")
            or type(material_result) is not dict
            or material_result.get("status")!=
                "source_owned_material_on_original_ink_ring_candidate"):
        return base
    for field in ("original_source_sha256",):
        if w4_result.get(field)!=material_result.get(field):
            return {**base,"first_failure":"source_finish_W4_pdf_root_conflict"}
    for owner_key,mark_key in (
        ("original_revision_id","original_revision_id"),
        ("original_snapshot_id","original_snapshot_id"),
        ("original_document_id","original_document_id"),
    ):
        if w4_result.get(owner_key)!=material_result.get(mark_key):
            return {**base,"first_failure":"source_finish_W4_issuer_lineage_conflict"}
    # Same PDF/revision is not same physical room. Only the very floor
    # polygon enclosing the producer-issued material mark can be passed to
    # W4; never associate a mark with another room by label or same SHA.
    w4_floor=_polygon(w4_result.get("original_source_floor_polygon_pdf_pts"))
    marked_floor=_polygon(
        material_result.get("original_source_floor_perimeter_polygon_pdf_pts"))
    marked_finish=_polygon(
        material_result.get("original_source_finish_perimeter_polygon_pdf_pts"))
    def source_page(value):
        if type(value) is int and value>0:
            return value
        if (type(value) is str and value.isdecimal()
                and value==str(int(value)) and int(value)>0):
            return int(value)
        return None
    floor_page=source_page(material_result.get("original_floor_page"))
    finish_page=source_page(material_result.get("original_finish_page"))
    w4_page=source_page(w4_result.get("original_floor_page"))
    if (w4_floor is None or marked_floor is None or marked_finish is None
            or not w4_floor.equals(marked_floor)
            or floor_page is None or finish_page is None or w4_page is None
            or floor_page!=w4_page or finish_page==floor_page):
        return {**base,
            "first_failure":"original_finish_mark_and_W4_physical_floor_mismatch"}
    def exact_original_ids(value, *, nonempty=True):
        return (
            type(value) in (tuple, list)
            and (not nonempty or bool(value))
            and all(type(v) is str and bool(v) and v == v.strip() for v in value)
            and len(set(value)) == len(value)
        )

    mark_ids = material_result.get("original_mark_source_record_ids")
    mark_text_ids = material_result.get("original_mark_text_observation_ids")
    competing_ids = material_result.get(
        "all_same_code_source_occurrence_record_ids"
    )
    # Original source occurrence IDs are NOT interchangeable with word/text
    # observations. A candidate without its source text and all competing
    # occurrence IDs may not be called ready for GPT1 to measure.
    if (not all(
                type(material_result.get(field)) is str
                and bool(material_result[field])
                and material_result[field] == material_result[field].strip()
                for field in (
                    "original_source_scope_ownership_id",
                    "original_finish_viewport_id",
                    "original_material_definition_id",
                    "original_finish_code",
                ))
            or not exact_original_ids(mark_ids)
            or len(mark_ids) != 1
            or not exact_original_ids(mark_text_ids)
            or not exact_original_ids(competing_ids)
            or mark_ids[0] not in competing_ids):
        return {**base,
            "first_failure":"original_finish_scope_or_unique_source_mark_unproven"}
    # An independently source-owned open doorway is represented as an ink
    # gap, not as a structural wall or a measured finish threshold.
    def native_gap(value):
        if type(value) not in (tuple, list) or len(value) != 2:
            return None
        coords = []
        for point in value:
            if (type(point) not in (tuple, list) or len(point) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v)
                           for v in point)):
                return None
            coords.append((round(float(point[0]), 3),
                           round(float(point[1]), 3)))
        if coords[0] == coords[1]:
            return None
        return tuple(coords)

    def boundary_edges(polygon):
        raw = tuple(polygon.exterior.coords)[:-1]
        vertices = tuple(
            (round(float(x), 3), round(float(y), 3)) for x, y in raw
        )
        return {
            frozenset((vertices[i], vertices[(i + 1) % len(vertices)]))
            for i in range(len(vertices))
        }

    has_door_gap = material_result.get(
        "source_original_doorway_ink_gap_candidate_only") is True
    floor_gap = finish_gap = None
    if has_door_gap:
        floor_gap = native_gap(
            material_result.get("source_original_floor_door_ink_gap_pdf_pts")
        )
        finish_gap = native_gap(
            material_result.get("source_original_finish_door_ink_gap_pdf_pts")
        )
        shift = material_result.get(
            "source_original_cross_sheet_translation_pdf_pts"
        )
        if (floor_gap is None or finish_gap is None
                or type(shift) not in (tuple, list) or len(shift) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in shift)):
            return {**base,
                "first_failure":"source_original_door_gap_receipt_invalid"}
        shifted = frozenset(
            (round(x + shift[0], 3), round(y + shift[1], 3))
            for x, y in floor_gap
        )
        if (frozenset(floor_gap) not in boundary_edges(w4_floor)
                or frozenset(finish_gap) not in boundary_edges(marked_finish)
                or shifted != frozenset(finish_gap)):
            return {**base,
                "first_failure":"source_original_door_gap_vs_W4_floor_conflict"}
    # Source gap remains a CANDIDATE for GPT1 independent threshold/wall work.
    # A caller's numerically populated room area is deliberately not
    # converted to finish m2. The existing GPT1/GPT3 verifier controls that.
    return {
        **base,
        "status":"gpt2_W4_source_finished_floor_ready_for_GPT1_measurement",
        "first_failure":"GPT1_independent_metric_room_area_and_finish_trade_seal",
        "source_document_id":w4_result["original_document_id"],
        "source_revision_id":w4_result["original_revision_id"],
        "source_snapshot_id":w4_result["original_snapshot_id"],
        "source_sha256":w4_result["original_source_sha256"],
        "physical_room_id":w4_result["original_physical_room_id"],
        "canonical_room_id":w4_result["original_canonical_room_id"],
        "source_room_face_record_id":w4_result["original_source_room_face_record_id"],
        "source_w4_wall_ids":w4_result["original_source_w4_wall_ids"],
        "original_ft_material_definition_id":
            material_result["original_material_definition_id"],
        "original_finish_code":material_result["original_finish_code"],
        # FT2 tile is laid on the EXPOSED floor, never under a wall.
        # Whether the A502 3570/2200 dimension terminals actually land
        # on these W4 finished faces is separately unproved here; do not
        # assert the 92mm strokes fall outside the validated W4 ring.
        # Every laid floor covering is measured to the INSIDE FINISHED
        # wall faces and ends at its source-owned doorway/finish threshold.
        # This is a measurement rule, not evidence that the actual finished
        # wall offsets or threshold positions have yet been authenticated.
        "floor_finish_measurement_boundary_basis":
            "inside_finished_wall_faces",
        "all_floor_finishes_exclude_wall_footprint":True,
        "floor_finish_doorway_transition_boundary_required":True,
        "original_finished_wall_face_boundary_authenticated":False,
        "original_doorway_finish_transition_boundary_authenticated":False,
        "FT2_exclude_wall_footprint":material_result["original_finish_code"]=="FT2",
        "FT3_exclude_wall_footprint":material_result["original_finish_code"]=="FT3",
        "FT2_92mm_wall_widths_already_outside_clear_figures":None,
        "original_dimension_terminal_to_finished_W4_face_proven":False,
        "original_D13_threshold_finish_area_verified":False,
        "source_original_doorway_ink_gap_w4_candidate_only":has_door_gap,
        "source_original_floor_door_ink_gap_pdf_pts":floor_gap,
        "source_original_finish_door_ink_gap_pdf_pts":finish_gap,
        "source_original_doorway_gap_is_structural_wall":False,
        "source_original_doorway_gap_is_finished_threshold":False,
        "source_finish_mark_record_ids": tuple(mark_ids),
        "source_finish_native_text_observation_ids": tuple(mark_text_ids),
        "source_all_competing_same_code_occurrence_record_ids":
            tuple(competing_ids),
        "source_finish_selected_mark_is_unique_in_reported_universe":True,
        "source_original_floor_page":w4_result["original_floor_page"],
        "source_original_finish_page":material_result["original_finish_page"],
        "source_metric_room_area_not_minted_here":True,
        "source_metric_room_area_quantity_provided":source_room_area_quantity is not None,
        "source_quantity_sealing_authority_granted":False,
    }
