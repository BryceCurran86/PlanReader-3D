"""Synthetic door-to-room material boundary source ownership and completeness."""
import pytest
from pb_cross_trade_geometry_reuse import derive_space_trade_quantities

ROOM={"canonical_room_id":"room-1","perimeter_m":20.0,"evidence_ids":["room-ring-source-1"]}
SPEC={"skirting":{"material":"MDF skirting","section":"Internal",
         "evidence_ids":["skirting-schedule-1"],
         "door_universe_complete":True,"door_source_scope_id":"room-1"}}
DOOR={"canonical_room_id":"room-1","opening_identity_id":"door-1",
      "width_m":0.9,"source_width_evidence_ids":["source-physical-door-width"]}

def _skirting(doors, spec=SPEC):
    return [q for q in derive_space_trade_quantities(
        ROOM,specs=spec,doors=doors
    ) if q.element=="Skirting boards"]

def test_exact_original_single_room_door_source_is_deducted_once():
    values=_skirting([DOOR])
    assert len(values)==1
    assert values[0].quantity==19.1

@pytest.mark.parametrize("bad",[
    {"width_m":0.9},
    {**DOOR,"canonical_room_id":"room-foreign"},
    {**DOOR,"opening_identity_id":""},
    {**DOOR,"source_width_evidence_ids":[]},
    {**DOOR,"source_width_evidence_ids":[" ev-door"]},
    {**DOOR,"width_m":True},
    {**DOOR,"width_m":"0.9"},
    {**DOOR,"width_m":float("inf")},
    {**DOOR,"width_m":float("nan")},
])
def test_missing_door_to_room_source_owner_does_not_mint_skirting(bad):
    assert _skirting([bad])==[]

def test_two_replays_of_same_original_door_are_not_counted_twice():
    assert _skirting([DOOR,DOOR])==[]

def test_incomplete_original_door_candidate_universe_cannot_publish_full_skirting():
    missing={**SPEC["skirting"],"door_universe_complete":False}
    assert _skirting([DOOR],{"skirting":missing})==[]

def test_empty_door_universe_requires_exact_source_completeness_scope():
    assert _skirting([])==[pytest.approx(_skirting([])[0])] if False else len(_skirting([]))==1
    missing={**SPEC["skirting"],"door_universe_complete":False}
    assert _skirting([],{"skirting":missing})==[]
