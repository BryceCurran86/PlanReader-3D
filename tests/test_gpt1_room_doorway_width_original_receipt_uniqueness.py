"""Duplicate measured doorway spans cannot double-deduct room skirting."""
from pb_cross_trade_geometry_reuse import derive_space_trade_quantities
from tests.test_gpt1_room_skirting_source_doors_complete import ROOM,SPEC,DOOR
import pytest

def _rows(doors,room=ROOM):
    return [q for q in derive_space_trade_quantities(room,SPEC,doors)
          if q.element=="Skirting boards"]

def test_independent_source_doorways_deduct_once_each():
    other={**DOOR,"opening_identity_id":"door-two",
       "source_width_evidence_ids":["source-door-width-two"],"width_m":0.8}
    assert [r.quantity for r in _rows([DOOR,other])]==[18.3]
    assert [r.quantity for r in _rows([other,DOOR])]==[18.3]

def test_different_physical_openings_reusing_one_original_width_receipt_abstain():
    other={**DOOR,"opening_identity_id":"door-two","width_m":0.8}
    assert _rows([DOOR,other])==[]
    assert _rows([other,DOOR])==[]

@pytest.mark.parametrize("bad",[True,False,1,"room-1 "," room-1",None])
def test_untyped_or_padded_canonical_room_cannot_mint_cornice_or_deduct_doors(bad):
    q=derive_space_trade_quantities({**ROOM,"canonical_room_id":bad},{
       **SPEC,"cornice":{"material":"90mm cove","section":"Internal","evidence_ids":["ev-cove"]}
    },[DOOR])
    assert q==[]
