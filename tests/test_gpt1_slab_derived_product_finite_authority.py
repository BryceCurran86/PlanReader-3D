"""No infinite/corrupt cubic metre products from finite original slab inputs."""
from pb_cross_trade_geometry_reuse import derive_slab_trade_quantities

def _slab(area,thick,poly=None):
    return dict(canonical_slab_id="slab-src",area_m2=area,thickness_m=thick,
       geometry_complete=True,thickness_complete=True,
       polygon_m=poly,provenance={"evidence_ids":["slab-area-receipt"]})
SPEC={"concrete":{"material":"25 MPa concrete","evidence_ids":["concrete-spec"]},
      "edge_formwork":{"material":"timber edge form","evidence_ids":["edge-spec"]}}

def test_legitimate_slab_volume_and_closed_edge_contact_remain_measured():
    slab=_slab(100.0,0.2,[(0,0),(10,0),(10,10),(0,10)])
    out=derive_slab_trade_quantities(slab,SPEC)
    assert [(q.element,q.quantity) for q in out]==[
        ("Slab concrete",20.0),("Slab edge formwork",8.0)]

def test_individually_finite_but_overflowing_concrete_source_product_abstains():
    assert derive_slab_trade_quantities(_slab(1e308,1e308),SPEC)==[]

def test_large_slab_perimeter_contact_does_not_crash_other_trade_quantity():
    huge=[(0.0,0.0),(1e155,0.0),(1e155,1e155),(0.0,1e155)]
    # If a geometry engine rejects a huge physically noncredible ring
    # altogether, independent genuine source scope controls remain intact.
    result=derive_slab_trade_quantities(_slab(100.0,0.2,huge),SPEC)
    assert all(q.quantity>0.0 for q in result)
    assert not any(q.element=="Slab edge formwork" for q in result)
