"""One signed source ceiling quantity cannot be re-issued to two ceiling IDs."""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.test_gpt2_malformed_ceiling_quantity_result_quarantine import _issued


def _second(issued, *, quantity_id=None):
    first = issued.records[0]
    second_ceiling_id = "another-physical-ceiling"
    second_quantity_id = (
        first.quantity.quantity_id if quantity_id is None else quantity_id
    )
    quantity = replace(
        first.quantity, quantity_id=second_quantity_id,
        input_entity_ids=(second_ceiling_id,),
    )
    canonical = replace(
        first.canonical_ceiling, canonical_ceiling_id=second_ceiling_id,
        ceiling_quantity_id=second_quantity_id,
    )
    return replace(
        first, canonical_ceiling_id=second_ceiling_id,
        physical_ceiling_surface_id=second_ceiling_id,
        canonical_ceiling=canonical, quantity=quantity,
    )


def test_two_distinct_ceiling_ids_cannot_duplicate_one_signed_quantity():
    issued = _issued()
    duplicated = _second(issued)
    for rows in ((issued.records[0], duplicated),
                 (duplicated, issued.records[0])):
        result = replace(issued, records=rows)
        assert result.records_by_ceiling_id == {}
        assert result.quantities == ()
        assert result.canonical_ceilings == ()


@pytest.mark.parametrize("bad_quantity_id", ["", " ", "\t", None, []])
def test_invalid_signed_quantity_id_fails_closed_even_when_other_record_valid(
    bad_quantity_id,
):
    issued = _issued()
    invalid = replace(
        issued.records[0],
        quantity=replace(issued.records[0].quantity, quantity_id=bad_quantity_id),
    )
    result = replace(issued, records=(issued.records[0], invalid))
    assert result.records_by_ceiling_id == {}
    assert result.quantities == ()


def test_independently_source_identified_ceiling_quantities_remain_visible():
    issued = _issued()
    second = _second(issued, quantity_id="independent-original-quantity-id")
    result = replace(issued, records=(second, issued.records[0]))
    assert set(result.records_by_ceiling_id) == {
        issued.records[0].canonical_ceiling_id, "another-physical-ceiling"
    }
    assert len(result.quantities) == 2
