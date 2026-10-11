"""Q01: a confirmed finish occurrence does not make Boolean PDF metrics authoritative."""
from __future__ import annotations

from copy import copy
from dataclasses import replace

import pytest

from pb_cross_view_floor_finish_authority import _area_value, _bbox, _matching_floor
from tests.test_cross_view_floor_finish_authority_v1 import _payload, _source_room_area_and_floor


@pytest.mark.parametrize("bad", [
    (True, 0.0, 10.0, 10.0),
    ("0", 0.0, 10.0, 10.0),
    (0.0, 0.0, float("nan"), 10.0),
    (0.0, 0.0, 10.0, float("inf")),
])
def test_forged_dimension_box_cannot_bind_material_occurrence(bad):
    assert _bbox(bad) is None


def test_native_typed_source_dimension_box_still_resolves():
    assert _bbox((0.0, 1.0, 10.0, 12.0)) == (0.0, 1.0, 10.0, 12.0)


@pytest.mark.parametrize("bad_area", [True, False, "8.64", float("nan"), float("inf")])
def test_replayed_figured_area_cannot_be_reused_as_floor_finish_m2(bad_area):
    source, areas, floors = _source_room_area_and_floor(_payload())
    record = copy(areas.records[0])
    evidence = copy(record.area_evidence)
    object.__setattr__(evidence, "normalized_value", bad_area)
    object.__setattr__(record, "area_evidence", evidence)
    assert _area_value(record) is None
    assert _matching_floor(floors, record) is None


def test_double_boolean_replay_does_not_make_a_fake_one_square_metre_floor():
    _source, areas, floors = _source_room_area_and_floor(_payload())
    record = copy(areas.records[0])
    evidence = copy(record.area_evidence)
    object.__setattr__(evidence, "normalized_value", True)
    object.__setattr__(record, "area_evidence", evidence)
    floor = replace(floors.floors[0], metric_area_m2=True)
    fake_floors = replace(floors, floors=(floor,))
    assert _matching_floor(fake_floors, record) is None


def test_authentic_documented_floor_area_remains_bound_to_physical_floor():
    _source, areas, floors = _source_room_area_and_floor(_payload())
    authentic = _matching_floor(floors, areas.records[0])
    assert authentic is not None
    assert authentic.metric_area_m2 == 8.64



@pytest.mark.parametrize("forged_receipts", [
    (" ev-area",), ("ev-area ",), ("ev-area", "ev-area"),
    ("ev-area", True), ("ev-area", ["unhashable"]),
    None, "ev-area",
])
def test_cross_view_floor_finish_cannot_normalize_canonical_source_receipts(forged_receipts):
    _source, areas, floors = _source_room_area_and_floor(_payload())
    authentic = floors.floors[0]
    tampered_floor = copy(authentic)
    object.__setattr__(tampered_floor, "evidence_ids", forged_receipts)
    assert _matching_floor(
        replace(floors, floors=(tampered_floor,)), areas.records[0],
    ) is None


@pytest.mark.parametrize("altered", [True, False, " ev-area", "ev-area "])
def test_replayed_figured_area_receipt_cannot_be_cast_to_floor_source_id(altered):
    _source, areas, floors = _source_room_area_and_floor(_payload())
    record = copy(areas.records[0])
    evidence = copy(record.area_evidence)
    object.__setattr__(evidence, "evidence_id", altered)
    object.__setattr__(record, "area_evidence", evidence)
    assert _matching_floor(floors, record) is None


def test_original_source_room_area_and_finish_match_after_exact_receipt_gate():
    _source, areas, floors = _source_room_area_and_floor(_payload())
    source_area = areas.records[0]
    assert _matching_floor(floors, source_area) is not None
    assert _matching_floor(floors, source_area).metric_area_m2 == 8.64



@pytest.mark.parametrize("forged_id", [
    True, False, 17, " room-area-id", "room-area-id ", "",
])
def test_canonical_floor_finish_rejects_normalized_source_area_quantity_id(forged_id):
    _source, areas, floors = _source_room_area_and_floor(_payload())
    altered_floor = copy(floors.floors[0])
    object.__setattr__(altered_floor, "metric_area_quantity_id", forged_id)
    assert _matching_floor(
        replace(floors, floors=(altered_floor,)), areas.records[0],
    ) is None


def test_canonical_floor_finish_preserves_producer_metric_source_identity():
    _source, areas, floors = _source_room_area_and_floor(_payload())
    record = _matching_floor(floors, areas.records[0])
    assert record is not None
    assert type(record.metric_area_quantity_id) is str
    assert record.metric_area_quantity_id
