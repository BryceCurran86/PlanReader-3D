"""Gross wall lining m² from real W4 boundary owner and FIRM source heights.

Consumes a producer-authenticated physical room W4-to-figured-metric length
shadow plus already-issued wall_height QuantityEvidence. It does NOT claim
wall material/finish side, opening deductions, measured building quantities
or a new customer FIRM. Missing or wrong-source heights ABSTAIN the whole
room; no default 2.7m height or implicit two-sided lining multiplier.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from pb_gpt1_producer_sealed_w4_metric_floor_shadow import SourceSealedW4MetricFloorShadow
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_wall_height_authority import WALL_HEIGHT_FAMILY, WALL_HEIGHT_FORMULA_VERSION


@dataclass(frozen=True)
class SourceSealedW4GrossWallLiningShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    physical_room_id: str
    canonical_floor_id: str
    per_w4_wall_gross_area_m2: tuple[tuple[str,float],...]
    per_w4_wall_length_m: tuple[tuple[str,float],...]
    original_wall_height_quantity_ids: tuple[tuple[str,str],...]
    total_single_face_gross_area_m2: float | None
    diagnostic_only: bool = True


def measure_source_sealed_w4_wall_gross_lining_shadow(
    w4_floor: SourceSealedW4MetricFloorShadow,
    wall_heights: tuple[QuantityEvidence,...],
) -> SourceSealedW4GrossWallLiningShadow:
    """Only direct-source FIRM wall heights; always a diagnostic area."""
    def block(reason):
        return SourceSealedW4GrossWallLiningShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),
            str(getattr(w4_floor,"physical_room_id","")),
            str(getattr(w4_floor,"canonical_floor_id","")),
            (),(),(),None,
        )
    if (
        type(w4_floor) is not SourceSealedW4MetricFloorShadow
        or w4_floor.status is not EvidenceResolutionStatus.CANDIDATE
        or w4_floor.diagnostic_only is not True
        or not w4_floor.original_source_face_boundary_wall_ids
        or type(w4_floor.candidate_wall_length_m_by_w4_id) is not tuple
        or not w4_floor.candidate_wall_length_m_by_w4_id
        or type(w4_floor.figured_source_side_to_w4_wall_id) is not tuple
        or not w4_floor.figured_source_side_to_w4_wall_id
        or type(wall_heights) is not tuple
    ):
        return block("original_w4_measured_wall_length_source_unavailable")
    lengths={}
    for wall_id, value in w4_floor.candidate_wall_length_m_by_w4_id:
        if (
            type(wall_id) is not str or not wall_id or wall_id in lengths
            or type(value) not in (int,float)
        ):
            return block("original_w4_wall_length_record_conflict")
        try:n=float(value)
        except (TypeError,ValueError,OverflowError):
            return block("original_w4_wall_length_record_conflict")
        if not math.isfinite(n) or n<=0:
            return block("original_w4_wall_length_record_conflict")
        lengths[wall_id]=n
    if set(lengths)!=set(w4_floor.original_source_face_boundary_wall_ids):
        return block("original_w4_wall_length_universe_incomplete")
    memberships=[wall_id for _,wall_id in w4_floor.figured_source_side_to_w4_wall_id]
    if set(memberships)!=set(lengths):
        return block("original_w4_metric_side_wall_membership_conflict")
    by_wall={}
    for height in wall_heights:
        if type(height) is not QuantityEvidence or len(height.input_entity_ids)!=1:
            return block("original_w4_wall_height_record_untrusted")
        wall_id=height.input_entity_ids[0]
        if type(wall_id) is not str or not wall_id or wall_id in by_wall:
            return block("original_w4_wall_height_duplicate_identity")
        by_wall[wall_id]=height
    if set(by_wall)!=set(lengths):
        return block("original_w4_wall_height_universe_incomplete")
    areas=[]
    source_quantities=[]
    for wall_id,length in sorted(lengths.items()):
        height=by_wall[wall_id]
        meta=height.metadata
        if (
            height.family!=WALL_HEIGHT_FAMILY
            or height.semantic_key!=f"wall_height:{wall_id}"
            or height.status!=AuthorityStatus.FIRM.value
            or height.abstained or height.blocking_reasons or height.reason_codes
            or height.authority!=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
            or height.formula_version!=WALL_HEIGHT_FORMULA_VERSION
            or height.formula!="authoritative_explicit_wall_height"
            or height.unit!="m"
            or not height.evidence_ids
            or len(height.evidence_ids)!=1
            or type(height.value) not in (int,float)
            or not isinstance(meta,Mapping)
            or meta.get("source_sha256")!=w4_floor.source_sha256
            or meta.get("revision_id")!=w4_floor.revision_id
            or meta.get("target_entity_id")!=wall_id
            or meta.get("page_id")!=w4_floor.page_id
            or meta.get("evidence_kind") not in ("wall_height_dimension","wall_height_schedule")
            or not isinstance(meta.get("evidence_snapshot_id"),str)
            or not meta.get("evidence_snapshot_id")
            or not isinstance(meta.get("viewport_id"),str)
            or not meta.get("viewport_id")
        ):
            return block("original_w4_direct_wall_height_provenance_unavailable")
        try:meters=float(height.value)
        except (TypeError,ValueError,OverflowError):
            return block("original_w4_wall_height_value_invalid")
        if not math.isfinite(meters) or meters<=0:
            return block("original_w4_wall_height_value_invalid")
        areas.append((wall_id,length*meters))
        source_quantities.append((wall_id,height.quantity_id))
    total=math.fsum(area for _,area in areas)
    if not math.isfinite(total) or total<=0:
        return block("original_w4_wall_gross_lining_arithmetic_invalid")
    return SourceSealedW4GrossWallLiningShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_w4_issuer_height_bound_single_face_gross_shadow_only",),
        w4_floor.physical_room_id,w4_floor.canonical_floor_id,
        tuple(areas),tuple(sorted(lengths.items())),
        tuple(source_quantities),total,
    )
