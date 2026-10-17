"""Join authentic same/cross-view published figured room area to a physical metric ring.

This does not publish an area. It binds a SOURCE PRODUCER RECORD to an
independent source-figured polygon candidate and an existing live canonical
floor, identifying the first missing authority without duplicate issuer logic.

Only records minted by original room-area producers are consumed. Candidate
computed m² can corroborate the original area but cannot replace, round, or
revise the issued EvidenceAtom nor become FIRM through this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections import Counter
from typing import Mapping

from pb_cross_view_room_area_authority import (
    CrossViewRoomAreaRecord, CrossViewRoomAreaResult,
)
from pb_same_view_room_area_authority import (
    SameViewRoomAreaRecord, SameViewRoomAreaResult,
)
from pb_cross_view_floor_finish_authority import (
    _matching_floor, _unique_documented_area_owner_receipts,
)
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceComposition
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalFiguredAreaProducerRingBinding:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    canonical_floor_id: str
    original_room_face_id: str
    original_physical_room_id: str
    original_figured_area_evidence_id: str | None
    original_room_area_m2: float | None
    original_figure_ids: tuple[str, ...]
    independently_calculated_polygon_m2: float | None
    diagnostic_only: bool = True


def bind_producer_figured_area_to_original_room_ring_shadow(
    physical_ring: FiguredPolygonMetricShadow,
    *,
    same_view: SameViewRoomAreaResult | None,
    cross_view: CrossViewRoomAreaResult | None,
    canonical_floors: LiveCanonicalFloorSurfaceComposition,
    original_room_face_id: str,
) -> OriginalFiguredAreaProducerRingBinding:
    """Exact original source face and physical room, never nearest/label."""
    def block(reason: str):
        return OriginalFiguredAreaProducerRingBinding(
            EvidenceResolutionStatus.ABSTAINED, (reason,), "",
            str(original_room_face_id), str(getattr(physical_ring,"physical_room_id","")),
            None, None, (), None,
        )
    if (
        type(physical_ring) is not FiguredPolygonMetricShadow
        or physical_ring.status is not EvidenceResolutionStatus.CANDIDATE
        or physical_ring.diagnostic_only is not True
        or type(canonical_floors) is not LiveCanonicalFloorSurfaceComposition
        or (same_view is not None and type(same_view) is not SameViewRoomAreaResult)
        or (cross_view is not None and type(cross_view) is not CrossViewRoomAreaResult)
        or (same_view is None and cross_view is None)
        or type(original_room_face_id) is not str or not original_room_face_id
    ):
        return block("source_producer_figured_ring_inputs_unavailable")
    # Reuse production precedence and collision quarantine: two source
    # measurements of one face do NOT each become a separate takeoff.
    by_source, disputed = _unique_documented_area_owner_receipts(
        same_view.records if same_view is not None else (),
        cross_view.records if cross_view is not None else (),
    )
    if original_room_face_id in disputed:
        return block("source_producer_figured_room_owner_conflict")
    record = by_source.get(original_room_face_id)
    if type(record) not in (SameViewRoomAreaRecord,CrossViewRoomAreaRecord):
        return block("source_producer_original_figured_area_unavailable")
    floor = _matching_floor(canonical_floors, record)
    if floor is None:
        return block("source_producer_figured_canonical_floor_binding_unavailable")
    metadata = record.area_evidence.metadata
    if not isinstance(metadata, Mapping):
        return block("source_producer_figured_area_lineage_unavailable")
    raw_dims = metadata.get("figured_dimension_ids")
    if (
        type(raw_dims) not in (tuple,list)
        or len(raw_dims)!=2
        or any(type(v) is not str or not v or v!=v.strip() for v in raw_dims)
        or len(set(raw_dims))!=2
    ):
        return block("source_producer_figured_dimension_source_ids_unavailable")
    if (
        record.physical_room_id != physical_ring.physical_room_id
        or floor.source_sha256 != physical_ring.source_sha256
        or floor.revision_id != physical_ring.revision_id
        or floor.page_id != physical_ring.page_id
        or floor.source_room_face_record_id != original_room_face_id
        or not set(raw_dims).issubset(set(physical_ring.source_figure_ids))
    ):
        return block("source_producer_figured_polygon_physical_scope_conflict")
    if (
        type(physical_ring.candidate_area_m2) is not float
        or not math.isfinite(physical_ring.candidate_area_m2)
        or physical_ring.candidate_area_m2<=0
    ):
        return block("source_producer_figured_polygon_unmeasured")
    try: source_area=float(record.area_evidence.normalized_value)
    except (TypeError,ValueError,OverflowError):
        return block("source_producer_figured_original_area_numeric_invalid")
    # Producers round original dimension products to 6 decimal places; this
    # bridge only compares independent numbers and never modifies either.
    if (
        not math.isfinite(source_area) or source_area<=0
        or not math.isclose(
            source_area,physical_ring.candidate_area_m2,
            abs_tol=5e-7,rel_tol=0,
        )
    ):
        return block("source_producer_figured_polygon_area_disagreement")
    return OriginalFiguredAreaProducerRingBinding(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_source_producer_figured_ring_confirmed_shadow_only",),
        floor.canonical_floor_id, original_room_face_id,
        record.physical_room_id,record.area_evidence.evidence_id,
        source_area,tuple(sorted(raw_dims)),
        physical_ring.candidate_area_m2,
    )
