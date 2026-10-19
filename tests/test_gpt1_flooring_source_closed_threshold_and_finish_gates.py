"""Physical inside-face and threshold assumptions stay provisional in generic flooring."""
import pytest
from pb_flooring_trade_authority import (
    FlooringSpaceSpec,calculate_carpet_flooring_items,
    calculate_timber_flooring_items,calculate_tiling_items,
)


def _s(kind="tiles",**kw):
    data=dict(
        space_id="source-neutral-room",room_name="Sample",floor_finish=kind,
        area_m2=8.40,perimeter_lm=11.6,
    )
    data.update(kw)
    return FlooringSpaceSpec(**data)


@pytest.mark.parametrize("bad",[True,False,"8.4",float("nan"),float("inf"),10**400,0,-8.4])
@pytest.mark.parametrize("func,finish",[
    (calculate_tiling_items,"tiles"),
    (calculate_timber_flooring_items,"timber"),
    (calculate_carpet_flooring_items,"carpet"),
])
def test_invalid_or_untyped_floor_m2_does_not_become_measured_internal_finish(bad,func,finish):
    assert func(_s(finish,area_m2=bad)) == []


def test_original_unmarked_finish_remains_provisional_not_commercial_firm():
    rows=calculate_tiling_items(_s())
    assert rows
    assert all(x.quantity_status=="Provisional" for x in rows)
    assert all(x.inclusion_status=="PROVISIONAL" for x in rows)
    assert rows[0].quantity==8.4


def test_default_900mm_doors_do_not_gain_verified_skirting_length():
    rows=calculate_tiling_items(_s())
    skirting=next(x for x in rows if "skirtings" in x.element.lower())
    assert skirting.quantity==10.7
    assert skirting.quantity_status=="Provisional"
    assert "assumption" in skirting.notes.lower()


@pytest.mark.parametrize("bad",["11.6",float("nan"),float("inf"),True,None,-5.0])
def test_invalid_original_room_perimeter_cannot_mint_skirting_or_waterproof_upturn(bad):
    rows=calculate_tiling_items(_s(perimeter_lm=bad,requires_waterproofing=True))
    assert len(rows)==1
    assert all("Waterproofing" not in x.element for x in rows)
    assert all("skirtings" not in x.element.lower() for x in rows)


def test_excess_door_width_is_not_silently_clamped_to_zero_skirting():
    rows=calculate_carpet_flooring_items(_s(
        "carpet",perimeter_lm=3.0,door_deduction_lm=5.0,
    ))
    assert len(rows)==2
    assert all(r.unit=="m²" for r in rows)


def test_generic_wet_area_waterproof_upturn_and_screed_are_provisional():
    rows=calculate_tiling_items(_s(
        is_wet_area=True,requires_waterproofing=True,requires_screed=True,
    ))
    assert len(rows)==4
    membrane=next(x for x in rows if "waterproofing" in x.element.lower())
    screed=next(x for x in rows if "screed" in x.element.lower())
    assert membrane.quantity==10.14
    assert membrane.inclusion_status=="PROVISIONAL"
    assert screed.inclusion_status=="PROVISIONAL"
    assert all(x.confidence=="Provisional" for x in rows)


@pytest.mark.parametrize("bad",["true",1,None])
def test_untyped_wet_area_flag_never_mints_wet_area_material(bad):
    assert calculate_tiling_items(_s(is_wet_area=bad)) == []
