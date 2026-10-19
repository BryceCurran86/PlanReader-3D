"""GPT1 Q01: FIRM canonical floors may only reuse typed source-owned room m²."""
from __future__ import annotations

from copy import copy
from dataclasses import replace

import pytest

from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
    publish_live_canonical_room_area_quantities,
)
from tests.test_live_floor_area_quantity_publication_integrity import (
    _source_area, _claim_with, _claim_with_canonical_room,
)
from tests.test_live_floor_finish_area_source_closed_export import _floor


def replay(**changes):
    original = copy(_source_area())
    for key, value in changes.items():
        object.__setattr__(original, key, value)
    return original


@pytest.mark.parametrize("bad", [True, False, "8.64", float("nan"), float("inf"), 0])
def test_replayed_source_value_cannot_make_positive_firm_floor_or_room_area(bad):
    forged = replay(value=bad)
    assert publish_live_floor_area_quantities(_claim_with(forged)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(forged)
    ) == ()


@pytest.mark.parametrize("bad", [True, False, "1.0", float("nan"), -0.2, 1.2])
def test_source_confidence_must_be_finite_typed_probability(bad):
    forged = replay(confidence=bad)
    assert publish_live_floor_area_quantities(_claim_with(forged)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(forged)
    ) == ()


@pytest.mark.parametrize("bad", [(), ("ev-area", "ev-area"), ("ev-room", "  "),
                                      ("ev-room", True), ("ev-room", "ev-area", "ev-room")])
def test_missing_duplicate_or_invalid_original_evidence_does_not_publish(bad):
    forged = replay(evidence_ids=bad)
    assert publish_live_floor_area_quantities(_claim_with(forged)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(forged)
    ) == ()


@pytest.mark.parametrize("bad", [True, "8.64", float("nan"), float("inf")])
def test_canonical_floor_metric_replay_cannot_authorize_firm_room_area(bad):
    floor = replace(_floor(), metric_area_m2=bad)
    claim = replace(_claim_with(_source_area()), canonical_floors=(floor,))
    assert publish_live_floor_area_quantities(claim) == ()


def test_original_firm_source_and_orthogonal_figured_area_work_without_scale():
    original = _source_area()
    floor = publish_live_floor_area_quantities(_claim_with(original))
    room = publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(original)
    )
    assert len(floor) == len(room) == 1
    assert floor[0].value == room[0].value == 8.64
    assert floor[0].unit == room[0].unit == "m2"



@pytest.mark.parametrize("corrupt_owner", [
    None, True, 7, "source-room-1", (), (" source-room-1",),
    ("source-room-1 ",), ("source-room-1", True),
])
def test_firm_floor_or_room_area_rejects_copied_source_owner_collection(corrupt_owner):
    forged = replay(input_entity_ids=corrupt_owner)
    assert publish_live_floor_area_quantities(_claim_with(forged)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(forged)
    ) == ()


@pytest.mark.parametrize("corrupt_id", [True, 123, "", " room-area-1", "room-area-1 "])
def test_firm_floor_or_room_area_rejects_copied_source_quantity_identity(corrupt_id):
    forged = replay(quantity_id=corrupt_id)
    assert publish_live_floor_area_quantities(_claim_with(forged)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(forged)
    ) == ()


def test_original_unmodified_source_membership_remains_firm_in_both_paths():
    source = _source_area()
    assert source.input_entity_ids == ("source-room-1",)
    assert len(publish_live_floor_area_quantities(_claim_with(source))) == 1
    assert len(publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(source)
    )) == 1



@pytest.mark.parametrize("field,forged", [
    ("metric_area_quantity_id", "room-area-1 "),
    ("metric_area_quantity_id", True),
    ("canonical_floor_id", " floor-1"),
    ("physical_floor_surface_id", "floor-1 "),
    ("room_entity_id", True),
    ("source_room_face_record_id", " face-1"),
])
def test_final_canonical_floor_refuses_cast_or_trim_of_original_physical_identity(field, forged):
    floor = replace(_floor(), **{field: forged})
    claim = replace(_claim_with(_source_area()), canonical_floors=(floor,))
    assert publish_live_floor_area_quantities(claim) == ()


def test_final_canonical_floor_keeps_original_source_room_area_identity():
    published = publish_live_floor_area_quantities(_claim_with(_source_area()))
    assert len(published) == 1
    assert published[0].value == 8.64
    assert published[0].metadata["upstream_room_area_quantity_id"] == "room-area-1"


@pytest.mark.parametrize("changes", [
    {"semantic_key": "room_area:foreign-source-room"},
    {"semantic_key": "room_area:source-room-1 "},
    {"semantic_key": "room_area:SOURCE-ROOM-1"},
    {"semantic_key": "room_area:source-room-2", "input_entity_ids": ("source-room-1",)},
    {"input_entity_ids": ("another-source-room",)},
    {"input_entity_ids": ("source-room-1",), "semantic_key": "room_area:source-room-1:foreign"},
])
def test_source_owner_semantic_must_equal_original_input_entity_for_both_reissues(changes):
    # Even the correct quantity ID, original metric value, and copied
    # evidence receipts cannot turn a mismatched source room owner FIRM.
    source = replay(**changes)
    assert publish_live_floor_area_quantities(_claim_with(source)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(source)
    ) == ()


def test_exact_source_room_owner_pair_preserves_unscaled_documented_area():
    source = _source_area()
    assert source.semantic_key == f"room_area:{source.input_entity_ids[0]}"
    assert len(publish_live_floor_area_quantities(_claim_with(source))) == 1
    assert len(publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(source)
    )) == 1


@pytest.mark.parametrize("bad", [
    "", "fake-source-hash", "a" * 63, "a" * 65,
    "g" * 64, " " + "a" * 63, "a" * 63 + " ", True, None, 23,
])
def test_copied_invalid_floor_source_sha_never_reissues_firm_source_area(bad):
    # Both apparent original owners carry the same forged SHA, so simple
    # metadata equality cannot be accepted as evidence of an original PDF.
    source = _source_area()
    forged = replace(
        source,
        metadata={**source.metadata, "source_sha256":bad},
    )
    floor = replace(_floor(), source_sha256=bad)
    claim = replace(
        _claim_with(forged),
        canonical_floors=(floor,),
    )
    assert publish_live_floor_area_quantities(claim) == ()
    assert publish_live_canonical_room_area_quantities(claim) == ()


@pytest.mark.parametrize("bad", [
    "", "fake-room-sha", "a" * 63, "a" * 65, "g" * 64,
    " a" + "a" * 62, True, None, 19,
])
def test_foreign_or_malformed_canonical_room_source_sha_abstains_without_crash(bad):
    claim = _claim_with_canonical_room(_source_area())
    original_floor = publish_live_floor_area_quantities(claim)
    assert len(original_floor) == 1
    foreign_room = replace(claim.canonical_rooms[0], source_sha256=bad)
    changed = replace(claim, canonical_rooms=(foreign_room,))
    # The valid floor claim is unrelated to an imported malformed canonical
    # room receipt; only the canonical ROOM reissue must be withheld.
    assert publish_live_floor_area_quantities(changed) == original_floor
    assert publish_live_canonical_room_area_quantities(changed) == ()


def test_valid_case_folded_sha_keeps_original_producer_firm_floor_and_room():
    src = _source_area()
    upper_sha = "A" * 64
    same = replace(
        src, metadata={**src.metadata, "source_sha256":upper_sha},
    )
    floor = replace(_floor(), source_sha256=upper_sha)
    claim = replace(
        _claim_with_canonical_room(same),
        canonical_floors=(floor,),
        canonical_rooms=(
            replace(
                _claim_with_canonical_room(same).canonical_rooms[0],
                source_sha256=upper_sha,
            ),
        ),
    )
    assert len(publish_live_floor_area_quantities(claim)) == 1
    assert len(publish_live_canonical_room_area_quantities(claim)) == 1
    assert len(publish_live_floor_area_quantities(_claim_with(src))) == 1


@pytest.mark.parametrize("alias", [True, 1, 1.0, " 1", "1 ", "", None])
def test_source_room_area_page_alias_never_mints_firm_canonical_floor(alias):
    source = _source_area()
    forged = replace(source, metadata={**source.metadata, "page_no": alias})
    assert publish_live_floor_area_quantities(_claim_with(forged)) == ()
    assert publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(forged)
    ) == ()


@pytest.mark.parametrize("alias", [True, 1, 1.0, " 1", "1 ", "", None])
def test_canonical_floor_original_page_alias_cannot_launder_source_area(alias):
    floor = replace(_floor(), page_id=alias)
    claim = replace(
        _claim_with_canonical_room(_source_area()),
        canonical_floors=(floor,),
    )
    assert publish_live_floor_area_quantities(claim) == ()


def test_original_exact_room_to_floor_source_page_remains_firm():
    assert len(publish_live_floor_area_quantities(_claim_with(_source_area()))) == 1
    assert len(publish_live_canonical_room_area_quantities(
        _claim_with_canonical_room(_source_area())
    )) == 1
