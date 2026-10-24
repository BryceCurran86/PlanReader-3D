"""One producer source receipt is not two independent measurements."""
import pytest
from pb_cross_trade_geometry_reuse import (
    derive_wall_trade_quantities,derive_floor_surface_trade_quantities,
    derive_ceiling_trade_quantities,derive_space_trade_quantities
)
from tests.test_cross_trade_geometry_reuse import _wall,_floor_surface,_ceiling_surface,_space

TRADES=[
 (_wall,"wall",derive_wall_trade_quantities,{"masonry":{"material":"brick","evidence_ids":["ev-brick"]}}),
 (_floor_surface,"floor",derive_floor_surface_trade_quantities,{"flooring":{"material":"vinyl","section":"Internal","evidence_ids":["ev-vinyl"]}}),
 (_ceiling_surface,"ceiling",derive_ceiling_trade_quantities,{"lining":{"material":"12mm plasterboard","section":"Internal","evidence_ids":["ev-lining"]}}),
 (_space,"space",derive_space_trade_quantities,{"cornice":{"material":"90mm cornice","section":"Internal","evidence_ids":["ev-cornice"]}}),
]
@pytest.mark.parametrize("bad",[
 ["ev-1","ev-1"],[" ev-1"],["ev-1 "],[True],[1],
 ["ev-1",None],["ev-1",True],[""],[],
 {"ev-1"}, "ev-1",
])
@pytest.mark.parametrize("hostkind,label,fn,spec",TRADES)
def test_original_host_source_receipts_untyped_or_duplicate_abstain(bad,hostkind,label,fn,spec):
    host=hostkind()
    host["evidence_ids"]=bad
    assert fn(host,spec)==[]

@pytest.mark.parametrize("bad",[["ev-1","ev-1"],[" ev-1"],["ev-1 "],[True],[""],[],{"ev-1"}])
def test_untrustworthy_trade_material_receipts_cannot_create_derived_items(bad):
    host=_wall()
    q=derive_wall_trade_quantities(host,{"masonry":{"material":"brick","evidence_ids":bad}})
    assert q==[]

def test_exact_original_source_identity_preserves_real_wall_quantity():
    q=derive_wall_trade_quantities(_wall(),{"masonry":{"material":"brick","evidence_ids":["ev-brick"]}})
    assert len(q)==1 and q[0].quantity==23.4
