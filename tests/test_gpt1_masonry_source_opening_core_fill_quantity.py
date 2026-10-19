"""Gold-free masonry source-area and material assumption coverage."""
from __future__ import annotations
import pytest
from pb_masonry_trade_authority import (
    MasonryWallSpec,calculate_brickwork_items,
    calculate_blockwork_items,calculate_lintel_items,
)

def _w(kind="brickwork_veneer",openings=None,**kw):
    args=dict(element_id="synthetic-masonry",wall_type=kind,
              description="synthetic source face",length_m=15.0,height_m=2.7,
              openings=[] if openings is None else openings)
    args.update(kw)
    return MasonryWallSpec(**args)

def test_real_typed_opening_deductions_keep_one_net_face():
    rows=calculate_brickwork_items(_w(openings=[
        {"width":1.8,"height":1.2,"area":2.16},
        {"width":0.9,"height":2.1,"area":1.89},
    ]))
    assert len(rows)==3
    assert rows[0].quantity==36.45
    assert rows[1].quantity_status=="Provisional"
    assert rows[2].quantity_status=="Provisional"

@pytest.mark.parametrize("openings", [
    [{"width":1.0}], [{"height":2.0}], [{"area":None}],
    [{"width":1.0,"height":2.0,"area":3.0}], [{"area":"2"}],
    [{"area":True}], [{"area":float("nan")}], [{"area":50.0}],
    [{"area":12.0},{"area":40.0}], [None], [3.0],
])
def test_corrupted_original_masonry_apertures_veto_whole_face(openings):
    spec=_w(openings=openings)
    assert calculate_brickwork_items(spec)==[]
    assert calculate_blockwork_items(_w("blockwork_200",openings=openings))==[]

@pytest.mark.parametrize("metric", [True,"15",float("inf"),float("nan"),10**400,0,-15])
def test_untyped_masonry_wall_metres_never_become_net_face(metric):
    assert calculate_brickwork_items(_w(length_m=metric))==[]

def test_core_fill_quantities_are_cubic_metres_and_design_estimates_only():
    result=calculate_blockwork_items(_w(
        "blockwork_200",length_m=20.0,height_m=3.0,
        openings=[{"width":2.4,"height":2.1,"area":5.04}],
        core_fill="full",has_bond_beam=True,
    ))
    grout=next(x for x in result if "Core fill" in x.element)
    assert grout.unit=="m³"
    assert grout.quantity==5.50
    assert grout.inclusion_status=="PROVISIONAL"
    assert grout.quantity_status=="Provisional"

def test_generic_lintel_bearings_are_not_source_measured():
    r=calculate_lintel_items(_w(openings=[{"width":1.2,"height":1.0}]))
    assert len(r)==1 and r[0].quantity==1.5
    assert r[0].quantity_status=="Provisional"
    assert r[0].inclusion_status=="PROVISIONAL"
