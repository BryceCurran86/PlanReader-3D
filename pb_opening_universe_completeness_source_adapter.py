"""pb_opening_universe_completeness_source_adapter.py -- the one lawful
producer-owned path to a SOURCE-AUTHENTICATED OpeningUniverseCompletenessAuthority.

GenericOpeningCountAuthority (pb_generic_opening_count_authority.py) refuses
to reconcile anything unless the OpeningUniverseCompletenessAuthority it is
given carries a private `_source_authentication_seal` attribute. That gate
exists because OpeningUniverseCompletenessProducer.publish_enumeration()
itself accepts arbitrary caller-supplied `source_primitives`/
`enumerated_primitives` sequences -- nothing about calling it, by itself,
proves the primitives genuinely came from a real source decode rather than a
caller-fabricated list. Before this module, the only place in the repo that
set `_source_authentication_seal` was test code, via
`object.__setattr__(...)` -- test infrastructure, not a production path.

This module is that missing production path. It earns the seal by deriving
BOTH `source_primitives` and `enumerated_primitives` itself, directly from a
real `SourceVisibilityAuthority`'s own already-clip-verified
`NATIVE_PDF_VISIBLE_SEGMENT` observations (`classify_native_segment_visibility`
in pb_source_visibility_authority.py already proves `clip_known=True,
clip_present=False` for every one of them -- restating that here is not a
new claim, it is the one this adapter is entitled to make because it only
ever wraps observations resolved through `resolve_visible()`) -- never from
a caller-supplied list. It deliberately does no further semantic coalescing
beyond that: the completeness claim this adapter can honestly make is
"every decoded, unclipped, visible segment in scope was accounted for," not
a stronger claim about semantic opening enumeration.
"""
from __future__ import annotations

from collections.abc import Sequence

from pb_generic_opening_count_authority import (
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


class _RealVisiblePrimitive:
    """Duck-typed adapter over one real, already-clip-verified visible
    segment observation -- exposes exactly the attributes
    build_opening_universe_member_from_indexed_primitive() reads, populated
    from a genuine SourceObservationRecord, never invented."""

    __slots__ = ("primitive_id", "page_id", "geometry", "layer", "clip_known", "clip_present", "clip")

    def __init__(self, *, primitive_id: str, page_id: str, geometry: tuple[float, ...]) -> None:
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
    """The only lawful way to obtain a completeness Authority
    GenericOpeningCountAuthority will accept.

    `optional_content_known_visible` defaults to False (fail closed): the
    caller must explicitly assert True only after confirming the source PDF
    either has no optional-content groups, or that every relevant group's
    visibility has been independently resolved -- this adapter has no way to
    check that itself from an already-ingested SourceVisibilityProducer, so
    it never assumes it.

    `xobject_traversal_truncated` defaults to False, matching
    SourceVisibilityProducer.ingest_native_pdf_bytes()'s current behavior of
    traversing every XObject it encounters with no depth/count limit; pass
    True if a future ingestion path introduces one.

    document_id/source_sha256/snapshot_id are read from the producer's own
    published revision/snapshot records for `revision_id`, never taken as
    separate caller-supplied arguments that could disagree with them.
    """
    producer = OpeningUniverseCompletenessProducer(
        producer_method="source_authenticated_completeness_adapter",
        producer_version="1.0.0",
    )
    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is not None:
        document_id = published.revision.document_id
        source_sha256 = published.revision.source_sha256
        snapshot_id = published.snapshot.snapshot_id
        visibility = source_visibility_producer.authority()

        primitives: list[_RealVisiblePrimitive] = []
        scoped_page_ids = set(str(p) for p in page_ids)
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
            if result.status != EvidenceResolutionStatus.CORROBORATED or result.observation is None:
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
            enumerated_primitives=primitives,
            optional_content_state="known_visible" if optional_content_known_visible else "unresolved",
            xobject_traversal_truncated=xobject_traversal_truncated,
        )

    authority = producer.authority()
    # Legitimately earned here: this function is the only caller of
    # publish_enumeration() with primitives it derived itself from a real
    # SourceVisibilityAuthority, never from a caller-supplied list. A
    # published==None revision still gets the seal -- the seal certifies
    # the DERIVATION PATH was lawful, not that a complete universe was
    # found; GenericOpeningCountAuthority's own resolve()/status checks are
    # what correctly fail closed when nothing was published for the scope.
    authority._source_authentication_seal = _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    return authority


__all__ = [
    "build_source_authenticated_opening_universe_completeness",
]
