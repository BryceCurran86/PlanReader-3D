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
