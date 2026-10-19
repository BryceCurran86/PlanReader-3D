"""Original physical metric values cannot be cast from text or bools."""
import pytest
from pb_cross_trade_geometry_reuse import (
    derive_wall_trade_quantities, derive_slab_trade_quantities,
    derive_floor_surface_trade_quantities, derive_ceiling_trade_quantities,
    derive_space_trade_quantities
)
from tests.test_cross_trade_geometry_reuse import (
    _wall,_slab,_floor_surface,_ceiling_surface,_space
)

@pytest.mark.parametrize("invalid",[True,False,"24",b"24",None,float("nan"),float("inf"),10**400])
@pytest.mark.parametrize("model,key,fn,specs",[
    (_wall,"net_area_m2",derive_wall_trade_quantities,{"masonry":{"material":"brick","evidence_ids":["ev-brick"]}}),
    (_slab,"thickness_m",derive_slab_trade_quantities,{"concrete":{"material":"25 MPa","evidence_ids":["ev-concrete"]}}),
    (_floor_surface,"metric_area_m2",derive_floor_surface_trade_quantities,{"flooring":{"material":"vinyl","section":"Internal","evidence_ids":["ev-floor"]}}),
    (_ceiling_surface,"area_m2",derive_ceiling_trade_quantities,{"lining":{"material":"plasterboard","section":"Internal","evidence_ids":["ev-ceil"]}}),
    (_space,"perimeter_m",derive_space_trade_quantities,{"cornice":{"material":"90mm cove","section":"Internal","evidence_ids":["ev-cove"]}}),
])
def test_bad_source_metric_never_mints_cross_trade_quantity(invalid,model,key,fn,specs):
    host=model()
    host[key]=invalid
    assert fn(host,specs)==[]

def test_valid_native_metric_wall_area_keeps_original_value():
    rows=derive_wall_trade_quantities(_wall(),{"masonry":{"material":"brick","evidence_ids":["ev-brick"]}})
    assert len(rows)==1
    assert rows[0].quantity==23.4
