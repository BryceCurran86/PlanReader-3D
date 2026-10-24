"""Original slab polygons must be simple finite physical edge loops."""
import pytest
from pb_cross_trade_geometry_reuse import derive_slab_trade_quantities

BASE = dict(canonical_slab_id="slab-a",area_m2=100.0,thickness_m=0.2,
  geometry_complete=True,thickness_complete=True,
  provenance={"evidence_ids":["source-slab-boundary"]})
SPECS = {"edge_formwork":{"material":"timber edge","evidence_ids":["ev-formwork"]}}

def _edge(points):
    slab={**BASE, "polygon_m":points}
    return [q for q in derive_slab_trade_quantities(slab,SPECS)
        if q.element=="Slab edge formwork"]

def test_source_simple_rectangle_generates_correct_metric_contact_area():
    out=_edge([(0,0),(10,0),(10,10),(0,10)])
    assert len(out)==1 and out[0].quantity==8.0

def test_legitimate_explicit_closed_ring_is_not_double_counted():
    out=_edge([(0,0),(10,0),(10,10),(0,10),(0,0)])
    assert len(out)==1 and out[0].quantity==8.0

@pytest.mark.parametrize("invalid", [
 [(0,0),(10,10),(0,10),(10,0)],
 [(0,0),(10,0),(10,0),(0,10)],
 [(0,0),(0,10),(0,20)],
 [(0,0),(10,0),(10,10),(0,10),(10,0)],
 [(0,0),(10,0),(10,10),(0,"10")],
 [(0,0),(10,0),(10,10),(0,True)],
 [(0,0),(10,0),(10,float("inf")),(0,10)],
 [(0,0),(10,0),(10,float("nan")),(0,10)],
])
def test_crossed_duplicate_collinear_or_untyped_slab_loop_abstains(invalid):
    assert _edge(invalid)==[]
