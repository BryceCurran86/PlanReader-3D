"""Exact original ceiling room-face ownership through real source seal/customer.

These source-shaped fixtures are not original-PDF authority or scored FIRM
measurements. The tests only veto forged source lineage at an existing issuer.
"""
from dataclasses import replace

import pytest

from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_lining_source_closed_export import (
    _claim, _quantity, _room,
)


CONSUMERS = (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
    project_live_ceiling_customer_rows,
)


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize(
    ("room_face", "quantity_face"),
    (
        ("", ""),
        (" face-1 ", " face-1 "),
        (123, 123),
        (True, True),
        ("face-1", " face-1 "),
        ("face-1", True),
        ("face-1", None),
        ("face-1", ""),
    ),
)
def test_invalid_original_room_face_receipt_cannot_reissue_ceiling(
    consumer, room_face, quantity_face,
):
    original = _quantity()
    quantity = replace(
        original,
        metadata={**original.metadata, "source_room_face_record_id": quantity_face},
    )
    room = replace(_room(), source_room_face_record_id=room_face)
    claim = replace(_claim(quantity), canonical_rooms=(room,))
    before = (claim.canonical_rooms, claim.ceiling_lining_quantity_evidence)
    with pytest.raises(SourceClosedRunConflictError, match="original room-face receipt"):
        consumer(claim, workspace_id=1, project_id="project-1")
    assert (claim.canonical_rooms, claim.ceiling_lining_quantity_evidence) == before


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_missing_original_room_face_key_is_not_empty_equivalence(consumer):
    original = _quantity()
    quantity = replace(
        original,
        metadata={key: value for key, value in original.metadata.items()
                  if key != "source_room_face_record_id"},
    )
    room = replace(_room(), source_room_face_record_id="")
    claim = replace(_claim(quantity), canonical_rooms=(room,))
    with pytest.raises(SourceClosedRunConflictError, match="original room-face receipt"):
        consumer(claim, workspace_id=1, project_id="project-1")


def test_genuine_exact_room_face_preserves_seal_and_customer_row():
    claim = _claim(_quantity())
    before = (claim.canonical_rooms, claim.ceiling_lining_quantity_evidence)
    traces = build_live_ceiling_lining_source_traces(
        claim, workspace_id=1, project_id="project-1",
    )
    sealed = seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1",
    )
    rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert tuple(traces) == ("qty-ceiling-1",)
    assert traces["qty-ceiling-1"].metadata["source_room_face_record_id"] == "face-1"
    assert len(sealed.quantities) == len(rows) == 1
    assert sealed.quantities[0].quantity_id == rows[0]["quantity_id"]
    assert sealed.quantities[0].value == rows[0]["quantity"] == 9.05352
    assert (claim.canonical_rooms, claim.ceiling_lining_quantity_evidence) == before
