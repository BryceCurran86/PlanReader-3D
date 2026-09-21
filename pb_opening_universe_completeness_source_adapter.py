"""Source-authenticated primitive-coverage adapter for opening completeness.

IMPORTANT: complete decoding of visible PDF segments is NOT proof that the
semantic physical-opening universe is complete. This adapter intentionally
publishes source coverage only and NEVER attaches the private
`_SOURCE_AUTHENTICATED_COMPLETENESS_SEAL` consumed by
`GenericOpeningCountAuthority`.

The previous implementation fed the same visible-segment collection to both
`source_primitives` and `enumerated_primitives`, then attached the commercial
completeness seal. That could prove only "all decoded visible segments were
accounted for", while downstream code interpreted the resulting member ids as
physical-opening competitors. Six G17 support segments for one opening (plus
ordinary wall/dimension/annotation geometry) therefore had the wrong semantic
contract.

A future source-authenticated semantic-opening enumerator must earn the
commercial seal only after it proves a complete set of physical-opening
competitors. Until that producer exists, this adapter remains deliberately
fail-closed for commercial counts.
"""
from __future__ import annotations

from collections.abc import Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_generic_opening_count_authority import (
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessProducer,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
    SemanticOpeningEnumerationSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


class _RealVisiblePrimitive:
    """Adapter over one producer-owned, clip-verified visible segment."""

    __slots__ = (
        "primitive_id",
        "page_id",
        "geometry",
        "layer",
        "clip_known",
        "clip_present",
        "clip",
    )

    def __init__(
        self,
        *,
        primitive_id: str,
        page_id: str,
        geometry: tuple[float, ...],
    ) -> None:
        self.primitive_id = primitive_id
        self.page_id = page_id
        self.geometry = geometry
        self.layer = ""
        self.clip_known = True
        self.clip_present = False
        self.clip = None


def build_source_authenticated_opening_universe_completeness(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    decision_scope_id: str,
    decision_scope_kind: str,
    page_ids: Sequence[str],
    optional_content_known_visible: bool = False,
    xobject_traversal_truncated: bool = False,
) -> OpeningUniverseCompletenessAuthority:
    """Publish authenticated primitive coverage, never semantic completeness.

    This compatibility name is retained because callers/tests already import
    it, but the returned authority is intentionally NOT commercially sealed.

    `source_primitives` are the complete visible-segment observations in the
    requested source scope. `enumerated_primitives` is intentionally empty:
    this module has no authority to claim that raw segments have been
    semantically enumerated into physical openings.

    Consequently the resulting completeness record is fail-closed with
    `semantic_enumeration_complete=False` whenever a source snapshot exists.
    """

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")

    producer = OpeningUniverseCompletenessProducer(
        producer_method="source_authenticated_primitive_coverage_adapter",
        producer_version="2.0.0",
    )
    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is not None:
        document_id = published.revision.document_id
        source_sha256 = published.revision.source_sha256
        snapshot_id = published.snapshot.snapshot_id
        visibility = source_visibility_producer.authority()

        primitives: list[_RealVisiblePrimitive] = []
        scoped_page_ids = {str(page_id) for page_id in page_ids}
        for observation_id in published.visible_observation_ids:
            result = visibility.resolve_visible(
                ObservationSelector(
                    document_id=document_id,
                    revision_id=revision_id,
                    source_sha256=source_sha256,
                    snapshot_id=snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.observation is None
            ):
                continue
            observation = result.observation
            if str(observation.page_id) not in scoped_page_ids:
                continue
            primitives.append(
                _RealVisiblePrimitive(
                    primitive_id=observation.observation_id,
                    page_id=observation.page_id,
                    geometry=observation.geometry,
                )
            )

        producer.publish_enumeration(
            decision_scope_id=decision_scope_id,
            decision_scope_kind=decision_scope_kind,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_ids=page_ids,
            viewport_id=None,
            coverage=published.coverage,
            source_primitives=primitives,
            # Deliberately empty. Visible primitive coverage is not semantic
            # opening enumeration.
            enumerated_primitives=(),
            optional_content_state=(
                "known_visible" if optional_content_known_visible else "unresolved"
            ),
            xobject_traversal_truncated=xobject_traversal_truncated,
            semantic_enumeration_proven=False,
        )

    # Deliberately DO NOT attach GenericOpeningCountAuthority's
    # _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL. Primitive coverage alone cannot
    # unlock a commercial count.
    return producer.authority()


def build_semantic_opening_inventory_completeness(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    decision_scope_id: str,
    page_ids: Sequence[str] | None = None,
    optional_content_known_visible: bool = False,
    xobject_traversal_truncated: bool = False,
) -> OpeningUniverseCompletenessAuthority:
    """Project the semantic opening inventory into the completeness contract.

    The semantic enumerator derives its inventory only from the producer-owned
    complete visible-source snapshot and independently re-proven physical
    openings.  Its representative observation ids therefore have the exact
    shape GenericOpeningCountAuthority will eventually consume.

    Commercial sealing remains fail-closed until the semantic producer proves
    physical_opening_universe_complete. Optional-content visibility is derived
    from the immutable stored PDF; caller flags cannot create that proof.
    """

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")

    semantic_producer = (
        SemanticOpeningEnumerationProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    if page_ids is None:
        semantic_result = semantic_producer.publish_document_scope(
            revision_id=revision_id,
            decision_scope_id=decision_scope_id,
        )
    else:
        semantic_result = semantic_producer.publish_page_scope(
            revision_id=revision_id,
            decision_scope_id=decision_scope_id,
            page_ids=tuple(str(page_id) for page_id in page_ids),
        )

    producer = OpeningUniverseCompletenessProducer(
        producer_method="source_authenticated_semantic_opening_inventory_adapter",
        producer_version="1.0.0",
    )
    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if (
        published is None
        or semantic_result.record is None
        or semantic_result.status is EvidenceResolutionStatus.CONFLICT
    ):
        return producer.authority()

    record = semantic_result.record
    semantic_authority = semantic_producer.authority()
    resolved = semantic_authority.resolve(
        SemanticOpeningEnumerationSelector(
            document_id=record.document_id,
            revision_id=record.revision_id,
            source_sha256=record.source_sha256,
            snapshot_id=record.snapshot_id,
            decision_scope_id=record.decision_scope_id,
        )
    )
    if resolved.record is None:
        return producer.authority()

    visibility = source_visibility_producer.authority()
    semantic_members: list[_RealVisiblePrimitive] = []
    for observation_id in resolved.record.representative_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.observation is None
        ):
            return producer.authority()
        observation = result.observation
        semantic_members.append(
            _RealVisiblePrimitive(
                primitive_id=observation.observation_id,
                page_id=observation.page_id,
                geometry=observation.geometry,
            )
        )

    completeness_record = producer.publish_enumeration(
        decision_scope_id=record.decision_scope_id,
        decision_scope_kind=record.decision_scope_kind,
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        page_ids=record.page_ids,
        viewport_id=None,
        coverage=published.coverage,
        # At this seam the source universe is the producer-owned semantic
        # inventory, not the raw segment universe. The same semantic members
        # are supplied on both sides only to fingerprint the inventory itself.
        source_primitives=semantic_members,
        enumerated_primitives=semantic_members,
        optional_content_state=source_visibility_producer.optional_content_state_for_scope(
            revision_id,
            page_ids=record.page_ids,
        ),
        # SourceVisibilityProducer owns the semantic source snapshot. It either
        # completes page decode or records failed coverage; callers cannot
        # assert or clear an independent XObject-truncation flag here.
        xobject_traversal_truncated=False,
        semantic_enumeration_proven=bool(
            resolved.record.physical_opening_universe_complete
        ),
    )
    authority = producer.authority()
    if (
        bool(resolved.record.physical_opening_universe_complete)
        and bool(completeness_record.semantic_enumeration_complete)
        and bool(completeness_record.decision_scope_complete)
    ):
        # Private in-process authentication consumed by GenericOpeningCountAuthority.
        # Ordinary callers cannot provide this seal or a completeness claim.
        authority._source_authentication_seal = _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    return authority


__all__ = [
    "build_semantic_opening_inventory_completeness",
    "build_source_authenticated_opening_universe_completeness",
]
