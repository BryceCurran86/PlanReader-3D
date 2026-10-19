"""Source-neutral structural concrete metric and count input proof tests."""
from __future__ import annotations
import pytest
from pb_concreting_trade_authority import (
    ConcreteElementSpec, calculate_slab_concrete_items,
    calculate_footing_concrete_items,calculate_column_concrete_items,
    calculate_beam_concrete_items,calculate_stairs_concrete_items,
)


def _spec(kind,**kwargs):
    args=dict(
        element_type=kind,element_id="synthetic-concrete",
        section="Structure",description="synthetic concrete metric",
    )
    args.update(kwargs)
    return ConcreteElementSpec(**args)


@pytest.mark.parametrize("source_area", [True,"100",float("nan"),float("inf"),10**400,-3.0])
def test_bad_original_slab_area_cannot_become_firm_concrete_supply(source_area):
    assert calculate_slab_concrete_items(_spec(
        "slab",area_m2=source_area,length_m=10,width_m=10,thickness_m=0.1,
    )) == []


def test_original_slab_two_axis_area_disagreement_never_selects_larger_quantity():
    assert calculate_slab_concrete_items(_spec(
        "slab",area_m2=120,length_m=10,width_m=10,thickness_m=0.1,
    )) == []


def test_matching_source_slab_area_and_dimensions_retain_physical_m3_quantity():
    rows=calculate_slab_concrete_items(_spec(
        "slab",area_m2=100,length_m=10,width_m=10,
        thickness_m=0.1,perimeter_lm=40,
    ))
    assert any(r.unit=="m³" and r.quantity==10.0 for r in rows)


@pytest.mark.parametrize("bad", [True,1.2,"3",0,None])
def test_footing_pad_forged_physical_count_abstains(bad):
    assert calculate_footing_concrete_items(_spec(
        "footing_pad",count=bad,length_m=1.2,width_m=1.2,thickness_m=0.5,
    )) == []


@pytest.mark.parametrize("bad", [True,1.2,"3",0,None])
def test_bored_pier_forged_physical_count_abstains(bad):
    assert calculate_footing_concrete_items(_spec(
        "bored_pier",count=bad,width_m=0.45,height_m=3.0,
    )) == []


@pytest.mark.parametrize("bad", [True,1.5,"4",0,None])
def test_column_forged_source_count_abstains(bad):
    assert calculate_column_concrete_items(_spec(
        "column",count=bad,length_m=0.35,width_m=0.35,height_m=2.7,
    )) == []


@pytest.mark.parametrize("bad", [True,"25",float("nan"),float("inf"),10**400])
def test_beam_untyped_metric_length_abstains(bad):
    assert calculate_beam_concrete_items(_spec(
        "beam",length_m=bad,width_m=0.4,thickness_m=0.6,
    )) == []


@pytest.mark.parametrize("bad", [True,1.5,"2",0,None])
def test_stair_flight_source_count_must_be_exact_integer(bad):
    assert calculate_stairs_concrete_items(_spec(
        "stairs",count=bad,width_m=1.0,height_m=2.7,
    )) == []


def test_original_stair_flight_count_survives_but_assumed_step_formwork_is_provisional():
    rows=calculate_stairs_concrete_items(_spec(
        "stairs",count=2,width_m=1.0,height_m=2.7,
    ))
    assert len(rows)==2
    assert rows[0].quantity==2.0
    assert rows[1].quantity_status=="Provisional"
    assert rows[1].inclusion_status=="PROVISIONAL"
