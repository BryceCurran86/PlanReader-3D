"""A boolean or corrupt drawing finish material is never quoteable."""
import pytest
from pb_cross_trade_geometry_reuse import derive_wall_trade_quantities,derive_floor_surface_trade_quantities
from tests.test_cross_trade_geometry_reuse import _wall,_floor_surface

def _wall_masonry(value):
    return derive_wall_trade_quantities(_wall(),{"masonry":{"material":value,"evidence_ids":["ev-material"]}})

@pytest.mark.parametrize("bad",[True,False,1,42,{"unexpected":"dict"},["tile"]," tile ","tile "," "])
def test_original_wall_material_must_be_exact_source_owned_string(bad):
    assert _wall_masonry(bad)==[]

def test_explicit_invalid_material_cannot_escape_through_fallback_system():
    out=derive_wall_trade_quantities(_wall(),{"masonry":{
        "material":True, "system":"brickwork",
        "evidence_ids":["ev-source"]
    }})
    assert out==[]

def test_original_unset_material_can_fall_back_to_real_source_system():
    out=derive_wall_trade_quantities(_wall(),{"masonry":{
        "material":None,"system":"230mm brickwork",
        "evidence_ids":["ev-source"]
    }})
    assert len(out)==1 and out[0].substrate=="230mm brickwork"

@pytest.mark.parametrize("bad",[" true "," vinyl ",True,12])
def test_invalid_floor_finish_definition_does_not_mint_floor_area(bad):
    out=derive_floor_surface_trade_quantities(_floor_surface(),{
       "flooring":{"material":bad,"evidence_ids":["ev-finish"],"section":"Internal"}
    })
    assert out==[]
