"""Commercial metadata revocation propagates back to the source-closed issuer."""
from dataclasses import replace

import pytest

from tests.test_gpt2_floor_finish_result_cross_room_source_quarantine import (
    _producer_result, _public_result,
)
from tests.test_gpt2_malformed_ceiling_quantity_result_quarantine import _issued


@pytest.mark.parametrize("inclusion", [None, "EXCLUSION", "PROVISIONAL", ""])
def test_removed_floor_finish_inclusion_revokes_quantity(monkeypatch, inclusion):
    record, _ = _producer_result(monkeypatch)
    quantity = replace(record.quantity, metadata={
        **record.quantity.metadata, "inclusion_status": inclusion,
    })
    result = _public_result(replace(record, quantity=quantity))
    assert result.records_by_floor_id == {}
    assert result.quantities == ()


@pytest.mark.parametrize("inclusion", [None, "EXCLUSION", "PROVISIONAL", ""])
def test_removed_ceiling_inclusion_revokes_signed_area(inclusion):
    issued = _issued()
    record = issued.records[0]
    quantity = replace(record.quantity, metadata={
        **record.quantity.metadata, "inclusion_status": inclusion,
    })
    result = replace(issued, records=(replace(record, quantity=quantity),))
    assert result.records_by_ceiling_id == {}
    assert result.quantities == ()


@pytest.mark.parametrize("allowed", [False, None, "yes", 1])
def test_reconstructed_ceiling_without_exact_commercial_permission_abstains(allowed):
    issued = _issued()
    record = issued.records[0]
    quantity = replace(record.quantity, metadata={
        **record.quantity.metadata, "commercial_projection_allowed": allowed,
    })
    result = replace(issued, records=(replace(record, quantity=quantity),))
    assert result.quantities == ()


def test_unmodified_true_inclusion_and_source_receipt_publish():
    original = _issued()
    assert original.records[0].quantity.metadata["inclusion_status"] == "INCLUSION"
    assert original.records[0].quantity.metadata["commercial_projection_allowed"] is True
    assert len(original.quantities) == 1
