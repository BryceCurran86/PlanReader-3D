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



@dataclass(frozen=True)
class SourceProducerFloorFinishBatch:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SourceProducerFloorFinishDiagnostic, ...]
    quarantined_physical_room_ids: tuple[str, ...]
    diagnostic_only: bool = True


def reconcile_source_producer_finish_batch_shadow(
    records: tuple[SourceProducerFloorFinishDiagnostic, ...],
) -> SourceProducerFloorFinishBatch:
    """One source area and one in-plan mark may authenticate one room only.

    Batch reconciliation must happen BEFORE any new signed finish-area issue;
    independent per-room positive handoffs cannot observe this conflict.
    Every rival claim is quarantined, with insertion-order independence.
    Original producer-selected signatories and source numeric values remain
    unchanged; this is never a customer-facing signed record.
    """
    from collections import Counter
    from dataclasses import replace

    if type(records) is not tuple or any(
        type(item) is not SourceProducerFloorFinishDiagnostic for item in records
    ):
        return SourceProducerFloorFinishBatch(
            EvidenceResolutionStatus.ABSTAINED,
            ("gpt1_original_finish_batch_records_untrusted",),(),(),
        )
    if not records:
        return SourceProducerFloorFinishBatch(
            EvidenceResolutionStatus.ABSTAINED,
            ("gpt1_original_finish_batch_no_source_rooms",),(),(),
        )
    keys = (
        ("physical_room_id", "gpt1_original_finish_physical_room_reused"),
        ("source_room_face_record_id", "gpt1_original_finish_source_face_reused"),
        ("canonical_floor_id", "gpt1_original_finish_floor_reused"),
        ("existing_room_area_quantity_id", "gpt1_original_finish_area_issuer_reused"),
        ("source_finish_occurrence_id", "gpt1_original_finish_plan_mark_reused"),
    )
    accepted = tuple(row for row in records if
        row.status is EvidenceResolutionStatus.CANDIDATE
    )
    owners = {
        field: Counter(getattr(row, field) for row in accepted
                       if isinstance(getattr(row, field), str)
                       and getattr(row, field))
        for field, _ in keys
    }
    ordered: list[SourceProducerFloorFinishDiagnostic] = []
    quarantine: set[str] = set()
    conflict = False
    for row in sorted(records,key=lambda r: (
        r.physical_room_id,r.canonical_floor_id,
        r.source_room_face_record_id,str(r.source_finish_occurrence_id),
    )):
        if row.status is not EvidenceResolutionStatus.CANDIDATE:
            ordered.append(row)
            continue
        reason = next((
            rule for field,rule in keys
            if not isinstance(getattr(row, field), str)
            or not getattr(row, field)
            or owners[field][getattr(row, field)]!=1
        ),None)
        if reason is None:
            ordered.append(row)
            continue
        conflict = True
        quarantine.add(row.physical_room_id)
        ordered.append(replace(
            row,status=EvidenceResolutionStatus.ABSTAINED,
            first_failure_code=reason,
            existing_room_area_quantity_id=None,
            existing_room_area_m2=None,
            source_finish_occurrence_id=None,
            source_finish_definition_id=None,
            source_finish_code=None,
            candidate_finish_area_m2=None,
            source_crosssheet_wall_equivalence_ids=(),
        ))
    if conflict:
        return SourceProducerFloorFinishBatch(
            EvidenceResolutionStatus.CONFLICT,
            ("gpt1_original_finish_batch_reused_source_authority",),
            tuple(ordered),tuple(sorted(quarantine)),
        )
    return SourceProducerFloorFinishBatch(
        EvidenceResolutionStatus.CANDIDATE,
        ("gpt1_original_finish_batch_candidate_shadow_only",),
        tuple(ordered),(),
    )


def diagnose_source_producer_floor_finish_with_w4_shadow(
    *,
    canonical_rooms: "LiveCanonicalRoomComposition",
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
    """Source-sealed W4 room gate preceding original material/floor handoff.

    This is the strict *opt-in consumer* for prospective source-authorized
    issuance. A caller-authored SourceWallRingFrameShadow is NOT an original
    W4 certificate. The real canonical-room producer must first replay its
    original sealed SourceRoomFaceAuthority scope with its actual W4 ownership.
    The returned result stays CANDIDATE and never signs commercial quantities.
    """
    from pb_live_canonical_room_composition import LiveCanonicalRoomComposition
    from pb_gpt1_producer_sealed_w4_metric_floor_shadow import (
        bind_producer_sealed_w4_metric_floor_shadow,
    )

    def abstain(reason: str) -> SourceProducerFloorFinishDiagnostic:
        return SourceProducerFloorFinishDiagnostic(
            EvidenceResolutionStatus.ABSTAINED,reason,
            str(getattr(physical_ring,"physical_room_id","")),
            str(original_room_face_id),
            str(getattr(crosssheet_floor,"canonical_floor_id","")),
            None,None,None,None,None,None,(),
        )
    if type(canonical_rooms) is not LiveCanonicalRoomComposition:
        return abstain("gpt1_original_producer_w4_room_composition_unavailable")
    verified=bind_producer_sealed_w4_metric_floor_shadow(
        canonical_rooms,canonical_floors,physical_ring,
        physical_room_id=physical_ring.physical_room_id,
    )
    if verified.status is not EvidenceResolutionStatus.CANDIDATE:
        return abstain(verified.reason_codes[0])
    if (
        verified.source_room_face_record_id != original_room_face_id
        or verified.canonical_floor_id != crosssheet_floor.canonical_floor_id
        or verified.physical_room_id != crosssheet_floor.physical_room_id
        or (verified.source_sha256,verified.revision_id,verified.snapshot_id,
            verified.decision_scope_id)
        != (crosssheet_floor.source_sha256,crosssheet_floor.revision_id,
            crosssheet_floor.producer_snapshot_id,
            crosssheet_floor.decision_scope_id)
        or verified.page_id != crosssheet_floor.original_room_page_id
        or not verified.original_published_boundary_subedges
        or not verified.original_source_face_boundary_wall_ids
    ):
        return abstain("gpt1_original_producer_w4_to_finish_lineage_conflict")
    result=diagnose_source_producer_floor_finish_handoff_shadow(
        physical_ring=physical_ring,
        original_room_face_id=original_room_face_id,
        same_view_areas=same_view_areas,
        cross_view_areas=cross_view_areas,
        canonical_floors=canonical_floors,
        original_signed_room_area=original_signed_room_area,
        structural_frame=structural_frame,
        crosssheet_floor=crosssheet_floor,
        finish_definition=finish_definition,
        complete_finish_occurrences=complete_finish_occurrences,
        native_paint_clip_receipts=native_paint_clip_receipts,
    )
    # No downstream code can mistake this for an already signed finish row.
    return result
