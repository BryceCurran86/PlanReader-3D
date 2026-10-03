"""Live source-owned bridge from opening authorities to count QuantityEvidence.

This module does not discover openings, infer semantic kind from topology, or
trust caller-authored counts. It replays the existing producer-owned schedule
binding and GenericOpeningCountAuthority over the exact source-authenticated
physical-opening universe assembled by LiveWallOpeningAuthorityComposition.
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


def _family_from_authenticated_mark(mark: object) -> str | None:
    normalized = normalize_opening_tag(mark)
    if normalized is None:
        return None
    trade = str(normalized.trade_type or "").strip().lower()
    if trade in {"door", "doors"}:
        return "door"
    if trade in {"window", "windows"}:
        return "window"
    return None


def publish_live_opening_count_quantities(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
) -> tuple[QuantityEvidence, ...]:
    """Publish exact mark/family counts through GenericOpeningCountAuthority.

    Physical existence and completeness stay owned by the existing opening
    authorities. Schedule evidence may classify a proven instance and may
    corroborate an explicit row quantity, but it never manufactures an opening.
    """
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be LiveWallOpeningAuthorityComposition"
        )

    semantic_record = wall_opening_composition.semantic_enumeration_result.record
    published = source_visibility_producer.published_snapshot_for_revision(
        wall_opening_composition.revision_id
    )
    if semantic_record is None or published is None:
        return ()

    view_authority = build_source_page_view_class_authority(
        source_visibility_producer=source_visibility_producer,
        revision_id=wall_opening_composition.revision_id,
        page_ids=wall_opening_composition.page_ids,
    )

    binding_producer = (
        ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    binding_results: dict[str, object] = {}
    opening_page_ids: dict[str, str] = {}

    for observation_id in semantic_record.representative_observation_ids:
        opening_selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        existence = wall_opening_composition.physical_opening_authority.prove_existence(
            opening_selector
        )
        opening = existence.existence_record
        if (
            existence.status is not EvidenceResolutionStatus.CORROBORATED
            or opening is None
        ):
            continue
        host_selector = wall_opening_composition.binding_selectors.get(
            opening.record_id
        )
        if host_selector is None:
            continue
        result = binding_producer.publish_scope(
            opening_selector=opening_selector,
            decision_scope_id=host_selector.decision_scope_id,
        )
        binding_results[opening.record_id] = result
        opening_page_ids[opening.record_id] = str(opening.page_id)

    binding_authority = binding_producer.authority()
    schedule_quantity_producer = ScheduleRowQuantityProducer.create()
    for opening_id, result in sorted(binding_results.items()):
        record = getattr(result, "record", None)
        if (
            getattr(result, "status", None)
            is not EvidenceResolutionStatus.CORROBORATED
            or record is None
        ):
            continue
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=schedule_quantity_producer,
            schedule_binding_authority=binding_authority,
            binding_selector=ScheduleOpeningInstanceBindingSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                decision_scope_id=record.decision_scope_id,
                opening_record_id=opening_id,
            ),
        )
    schedule_quantity_authority = schedule_quantity_producer.authority()

    quantities: dict[str, QuantityEvidence] = {}
    for page_id in wall_opening_composition.page_ids:
        universe_authority = (
            wall_opening_composition.opening_universe_completeness_authorities.get(
                page_id
            )
        )
        universe_result = wall_opening_composition.opening_universe_results.get(
            page_id
        )
        universe_record = (
            universe_result.record if universe_result is not None else None
        )
        if universe_authority is None or universe_record is None:
            continue

        count_producer = GenericOpeningCountProducer.from_authorities(
            opening_universe_authority=universe_authority,
            physical_opening_authority=(
                wall_opening_composition.physical_opening_authority
            ),
            viewport_view_class_authority=view_authority,
            schedule_binding_authority=binding_authority,
            schedule_row_quantity_authority=schedule_quantity_authority,
        )

        page_marks: dict[str, str] = {}
        for opening_id, result in binding_results.items():
            if opening_page_ids.get(opening_id) != str(page_id):
                continue
            record = getattr(result, "record", None)
            if (
                getattr(result, "status", None)
                is not EvidenceResolutionStatus.CORROBORATED
                or record is None
            ):
                continue
            mark = str(
                getattr(record, "schedule_row_type_mark", None)
                or getattr(record, "tag_mark", None)
                or ""
            ).strip().upper()
            family = _family_from_authenticated_mark(mark)
            if mark and family is not None:
                page_marks[mark] = family

        for mark, family in sorted(page_marks.items()):
            result = count_producer.publish(
                GenericOpeningCountSelector(
                    document_id=universe_record.document_id,
                    revision_id=universe_record.revision_id,
                    source_sha256=universe_record.source_sha256,
                    snapshot_id=universe_record.snapshot_id,
                    decision_scope_id=universe_record.decision_scope_id,
                    opening_family=family,
                    opening_mark=mark,
                )
            )
            record = result.record
            quantity = record.quantity_evidence if record is not None else None
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and quantity is not None
                and not quantity.abstained
            ):
                quantities[quantity.quantity_id] = quantity

    return tuple(quantities[key] for key in sorted(quantities))


__all__ = ["publish_live_opening_count_quantities"]
