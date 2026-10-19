"""Floor area trade reuse must not turn arbitrary authority into FIRM."""
import pytest
from pb_cross_trade_geometry_reuse import derive_floor_surface_trade_quantities,derive_ceiling_trade_quantities
from tests.test_cross_trade_geometry_reuse import _floor_surface,_ceiling_surface

FLOOR={"flooring":{"material":"vinyl","section":"Internal","evidence_ids":["ev-fin"]}}
CEILING={"lining":{"material":"plasterboard","section":"Internal","evidence_ids":["ev-lin"]}}

def test_true_documented_or_scaled_source_area_retains_original_floor_m2():
    for source in ["pdf_scaled","documented_dimension","user_approved"]:
        floor=_floor_surface()
        floor["metric_area_authority"]=source
        rows=derive_floor_surface_trade_quantities(floor,FLOOR)
        assert len(rows)==1 and rows[0].quantity==24.0

@pytest.mark.parametrize("bad",[
    None,True,False,4.0,"assumed","default","model_derived","ai_detected",
    "provisional","reference_only","pdf_scaled "," pdf_scaled",""
])
def test_forbidden_or_aliased_original_floor_area_authority_abstains(bad):
    floor=_floor_surface()
    floor["metric_area_authority"]=bad
    assert derive_floor_surface_trade_quantities(floor,FLOOR)==[]

@pytest.mark.parametrize("field,bad",[
    ("canonical_floor_id",True),("canonical_floor_id"," floor_101"),
    ("metric_area_quantity_id",123),("metric_area_quantity_id",True),
    ("metric_area_quantity_id"," qty-floor-101"),
])
def test_floor_original_object_and_quantity_ids_must_be_literal(field,bad):
    floor=_floor_surface()
    floor[field]=bad
    assert derive_floor_surface_trade_quantities(floor,FLOOR)==[]

def test_ceiling_scale_owner_id_is_exact_str_not_numeric_alias():
    ceiling=_ceiling_surface()
    for bad in [True,123," scale-record-1","scale-record-1 "]:
        changed={**ceiling,"physical_scale_record_id":bad}
        assert derive_ceiling_trade_quantities(changed,CEILING)==[]
