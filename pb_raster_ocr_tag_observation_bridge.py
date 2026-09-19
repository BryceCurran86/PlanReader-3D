"""Producer-owned raster OCR -> opening TagObservation bridge.

This module is intentionally narrow. It does not run OCR itself and it never
decides opening identity. It consumes only OCR observations published by
SourceVisibilityProducer.publish_page_raster_ocr_observations(), restricts them
to an authenticated, complete floor-plan viewport, filters to explicit generic
opening tags, and converts those source observations into sealed TagObservation
objects understood by OpeningIdentityResolver and the CLOS pre-filter.

Authority boundary:
- OCR text remains evidence-only.
- A returned TagObservation proves only that the producer observed a textual
  opening-like tag inside the authenticated floor-plan viewport.
- It does not prove that the tag belongs to any physical aperture.
- CLOS/proximity still cannot mint PROVEN_SAME.
- Commercial counts remain out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_tag_normalization import normalize_opening_tag
from pb_source_observation_authority import ObservationSelector
from pb_source_opening_candidate_authority import (
    AuthenticatedViewportDecision,
    TagObservation,
)
from pb_source_visibility_authority import (
    RASTER_OCR_SOURCE_OBSERVATION_EXISTS,
    SourceVisibilityProducer,
)
from pb_viewport_view_class_authority import VIEW_KIND_FLOOR_PLAN


RASTER_OCR_TAG_BRIDGE_SCHEMA_VERSION = "1.0.0"

RASTER_OCR_TAG_BRIDGE_RESOLVED = "raster_ocr_tag_bridge_resolved"
RASTER_OCR_TAG_BRIDGE_VIEWPORT_UNAUTHENTICATED = (
    "raster_ocr_tag_bridge_viewport_unauthenticated"
)
RASTER_OCR_TAG_BRIDGE_SCOPE_MISMATCH = "raster_ocr_tag_bridge_scope_mismatch"
RASTER_OCR_TAG_BRIDGE_NO_TAGS = "raster_ocr_tag_bridge_no_explicit_opening_tags"

_BRIDGE_SEAL = object()


@dataclass(frozen=True)
class RasterOCRTagBridgeResult:
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    tags: Tuple[TagObservation, ...] = ()
    schema_version: str = RASTER_OCR_TAG_BRIDGE_SCHEMA_VERSION


class RasterOCRTagObservationBridge:
    """Read-only bridge from receipted OCR source observations to tags.

    Obtain instances through create(). The bridge cannot write source
    observations and cannot create OCR records from caller-authored text.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _BRIDGE_SEAL:
            raise TypeError(
                "RasterOCRTagObservationBridge must be obtained from create()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be exact SourceVisibilityProducer"
            )
        self._source_visibility_producer = source_visibility_producer

    @classmethod
    def create(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "RasterOCRTagObservationBridge":
        return cls(source_visibility_producer, _seal=_BRIDGE_SEAL)

    @staticmethod
    def _bbox_inside(
        inner: tuple[float, float, float, float],
        outer: tuple[float, float, float, float],
    ) -> bool:
        ix0, iy0, ix1, iy1 = inner
        ox0, oy0, ox1, oy1 = outer
        return (
            min(ox0, ox1) <= min(ix0, ix1)
            and min(oy0, oy1) <= min(iy0, iy1)
            and max(ix0, ix1) <= max(ox0, ox1)
            and max(iy0, iy1) <= max(oy0, oy1)
        )

    def produce_for_viewport(
        self,
        viewport_decision: AuthenticatedViewportDecision,
    ) -> RasterOCRTagBridgeResult:
        """Return producer-owned explicit opening tags inside one floor plan.

        The viewport must already be authenticated by
        authenticate_viewport_decision(). A caller-authored viewport, stale
        snapshot, cropped viewport, or non-floor-plan view fails closed.
        """
        if type(viewport_decision) is not AuthenticatedViewportDecision:
            raise TypeError(
                "viewport_decision must be AuthenticatedViewportDecision"
            )

        viewport = viewport_decision.viewport
        selector = viewport_decision.selector
        if (
            viewport_decision.status is not EvidenceResolutionStatus.CORROBORATED
            or viewport_decision.view_kind != VIEW_KIND_FLOOR_PLAN
            or not viewport_decision.is_uncropped
            or selector is None
            or viewport.bounding_box is None
        ):
            return RasterOCRTagBridgeResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(RASTER_OCR_TAG_BRIDGE_VIEWPORT_UNAUTHENTICATED,),
            )

        current = self._source_visibility_producer.published_snapshot_for_revision(
            selector.revision_id
        )
        if (
            current is None
            or current.revision.document_id != selector.document_id
            or current.revision.revision_id != selector.revision_id
            or current.revision.source_sha256 != selector.source_sha256
            or current.snapshot.snapshot_id != selector.snapshot_id
            or viewport.view_id != selector.viewport_id
        ):
            return RasterOCRTagBridgeResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(RASTER_OCR_TAG_BRIDGE_SCOPE_MISMATCH,),
            )

        page_id = str(viewport.page_number)
        viewport_bbox = tuple(float(v) for v in viewport.bounding_box)
        ocr_authority = self._source_visibility_producer.raster_ocr_authority()

        tags: list[TagObservation] = []
        seen_ids: set[str] = set()
        for observation_id in current.snapshot.observation_ids:
            resolved = ocr_authority.resolve_ocr(
                ObservationSelector(
                    document_id=current.revision.document_id,
                    revision_id=current.revision.revision_id,
                    source_sha256=current.revision.source_sha256,
                    snapshot_id=current.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = resolved.observation
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or resolved.proposition != RASTER_OCR_SOURCE_OBSERVATION_EXISTS
                or observation is None
                or observation.page_id != page_id
                or len(observation.geometry) < 4
            ):
                continue

            bbox = tuple(float(v) for v in observation.geometry[:4])
            if not self._bbox_inside(bbox, viewport_bbox):
                continue

            normalized = normalize_opening_tag(observation.raw_text)
            if normalized is None:
                continue
            if observation.observation_id in seen_ids:
                continue

            tags.append(
                TagObservation.from_source_observation(
                    observation,
                    viewport_id=viewport.view_id,
                )
            )
            seen_ids.add(observation.observation_id)

        if not tags:
            return RasterOCRTagBridgeResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(RASTER_OCR_TAG_BRIDGE_NO_TAGS,),
            )

        tags.sort(
            key=lambda tag: (
                tag.bounding_box[1],
                tag.bounding_box[0],
                tag.observation_id,
            )
        )
        return RasterOCRTagBridgeResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(RASTER_OCR_TAG_BRIDGE_RESOLVED,),
            tags=tuple(tags),
        )


__all__ = [
    "RASTER_OCR_TAG_BRIDGE_NO_TAGS",
    "RASTER_OCR_TAG_BRIDGE_RESOLVED",
    "RASTER_OCR_TAG_BRIDGE_SCHEMA_VERSION",
    "RASTER_OCR_TAG_BRIDGE_SCOPE_MISMATCH",
    "RASTER_OCR_TAG_BRIDGE_VIEWPORT_UNAUTHENTICATED",
    "RasterOCRTagBridgeResult",
    "RasterOCRTagObservationBridge",
]
