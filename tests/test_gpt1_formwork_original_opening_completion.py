"""Synthetic formwork quantity safeguards for complete source apertures and axes."""
from __future__ import annotations
import pytest
from pb_formwork_trade_authority import (
    FormworkElementSpec,calculate_soffit_formwork_items,
    calculate_edge_formwork_items,calculate_wall_formwork_items,
    calculate_column_formwork_items,calculate_beam_formwork_items,
    calculate_stepdowns_and_penetrations,
)


def _s(kind,**kw):
    data=dict(element_type=kind,element_id="source-neutral",section="Structure",
              description="synthetic physical formwork")
    data.update(kw)
    return FormworkElementSpec(**data)


def test_authentic_wall_deductions_preserve_net_double_form_faces_and_blockouts():
    source=_s("wall",length_m=20,height_m=3,depth_m=0.2,
              openings=[{"width":2.0,"height":1.5,"area":3.0},
                        {"width":1.0,"height":2.1,"area":2.1}])
    rows=calculate_wall_formwork_items(source)
    assert len(rows)==3
    assert rows[0].quantity==109.8
    assert rows[1].quantity==7.0
    assert all(x.inclusion_status=="PROVISIONAL" for x in rows[1:])


@pytest.mark.parametrize("openings",[
    [{"width":2.0,"height":1.5,"area":4.0}],
    [{"height":1.5}], [{"width":2.0}], [{"area":"3.0"}],
    [{"width":True,"height":1.5,"area":3.0}],
    [{"area":float("nan")}],
    [{"area":61.0}], [{"width":15.0,"height":5.0}],
    [{"width":2.0,"height":1.5,"area":3.0},{"area":None}],
])
def test_missing_or_conflicting_aperture_deduction_abstains_whole_wall(openings):
    rows=calculate_wall_formwork_items(_s(
        "wall",length_m=20,height_m=3,depth_m=0.2,openings=openings,
    ))
    assert rows==[]


@pytest.mark.parametrize("bad",[True,False,"20",float("nan"),float("inf"),10**400,0.0])
def test_untyped_wall_metric_cannot_mint_double_side_m2(bad):
    assert calculate_wall_formwork_items(_s("wall",length_m=bad,height_m=3))==[]


def test_genuine_finite_soffit_source_area_is_kept_without_inventing_drop_panels():
    rows=calculate_soffit_formwork_items(_s(
        "soffit",area_m2=200,propping_height_m=3.0,
    ))
    assert len(rows)==1 and rows[0].quantity==200


def test_conflicting_original_soffit_area_and_axes_abstain():
    assert calculate_soffit_formwork_items(_s(
        "soffit",area_m2=200,length_m=10,width_m=10,
    ))==[]


@pytest.mark.parametrize("bad",[True,1.5,"4",0,None])
def test_original_column_and_penetration_count_never_coerces_bool_fraction(bad):
    assert calculate_column_formwork_items(_s(
        "column",count=bad,width_m=.4,depth_m=.4,height_m=3,
    ))==[]
    assert calculate_stepdowns_and_penetrations(_s(
        "penetration",count=bad,width_m=.2,depth_m=.2,
    ))==[]


def test_original_beam_and_slab_edge_finite_dimensions_remain_accepted():
    assert calculate_beam_formwork_items(_s(
        "beam",length_m=15,width_m=.4,depth_m=.5,
    ))[0].quantity==21.0
    assert calculate_edge_formwork_items(_s(
        "edge",perimeter_lm=60,depth_m=.2,
    ))[0].quantity==60.0
