"""Source-figured physical opening reveals and frame lengths — shadow only.

Separate door and window opening semantics come from independent schedule and
physical opening authority, not callout suffix or a default opening type.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class DocumentedPhysicalOpeningFrame:
    physical_opening_id: str
    source_opening_kind: str
    width_mm: float
    height_mm: float
    structural_reveal_depth_mm: float
    source_width_dimension_id: str
    source_height_dimension_id: str
    source_depth_dimension_id: str
    physical_host_wall_id: str
    host_binding_receipt_ids: tuple[str,...]
    original_source_frame_receipt_ids: tuple[str,...]
    source_sha256: str
    revision_id: str
    page_id: str


@dataclass(frozen=True)
class FiguredOpeningRevealShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    candidate_reveal_surface_m2: float | None
    candidate_frame_linear_m: float | None
    candidate_structural_void_area_m2: float | None
    source_dimension_ids: tuple[str,...]
    diagnostic_only: bool = True


def measure_source_figured_opening_reveals_shadow(
    opening: DocumentedPhysicalOpeningFrame,
) -> FiguredOpeningRevealShadow:
    """Three sides for a door, four for a window; no invented sill or height."""
    def block(reason):
        return FiguredOpeningRevealShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),None,None,None,()
        )
    if type(opening) is not DocumentedPhysicalOpeningFrame:
        return block("original_opening_reveal_record_untrusted")
    if opening.source_opening_kind not in ("door","window"):
        return block("original_opening_reveal_semantic_kind_unavailable")
    identity=(opening.physical_opening_id,opening.physical_host_wall_id,
              opening.source_sha256,opening.revision_id,opening.page_id,
              opening.source_width_dimension_id,opening.source_height_dimension_id,
              opening.source_depth_dimension_id)
    if (
        any(type(v) is not str or not v or v!=v.strip() for v in identity)
        or len(set(identity[-3:])) != 3
        or type(opening.host_binding_receipt_ids) not in (list,tuple)
        or type(opening.original_source_frame_receipt_ids) not in (list,tuple)
        or not opening.host_binding_receipt_ids or not opening.original_source_frame_receipt_ids
        or any(type(v) is not str or not v for v in
               (*opening.host_binding_receipt_ids,*opening.original_source_frame_receipt_ids))
        or set(opening.host_binding_receipt_ids).intersection(
            opening.original_source_frame_receipt_ids
        )
    ):
        return block("original_opening_reveal_source_lineage_unavailable")
    dimensions=[]
    for value in (
        opening.width_mm,opening.height_mm,opening.structural_reveal_depth_mm
    ):
        if type(value) not in (int,float):
            return block("original_opening_reveal_documented_dimensions_unavailable")
        try:
            dim=float(value)
        except (TypeError,ValueError,OverflowError):
            return block("original_opening_reveal_documented_dimensions_unavailable")
        if not math.isfinite(dim) or dim<=0:
            return block("original_opening_reveal_documented_dimensions_unavailable")
        dimensions.append(dim)
    width,height,depth=dimensions
    if depth>width or depth>height:
        return block("original_opening_reveal_structural_depth_conflict")
    vertical_and_head=2*height+width
    all_reveals=vertical_and_head + (width if opening.source_opening_kind=="window" else 0)
    area=all_reveals*depth/1_000_000.0
    frame_length=all_reveals/1000.0
    clear_void=width*height/1_000_000.0
    if not all(math.isfinite(x) and x>0 for x in (area,frame_length,clear_void)):
        return block("original_opening_reveal_measurement_unrepresentable")
    return FiguredOpeningRevealShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_opening_reveal_figured_shadow_only",),
        area,frame_length,clear_void,
        tuple(sorted(identity[-3:])),
    )
