"""GPT1 Q01/Q07: physical canonical floor-area source-ownership regression.

Tests are synthetic caller-adversarial copies of EXISTING production fixture
evidence; they never supply data to producers or frozen evaluations.
No new original source area or floor-finish authority is asserted.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with,
    _source_area,
)
from tests.test_live_floor_finish_area_source_closed_export import _floor


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("family", "floor_area"),
        ("semantic_key", "room_area:foreign-room"),
        ("input_entity_ids", ("foreign-room",)),
        ("unit", "ft2"),
        ("status", AuthorityStatus.PROVISIONAL.value),
        ("authority", MeasurementAuthorityType.MODEL_DERIVED.value),
        ("value", 0.0),
        ("evidence_ids", ()),
        ("evidence_ids", ("ev-area ",)),
        ("evidence_ids", (123,)),
        ("evidence_ids", ("ev-area", "ev-foreign")),
        ("metadata:source_sha256", "b" * 64),
        ("metadata:source_sha256", ""),
        ("metadata:revision_id", "R2"),
        ("metadata:revision_id", ""),
        ("metadata:page_no", "2"),
        ("metadata:page_no", 2),
        ("metadata:page_no", ""),
        ("metadata:viewport_id", "foreign-view"),
        ("metadata:viewport_id", ""),
        ("metadata:room_snapshot_id", "foreign-physical-room-snapshot"),
        ("metadata:source_room_face_record_id", "foreign-source-room-face"),
    ],
)
def test_source_area_may_not_reissue_on_foreign_metadata_or_identity(field, bad):
    source = _source_area()
    if field.startswith("metadata:"):
        key = field.removeprefix("metadata:")
        altered = replace(source, metadata={**dict(source.metadata), key: bad})
    else:
        altered = replace(source, **{field: bad})
    assert publish_live_floor_area_quantities(_claim_with(altered)) == ()
    # Tampered evidence is a replay only. The original typed source stays firm.
    assert publish_live_floor_area_quantities(_claim_with(source))[0].value == 8.64


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("canonical_floor_id", None),
        ("canonical_floor_id", True),
        ("canonical_floor_id", " floor-1"),
        ("physical_floor_surface_id", None),
        ("physical_floor_surface_id", True),
        ("physical_floor_surface_id", "floor-1 "),
        ("room_entity_id", None),
        ("room_entity_id", True),
        ("room_entity_id", "room-1 "),
        ("source_room_face_record_id", None),
        ("source_room_face_record_id", True),
        ("source_room_face_record_id", "face-1 "),
        ("metric_area_quantity_id", None),
        ("metric_area_quantity_id", True),
        ("metric_area_quantity_id", " room-area-1"),
        ("source_sha256", "bad"),
        ("source_sha256", "b" * 64),
        ("revision_id", "foreign-revision"),
        ("viewport_id", "foreign-view"),
        ("metric_area_m2", 0.0),
        ("metric_area_m2", "8.64"),
        ("metric_area_authority", MeasurementAuthorityType.MODEL_DERIVED.value),
    ],
)
def test_floor_owner_cannot_borrow_source_quantity_from_altered_identity(field, bad):
    floor = _floor()
    altered = replace(floor, **{field: bad})
    claim = replace(_claim_with(_source_area()), canonical_floors=(altered,))
    assert publish_live_floor_area_quantities(claim) == ()
    assert publish_live_floor_area_quantities(_claim_with(_source_area()))[0].value == 8.64


def test_original_synthetic_source_area_still_emits_one_firm_exact_floor():
    source = _source_area()
    output = publish_live_floor_area_quantities(_claim_with(source))
    assert len(output) == 1
    assert output[0].family == "floor_area"
    assert output[0].status == AuthorityStatus.FIRM.value
    assert output[0].unit == "m2"
    assert output[0].value == 8.64
    assert output[0].input_entity_ids == ("floor-1",)
    assert output[0].metadata["upstream_room_area_quantity_id"] == source.quantity_id


def test_source_replay_input_permutation_is_idempotent_and_nonmutating():
    source = _source_area()
    before = source.to_dict()
    once = publish_live_floor_area_quantities(_claim_with(source))
    double = publish_live_floor_area_quantities(_claim_with(source, source))
    assert once == double
    assert source.to_dict() == before


def test_competing_firm_source_id_replay_is_quarantined_irrespective_of_order():
    source = _source_area()
    conflicting = replace(source, value=8.65)
    for order in ((source, conflicting), (conflicting, source),
                  (source, conflicting, source)):
        assert publish_live_floor_area_quantities(_claim_with(*order)) == ()
    assert publish_live_floor_area_quantities(_claim_with(source))[0].value == 8.64
