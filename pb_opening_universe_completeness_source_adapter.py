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
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessProducer,
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


__all__ = [
    "build_source_authenticated_opening_universe_completeness",
]
