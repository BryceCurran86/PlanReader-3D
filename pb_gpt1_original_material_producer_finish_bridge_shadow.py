"""Bridge existing SourceMaterialSemanticProducer output to cross-sheet floor proof.

Unlike raw plan text matching, this consumes the repository's exact definition
and occurrence result types, requires one complete material occurrence universe
and independently issued paint/clip evidence for the *same exact mark*.

This composition does not elevate source statuses or publish a quantity.
"""
from __future__ import annotations
from dataclasses import dataclass
from shapely.geometry import box
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionResult, SourceMaterialOccurrenceScopeResult,
    SourceMaterialDefinitionRecord, SourceMaterialOccurrenceRecord,
)
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,
    AuthenticatedFloorFinishPlanMark,
    PhysicalFloorFinishCandidate,
    bind_source_finish_mark_to_corresponded_floor_shadow,
    _safe_polygon,
)


@dataclass(frozen=True)
class OriginalAuthenticatedTextPaintClipReceipt:
    original_source_occurrence_id: str
    source_text_observation_ids: tuple[str,...]
    original_glyph_paint_evidence_id: str
    original_clip_evidence_id: str
    source_partition_id: str
    source_sha256: str
    revision_id: str
    page_id: str
    viewport_id: str
    original_paint_and_clip_status: str


def use_original_semantic_producer_for_finish_shadow(
    measured: FiguredPolygonMetricShadow,
    correspondence: PhysicalFloorFinishCorrespondenceShadow,
    definition: SourceMaterialDefinitionResult,
    occurrence_scope: SourceMaterialOccurrenceScopeResult,
    paint_receipts: tuple[OriginalAuthenticatedTextPaintClipReceipt,...],
) -> PhysicalFloorFinishCandidate:
    """Only actual source-owned material result objects enter this candidate."""
    def block(reason):
        return PhysicalFloorFinishCandidate(
            EvidenceResolutionStatus.ABSTAINED,(reason,),
            str(getattr(correspondence,"canonical_floor_id","")),
            None,None,None,None,
        )
    if (
        type(definition) is not SourceMaterialDefinitionResult
        or definition.status is not EvidenceResolutionStatus.CORROBORATED
        or type(definition.record) is not SourceMaterialDefinitionRecord
        or type(occurrence_scope) is not SourceMaterialOccurrenceScopeResult
        or occurrence_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or occurrence_scope.scope_complete is not True
        or type(occurrence_scope.records) is not tuple
        or type(paint_receipts) is not tuple
    ):
        return block("source_material_definition_or_occurrence_scope_unavailable")
    defrow=definition.record
    if (
        (defrow.source_sha256,defrow.revision_id,defrow.snapshot_id)
        != (correspondence.source_sha256,correspondence.revision_id,
            correspondence.producer_snapshot_id)
        or not defrow.source_definition_ids
        or not defrow.source_page_ids or not defrow.source_viewport_ids
    ):
        return block("original_finish_definition_source_lineage_conflict")
    owned={};seen_text=set()
    for record in paint_receipts:
        if (
            type(record) is not OriginalAuthenticatedTextPaintClipReceipt
            or type(record.original_source_occurrence_id) is not str
            or not record.original_source_occurrence_id
            or record.original_source_occurrence_id in owned
            or record.original_paint_and_clip_status
               != "original_visible_native_glyph_and_clip_authenticated"
            or not record.original_glyph_paint_evidence_id
            or not record.original_clip_evidence_id
            or record.original_clip_evidence_id==record.original_glyph_paint_evidence_id
            or not record.source_partition_id
            or (record.source_sha256,record.revision_id,record.page_id)
               != (correspondence.source_sha256,correspondence.revision_id,
                   correspondence.original_finish_page_id)
            or type(record.source_text_observation_ids) not in (tuple,list)
            or not record.source_text_observation_ids
            or len(set(record.source_text_observation_ids))
               != len(record.source_text_observation_ids)
            or seen_text.intersection(record.source_text_observation_ids)
        ):
            return block("original_native_paint_clip_receipt_unverified")
        seen_text.update(record.source_text_observation_ids)
        owned[record.original_source_occurrence_id]=record
    support=_safe_polygon(correspondence.finish_support_polygon_pts)
    if support is None:
        return block("source_material_original_support_perimeter_unavailable")
    marks=[]
    seen_occurrence=set()
    for occurrence in occurrence_scope.records:
        if type(occurrence) is not SourceMaterialOccurrenceRecord:
            return block("source_material_occurrence_type_invalid")
        if occurrence.record_id in seen_occurrence:
            return block("source_material_occurrence_duplicate")
        seen_occurrence.add(occurrence.record_id)
        if (
            occurrence.definition_record_id!=defrow.record_id
            or occurrence.code!=defrow.code
            or occurrence.semantic_finish!=defrow.semantic_finish
        ):
            # Other authenticated material marks on the same sheet can be
            # legitimate distinct rooms. Only an actual competing mark INSIDE
            # this exact physical room must defeat this one-material claim.
            if occurrence.page_id == correspondence.original_finish_page_id:
                try:
                    other=box(*map(float,occurrence.bbox_pdf_pts))
                except (TypeError,ValueError,OverflowError):
                    return block("source_material_competing_mark_geometry_invalid")
                if support.contains(other):
                    return block("source_material_competing_definition_in_finish_scope")
            continue
        if (
            (occurrence.source_sha256,occurrence.revision_id,
             occurrence.snapshot_id)
            != (defrow.source_sha256,defrow.revision_id,defrow.snapshot_id)
        ):
            return block("source_material_occurrence_source_lineage_conflict")
        receipt=owned.get(occurrence.record_id)
        if receipt is None:
            return block("source_material_original_occurrence_paint_clip_unavailable")
        if (
            receipt.viewport_id!=occurrence.viewport_id
            or set(receipt.source_text_observation_ids)
               != set(occurrence.source_text_observation_ids)
        ):
            return block("source_material_native_word_receipt_owner_conflict")
        marks.append(AuthenticatedFloorFinishPlanMark(
            source_occurrence_id=occurrence.record_id,
            source_definition_id=defrow.record_id,
            original_glyph_paint_receipt_id=receipt.original_glyph_paint_evidence_id,
            original_clip_receipt_id=receipt.original_clip_evidence_id,
            source_partition_id=receipt.source_partition_id,
            source_material_code=occurrence.code,
            semantic_finish=occurrence.semantic_finish,
            source_plan_bbox_pts=occurrence.bbox_pdf_pts,
            source_sha256=occurrence.source_sha256,
            revision_id=occurrence.revision_id,
            page_id=occurrence.page_id,
            viewport_id=occurrence.viewport_id,
            is_original_plan_occurrence=(
                occurrence.page_id==correspondence.original_finish_page_id
            ),
        ))
    if not marks:
        return block("source_material_exact_painted_plan_mark_unavailable")
    return bind_source_finish_mark_to_corresponded_floor_shadow(
        measured,correspondence,tuple(marks)
    )
