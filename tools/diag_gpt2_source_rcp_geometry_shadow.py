"""Original-source A120 RCP boundary and grid ink shadow.

The source plan viewport comes only from an existing F07 source producer.
Native source lines produce a ceiling OUTLINE CANDIDATE, not square metres.
Regular grid spacing is drafting evidence, not grid-ceiling material proof.
"""
from __future__ import annotations
import math

from shapely.geometry import Polygon, box

from pb_cross_view_ceiling_finish_authority import (
    _rcp_viewports, _source_bytes, _definition_is_ceiling_finish,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionSelector,
    SourceMaterialOccurrenceSelector,
    SourceMaterialSemanticAuthority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gpt2_source_room_graph_shadow import audit_original_room_edge_graph
from tools.diag_original_room_four_edge_source_ink_shadow import _line


def _grid_source_ink_in_frame(page, original_ids: tuple[str,...], boundary):
    """Source-native GRID candidate without a claim of construction spacing."""
    if type(original_ids) is not tuple or len(original_ids)>20000 or len(set(original_ids))!=len(original_ids):
        raise ValueError("bounded_unique_original_rcp_grid_members_required")
    x0,y0,x1,y1=boundary
    rows=[]
    originals=page.get_drawings()
    for ident in original_ids:
        record=_line(originals,ident)
        a,b=record["ends"]
        if not (x0<=a[0]<=x1 and x0<=b[0]<=x1 and
                y0<=a[1]<=y1 and y0<=b[1]<=y1):
            raise ValueError("original_rcp_grid_source_outside_viewport")
        axis=("source_grid_vertical_candidate" if a[0]==b[0]
              else "source_grid_horizontal_candidate" if a[1]==b[1]
              else "source_grid_diagonal_unclassified")
        rows.append({"native_source_id":ident,
                     "original_source_axis":axis,
                     "source_ink":record,
                     "actual_grid_material_and_spacing_authenticated":False})
    return tuple(rows)


def _native_grid_spacing_candidates(rows):
    """Original PDF-point differences only; no invented ceiling tile size."""
    groups={"source_grid_horizontal_candidate":set(),
            "source_grid_vertical_candidate":set()}
    for row in rows:
        axis=row["original_source_axis"]
        if axis in groups:
            first=row["source_ink"]["ends"][0]
            groups[axis].add(first[1] if "horizontal" in axis else first[0])
    answers={}
    for axis,ordinates in groups.items():
        values=sorted(ordinates)
        gaps=tuple(round(b-a,3) for a,b in zip(values,values[1:]))
        regular=(len(values)>=3 and bool(gaps) and
                 len(set(gaps))==1 and gaps[0]>0)
        answers[axis]={
            "source_original_ordinates_pdf_pts":tuple(values),
            "source_spacing_intervals_pdf_pts":gaps,
            "source_repeating_grid_spacing_candidate":regular,
            "source_metric_spacing_or_material_issued":False,
        }
    return answers


def audit_original_rcp_ceiling_ink(
    source: SourceVisibilityProducer, *, revision_id: str,
    original_rcp_page: int, original_rcp_viewport_id: str,
    boundary_source_ids: tuple[str,...],
    grid_source_ids: tuple[str,...]=(),
)->dict:
    """F07-issued RCP viewport + full actual-source boundary graph.

    Do not infer an internal ceiling finish or cut floor area from schedule
    rows, repeated GRID strokes, nested legends or a viewport frame.
    """
    blocked={"status":"original_rcp_source_unavailable",
             "first_failure":"RCP_source_viewport_or_geometry_missing",
             "original_ceiling_areas_m2":None,
             "source_grid_material_issued":False,
             "source_physical_room_binding_issued":False,
             "new_firm_quantities":0}
    if (type(source) is not SourceVisibilityProducer
            or type(revision_id) is not str or not revision_id
            or type(original_rcp_page) is not int or original_rcp_page<1
            or type(original_rcp_viewport_id) is not str
            or not original_rcp_viewport_id):
        return {**blocked,"first_failure":"original_rcp_source_selector_invalid"}
    published=source.published_snapshot_for_revision(revision_id)
    raw=_source_bytes(source,revision_id)
    if published is None or raw is None:
        return {**blocked,"first_failure":"source_revision_or_private_pdf_unavailable"}
    frame=_rcp_viewports(source,revision_id=revision_id).get(
        (str(original_rcp_page),original_rcp_viewport_id))
    if frame is None:
        return {**blocked,"first_failure":"original_F07_rcp_viewport_not_authenticated"}
    if (type(boundary_source_ids) is not tuple
            or not boundary_source_ids
            or set(boundary_source_ids)&set(grid_source_ids)):
        return {**blocked,"first_failure":"distinct_boundary_and_grid_ancestors_required"}
    try:
        graph=audit_original_room_edge_graph(
            raw,source_sha256=published.revision.source_sha256,
            page_1_based=original_rcp_page,source_edge_ids=boundary_source_ids)
    except ValueError as exc:
        return {**blocked,"first_failure":str(exc)}
    inside=graph["native_components"]
    if (len(inside)!=1 or graph["native_candidate_ring_count"]!=1
            or graph["interior_stroke_intersections_and_overlaps"]):
        return {**blocked,"first_failure":"original_rcp_physical_ceiling_outline_unclosed",
                "source_boundary_graph":graph}
    ring=inside[0]["source_simple_ring_candidate"]
    polygon=Polygon(ring["vertices_pdf_pts"])
    if (not polygon.is_valid or polygon.area<=0
            or any(not (frame[0]<=x<=frame[2] and frame[1]<=y<=frame[3])
                   for x,y in ring["vertices_pdf_pts"])):
        return {**blocked,"first_failure":"source_ceiling_outline_outside_rcp_scope",
                "source_boundary_graph":graph}
    import fitz
    with fitz.open(stream=raw,filetype="pdf") as pdf:
        page=pdf[original_rcp_page-1]
        try:
            rows=_grid_source_ink_in_frame(page,grid_source_ids,frame)
        except ValueError as exc:
            return {**blocked,"first_failure":str(exc),
                    "source_boundary_graph":graph}
    return {
        **blocked,
        "status":"original_rcp_source_ink_ceiling_polygon_candidate",
        "first_failure":"W4_structural_ceiling_boundary_and_room_identity",
        "original_document_id":published.revision.document_id,
        "original_revision_id":revision_id,
        "original_snapshot_id":published.snapshot.snapshot_id,
        "original_source_sha256":published.revision.source_sha256,
        "original_rcp_page":original_rcp_page,
        "original_rcp_viewport_id":original_rcp_viewport_id,
        "original_rcp_viewport_bbox_pdf_pts":frame,
        "source_boundary_graph":graph,
        "source_ceiling_ink_polygon_pdf_pts":ring["vertices_pdf_pts"],
        "source_ceiling_polygon_area_pdf_pt2_not_m2":ring["native_area_pdf_pt2"],
        "original_grid_source_ink_candidates":rows,
        "original_grid_spacing_candidates_pdf_pts":
            _native_grid_spacing_candidates(rows),
        "source_ceiling_material_occurrence_issued":False,
    }


def audit_original_rcp_source_finish_occurrence(
    rcp_candidate: dict, *,
    authority: SourceMaterialSemanticAuthority,
    definition_selector: SourceMaterialDefinitionSelector,
    occurrence_selector: SourceMaterialOccurrenceSelector,
    original_finish_code: str,
) -> dict:
    """Read producer-issued material occurrence, never geometrically guess it."""
    base={"status":"rcp_finish_occurrence_source_unresolved",
          "first_failure":"source_rcp_polygon_or_original_material_missing",
          "original_source_finish_record_ids":(),
          "source_ceiling_metric_area_issued":False,
          "new_firm_quantities":0}
    if (type(rcp_candidate) is not dict or
            rcp_candidate.get("status")!="original_rcp_source_ink_ceiling_polygon_candidate"):
        return base
    if (type(authority) is not SourceMaterialSemanticAuthority or
            type(definition_selector) is not SourceMaterialDefinitionSelector or
            type(occurrence_selector) is not SourceMaterialOccurrenceSelector or
            type(original_finish_code) is not str or not original_finish_code):
        return {**base,"first_failure":"source_material_issuer_missing"}
    root=rcp_candidate["original_source_sha256"]
    if (definition_selector.source_sha256!=root
            or occurrence_selector.source_sha256!=root
            or definition_selector.document_id!=occurrence_selector.document_id
            or definition_selector.revision_id!=occurrence_selector.revision_id
            or definition_selector.snapshot_id!=occurrence_selector.snapshot_id
            or definition_selector.revision_id!=rcp_candidate["original_revision_id"]
            or definition_selector.snapshot_id!=rcp_candidate["original_snapshot_id"]
            or occurrence_selector.page_id!=str(rcp_candidate["original_rcp_page"])
            or occurrence_selector.viewport_id!=rcp_candidate["original_rcp_viewport_id"]
            or definition_selector.code.upper()!=original_finish_code.upper()):
        return {**base,"first_failure":"original_rcp_source_material_lineage_conflict"}
    definition=authority.resolve_definition(definition_selector)
    if (definition.status is not EvidenceResolutionStatus.CORROBORATED
            or definition.record is None
            or not _definition_is_ceiling_finish(definition.record)):
        return {**base,"first_failure":"original_ceiling_material_schedule_unsupported"}
    scope=authority.resolve_occurrences(occurrence_selector)
    if (scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not scope.scope_complete or not scope.source_viewport_ownership_id
            or scope.unresolved_source_text_observation_ids):
        return {**base,"first_failure":"original_rcp_occurrence_scope_incomplete"}
    polygon=Polygon(rcp_candidate["source_ceiling_ink_polygon_pdf_pts"])
    inside=[]
    for occ in scope.records:
        if occ.code.upper()!=original_finish_code.upper():
            continue
        if (occ.definition_record_id!=definition.record.record_id
                or occ.revision_id!=occurrence_selector.revision_id
                or occ.snapshot_id!=occurrence_selector.snapshot_id
                or occ.source_sha256!=root
                or occ.page_id!=occurrence_selector.page_id
                or occ.viewport_id!=occurrence_selector.viewport_id
                or not occ.source_text_observation_ids):
            return {**base,"first_failure":"source_rcp_mark_ancestry_conflict"}
        if polygon.contains(box(*occ.bbox_pdf_pts)):
            inside.append(occ)
    if len(inside)!=1:
        return {**base,"first_failure":"original_rcp_finish_mark_missing_or_competing"}
    return {
        **base,
        "status":"original_rcp_material_in_ceiling_ink_candidate",
        "first_failure":"physical_ceiling_room_binding_and_metric_measurement",
        "original_source_finish_record_ids":(inside[0].record_id,),
        "original_source_finish_code":original_finish_code,
        "original_material_definition_record_id":definition.record.record_id,
        "original_rcp_scope_ownership_id":scope.source_viewport_ownership_id,
        "source_ceiling_ink_polygon_pdf_pts":
            rcp_candidate["source_ceiling_ink_polygon_pdf_pts"],
        "original_source_sha256":root,
        "original_revision_id":rcp_candidate["original_revision_id"],
        "original_snapshot_id":rcp_candidate["original_snapshot_id"],
    }


def audit_original_rcp_grid_ink_intersections(
    rcp_candidate: dict,
)->dict:
    """Actual source-line grid crossings, not inferred tile size or m².

    Only independently present horizontal and vertical source segments can
    make a crossing. Do not extend any line to the room edge, infer missing
    grid rows, or treat an axis title as a physical grid segment.
    """
    base={"status":"original_rcp_grid_crossings_unavailable",
          "original_source_grid_intersections_pdf_pts":(),
          "source_grid_cell_metric_size_issued":False,
          "source_ceiling_area_or_grid_quantity_issued":False,
          "new_firm_quantities":0}
    if (type(rcp_candidate) is not dict or
            rcp_candidate.get("status")!="original_rcp_source_ink_ceiling_polygon_candidate"):
        return base
    ink=rcp_candidate.get("original_grid_source_ink_candidates",())
    if not isinstance(ink,(tuple,list)):
        return base
    vertical=[e for e in ink if
              e["original_source_axis"]=="source_grid_vertical_candidate"]
    horizontal=[e for e in ink if
                e["original_source_axis"]=="source_grid_horizontal_candidate"]
    polygon=Polygon(rcp_candidate["source_ceiling_ink_polygon_pdf_pts"])
    from shapely.geometry import Point
    hits=set()
    for v in vertical:
        (vx,va),(vxx,vb)=v["source_ink"]["ends"]
        for h in horizontal:
            (ha,hy),(hb,hyy)=h["source_ink"]["ends"]
            if (min(va,vb)<=hy<=max(va,vb)
                    and min(ha,hb)<=vx<=max(ha,hb)
                    and polygon.contains(Point(vx,hy))):
                hits.add((vx,hy))
    return {
        **base,
        "status":"native_rcp_grid_ink_intersection_candidates_only",
        "original_source_grid_intersections_pdf_pts":
            tuple(sorted(hits)),
        "original_source_orthogonal_grid_segment_counts":{
            "vertical":len(vertical),"horizontal":len(horizontal),
        },
        "original_interior_source_grid_crossing_count":len(hits),
        "structural_ceiling_zone_or_grid_identity_proven":False,
    }


def audit_competing_original_rcp_zone_owners(
    candidate_zones: tuple[dict, ...],
)->dict:
    """Preserve overlapping ceiling zone ink and reused mark/grid ancestry.

    No input ordering or lowest-area tie-break is allowed. Duplicated
    source physical edges or identical issued occurrence records assigned
    to more than one region remain an explicit cross-zone blocker.
    """
    if type(candidate_zones) is not tuple or not candidate_zones or len(candidate_zones)>64:
        raise ValueError("bounded_original_rcp_zone_census_required")
    owners={}
    shared={}
    all_out=[]
    for index, zone in enumerate(candidate_zones):
        if type(zone) is not dict:
            raise ValueError("original_source_rcp_candidate_receipt_required")
        if zone.get("status") not in {
            "original_rcp_source_ink_ceiling_polygon_candidate",
            "original_rcp_material_in_ceiling_ink_candidate",
        }:
            all_out.append({"index":index,"candidate":zone,"eligible":False})
            continue
        root=zone.get("original_source_sha256")
        revision=zone.get("original_revision_id")
        snapshot=zone.get("original_snapshot_id")
        if not all(type(v) is str and v for v in (root,revision,snapshot)):
            all_out.append({"index":index,"candidate":zone,"eligible":False})
            continue
        graph=zone.get("source_boundary_graph",{})
        for ident in graph.get("original_native_edge_ids",()):
            key=(root,revision,snapshot,"boundary",ident)
            owners.setdefault(key,[]).append(index)
        for line in zone.get("original_grid_source_ink_candidates",()):
            if type(line) is not dict or not line.get("native_source_id"):
                raise ValueError("original_rcp_grid_ink_source_ancestry_invalid")
            key=(root,revision,snapshot,"grid",line["native_source_id"])
            owners.setdefault(key,[]).append(index)
        for ident in zone.get("original_source_finish_record_ids",()):
            key=(root,revision,snapshot,"mark",ident)
            shared.setdefault(key,[]).append(index)
        all_out.append({"index":index,"candidate":zone,"eligible":True})
    conflicts=[
        {"source_ancestry_key":list(key),"competing_zone_indexes":tuple(owners[key])}
        for key in sorted(owners) if len(owners[key])>1
    ]+[
        {"source_ancestry_key":list(key),"competing_zone_indexes":tuple(shared[key])}
        for key in sorted(shared) if len(shared[key])>1
    ]
    return {
        "status":("original_rcp_competing_zone_source_ownership" if conflicts
                  else "original_rcp_source_zone_candidates_only"),
        "all_original_rcp_candidate_zones":tuple(all_out),
        "source_competing_grid_boundary_or_finish_mark_owners":tuple(conflicts),
        "original_rcp_unique_room_identity_issued":False,
        "source_ceiling_area_or_quantity_issued":False,
        "new_firm_quantities":0,
    }


def audit_original_rcp_mark_in_source_ink_enclosure(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    floor_page_1_based: int, rcp_page_1_based: int,
    original_side_pairs: dict[str,tuple[str,str]],
    expected_translation_pdf_pts: tuple[float,float],
    ceiling_code_literal: str,
) -> dict:
    """Actual p7→p9 original source ink + printed ceiling mark (not m2).

    OFFICE and PWD use opposite orientations of the real missing top-wall
    doorway. A source-visible code inside an open source-ink box is a mark
    *candidate*. Never inherit floor area, guess an RCP ceiling height,
    close the wall gap or elevate untrusted text to a producer-issued mark.
    """
    from tools.diag_original_room_four_edge_source_ink_shadow import (
        audit_source_enclosure_correspondence,
    )
    from tools.diag_original_finish_mark_in_room_ink_shadow import (
        _native_mark_containment_census,
    )
    import hashlib
    import fitz
    base={
        "status":"original_RCP_source_mark_unavailable",
        "new_firm_quantities":0,
        "ceiling_metric_area_m2":None,
        "physical_ceiling_room_identity_proven":False,
        "source_ceiling_material_occurrence_issued":False,
        "original_top_door_gap_physically_closed":False,
    }
    if (type(ceiling_code_literal) is not str
            or not ceiling_code_literal or not ceiling_code_literal.isascii()
            or not ceiling_code_literal.isalnum()):
        raise ValueError("explicit_original_ceiling_mark_code_required")
    witness=audit_source_enclosure_correspondence(
        original_pdf_bytes,expected_sha256=expected_sha256,
        floor_page_1_based=floor_page_1_based,
        finish_page_1_based=rcp_page_1_based,
        original_side_pairs=original_side_pairs,
        expected_translation_pdf_pts=expected_translation_pdf_pts,
    )
    if witness.get("status")!="original_four_edge_ink_correspondence_with_unclosed_doorway":
        return {**base,"first_failure":"independent_source_wall_registration_unavailable"}
    sides=witness["original_witnesses"]
    left=sides["left"]["finish_source"]["ends"][0][0]
    right=sides["right"]["finish_source"]["ends"][0][0]
    upper=sides["top_partial"]["finish_source"]["ends"][0][1]
    lower=sides["bottom"]["finish_source"]["ends"][0][1]
    if not (left<right and upper<lower):
        return {**base,"first_failure":"original_rcp_room_source_ink_box_invalid"}
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as doc:
        marks=_native_mark_containment_census(
            doc[rcp_page_1_based-1].get_text("words"),
            code=ceiling_code_literal,
            bbox=(left,upper,right,lower),
        )
    if not marks["unique_native_code_word_in_enclosure"]:
        return {
            **base,"first_failure":"original_rcp_mark_missing_or_competing",
            "original_RCP_source_mark_census":marks,
            "original_source_ink_wall_registration":witness,
        }
    return {
        **base,
        "status":"original_RCP_ink_enclosed_ceiling_mark_candidate_only",
        "first_failure":"source_material_issuer_W4_ceiling_zone_and_metric_surface",
        "original_source_sha256":expected_sha256,
        "original_floor_page_1_based":floor_page_1_based,
        "original_rcp_page_1_based":rcp_page_1_based,
        "source_native_p7_to_rcp_translation_pdf_pts":
            list(expected_translation_pdf_pts),
        "source_rcp_ink_enclosure_bbox_pdf_pts":[left,upper,right,lower],
        "source_rcp_partial_wall_anchor":
            witness["original_top_partial_wall_anchor"],
        "source_original_unclosed_door_gap_pdf_pts":
            witness["original_top_gap_pdf_pts"],
        "original_ceiling_code_literal_untrusted":ceiling_code_literal,
        "original_RCP_source_mark_census":marks,
        "original_source_ink_wall_registration":witness,
    }
