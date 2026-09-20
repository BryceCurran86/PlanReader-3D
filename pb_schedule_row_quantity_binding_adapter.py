"""Source-authenticated bridge from schedule binding to row quantity.

Positive quantity evidence must be resolved from a producer-owned
`ScheduleOpeningInstanceBindingAuthority`; ordinary callers may provide only a
selector/address. A constructible `ScheduleOpeningInstanceBindingRecord` is
not accepted as authority.

This closes the trust gap where a caller could fabricate a record carrying
`schedule_row_count_explicit=True` and an arbitrary count, then republish it as
`ScheduleRowQuantityAuthority` evidence.
"""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_schedule_row_quantity_authority import (
    SCHEDULE_ROW_QTY_INCOMPLETE,
    ScheduleRowQuantityProducer,
    _AUTHENTICATED_BINDING_SEAL,
    ScheduleRowQuantityResult,
    ScheduleRowQuantitySelector,
)


def publish_schedule_row_quantity_from_binding(
    *,
    schedule_row_quantity_producer: ScheduleRowQuantityProducer,
    schedule_binding_authority: ScheduleOpeningInstanceBindingAuthority,
    binding_selector: ScheduleOpeningInstanceBindingSelector,
) -> ScheduleRowQuantityResult:
    """Resolve a producer-owned binding, then republish its explicit count.

    Consumers supply only an address (`binding_selector`). The positive
    binding record is obtained internally from `schedule_binding_authority`.

    Missing/unresolved bindings and implicit historical default counts fail
    closed and never publish a positive quantity. A positive binding already
    proves complete source coverage plus unique matching-row discovery, so no
    caller-supplied universe-complete boolean exists on this API.
    """

    if type(schedule_row_quantity_producer) is not ScheduleRowQuantityProducer:
        raise TypeError(
            "schedule_row_quantity_producer must be producer-owned "
            "ScheduleRowQuantityProducer"
        )
    if type(schedule_binding_authority) is not ScheduleOpeningInstanceBindingAuthority:
        raise TypeError(
            "schedule_binding_authority must be producer-owned "
            "ScheduleOpeningInstanceBindingAuthority"
        )
    if type(binding_selector) is not ScheduleOpeningInstanceBindingSelector:
        raise TypeError(
            "binding_selector must be ScheduleOpeningInstanceBindingSelector"
        )

    binding_result = schedule_binding_authority.resolve(binding_selector)
    binding_record = binding_result.record
    if (
        binding_result.status is not EvidenceResolutionStatus.CORROBORATED
        or binding_record is None
    ):
        return ScheduleRowQuantityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=tuple(
                dict.fromkeys(
                    (
                        SCHEDULE_ROW_QTY_INCOMPLETE,
                        *binding_result.reason_codes,
                    )
                )
            ),
            record=None,
        )

    selector = ScheduleRowQuantitySelector(
        document_id=binding_record.document_id,
        revision_id=binding_record.revision_id,
        source_sha256=binding_record.source_sha256,
        snapshot_id=binding_record.snapshot_id,
        schedule_page_id=binding_record.schedule_page_id,
        schedule_row_observation_ids=tuple(
            sorted(binding_record.schedule_row_observation_ids)
        ),
    )

    if (
        not binding_record.schedule_row_count_explicit
        or binding_record.schedule_row_count is None
    ):
        return ScheduleRowQuantityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SCHEDULE_ROW_QTY_INCOMPLETE,),
            record=None,
        )

    return schedule_row_quantity_producer._publish_from_authenticated_binding(
        selector,
        declared_count=int(binding_record.schedule_row_count),
        type_mark=binding_record.schedule_row_type_mark,
        _seal=_AUTHENTICATED_BINDING_SEAL,
    )


__all__ = [
    "publish_schedule_row_quantity_from_binding",
]
