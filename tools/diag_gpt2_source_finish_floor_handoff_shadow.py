"""Source-owned floor/finish occurrence handoff, default-off and quantity-free.

Consumes only records issued by the existing material producer and exact
SHA-pinned native ink graph receipts. Geometry correspondence cannot replace
structural W4 ownership, official scale, source mark clip/glyph trust, or
physical ring closure. Never constructs commercial QuantityEvidence.
"""
from __future__ import annotations

from collections import defaultdict
import math

from shapely.geometry import Polygon, box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionSelector,
    SourceMaterialOccurrenceSelector,
    SourceMaterialSemanticAuthority,
)


def _single_ring(graph: dict):
    if type(graph) is not dict or graph.get("native_candidate_ring_count")!=1:
        return None
    comps=graph.get("native_components",())
    if len(comps)!=1 or graph.get("interior_stroke_intersections_and_overlaps"):
        return None
    ring=comps[0].get("source_simple_ring_candidate")
    if not ring or len(ring.get("vertices_pdf_pts",()))<4:
        return None
    return ring


def audit_gpt2_original_cross_sheet_ring_correspondence(
    floor_graph: dict, finish_graph: dict, *,
    original_source_registration: dict,
    translation_pdf_pts: tuple[float,float],
) -> dict:
    """Exact source-ink perimeter match, never elects a physical room owner."""
    base={"status":"source_floor_finish_ring_correspondence_abstained",
          "new_firm_quantities":0,"physical_room_identity_proven":False,
          "source_finished_face_verified":False}
    if type(floor_graph) is not dict or type(finish_graph) is not dict:
        return {**base,"first_failure":"source_graph_receipt_missing"}
    sha=floor_graph.get("source_sha256")
    if (not isinstance(sha,str) or not sha
            or sha!=finish_graph.get("source_sha256")):
        return {**base,"first_failure":"original_source_pdf_root_mismatch"}
    if (type(translation_pdf_pts) is not tuple or len(translation_pdf_pts)!=2
            or any(type(z) not in (int,float) or not math.isfinite(z)
                   for z in translation_pdf_pts)):
        return {**base,"first_failure":"original_registration_transform_invalid"}
    reg=original_source_registration
    if (type(reg) is not dict or reg.get("status") !=
            "original_four_edge_ink_correspondence_with_unclosed_doorway"
            or reg.get("original_source_sha256")!=sha
            or reg.get("original_floor_page_id")!=floor_graph.get("page_1_based")
            or reg.get("original_finish_page_id")!=finish_graph.get("page_1_based")
            or tuple(reg.get("source_translation_candidate_pdf_pts",()))!=
                tuple(translation_pdf_pts)):
        return {**base,"first_failure":"original_registration_issuer_or_scope_missing"}
    witnesses=reg.get("original_witnesses")
    if type(witnesses) is not dict or not witnesses:
        return {**base,"first_failure":"original_registration_witnesses_missing"}
    floor_ids=set(floor_graph.get("original_native_edge_ids",()))
    finish_ids=set(finish_graph.get("original_native_edge_ids",()))
    if any(
        role.get("floor_source",{}).get("identity") not in floor_ids
        or role.get("finish_source",{}).get("identity") not in finish_ids
        for role in witnesses.values()
    ):
        return {**base,"first_failure":"unjoined_source_wall_ancestry"}
    floor_ring=_single_ring(floor_graph)
    finish_ring=_single_ring(finish_graph)
    if not floor_ring or not finish_ring:
        return {**base,"first_failure":"physical_floor_or_finish_source_ring_open"}
    dx,dy=translation_pdf_pts
    transferred={(round(x+dx,3),round(y+dy,3))
                 for x,y in floor_ring["vertices_pdf_pts"]}
    received={tuple(v) for v in finish_ring["vertices_pdf_pts"]}
    if transferred != received or len(transferred)!=len(received):
        return {**base,"first_failure":"competing_cross_sheet_original_perimeter"}
    # Vertex equality alone is insufficient: source perimeter must have the
    # same number of actual independently issued original source side edges.
    if len(floor_ring["source_edge_ids"])!=len(finish_ring["source_edge_ids"]):
        return {**base,"first_failure":"original_cross_sheet_edge_membership_count_conflict"}
    return {
        **base,
        "status":"original_source_ink_ring_translation_candidate",
        "first_failure":"W4_structural_wall_and_physical_room_identity",
        "original_source_sha256":sha,
        "original_floor_page":floor_graph["page_1_based"],
        "original_finish_page":finish_graph["page_1_based"],
        "source_cross_sheet_translation_pdf_pts":[dx,dy],
        "original_floor_source_ids":tuple(sorted(floor_ids)),
        "original_finish_source_ids":tuple(sorted(finish_ids)),
        "source_finishes_perimeter_polygon_pdf_pts":
            finish_ring["vertices_pdf_pts"],
        "geometric_ink_correspondence_only":True,
    }


def audit_gpt2_source_material_floor_handoff(
    source_registration: dict, *,
    material_authority: SourceMaterialSemanticAuthority,
    definition_selector: SourceMaterialDefinitionSelector,
    occurrence_selector: SourceMaterialOccurrenceSelector,
    original_finish_code: str,
) -> dict:
    """Bridge producer-authenticated source material to source-only geometry.

    No proximity or page-title inference; mark must be the ONLY source-owned
    occurrence from its original eligible viewport within a complete ring.
    Even a positive handoff is unscored and not an area measurement.
    """
    result={
        "status":"source_finished_floor_material_handoff_abstained",
        "first_failure":"upstream_source_identity_unavailable",
        "original_mark_source_record_ids":(),
        "structural_room_issuer_granted":False,
        "canonical_floor_finish_quantity_granted":False,
        "new_firm_quantities":0,
    }
    if type(material_authority) is not SourceMaterialSemanticAuthority:
        return {**result,"first_failure":"producer_owned_material_authority_required"}
    if (type(definition_selector) is not SourceMaterialDefinitionSelector
            or type(occurrence_selector) is not SourceMaterialOccurrenceSelector):
        return {**result,"first_failure":"producer_owned_material_selectors_required"}
    if (type(original_finish_code) is not str or
            not original_finish_code or original_finish_code.strip()!=original_finish_code):
        return {**result,"first_failure":"original_finish_code_invalid"}
    if type(source_registration) is not dict:
        return {**result,"first_failure":"source_cross_sheet_registration_missing"}
    root=source_registration.get("original_source_sha256")
    if (source_registration.get("status")!="original_source_ink_ring_translation_candidate"
            or root!=definition_selector.source_sha256
            or root!=occurrence_selector.source_sha256
            or definition_selector.revision_id!=occurrence_selector.revision_id
            or definition_selector.snapshot_id!=occurrence_selector.snapshot_id
            or definition_selector.document_id!=occurrence_selector.document_id
            or occurrence_selector.page_id!=str(source_registration.get("original_finish_page"))
            or definition_selector.code.upper()!=original_finish_code.upper()):
        return {**result,"first_failure":"material_graph_revision_page_scope_or_code_conflict"}
    definition=material_authority.resolve_definition(definition_selector)
    if definition.status is not EvidenceResolutionStatus.CORROBORATED or definition.record is None:
        return {**result,"first_failure":"original_finish_definition_not_authenticated"}
    record=definition.record
    if (record.code.upper()!=original_finish_code.upper()
            or record.source_sha256!=root or
            record.revision_id!=definition_selector.revision_id or
            record.snapshot_id!=definition_selector.snapshot_id or
            record.document_id!=definition_selector.document_id):
        return {**result,"first_failure":"original_material_definition_root_conflict"}
    scope=material_authority.resolve_occurrences(occurrence_selector)
    if (scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not scope.scope_complete or
            not scope.source_viewport_ownership_id or
            scope.unresolved_source_text_observation_ids):
        return {**result,"first_failure":"original_finish_occurrence_scope_incomplete"}
    polygon=Polygon(source_registration["source_finishes_perimeter_polygon_pdf_pts"])
    if not polygon.is_valid or polygon.area<=0:
        return {**result,"first_failure":"original_finish_ink_polygon_invalid"}
    inside=[];all_matching=[]
    for occurrence in scope.records:
        if occurrence.code.upper()!=original_finish_code.upper():
            continue
        all_matching.append(occurrence)
        if (occurrence.definition_record_id!=record.record_id
                or occurrence.document_id!=occurrence_selector.document_id
                or occurrence.revision_id!=occurrence_selector.revision_id
                or occurrence.snapshot_id!=occurrence_selector.snapshot_id
                or occurrence.source_sha256!=root
                or occurrence.page_id!=occurrence_selector.page_id
                or occurrence.viewport_id!=occurrence_selector.viewport_id):
            return {**result,"first_failure":"material_occurrence_definition_or_source_root_conflict"}
        if (not occurrence.source_text_observation_ids
                or len(set(occurrence.source_text_observation_ids))!=
                    len(occurrence.source_text_observation_ids)):
            return {**result,"first_failure":"original_material_mark_text_lineage_incomplete"}
        try:
            boundary=box(*occurrence.bbox_pdf_pts)
        except (TypeError,ValueError,OverflowError):
            return {**result,"first_failure":"original_material_mark_geometry_invalid"}
        if polygon.contains(boundary):
            inside.append(occurrence)
    if len(inside)!=1:
        return {**result,"first_failure":"original_finish_mark_missing_or_competing"}
    matched=inside[0]
    return {
        **result,"status":"source_owned_material_on_original_ink_ring_candidate",
        "first_failure":"W4_physical_finished_face_and_metric_area",
        "original_source_sha256":root,
        "original_document_id":occurrence_selector.document_id,
        "original_revision_id":occurrence_selector.revision_id,
        "original_snapshot_id":occurrence_selector.snapshot_id,
        "original_floor_page":source_registration["original_floor_page"],
        "original_finish_page":source_registration["original_finish_page"],
        "original_finish_viewport_id":occurrence_selector.viewport_id,
        "original_finish_code":original_finish_code,
        "original_material_definition_id":record.record_id,
        "original_source_scope_ownership_id":scope.source_viewport_ownership_id,
        "original_mark_source_record_ids":(matched.record_id,),
        "original_mark_text_observation_ids":matched.source_text_observation_ids,
        "all_same_code_source_occurrence_record_ids":
            tuple(sorted(x.record_id for x in all_matching)),
    }


def audit_gpt2_competing_source_floor_handoffs(
    candidates: tuple[dict, ...],
) -> dict:
    """Do not assign a single printed source finish mark to multiple rooms."""
    if type(candidates) is not tuple or not candidates or len(candidates)>64:
        raise ValueError("bounded_original_source_room_handoffs_required")
    by_mark=defaultdict(list)
    for i,candidate in enumerate(candidates):
        if type(candidate) is not dict:
            raise ValueError("original_room_handoff_receipt_required")
        if candidate.get("status")=="source_owned_material_on_original_ink_ring_candidate":
            for source_id in candidate.get("original_mark_source_record_ids",()):
                if type(source_id) is not str or not source_id:
                    raise ValueError("original_material_mark_identity_required")
                by_mark[(candidate.get("original_source_sha256"),
                         candidate.get("original_revision_id"),
                         candidate.get("original_snapshot_id"),
                         source_id)].append(i)
    conflicts=tuple(
        {"source_original_mark_key":list(k),
         "competing_candidate_indexes":list(by_mark[k])}
        for k in sorted(by_mark) if len(by_mark[k])>1
    )
    return {
        "status":("original_finish_mark_competing_physical_rooms" if conflicts
                  else "original_source_floor_handoff_candidates_only"),
        "all_source_floor_candidates":candidates,
        "original_mark_ownership_conflicts":conflicts,
        "unique_source_mark_identity_elected":False,
        "new_firm_quantities":0,
    }
