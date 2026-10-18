"""Maryborough-style RCP ceiling finish area from original source material roles.

No candidate source code becomes a ceiling lining merely by containing GRID,
IPF1 or CLxx. Definition meaning comes from SourceMaterialSemanticProducer
and an independently source-proven planar ceiling zone, after exact W4
cross-sheet correspondence. Signage cladding remains a material OTHER role.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

from pb_gpt1_original_crosssheet_marked_sections_shadow import (
    OriginalSourceMarkedSectionsShadow,
)
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow, AuthenticatedFloorFinishPlanMark,
)
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionResult, SourceMaterialDefinitionRecord,
)
from pb_migration_contracts import EvidenceResolutionStatus

_ALLOWED_CEILING_SEMANTICS=frozenset({
    "ceiling_grid","plasterboard","fibre_cement",
    "insulated_panel","sandwich_panel",
})


@dataclass(frozen=True)
class OriginalCeilingSurfaceRoleReceipt:
    physical_ceiling_surface_id: str
    physical_room_id: str
    original_source_page_id: str
    original_source_ceiling_role_evidence_ids: tuple[str,...]
    original_surface_plane_semantic: str
    source_sha256: str
    revision_id: str
    source_snapshot_id: str


@dataclass(frozen=True)
class OriginalRcpCeilingZonesShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    source_ceiling_surface_id: str
    candidate_ceiling_lining_m2_by_code: tuple[tuple[str,float],...]
    candidate_ceiling_lining_m2_by_semantic: tuple[tuple[str,float],...]
    candidate_unassigned_ceiling_area_m2: float | None
    source_definition_ids: tuple[str,...]
    diagnostic_only: bool = True


def reconcile_source_rcp_ceiling_material_zones_shadow(
    marked_zones: OriginalSourceMarkedSectionsShadow,
    physical_correspondence: PhysicalFloorFinishCorrespondenceShadow,
    role: OriginalCeilingSurfaceRoleReceipt,
    original_material_definitions: tuple[SourceMaterialDefinitionResult,...],
    original_plan_marks: tuple[AuthenticatedFloorFinishPlanMark,...],
) -> OriginalRcpCeilingZonesShadow:
    """Reject unrelated sheet material rows; never infer a ceiling finish."""
    def block(reason):
        return OriginalRcpCeilingZonesShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),
            str(getattr(role,"physical_ceiling_surface_id","")),
            (),(),None,(),
        )
    if (
        type(marked_zones) is not OriginalSourceMarkedSectionsShadow
        or marked_zones.status is not EvidenceResolutionStatus.CANDIDATE
        or type(physical_correspondence) is not PhysicalFloorFinishCorrespondenceShadow
        or physical_correspondence.status is not EvidenceResolutionStatus.CANDIDATE
        or type(role) is not OriginalCeilingSurfaceRoleReceipt
        or role.physical_room_id!=physical_correspondence.physical_room_id
        or (role.source_sha256,role.revision_id,role.source_snapshot_id)
           != (physical_correspondence.source_sha256,
               physical_correspondence.revision_id,
               physical_correspondence.producer_snapshot_id)
        or role.original_source_page_id!=physical_correspondence.original_finish_page_id
        or role.original_surface_plane_semantic!="original_flat_horizontal_ceiling"
        or type(role.physical_ceiling_surface_id) is not str
        or not role.physical_ceiling_surface_id
        or type(role.original_source_ceiling_role_evidence_ids) not in (tuple,list)
        or not role.original_source_ceiling_role_evidence_ids
        or type(original_material_definitions) not in (tuple,list)
        or type(original_plan_marks) not in (tuple,list)
    ):
        return block("original_rcp_ownership_or_horizontal_plane_unproven")
    by_code={}
    by_semantic={}
    known_definitions={}
    for definition in original_material_definitions:
        if (type(definition) is not SourceMaterialDefinitionResult
                or definition.status is not EvidenceResolutionStatus.CORROBORATED
                or type(definition.record) is not SourceMaterialDefinitionRecord):
            return block("original_rcp_material_definition_untrusted")
        record=definition.record
        if (
            (record.source_sha256,record.revision_id,record.snapshot_id)
            != (role.source_sha256,role.revision_id,role.source_snapshot_id)
            or record.code in known_definitions
            or record.semantic_finish not in _ALLOWED_CEILING_SEMANTICS
        ):
            return block("original_rcp_material_is_not_ceiling_lining")
        known_definitions[record.code]=record
    occurrences={}
    for mark in original_plan_marks:
        if type(mark) is not AuthenticatedFloorFinishPlanMark:
            return block("original_rcp_mark_type_invalid")
        if mark.source_occurrence_id in occurrences:
            return block("original_rcp_reused_material_occurrence")
        if (
            not mark.is_original_plan_occurrence
            or (mark.source_sha256,mark.revision_id,mark.page_id)
              != (role.source_sha256,role.revision_id,
                  role.original_source_page_id)
        ):
            return block("original_rcp_material_mark_sheet_unverified")
        definition=known_definitions.get(mark.source_material_code)
        if definition is None or (
            mark.source_definition_id!=definition.record_id
            or mark.semantic_finish!=definition.semantic_finish
            or not mark.original_glyph_paint_receipt_id
            or not mark.original_clip_receipt_id
        ):
            return block("original_rcp_mark_definition_or_visibility_unverified")
        occurrences[mark.source_occurrence_id]=mark
    if set(occurrences)!=set(marked_zones.exact_occurrence_ids):
        return block("original_rcp_marked_ceiling_universe_incomplete")
    for section,code,occurrence,area in marked_zones.measured_section_material_m2:
        mark=occurrences.get(occurrence)
        if mark is None or mark.source_material_code!=code:
            return block("original_rcp_material_occurrence_section_conflict")
        if type(area) not in (int,float) or not math.isfinite(area) or area<=0:
            return block("original_rcp_material_zone_area_invalid")
        by_code[code]=by_code.get(code,0.)+area
        semantic=known_definitions[code].semantic_finish
        by_semantic[semantic]=by_semantic.get(semantic,0.)+area
    return OriginalRcpCeilingZonesShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_source_rcp_ceiling_material_shadow_only",),
        role.physical_ceiling_surface_id,
        tuple(sorted(by_code.items())),
        tuple(sorted(by_semantic.items())),
        marked_zones.unallocated_parent_area_m2,
        tuple(sorted(v.record_id for v in known_definitions.values())),
    )
