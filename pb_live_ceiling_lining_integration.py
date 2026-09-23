"""Fail-closed live ceiling-lining prediction boundary.

This module is the production bridge from the fully source-owned ceiling shadow
chain into GenericPlanReaderExtractor. It does not read benchmark IDs, mappings,
expected quantities, project names, or filenames as prediction features.

A single document-level ceiling_lining quantity is emitted only when:
- exactly one floor-plan viewport exists across the requested extraction scope;
- that viewport is F.07 RESOLVED and has an owned bounding box;
- every authenticated room in that viewport has a FIRM PDF-scaled area;
- every such room has one non-abstained source-owned ceiling-finish claim;
- all room finish descriptors agree on one finish system;
- the physical scale bridge is corroborated from native graphic scale evidence;
- every ceiling quantity exactly reuses its own same-scope FIRM room area.

Multiple floor plans are not summed because cross-viewport/cross-page physical
identity is not yet proven. Partial room coverage never becomes a building
total. The resulting quantity is live extraction evidence only; commercial
review remains governed by the separate ceiling review-promotion boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Optional, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import measurement_authority_for_page_scale
from pb_source_ceiling_finish_evidence import SOURCE_CEILING_FINISH_METHOD
from pb_source_owned_ceiling_lining_pipeline import (
    run_source_owned_ceiling_lining_shadow,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    segment_page_viewports,
)


LIVE_CEILING_LINING_SCHEMA_VERSION = "1.0.0"
LIVE_CEILING_LINING_RESOLVED = "live_ceiling_lining_resolved"
LIVE_CEILING_LINING_NO_FLOOR_PLAN = "live_ceiling_lining_no_floor_plan"
LIVE_CEILING_LINING_SCOPE_NOT_UNIQUE = "live_ceiling_lining_scope_not_unique"
LIVE_CEILING_LINING_VIEWPORT_NOT_RESOLVED = "live_ceiling_lining_viewport_not_resolved"
LIVE_CEILING_LINING_ROOM_AUTHORITY_UNAVAILABLE = (
    "live_ceiling_lining_room_authority_unavailable"
)
LIVE_CEILING_LINING_AREA_UNAVAILABLE = "live_ceiling_lining_area_unavailable"
LIVE_CEILING_LINING_FINISH_INCOMPLETE = "live_ceiling_lining_finish_incomplete"
LIVE_CEILING_LINING_FINISH_CONFLICT = "live_ceiling_lining_finish_conflict"
LIVE_CEILING_LINING_SCALE_UNAVAILABLE = "live_ceiling_lining_scale_unavailable"
LIVE_CEILING_LINING_VALUE_INVALID = "live_ceiling_lining_value_invalid"


@dataclass(frozen=True)
class LiveCeilingLiningResolution:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    quantity_m2: Optional[float] = None
    finish_descriptor: str = ""
    source_page: Optional[int] = None
    viewport_id: str = ""
    viewport_bbox: Optional[tuple[float, float, float, float]] = None
    confidence: float = 0.0
    room_entity_ids: tuple[str, ...] = ()
    room_area_quantity_ids: tuple[str, ...] = ()
    ceiling_quantity_ids: tuple[str, ...] = ()
    physical_scale_record_id: str = ""
    source_sha256: str = ""
    revision_id: str = ""
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION


def _blocked(
    reason: str,
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
    source_sha256: str = "",
    revision_id: str = "",
) -> LiveCeilingLiningResolution:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return LiveCeilingLiningResolution(
        status=status,
        reason_codes=(reason,),
        source_sha256=source_sha256,
        revision_id=revision_id,
    )


def _norm(value: object) -> str:
    return " ".join(str(value if value is not None else "").split()).strip().casefold()


def resolve_live_ceiling_lining(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
) -> LiveCeilingLiningResolution:
    """Resolve one generic live ceiling-lining prediction or abstain.

    Pages use zero-based extractor page indexes, matching extract_from_pdf.
    """

    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF file not found at: {path}")

    source_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    document_id = f"live-ceiling:{source_sha256[:32]}"

    source = SourceVisibilityProducer(
        producer_method="live_ceiling_lining",
        producer_version=LIVE_CEILING_LINING_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=source_bytes,
        source_locator="live_extractor_source",
    )

    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        target_pages = (
            list(range(pdf.page_count))
            if pages is None
            else [int(index) for index in pages]
        )
        floor_plans = []
        for page_index in target_pages:
            if page_index < 0 or page_index >= pdf.page_count:
                continue
            page = pdf.load_page(page_index)
            for viewport in segment_page_viewports(
                page,
                page_number=page_index + 1,
            ):
                if viewport.view_type == DrawingViewType.FLOOR_PLAN.value:
                    floor_plans.append(viewport)
    finally:
        pdf.close()

    if not floor_plans:
        return _blocked(
            LIVE_CEILING_LINING_NO_FLOOR_PLAN,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    if len(floor_plans) != 1:
        return _blocked(
            LIVE_CEILING_LINING_SCOPE_NOT_UNIQUE,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    floor_plan = floor_plans[0]
    if (
        floor_plan.status != ViewportSegmentationStatus.RESOLVED.value
        or floor_plan.bounding_box is None
    ):
        return _blocked(
            LIVE_CEILING_LINING_VIEWPORT_NOT_RESOLVED,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    page_no = int(floor_plan.page_number)
    viewport_id = str(floor_plan.view_id)
    viewport_bbox = tuple(float(value) for value in floor_plan.bounding_box)

    viewport = ViewportEvidence(
        viewport_id=viewport_id,
        document_id=published.revision.document_id,
        page_id=str(page_no),
        bbox=viewport_bbox,
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=float(floor_plan.confidence),
    )
    context = ProviderContext(
        run_id=f"live-ceiling-run:{source_sha256[:20]}",
        workspace_id="live-extractor",
        project_id="live-extractor",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(page_no - 1,),
        owned_viewport_ids=(viewport_id,),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(page_no,),
        viewport_page_ownership=((viewport_id, page_no),),
    )

    result = run_source_owned_ceiling_lining_shadow(
        source_visibility_producer=source,
        context=context,
        viewport=viewport,
        page_no=page_no,
    )

    if result.status is not EvidenceResolutionStatus.CORROBORATED:
        return _blocked(
            LIVE_CEILING_LINING_ROOM_AUTHORITY_UNAVAILABLE,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    scale_bridge = result.scale_bridge
    calibration = scale_bridge.calibration
    scale_evidence = scale_bridge.physical_scale_evidence
    if (
        scale_bridge.status is not EvidenceResolutionStatus.CORROBORATED
        or calibration is None
        or scale_evidence is None
        or not scale_evidence.record_id
        or measurement_authority_for_page_scale(calibration)
        != AuthorityStatus.FIRM.value
    ):
        return _blocked(
            LIVE_CEILING_LINING_SCALE_UNAVAILABLE,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    areas = tuple(result.room_area_quantities)
    ceilings = tuple(result.ceiling_quantities)
    if not areas or len(areas) != len(ceilings):
        return _blocked(
            LIVE_CEILING_LINING_AREA_UNAVAILABLE,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    area_by_id = {area.quantity_id: area for area in areas}
    room_ids: list[str] = []
    finish_descriptors: list[str] = []
    values: list[float] = []
    confidences: list[float] = []

    for area in areas:
        if (
            area.abstained
            or area.value is None
            or area.status != AuthorityStatus.FIRM.value
            or area.authority != MeasurementAuthorityType.PDF_SCALED.value
            or len(area.input_entity_ids) != 1
            or area.blocking_reasons
        ):
            return _blocked(
                LIVE_CEILING_LINING_AREA_UNAVAILABLE,
                source_sha256=source_sha256,
                revision_id=published.revision.revision_id,
            )

    for ceiling in ceilings:
        metadata = ceiling.metadata if isinstance(ceiling.metadata, dict) else {}
        upstream_id = str(metadata.get("upstream_area_quantity_id") or "")
        upstream = area_by_id.get(upstream_id)
        descriptor = str(metadata.get("finish_descriptor") or "").strip()
        methods = tuple(
            str(value) for value in (metadata.get("finish_source_methods") or ())
        )
        if (
            ceiling.abstained
            or ceiling.value is None
            or ceiling.status != AuthorityStatus.PROVISIONAL.value
            or ceiling.authority != MeasurementAuthorityType.MODEL_DERIVED.value
            or ceiling.blocking_reasons
            or metadata.get("shadow_only") is not True
            or metadata.get("commercial_projection_allowed") is not False
            or upstream is None
            or len(ceiling.input_entity_ids) != 1
            or ceiling.input_entity_ids != upstream.input_entity_ids
            or float(ceiling.value) != float(upstream.value)
            or not descriptor
            or SOURCE_CEILING_FINISH_METHOD not in methods
        ):
            return _blocked(
                LIVE_CEILING_LINING_FINISH_INCOMPLETE,
                source_sha256=source_sha256,
                revision_id=published.revision.revision_id,
            )
        room_ids.append(ceiling.input_entity_ids[0])
        finish_descriptors.append(descriptor)
        values.append(float(ceiling.value))
        confidences.append(float(ceiling.confidence))

    if len(set(room_ids)) != len(room_ids):
        return _blocked(
            LIVE_CEILING_LINING_ROOM_AUTHORITY_UNAVAILABLE,
            status=EvidenceResolutionStatus.CONFLICT,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    normalized_finishes = {_norm(value) for value in finish_descriptors}
    if len(normalized_finishes) != 1:
        return _blocked(
            LIVE_CEILING_LINING_FINISH_CONFLICT,
            status=EvidenceResolutionStatus.CONFLICT,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    total = math.fsum(values)
    if not math.isfinite(total) or total <= 0.0:
        return _blocked(
            LIVE_CEILING_LINING_VALUE_INVALID,
            status=EvidenceResolutionStatus.CONFLICT,
            source_sha256=source_sha256,
            revision_id=published.revision.revision_id,
        )

    return LiveCeilingLiningResolution(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(LIVE_CEILING_LINING_RESOLVED,),
        quantity_m2=round(total, 6),
        finish_descriptor=finish_descriptors[0],
        source_page=page_no,
        viewport_id=viewport_id,
        viewport_bbox=viewport_bbox,
        confidence=min(confidences) if confidences else 0.0,
        room_entity_ids=tuple(sorted(room_ids)),
        room_area_quantity_ids=tuple(sorted(area.quantity_id for area in areas)),
        ceiling_quantity_ids=tuple(
            sorted(ceiling.quantity_id for ceiling in ceilings)
        ),
        physical_scale_record_id=scale_evidence.record_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
    )


__all__ = [
    "LIVE_CEILING_LINING_AREA_UNAVAILABLE",
    "LIVE_CEILING_LINING_FINISH_CONFLICT",
    "LIVE_CEILING_LINING_FINISH_INCOMPLETE",
    "LIVE_CEILING_LINING_NO_FLOOR_PLAN",
    "LIVE_CEILING_LINING_RESOLVED",
    "LIVE_CEILING_LINING_ROOM_AUTHORITY_UNAVAILABLE",
    "LIVE_CEILING_LINING_SCALE_UNAVAILABLE",
    "LIVE_CEILING_LINING_SCHEMA_VERSION",
    "LIVE_CEILING_LINING_SCOPE_NOT_UNIQUE",
    "LIVE_CEILING_LINING_VALUE_INVALID",
    "LIVE_CEILING_LINING_VIEWPORT_NOT_RESOLVED",
    "LiveCeilingLiningResolution",
    "resolve_live_ceiling_lining",
]
