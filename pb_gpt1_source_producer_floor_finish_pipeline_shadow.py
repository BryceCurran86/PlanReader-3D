"""One real-producer-input path towards an original-source floor-finish handoff.

Ties source-owned room area, canonical original floor, structural correspondence,
full source material occurrence universe and unchanged FIRM room-area receipt.
It intentionally returns a diagnostic candidate, NOT a new QuantityEvidence.

The existing commercial CrossViewFloorFinishProducer remains the sole issuer.
Only after GPT2 validates original cross-sheet structural equivalence, the
specific plan mark and this independent lineage may a separate authority
promotion be reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass

from pb_cross_view_room_area_authority import CrossViewRoomAreaResult
from pb_same_view_room_area_authority import SameViewRoomAreaResult
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceComposition
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionResult,SourceMaterialOccurrenceScopeResult,
)
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_producer_figured_area_ring_bridge_shadow import (
    bind_producer_figured_area_to_original_room_ring_shadow,
)
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,
)
from pb_gpt1_original_two_view_wall_frame_shadow import SourceWallRingFrameShadow
from pb_gpt1_original_material_producer_finish_bridge_shadow import (
    OriginalAuthenticatedTextPaintClipReceipt,
    use_original_semantic_producer_for_finish_shadow,
)
from pb_gpt1_original_firm_area_finish_handoff_shadow import (
    reuse_authenticated_room_area_for_finish_shadow,
)
from pb_migration_contracts import QuantityEvidence,EvidenceResolutionStatus


@dataclass(frozen=True)
class SourceProducerFloorFinishDiagnostic:
    status: EvidenceResolutionStatus
    first_failure_code: str | None
    physical_room_id: str
    source_room_face_record_id: str
    canonical_floor_id: str
    existing_room_area_quantity_id: str | None
    existing_room_area_m2: float | None
    source_finish_occurrence_id: str | None
    source_finish_definition_id: str | None
    source_finish_code: str | None
    candidate_finish_area_m2: float | None
    source_crosssheet_wall_equivalence_ids: tuple[str,...]
    diagnostic_only: bool = True


def diagnose_source_producer_floor_finish_handoff_shadow(
    *,
    physical_ring: FiguredPolygonMetricShadow,
    original_room_face_id: str,
    same_view_areas: SameViewRoomAreaResult | None,
    cross_view_areas: CrossViewRoomAreaResult | None,
    canonical_floors: LiveCanonicalFloorSurfaceComposition,
    original_signed_room_area: QuantityEvidence,
    structural_frame: SourceWallRingFrameShadow,
    crosssheet_floor: PhysicalFloorFinishCorrespondenceShadow,
    finish_definition: SourceMaterialDefinitionResult,
    complete_finish_occurrences: SourceMaterialOccurrenceScopeResult,
    native_paint_clip_receipts: tuple[OriginalAuthenticatedTextPaintClipReceipt,...],
) -> SourceProducerFloorFinishDiagnostic:
    """Expose the first true missing source gate with no commercial promotion."""
    def blocked(reason):
        return SourceProducerFloorFinishDiagnostic(
            EvidenceResolutionStatus.ABSTAINED,reason,
            str(getattr(physical_ring,"physical_room_id","")),
            str(original_room_face_id),
            str(getattr(crosssheet_floor,"canonical_floor_id","")),
            None,None,None,None,None,None,(),
        )
    bound=bind_producer_figured_area_to_original_room_ring_shadow(
        physical_ring,same_view=same_view_areas,cross_view=cross_view_areas,
        canonical_floors=canonical_floors,
        original_room_face_id=original_room_face_id,
    )
    if bound.status is not EvidenceResolutionStatus.CANDIDATE:
        return blocked(bound.reason_codes[0])
    if (
        type(structural_frame) is not SourceWallRingFrameShadow
        or structural_frame.status is not EvidenceResolutionStatus.CANDIDATE
        or type(crosssheet_floor) is not PhysicalFloorFinishCorrespondenceShadow
        or crosssheet_floor.status is not EvidenceResolutionStatus.CANDIDATE
        or bound.canonical_floor_id != crosssheet_floor.canonical_floor_id
        or bound.original_room_face_id != crosssheet_floor.source_room_face_record_id
        or bound.original_physical_room_id != crosssheet_floor.physical_room_id
        or tuple(sorted(structural_frame.matched_wall_equivalence_receipts))
            != tuple(sorted(crosssheet_floor.wall_equivalence_receipts))
        or not structural_frame.matched_wall_equivalence_receipts
    ):
        return blocked("gpt1_source_crosssheet_physical_wall_equivalence_unavailable")
    mark=use_original_semantic_producer_for_finish_shadow(
        physical_ring,crosssheet_floor,
        finish_definition,complete_finish_occurrences,
        native_paint_clip_receipts,
    )
    if mark.status is not EvidenceResolutionStatus.CANDIDATE:
        return blocked(mark.reason_codes[0])
    matched=[
        floor for floor in canonical_floors.floors
        if floor.canonical_floor_id == bound.canonical_floor_id
        and floor.source_room_face_record_id==bound.original_room_face_id
        and floor.metric_area_quantity_id==original_signed_room_area.quantity_id
    ]
    if len(matched)!=1:
        return blocked("gpt1_source_original_firm_room_area_handoff_unavailable")
    preserved=reuse_authenticated_room_area_for_finish_shadow(
        matched[0],original_signed_room_area,crosssheet_floor,mark,
    )
    if preserved.status is not EvidenceResolutionStatus.CANDIDATE:
        return blocked(preserved.reason_codes[0])
    if (
        preserved.original_room_area_quantity_id != original_signed_room_area.quantity_id
        or preserved.original_canonical_floor_id != bound.canonical_floor_id
        or preserved.original_floor_finish_occurrence_id!=mark.original_occurrence_id
    ):
        return blocked("gpt1_source_producer_quantity_lineage_conflict")
    return SourceProducerFloorFinishDiagnostic(
        EvidenceResolutionStatus.CANDIDATE,None,bound.original_physical_room_id,
        bound.original_room_face_id,bound.canonical_floor_id,
        preserved.original_room_area_quantity_id,
        preserved.candidate_finish_area_m2,
        preserved.original_floor_finish_occurrence_id,
        preserved.original_floor_finish_definition_id,
        preserved.original_floor_finish_code,
        preserved.candidate_finish_area_m2,
        tuple(sorted(structural_frame.matched_wall_equivalence_receipts)),
    )
