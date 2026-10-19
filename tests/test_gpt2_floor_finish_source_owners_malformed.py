"""Malformed original floor-finish source owner must abstain, never crash."""
from dataclasses import replace
import copy

import pytest

from tests.test_gpt2_floor_finish_result_cross_room_source_quarantine import (
    _producer_result, _different_room, _public_result,
)


@pytest.mark.parametrize("field", [
    "canonical_floor_id", "physical_floor_surface_id",
    "physical_room_id", "source_room_face_record_id",
    "occurrence_record_id", "occurrence_evidence_id",
])
@pytest.mark.parametrize("bad", [[], {}, None, " "])
def test_unhashable_or_blank_ft2_ft3_source_owner_fails_closed(monkeypatch, field, bad):
    good, _ = _producer_result(monkeypatch)
    independent = _different_room(good)
    invalid = replace(independent, **{field: bad})
    for rows in ((good, invalid), (invalid, good)):
        result = _public_result(*rows)
        assert result.records_by_floor_id == {}
        assert result.quantities == ()


def test_unhashable_secondary_quantity_original_evidence_fails_closed(monkeypatch):
    good, _ = _producer_result(monkeypatch)
    independent = _different_room(good)
    forged = copy.copy(independent.quantity)
    object.__setattr__(forged, "evidence_ids", ([],))
    result = _public_result(good, replace(independent, quantity=forged))
    assert result.records_by_floor_id == {}
    assert result.quantities == ()


def test_independent_source_mark_and_original_room_area_survive(monkeypatch):
    good, _ = _producer_result(monkeypatch)
    independent = _different_room(good)
    result = _public_result(good, independent)
    assert len(result.records_by_floor_id) == 2
    assert len(result.quantities) == 2
