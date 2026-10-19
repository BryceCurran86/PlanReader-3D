"""Reconstructed FIRM ceiling result cannot expose a malformed quantity row."""
from __future__ import annotations

from dataclasses import replace

import pytest

import pb_cross_view_ceiling_quantity_authority as ceiling_quantity
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_ceiling_quantity_authority import (
    _rooms, _bridge, _finish,
)


def _issued():
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_area_bridges=(_bridge(),),
        finishes=_finish(),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    return result


@pytest.mark.parametrize("rogue", [None, {}, (), "room", object()])
def test_untyped_rogue_record_quarantines_entire_ceiling_customer_projection(rogue):
    issued = _issued()
    for records in (
        (issued.records[0], rogue),
        (rogue, issued.records[0]),
    ):
        reconstructed = replace(issued, records=records)
        assert reconstructed.records_by_ceiling_id == {}
        assert reconstructed.quantities == ()
        assert reconstructed.canonical_ceilings == ()


@pytest.mark.parametrize("field,bad", [
    ("canonical_ceiling", None),
    ("canonical_ceiling", {}),
    ("quantity", None),
    ("quantity", {}),
])
def test_malformed_embedded_ceiling_or_quantity_refuses_all_records(field, bad):
    issued = _issued()
    rogue = replace(issued.records[0], **{field: bad})
    reconstructed = replace(issued, records=(issued.records[0], rogue))
    assert reconstructed.records_by_ceiling_id == {}
    assert reconstructed.quantities == ()
    assert reconstructed.canonical_ceilings == ()


def test_valid_original_source_owned_ceiling_quantity_remains_visible():
    issued = _issued()
    assert len(issued.records_by_ceiling_id) == 1
    assert len(issued.quantities) == 1
    assert len(issued.canonical_ceilings) == 1
