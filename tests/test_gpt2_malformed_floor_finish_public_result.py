"""Malformed reconstructed floor-finish source rows cannot bypass mark ownership."""
from dataclasses import replace

import pytest

from tests.test_gpt2_floor_finish_result_cross_room_source_quarantine import (
    _producer_result, _different_room, _public_result,
)


@pytest.mark.parametrize("rogue", [None, object(), {}, [], (), "fake-floor"])
def test_untyped_reconstructed_floor_finish_record_abstains_entire_projection(
    monkeypatch, rogue,
):
    first, _floors = _producer_result(monkeypatch)
    independent = _different_room(first)
    for rows in ((first, rogue, independent), (rogue, first, independent)):
        result = _public_result(*rows)
        assert result.records_by_floor_id == {}
        assert result.quantities == ()


def test_bad_embedded_quantity_abstains_instead_of_publishing_a_sibling(monkeypatch):
    first, _floors = _producer_result(monkeypatch)
    independent = _different_room(first)
    forged = replace(independent, quantity=None)
    result = _public_result(first, forged)
    assert result.records_by_floor_id == {}
    assert result.quantities == ()


def test_independent_typed_source_floor_finish_quantities_still_visible(monkeypatch):
    first, _floors = _producer_result(monkeypatch)
    independent = _different_room(first)
    result = _public_result(independent, first)
    assert len(result.records_by_floor_id) == 2
    assert len(result.quantities) == 2
