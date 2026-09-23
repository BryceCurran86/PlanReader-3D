"""Shadow-only end-to-end source room -> room area -> ceiling lining pipeline.

This module composes existing authorities without creating new authority:

SourceRoomFaceAuthority
  -> build_source_room_area_bridge
  -> CeilingLiningShadowProvider

It never writes live ExtractedPrediction rows, benchmark definitions,
commercial takeoff rows, or JobHub payloads.  Ceiling lining remains
PROVISIONAL/BLOCKED exactly as governed by the existing provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from pb_ceiling_lining_shadow_provider import (
    CeilingLiningShadowInputs,
    CeilingLiningShadowProvider,
)
from pb_geometry_takeoff_model import ScaleCalibration
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    QuantityEvidence,
    ViewportEvidence,
)
from pb_migration_provider_envelope import ProviderContext, ProviderResult
from pb_source_room_area_bridge import (
    SourceRoomAreaBridgeResult,
    build_source_room_area_bridge,
)
from pb_source_room_face_authority import (
    SourceRoomFaceAuthority,
    SourceRoomFaceSelector,
)


SOURCE_CEILING_PIPELINE_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class SourceCeilingLiningShadowResult:
    room_area_bridge: SourceRoomAreaBridgeResult
    ceiling_result: ProviderResult
    schema_version: str = SOURCE_CEILING_PIPELINE_SCHEMA_VERSION

    @property
    def room_area_quantities(self) -> tuple[QuantityEvidence, ...]:
        return self.room_area_bridge.quantities

    @property
    def ceiling_quantities(self) -> tuple[QuantityEvidence, ...]:
        return tuple(self.ceiling_result.quantities)


def run_source_ceiling_lining_shadow(
    *,
    room_face_authority: SourceRoomFaceAuthority,
    selector: SourceRoomFaceSelector,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
    unscoped_finish_candidates: Sequence[EvidenceAtom],
    scale_calibration: Optional[ScaleCalibration] = None,
    explicit_area_evidence_by_room_id: Optional[Mapping[str, EvidenceAtom]] = None,
) -> SourceCeilingLiningShadowResult:
    """Run the authenticated room-area and ceiling-lining shadow chain.

    The room-area bridge independently enforces room ownership and delegates
    metric authority to build_room_area_quantities.  The ceiling provider then
    independently rebinds finish evidence to the same producer-owned room-face
    authority.  No status or quantity is promoted here.
    """

    room_area = build_source_room_area_bridge(
        room_face_authority=room_face_authority,
        selector=selector,
        context=context,
        document=document,
        viewport=viewport,
        page_no=page_no,
        scale_calibration=scale_calibration,
        explicit_area_evidence_by_room_id=explicit_area_evidence_by_room_id,
    )

    provider = CeilingLiningShadowProvider(
        inputs=CeilingLiningShadowInputs(
            document=room_area.document,
            viewport=viewport,
            page_no=page_no,
            authoritative_area_quantities=tuple(room_area.quantities),
            unscoped_finish_candidates=tuple(unscoped_finish_candidates),
            source_room_face_authority=room_face_authority,
            source_room_face_selector=selector,
        )
    )
    ceiling = provider.extract(context)
    return SourceCeilingLiningShadowResult(
        room_area_bridge=room_area,
        ceiling_result=ceiling,
    )


__all__ = [
    "SOURCE_CEILING_PIPELINE_SCHEMA_VERSION",
    "SourceCeilingLiningShadowResult",
    "run_source_ceiling_lining_shadow",
]
