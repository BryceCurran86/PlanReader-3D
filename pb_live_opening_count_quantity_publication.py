"""Live source-authenticated opening-count QuantityEvidence publication.

This bridge does not create openings, infer counts, or accept caller-selected
instance sets. It replays the existing GenericOpeningCountAuthority separately
for each producer-authenticated page opening universe.
"""
from __future__ import annotations

from pb_generic_opening_count_authority import (
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
)
from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_opening_tag_normalization import normalize_opening_tag
from pb_page_view_class_source_adapter import build_source_page_view_class_authority
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


def publish_live_authenticated_opening_count_quantities(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
) -> tuple[QuantityEvidence, ...]:
    """Publish exact per-mark counts from page-complete physical universes."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be LiveWallOpeningAuthorityComposition"
        )

    published = source_visibility_producer.published_snapshot_for_revision(
        wall_opening_composition.revision_id
    )
    if published is None:
        return ()

    binding_producer = (
        ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    physical = wall_opening_composition.physical_opening_authority

    # First publish bindings in the exact page scope owned by the corresponding
    # opening-universe completeness authority.
    page_bindings: dict[str, dict[str, object]] = {}
    page_selectors: dict[str, dict[str, ScheduleOpeningInstanceBindingSelector]] = {}

    for page_id in wall_opening_composition.page_ids:
        universe_result = wall_opening_composition.opening_universe_results.get(page_id)
        universe_record = universe_result.record if universe_result is not None else None
        if (
            universe_result is None
            or universe_result.status is not EvidenceResolutionStatus.CORROBORATED
            or universe_record is None
            or not bool(universe_record.decision_scope_complete)
        ):
            continue

        accounted_ids = tuple(
            getattr(universe_record, "accounted_source_observation_ids", ()) or ()
        )
        if not accounted_ids:
            accounted_ids = tuple(
                getattr(universe_record, "accounted_member_ids", ()) or ()
            )

        for observation_id in accounted_ids:
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
                or str(opening.page_id) != str(page_id)
            ):
                continue

            scope_id = str(universe_record.decision_scope_id)
            result = binding_producer.publish_scope(
                opening_selector=opening_selector,
                decision_scope_id=scope_id,
            )
            selector = ScheduleOpeningInstanceBindingSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                decision_scope_id=scope_id,
                opening_record_id=opening.record_id,
            )
            page_bindings.setdefault(str(page_id), {})[opening.record_id] = result
            page_selectors.setdefault(str(page_id), {})[opening.record_id] = selector

    if not page_bindings:
        return ()

    binding_authority = binding_producer.authority()
    row_quantity_producer = ScheduleRowQuantityProducer.create()

    # Republish explicit source quantities only. Historical parser default=1
    # never establishes a positive commercial quantity.
    for page_id in sorted(page_bindings):
        for opening_id in sorted(page_bindings[page_id]):
            result = page_bindings[page_id][opening_id]
            record = getattr(result, "record", None)
            if (
                getattr(result, "status", None)
                is not EvidenceResolutionStatus.CORROBORATED
                or record is None
                or not bool(record.schedule_row_count_explicit)
                or record.schedule_row_count is None
            ):
                continue
            publish_schedule_row_quantity_from_binding(
                schedule_row_quantity_producer=row_quantity_producer,
                schedule_binding_authority=binding_authority,
                binding_selector=page_selectors[page_id][opening_id],
            )

    schedule_quantity_authority = row_quantity_producer.authority()
    view_authority = build_source_page_view_class_authority(
        source_visibility_producer=source_visibility_producer,
        revision_id=published.revision.revision_id,
        page_ids=wall_opening_composition.page_ids,
    )

    quantities: dict[str, QuantityEvidence] = {}
    for page_id in sorted(page_bindings):
        universe_authority = (
            wall_opening_composition.opening_universe_completeness_authorities.get(
                page_id
            )
        )
        universe_result = wall_opening_composition.opening_universe_results.get(page_id)
        universe_record = universe_result.record if universe_result is not None else None
        if universe_authority is None or universe_record is None:
            continue

        count_producer = GenericOpeningCountProducer.from_authorities(
            opening_universe_authority=universe_authority,
            physical_opening_authority=physical,
            viewport_view_class_authority=view_authority,
            schedule_binding_authority=binding_authority,
            schedule_row_quantity_authority=schedule_quantity_authority,
        )

        marks: set[str] = set()
        for result in page_bindings[page_id].values():
            record = getattr(result, "record", None)
            if (
                getattr(result, "status", None)
                is not EvidenceResolutionStatus.CORROBORATED
                or record is None
                or not bool(record.schedule_row_count_explicit)
                or record.schedule_row_count is None
            ):
                continue
            normalized = normalize_opening_tag(record.schedule_row_type_mark)
            if normalized is not None:
                marks.add(normalized.tag)

        for mark in sorted(marks):
            count_result = count_producer.publish(
                GenericOpeningCountSelector(
                    document_id=universe_record.document_id,
                    revision_id=universe_record.revision_id,
                    source_sha256=universe_record.source_sha256,
                    snapshot_id=universe_record.snapshot_id,
                    decision_scope_id=universe_record.decision_scope_id,
                    opening_mark=mark,
                )
            )
            record = count_result.record
            quantity = record.quantity_evidence if record is not None else None
            if (
                count_result.status is EvidenceResolutionStatus.CORROBORATED
                and record is not None
                and record.schedule_corroborated
                and quantity is not None
                and not quantity.abstained
                and quantity.input_entity_ids
            ):
                quantities[quantity.quantity_id] = quantity

    return tuple(quantities[key] for key in sorted(quantities))


__all__ = [
    "LIVE_OPENING_COUNT_QUANTITY_SCHEMA_VERSION",
    "publish_live_authenticated_opening_count_quantities",
]
