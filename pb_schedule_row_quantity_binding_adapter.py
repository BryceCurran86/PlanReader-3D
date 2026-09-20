"""pb_schedule_row_quantity_binding_adapter.py -- the one lawful path from a
CORROBORATED ScheduleOpeningInstanceBindingRecord to a published
ScheduleRowQuantityAuthority entry.

ScheduleRowQuantityProducer.publish() (pb_schedule_row_quantity_authority.py)
takes `declared_count: int` as a bare caller-supplied argument -- nothing
about calling it, by itself, proves that count came from a genuinely parsed,
source-authenticated schedule quantity cell rather than caller fabrication
(e.g. a hand-built ScheduleEntry(type_mark="W1", count=3)).

ScheduleOpeningInstanceBindingProducer.publish_scope()
(pb_schedule_opening_instance_binding_authority.py) already derives exactly
that: for the EXACT schedule_row_observation_ids it matched, it independently
resolves each cell's trusted text (via PdfTextIntegrityAuthority), groups
them into rows, detects the header, and parses the row with
pb_opening_schedule_v171.parse_schedule_rows() -- the same source-authenticated
chain a from-scratch quantity producer would have to rebuild. Its record
already carries the result as `schedule_row_count` /
`schedule_row_count_explicit`.

This module is the one place that should ever feed
ScheduleRowQuantityProducer.publish() in production: it takes an existing
binding record and republishes its already-authenticated count, rather than
re-deriving (and risking a second, possibly-divergent parse of the same
page) or accepting an arbitrary caller int. `count_explicit=False` -- the
historical ambiguous default used when a schedule row had no legible
quantity cell -- always fails closed: an implicit default must never be
treated as an authenticated declared count.
"""
from __future__ import annotations

from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingRecord,
)
from pb_schedule_row_quantity_authority import (
    ScheduleRowQuantityProducer,
    ScheduleRowQuantityResult,
    ScheduleRowQuantitySelector,
)


def publish_schedule_row_quantity_from_binding(
    *,
    schedule_row_quantity_producer: ScheduleRowQuantityProducer,
    binding_record: ScheduleOpeningInstanceBindingRecord,
    universe_complete: bool,
) -> ScheduleRowQuantityResult:
    """Republish a binding record's own authenticated count/mark into
    ScheduleRowQuantityAuthority. Never derives a new value.

    Fails closed (publishes an ABSTAINED result, never a fabricated count)
    whenever `binding_record.schedule_row_count_explicit` is False.
    """
    if type(schedule_row_quantity_producer) is not ScheduleRowQuantityProducer:
        raise TypeError(
            "schedule_row_quantity_producer must be producer-owned "
            "ScheduleRowQuantityProducer"
        )
    if type(binding_record) is not ScheduleOpeningInstanceBindingRecord:
        raise TypeError(
            "binding_record must be a ScheduleOpeningInstanceBindingRecord"
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
        return schedule_row_quantity_producer.publish(
            selector,
            declared_count=0,
            type_mark=None,
            universe_complete=False,
        )

    return schedule_row_quantity_producer.publish(
        selector,
        declared_count=int(binding_record.schedule_row_count),
        type_mark=binding_record.schedule_row_type_mark,
        universe_complete=bool(universe_complete),
    )


__all__ = [
    "publish_schedule_row_quantity_from_binding",
]
