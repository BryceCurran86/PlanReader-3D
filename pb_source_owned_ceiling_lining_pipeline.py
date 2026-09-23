"""Fully source-owned ceiling-lining shadow composition.

One already-ingested SourceVisibilityProducer is the evidence root. This module
derives, in order, producer-owned wall candidates, source room faces, trusted
ceiling-finish text, native graphic scale-bar calibration, room areas, and the
existing ceiling-lining shadow quantities.

Callers provide only normal execution context and viewport ownership. They do
not provide room polygons, finish text, text bboxes, scale values, wall
candidates, or quantity evidence.

Shadow-only: no GenericPlanReaderExtractor prediction, benchmark gold, scoring,
commercial takeoff, or JobHub publication is written here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from pb_geometry_takeoff_model import ScaleCalibration
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_scale_authority import (
    PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE,
    PhysicalScaleProducer,
    PhysicalScaleResult,
    PhysicalScaleSelector,
)
from pb_physical_scale_calibration_bridge import (
    PhysicalScaleCalibrationBridgeResult,
    build_physical_scale_calibration,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_ceiling_finish_evidence import (
    collect_source_owned_ceiling_finish_candidates,
)
from pb_source_ceiling_lining_shadow_pipeline import (
    SourceCeilingLiningShadowResult,
    run_source_ceiling_lining_shadow,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE_OWNED_CEILING_SHADOW_SCHEMA_VERSION = "1.0.0"
SOURCE_OWNED_CEILING_SHADOW_COMPOSED = "source_owned_ceiling_shadow_composed"
SOURCE_OWNED_CEILING_SHADOW_CONTEXT_MISMATCH = (
    "source_owned_ceiling_shadow_context_mismatch"
)
SOURCE_OWNED_CEILING_SHADOW_ROOM_AUTHORITY_UNAVAILABLE = (
    "source_owned_ceiling_shadow_room_authority_unavailable"
)


@dataclass(frozen=True)
class SourceOwnedCeilingLiningShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    effective_context: ProviderContext
    document: DocumentEvidence
    room_face_selector: SourceRoomFaceSelector
    finish_candidates: tuple[EvidenceAtom, ...]
    physical_scale_result: PhysicalScaleResult
    scale_bridge: PhysicalScaleCalibrationBridgeResult
    pipeline: SourceCeilingLiningShadowResult
    schema_version: str = SOURCE_OWNED_CEILING_SHADOW_SCHEMA_VERSION

    @property
    def room_area_quantities(self) -> tuple[QuantityEvidence, ...]:
        return self.pipeline.room_area_quantities

    @property
    def ceiling_quantities(self) -> tuple[QuantityEvidence, ...]:
        return self.pipeline.ceiling_quantities

    @property
    def scale_calibration(self) -> ScaleCalibration | None:
        return self.scale_bridge.calibration


def _document_from_source(
    *,
    published,
    finish_candidates: tuple[EvidenceAtom, ...],
) -> DocumentEvidence:
    page_count = int(published.coverage.total_pages)
    return DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        page_count=page_count,
        page_ids=tuple(str(index) for index in range(1, page_count + 1)),
        evidence_ids=tuple(sorted(atom.evidence_id for atom in finish_candidates)),
        producer=published.revision.producer_method,
        producer_version=published.revision.producer_version,
        metadata={
            "source_owned_ceiling_shadow": True,
            "source_snapshot_id": published.snapshot.snapshot_id,
        },
    )


def _entry_context_matches(
    *,
    published,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> bool:
    if not context.revision_id or not context.current_revision_id:
        return False
    if context.revision_id != context.current_revision_id:
        return False
    if published.revision.document_id != context.document_id:
        return False
    if published.revision.revision_id != context.current_revision_id:
        return False
    if published.revision.source_sha256 != context.source_sha256:
        return False
    if context.evidence_snapshot_id != published.snapshot.snapshot_id:
        return False
    if viewport.document_id != context.document_id:
        return False
    if viewport.viewport_id not in context.trusted_viewport_ids():
        return False
    if int(page_no) not in context.trusted_page_numbers():
        return False
    if viewport.page_id != str(int(page_no)):
        return False
    mapped = context.page_for_viewport(viewport.viewport_id)
    if mapped is not None and int(mapped) != int(page_no):
        return False
    return True


def _physical_scale(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    published,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> tuple[
    PhysicalScaleResult,
    PhysicalScaleSelector,
    PhysicalScaleCalibrationBridgeResult,
]:
    producer = PhysicalScaleProducer.from_source_visibility_producer(
        source_visibility_producer
    )
    scoped_selector = PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=viewport.page_id,
        viewport_id=viewport.viewport_id,
    )
    published_scale = producer.publish_scope(scoped_selector)
    selected = scoped_selector

    # A caller's viewport id may represent the whole page rather than a
    # segmented source viewport. Fall back to page-wide scale ONLY when the
    # sealed physical-scale producer says the scoped viewport is unavailable.
    # The page-wide call itself then succeeds only when that same producer
    # proves there is no usable segmented viewport.
    if published_scale.reason_codes == (PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE,):
        page_selector = PhysicalScaleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=viewport.page_id,
            viewport_id=None,
        )
        page_result = producer.publish_scope(page_selector)
        published_scale = page_result
        selected = page_selector

    authority = producer.authority()
    bridge = build_physical_scale_calibration(
        physical_scale_authority=authority,
        selector=selected,
        context=context,
        viewport=viewport,
        page_no=page_no,
    )
    return published_scale, selected, bridge


def run_source_owned_ceiling_lining_shadow(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> SourceOwnedCeilingLiningShadowResult:
    """Run the complete producer-owned ceiling-lining shadow path."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be producer-owned SourceVisibilityProducer"
        )

    revision_id = str(context.current_revision_id or "")
    entry = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if entry is None or not _entry_context_matches(
        published=entry,
        context=context,
        viewport=viewport,
        page_no=page_no,
    ):
        # Build an empty but well-formed result shell using the caller context.
        empty_document = DocumentEvidence(
            document_id=context.document_id,
            source_sha256=context.source_sha256,
            page_count=0,
            page_ids=(),
            evidence_ids=(),
            producer="source_owned_ceiling_shadow",
            producer_version=SOURCE_OWNED_CEILING_SHADOW_SCHEMA_VERSION,
        )
        selector = SourceRoomFaceSelector(
            document_id=context.document_id,
            revision_id=revision_id or "unbound",
            source_sha256=context.source_sha256,
            snapshot_id=context.evidence_snapshot_id,
            page_id=str(int(page_no)),
            decision_scope_id=f"wall-source:page-{int(page_no)}",
        )
        # Reuse empty authorities through the existing pipeline is impossible
        # without a sealed room authority, so context mismatch is raised as an
        # explicit boundary error rather than fabricating evidence objects.
        raise ValueError(SOURCE_OWNED_CEILING_SHADOW_CONTEXT_MISMATCH)

    # Building physical wall candidates is allowed to augment the producer
    # snapshot with producer-owned raster-visible segments.
    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source_visibility_producer,
        page_ids=(viewport.page_id,),
    )
    post = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if post is None:
        raise RuntimeError(SOURCE_OWNED_CEILING_SHADOW_CONTEXT_MISMATCH)

    # Rebind only when THIS trusted wall-build operation advanced the exact
    # entry snapshot. Arbitrary stale caller contexts were rejected above.
    effective_context = (
        context
        if post.snapshot.snapshot_id == entry.snapshot.snapshot_id
        else replace(context, evidence_snapshot_id=post.snapshot.snapshot_id)
    )

    room_face_authority = build_source_room_face_authority(
        wall_producer.authority()
    )
    room_selector = SourceRoomFaceSelector(
        document_id=post.revision.document_id,
        revision_id=post.revision.revision_id,
        source_sha256=post.revision.source_sha256,
        snapshot_id=post.snapshot.snapshot_id,
        page_id=viewport.page_id,
        decision_scope_id=f"wall-source:page-{viewport.page_id}",
    )
    room_result = room_face_authority.resolve_scope(room_selector)

    finish_candidates = collect_source_owned_ceiling_finish_candidates(
        source_visibility_producer=source_visibility_producer,
        context=effective_context,
        viewport=viewport,
        page_no=page_no,
    )
    document = _document_from_source(
        published=post,
        finish_candidates=finish_candidates,
    )

    physical_scale_result, _scale_selector, scale_bridge = _physical_scale(
        source_visibility_producer=source_visibility_producer,
        published=post,
        context=effective_context,
        viewport=viewport,
        page_no=page_no,
    )

    pipeline = run_source_ceiling_lining_shadow(
        room_face_authority=room_face_authority,
        selector=room_selector,
        context=effective_context,
        document=document,
        viewport=viewport,
        page_no=page_no,
        unscoped_finish_candidates=finish_candidates,
        scale_calibration=scale_bridge.calibration,
    )

    if (
        room_result.status is not EvidenceResolutionStatus.CORROBORATED
        or not room_result.scope_complete
        or not room_result.records
    ):
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            SOURCE_OWNED_CEILING_SHADOW_ROOM_AUTHORITY_UNAVAILABLE,
            *room_result.reason_codes,
        )
    else:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (SOURCE_OWNED_CEILING_SHADOW_COMPOSED,)

    return SourceOwnedCeilingLiningShadowResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(reasons)),
        effective_context=effective_context,
        document=document,
        room_face_selector=room_selector,
        finish_candidates=finish_candidates,
        physical_scale_result=physical_scale_result,
        scale_bridge=scale_bridge,
        pipeline=pipeline,
    )


__all__ = [
    "SOURCE_OWNED_CEILING_SHADOW_COMPOSED",
    "SOURCE_OWNED_CEILING_SHADOW_CONTEXT_MISMATCH",
    "SOURCE_OWNED_CEILING_SHADOW_ROOM_AUTHORITY_UNAVAILABLE",
    "SOURCE_OWNED_CEILING_SHADOW_SCHEMA_VERSION",
    "SourceOwnedCeilingLiningShadowResult",
    "run_source_owned_ceiling_lining_shadow",
]
