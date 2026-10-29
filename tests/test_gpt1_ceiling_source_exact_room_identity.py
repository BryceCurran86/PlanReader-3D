"""Original room identity is not a normalized ceiling source authority receipt.

These are source-neutral negative tests, not evidence of new FIRM ceiling area.
"""
from dataclasses import replace

import pytest

from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_ceiling_lining_source_closed_export import (
    _canonical_ceiling,
    _claim,
    _quantity,
    _room,
)


class ImportedString(str):
    """An imported string-like alias is not a native producer receipt."""


@pytest.mark.parametrize(
    ("field", "forged"),
    (
        ("canonical_room_id", " canonical-room-1"),
        ("canonical_room_id", "canonical-room-1 "),
        ("canonical_room_id", ImportedString("canonical-room-1")),
        ("physical_room_id", " physical-room-1"),
        ("physical_room_id", "physical-room-1 "),
        ("physical_room_id", ImportedString("physical-room-1")),
    ),
)
def test_original_quantity_room_alias_cannot_inherit_firm_ceiling_area(field, forged):
    original = _quantity()
    tampered = replace(
        original, metadata={**dict(original.metadata), field: forged},
    )
    before = dict(tampered.metadata)
    with pytest.raises(SourceClosedRunConflictError, match="exact original room identity"):
        build_live_ceiling_lining_source_traces(
            _claim(tampered), workspace_id=1, project_id="project-1",
        )
    assert dict(tampered.metadata) == before


@pytest.mark.parametrize(
    ("field", "forged"),
    (
        ("canonical_room_id", " canonical-room-1"),
        ("canonical_room_id", "canonical-room-1 "),
        ("canonical_room_id", ImportedString("canonical-room-1")),
        ("physical_room_id", " physical-room-1"),
        ("physical_room_id", "physical-room-1 "),
        ("physical_room_id", ImportedString("physical-room-1")),
    ),
)
def test_original_producer_room_alias_cannot_authenticate_ceiling_source(field, forged):
    original = _quantity()
    room = replace(_room(), **{field: forged})
    claim = replace(_claim(original), canonical_rooms=(room,))
    with pytest.raises(SourceClosedRunConflictError, match="exact original room identity"):
        seal_live_ceiling_lining_run(
            claim, workspace_id=1, project_id="project-1",
        )


@pytest.mark.parametrize(
    "forged",
    (
        " canonical-room-1",
        "canonical-room-1 ",
        ImportedString("canonical-room-1"),
    ),
)
def test_original_ceiling_room_reference_must_match_unmodified_source(forged):
    original = _quantity()
    ceiling = replace(_canonical_ceiling(original), room_entity_id=forged)
    with pytest.raises(SourceClosedRunConflictError, match="exact original room identity"):
        build_live_ceiling_lining_source_traces(
            _claim(original, canonical_ceiling=ceiling),
            workspace_id=1, project_id="project-1",
        )


def test_exact_native_original_room_receipts_keep_firm_customer_row():
    original = _quantity()
    claim = _claim(original)
    traces = build_live_ceiling_lining_source_traces(
        claim, workspace_id=1, project_id="project-1",
    )
    assert tuple(traces) == (original.quantity_id,)
    assert traces[original.quantity_id].metadata["canonical_room_id"] == "canonical-room-1"
    assert traces[original.quantity_id].metadata["physical_room_id"] == "physical-room-1"
    rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == original.quantity_id
    assert rows[0]["location"] == "physical-room-1"
    assert rows[0]["quantity"] == original.value


def test_original_abstention_remains_unpublished():
    original = _quantity()
    blocked = replace(
        original, status="blocked", abstained=True, value=None,
        blocking_reasons=("source_unresolved",),
    )
    assert project_live_ceiling_customer_rows(
        _claim(blocked), workspace_id=1, project_id="project-1",
    ) == ()
