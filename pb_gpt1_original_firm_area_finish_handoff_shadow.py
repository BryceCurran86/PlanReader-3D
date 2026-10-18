"""Shadow floor-finish handoff reusing an ALREADY FIRM original room area.

The three original Maryborough plain areas are producer-originated room_area
QuantityEvidence. Do not remeasure them, alter their IDs or call them FT3
without independent original finish occurrence and true physical correspondence.
This adapter is a strictly diagnostic bridge; it never signs or changes rows.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_migration_contracts import QuantityEvidence,EvidenceResolutionStatus
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCandidate, PhysicalFloorFinishCorrespondenceShadow,
)


@dataclass(frozen=True)
class OriginalFirmAreaToFinishHandoffShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    original_room_area_quantity_id: str | None
    original_canonical_floor_id: str
    original_floor_finish_occurrence_id: str | None
    original_floor_finish_definition_id: str | None
    original_floor_finish_code: str | None
    candidate_finish_area_m2: float | None
    original_source_room_face_id: str
    original_source_sha256: str
    original_revision_id: str
    original_snapshot_id: str
    diagnostic_only: bool = True


def reuse_authenticated_room_area_for_finish_shadow(
    floor: LiveCanonicalFloorSurfaceObject,
    original_firm_area: QuantityEvidence,
    correspondence: PhysicalFloorFinishCorrespondenceShadow,
    finish_candidate: PhysicalFloorFinishCandidate,
) -> OriginalFirmAreaToFinishHandoffShadow:
    """Area value/quantity ID remain exactly those of the original issuer."""
    def block(reason):
        return OriginalFirmAreaToFinishHandoffShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),None,
            str(getattr(floor,"canonical_floor_id","")),
            None,None,None,None,
            str(getattr(floor,"source_room_face_record_id","")),
            str(getattr(floor,"source_sha256","")),
            str(getattr(floor,"revision_id","")),
            str(getattr(floor,"snapshot_id","")),
        )
    if (
        type(floor) is not LiveCanonicalFloorSurfaceObject
        or type(original_firm_area) is not QuantityEvidence
        or type(correspondence) is not PhysicalFloorFinishCorrespondenceShadow
        or type(finish_candidate) is not PhysicalFloorFinishCandidate
        or correspondence.status is not EvidenceResolutionStatus.CANDIDATE
        or finish_candidate.status is not EvidenceResolutionStatus.CANDIDATE
    ):
        return block("original_firm_room_area_finish_source_unavailable")
    if (
        floor.source_sha256 != correspondence.source_sha256
        or floor.revision_id != correspondence.revision_id
        or floor.canonical_floor_id != correspondence.canonical_floor_id
        or finish_candidate.original_floor_id != floor.canonical_floor_id
        or floor.source_room_face_record_id != correspondence.source_room_face_record_id
        or floor.page_id != correspondence.original_room_page_id
        or floor.snapshot_id != correspondence.producer_snapshot_id
    ):
        return block("original_firm_floor_finish_physical_lineage_conflict")
    if (
        original_firm_area.abstained
        or original_firm_area.family != "room_area"
        or original_firm_area.status.lower() != "firm"
        or original_firm_area.unit not in ("m2","m²")
        or original_firm_area.blocking_reasons
        or original_firm_area.quantity_id != floor.metric_area_quantity_id
        or not original_firm_area.evidence_ids
        or (type(original_firm_area.value) not in (int,float))
        or (type(floor.metric_area_m2) not in (int,float))
    ):
        return block("original_firm_room_area_quantity_identity_unverified")
    try:
        original=float(original_firm_area.value)
        current=float(floor.metric_area_m2)
    except (TypeError,ValueError,OverflowError):
        return block("original_firm_room_area_quantity_numeric_invalid")
    if (
        not math.isfinite(original) or not math.isfinite(current)
        or original<=0 or current<=0
        or original!=current
    ):
        return block("original_firm_room_area_quantity_numeric_conflict")
    meta=original_firm_area.metadata
    if (
        meta.get("source_sha256") != floor.source_sha256
        or meta.get("revision_id") != floor.revision_id
        or meta.get("source_room_face_record_id") not in (
            None,floor.source_room_face_record_id,
        )
    ):
        return block("original_firm_room_area_receipt_scope_conflict")
    if (
        not finish_candidate.original_occurrence_id
        or not finish_candidate.original_definition_id
        or not finish_candidate.original_finish_code
        or type(finish_candidate.candidate_area_m2) not in (int,float)
    ):
        return block("original_floor_finish_material_proof_unavailable")
    try:proposed=float(finish_candidate.candidate_area_m2)
    except (ValueError,TypeError,OverflowError):
        return block("original_floor_finish_area_numeric_invalid")
    if not math.isfinite(proposed) or proposed<=0 or not math.isclose(
        proposed,current,rel_tol=0,abs_tol=1e-6
    ):
        return block("original_floor_finish_area_disagrees_with_signed_room_area")
    return OriginalFirmAreaToFinishHandoffShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("authenticated_room_area_original_identity_preserved_shadow_only",),
        original_firm_area.quantity_id,floor.canonical_floor_id,
        finish_candidate.original_occurrence_id,
        finish_candidate.original_definition_id,
        finish_candidate.original_finish_code,original,
        floor.source_room_face_record_id,floor.source_sha256,
        floor.revision_id,floor.snapshot_id,
    )
