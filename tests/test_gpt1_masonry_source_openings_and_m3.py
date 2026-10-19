"""Gold-free opening-area, grout-unit and lintel-completeness checks."""
from __future__ import annotations
import pytest
from pb_masonry_trade_authority import (
    MasonryWallSpec,calculate_brickwork_items,calculate_blockwork_items,
    calculate_lintel_items,
)


def _s(kind="brickwork_veneer",**kw):
    data=dict(element_id="source-neutral",wall_type=kind,
      description="synthetic wall",section="External",length_m=15.0,
      height_m=2.7,openings=[{"width":1.8,"height":1.2,"area":2.16}])
    data.update(kw)
    return MasonryWallSpec(**data)


def test_brickwork_positive_original_aperture_retained_provisional_ties_dpc():
    items=calculate_brickwork_items(_s())
    assert len(items)==3
    assert items[0].quantity==38.34
    assert all(x.inclusion_status=="PROVISIONAL" for x in items)


@pytest.mark.parametrize("ops",[
    [{"area":0.0}],[{"area":True}],[{"area":"2.16"}],
    [{"area":float("inf")}],[{"width":1.8}],
    [{"height":1.2}],[{"width":1.8,"height":1.2,"area":3.0}],
    [{"width":20.0,"height":3.0}], [{"area":42.0}],
    [{"width":1.8,"height":1.2,"area":2.16},{}],
])
def test_incomplete_or_impossible_original_opening_abstains_bricks_and_blocks(ops):
    assert calculate_brickwork_items(_s(openings=ops))==[]
    assert calculate_blockwork_items(_s("blockwork_200",openings=ops))==[]


def test_real_grout_volume_is_m3_provisional_not_item():
    items=calculate_blockwork_items(_s(
        "blockwork_200",length_m=20.0,height_m=3.0,
        openings=[{"width":2.4,"height":2.1,"area":5.04}],
        core_fill="full",has_bond_beam=True,
    ))
    grout=next(x for x in items if "Core fill" in x.element)
    assert grout.quantity==5.50
    assert grout.unit=="m³"
    assert grout.inclusion_status=="PROVISIONAL"


@pytest.mark.parametrize("bad",[True,0,-0.3,"2.0",None,float("nan"),float("inf"),10**400])
def test_no_partial_lintel_set_can_ignore_one_bad_original_opening(bad):
    assert calculate_lintel_items(_s(openings=[
       {"width":1.2,"height":1.0},{"width":bad,"height":2.1}
    ]))==[]


def test_source_widths_allow_provisional_lintel_lengths_not_verified_sections():
    items=calculate_lintel_items(_s(openings=[
       {"width":1.2,"height":1.0},{"width":2.4,"height":2.1}
    ]))
    assert [x.quantity for x in items]==[1.5,2.7]
    assert all(x.quantity_status=="Provisional" for x in items)
