"""Live source-authenticated opening-count QuantityEvidence publication.

This module is a narrow commercial bridge over already reviewed producer-owned
authorities. It does not create opening instances, infer schedule counts, or
accept caller-selected candidate sets.

A positive quantity requires:
- a complete source-authenticated semantic physical-opening universe;
- producer-owned physical opening identity for every member;
- a unique source schedule-row binding for each classified member;
- an explicit (not historical default) schedule quantity;
- exact agreement between the authenticated physical instance count and the
  source-declared schedule quantity; and
- authoritative floor-plan view classification.

Schedule-only quantities and implicit default counts remain fail-closed.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from pb_generic_opening_count_authority import (
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
)
from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_opening_tag_normalization import normalize_opening_tag
from pb_page_view_class_source_adapter import (
    build_source_page_view_class_authority,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_schedule_row_quantity_authority import ScheduleRowQuantityProducer
from pb_schedule_row_quantity_binding_adapter import (
    publish_schedule_row_quantity_from_binding,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_OPENING_COUNT_QUANTITY_SCHEMA_VERSION = "1.0.0"


def _authentic_source_id_universe(ids: object) -> bool:
    """A complete original source inventory cannot silently deduplicate IDs."""
    return (
        isinstance(ids, (tuple, list))
        and bool(ids)
        and all(type(value) is str and value and value == value.strip() for value in ids)
        and len(set(ids)) == len(ids)
    )


def _valid_explicit_source_count(count: object) -> bool:
    """Explicit producer-owned item count, never a guessed per-detection one."""
    if type(count) not in (int, float):
        return False
    try:
        number = float(count)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(number) and number > 0 and number.is_integer()


def _source_count_quantity_ready_for_publication(quantity: object) -> bool:
    """Final exact-source count check independent of schedule-row discovery."""
    if type(quantity) is not QuantityEvidence:
        return False
    return (
        quantity.family == "opening_count"
        and not quantity.abstained
        and quantity.status == "firm"
        and quantity.unit == "ea"
        and not quantity.blocking_reasons
        and _valid_explicit_source_count(quantity.value)
        and _authentic_source_id_universe(quantity.input_entity_ids)
        and int(quantity.value) == len(quantity.input_entity_ids)
    )


def publish_live_authenticated_opening_count_quantities(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
) -> tuple[QuantityEvidence, ...]:
    """Publish deterministic per-mark counts from live producer-owned authority.

    The caller supplies no opening IDs, marks, counts, schedule rows, or expected
    quantities. Every positive selector is discovered from the producer-owned
    semantic opening inventory and source-authenticated schedule bindings.
    """

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be LiveWallOpeningAuthorityComposition"
        )

    published = source_visibility_producer.published_snapshot_for_revision(
        wall_opening_composition.revision_id
    )
    semantic = wall_opening_composition.semantic_enumeration_result
    semantic_record = semantic.record
    if (
        published is None
        or semantic.status is not EvidenceResolutionStatus.CORROBORATED
        or semantic_record is None
        or semantic_record.physical_opening_universe_complete is not True
        or published.revision.document_id != semantic_record.document_id
        or published.revision.revision_id != semantic_record.revision_id
        or published.revision.source_sha256 != semantic_record.source_sha256
        or published.snapshot.snapshot_id != semantic_record.snapshot_id
        or not _authentic_source_id_universe(semantic_record.representative_observation_ids)
    ):
        return ()

    # Original semantic completeness must account for every source plan page
    # and exactly the declared physical opening identities. Never certify a
    # convenient subset as the entire count universe.
    semantic_pages = semantic_record.page_ids
    semantic_member_ids = semantic_record.physical_opening_record_ids
    if (
        semantic_record.structural_enumeration_complete is not True
        or not _authentic_source_id_universe(semantic_pages)
        or set(semantic_pages) != set(wall_opening_composition.page_ids)
        or not _authentic_source_id_universe(semantic_member_ids)
        or len(semantic_member_ids) != len(semantic_record.representative_observation_ids)
    ):
        return ()
    scope_id = semantic_record.decision_scope_id
    if type(scope_id) is not str or not scope_id or scope_id != scope_id.strip():
        return ()

    binding_producer = (
        ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    physical = wall_opening_composition.physical_opening_authority

    # Discover every binding from the complete producer-owned semantic universe.
    # A missing binding is retained as unresolved by GenericOpeningCountAuthority;
    # this bridge never narrows the universe to the convenient members.
    binding_selectors: dict[str, ScheduleOpeningInstanceBindingSelector] = {}
    binding_results = {}
    physical_source_receipts: dict[str, tuple[str, ...]] = {}
    seen_physical_opening_ids: set[str] = set()
    for observation_id in semantic_record.representative_observation_ids:
        opening_selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        existence = physical.prove_existence(opening_selector)
        opening = existence.existence_record
        if (
            existence.status is not EvidenceResolutionStatus.CORROBORATED
            or opening is None
        ):
            # The upstream semantic inventory says this source scope is
            # complete. Losing one of its candidate physical members would
            # make a matching schedule count for a smaller subset look FIRM.
            # Fail closed for the entire mark inventory, not the one member.
            return ()
        # A complete source semantic universe may not collapse two distinct
        # existence observations into one identical opening identity by
        # dictionary overwrite. Preserve unresolved universes as ABSTAIN.
        if (
            type(opening.record_id) is not str
            or not opening.record_id.strip()
            or opening.record_id in seen_physical_opening_ids
        ):
            return ()
        # The producer's source-owned physical opening must belong to this
        # original document, revision, snapshot, page and observation receipt.
        if (
            opening.document_id != published.revision.document_id
            or opening.revision_id != published.revision.revision_id
            or opening.source_sha256 != published.revision.source_sha256
            or opening.snapshot_id != published.snapshot.snapshot_id
            or opening.page_id not in semantic_pages
            or not _authentic_source_id_universe(opening.source_observation_ids)
            or observation_id not in opening.source_observation_ids
        ):
            return ()
        seen_physical_opening_ids.add(opening.record_id)
        physical_source_receipts[opening.record_id] = tuple(opening.source_observation_ids)
        selector = ScheduleOpeningInstanceBindingSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            decision_scope_id=scope_id,
            opening_record_id=opening.record_id,
        )
        binding_selectors[opening.record_id] = selector
        binding_results[opening.record_id] = binding_producer.publish_scope(
            opening_selector=opening_selector,
            decision_scope_id=scope_id,
        )

    if (
        not binding_selectors
        or len(binding_selectors) != len(semantic_record.representative_observation_ids)
        or set(binding_selectors) != set(semantic_member_ids)
        or any(
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.record is None
            for result in binding_results.values()
        )
    ):
        return ()

    binding_authority = binding_producer.authority()
    row_quantity_producer = ScheduleRowQuantityProducer.create()

    # Publish each exact explicit schedule row once through the existing
    # authority-resolved adapter. Historical parser default count=1 never
    # reaches this positive path.
    published_rows: set[tuple[str, tuple[str, ...]]] = set()
    authenticated_marks: set[str] = set()
    for opening_id in sorted(binding_results):
        result = binding_results[opening_id]
        record = result.record
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or record is None
            or not record.schedule_row_count_explicit
            or not _valid_explicit_source_count(record.schedule_row_count)
            or type(record.schedule_page_id) is not str
            or not record.schedule_page_id.strip()
            or not _authentic_source_id_universe(record.schedule_row_observation_ids)
        ):
            continue

        normalized = normalize_opening_tag(record.schedule_row_type_mark)
        if normalized is None:
            continue
        row_key = (
            str(record.schedule_page_id),
            tuple(sorted(record.schedule_row_observation_ids)),
        )
        if row_key not in published_rows:
            row_result = publish_schedule_row_quantity_from_binding(
                schedule_row_quantity_producer=row_quantity_producer,
                schedule_binding_authority=binding_authority,
                binding_selector=binding_selectors[opening_id],
            )
            if (
                row_result.status is not EvidenceResolutionStatus.CORROBORATED
                or row_result.record is None
            ):
                continue
            published_rows.add(row_key)
        authenticated_marks.add(normalized.tag)

    if not authenticated_marks:
        return ()

    view_authority = build_source_page_view_class_authority(
        source_visibility_producer=source_visibility_producer,
        revision_id=published.revision.revision_id,
        page_ids=wall_opening_composition.page_ids,
    )
    count_producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=(
            wall_opening_composition.opening_universe_completeness_authority
        ),
        physical_opening_authority=physical,
        viewport_view_class_authority=view_authority,
        schedule_binding_authority=binding_authority,
        schedule_row_quantity_authority=row_quantity_producer.authority(),
    )

    quantities: list[QuantityEvidence] = []
    seen_quantity_ids: set[str] = set()
    for mark in sorted(authenticated_marks):
        result = count_producer.publish(
            GenericOpeningCountSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                decision_scope_id=scope_id,
                opening_mark=mark,
            )
        )
        record = result.record
        quantity = record.quantity_evidence if record is not None else None
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or record is None
            or not record.schedule_corroborated
            or not _source_count_quantity_ready_for_publication(quantity)
        ):
            continue
        # Reauthenticate the *final* quantity returned by the source-count
        # authority, not merely its status. A replayed entity list, source
        # receipt set, count or mark can otherwise reach customer projection.
        physical_ids = record.physical_instance_record_ids
        receipt_ids = quantity.evidence_ids
        if (
            record.document_id != published.revision.document_id
            or record.revision_id != published.revision.revision_id
            or record.source_sha256 != published.revision.source_sha256
            or record.snapshot_id != published.snapshot.snapshot_id
            or record.decision_scope_id != scope_id
            or record.opening_mark != mark
            or type(record.count) is not int
            or record.count <= 0
            or not _authentic_source_id_universe(physical_ids)
            or len(physical_ids) != record.count
            or not set(physical_ids).issubset(binding_selectors)
            or quantity.value != float(record.count)
            or tuple(quantity.input_entity_ids) != tuple(physical_ids)
            or not _authentic_source_id_universe(receipt_ids)
            or not _authentic_source_id_universe(record.schedule_row_ids)
            or not set(record.schedule_row_ids).issubset(set(receipt_ids))
            or any(
                not set(physical_source_receipts[opening_id]).issubset(set(receipt_ids))
                for opening_id in physical_ids
            )
            or not isinstance(quantity.metadata, Mapping)
            or quantity.metadata.get("schedule_corroborated") is not True
            or quantity.metadata.get("commercial_projection_allowed") is not True
        ):
            return ()
        if quantity.quantity_id in seen_quantity_ids:
            # A duplicate commercial identity is not a successful count.
            return ()
        seen_quantity_ids.add(quantity.quantity_id)
        quantities.append(quantity)

    return tuple(sorted(quantities, key=lambda item: item.quantity_id))


__all__ = [
    "LIVE_OPENING_COUNT_QUANTITY_SCHEMA_VERSION",
    "publish_live_authenticated_opening_count_quantities",
]
