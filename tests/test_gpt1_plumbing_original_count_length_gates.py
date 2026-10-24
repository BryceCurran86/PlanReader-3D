"""Source-neutral plumbing quantity tests. All amounts are synthetic."""
from __future__ import annotations

import pytest
from pb_plumbing_trade_authority import (
    PlumbingFixtureSpec, PlumbingPipeRunSpec,
    calculate_fixture_items, calculate_drainage_items,
    calculate_water_supply_items, calculate_stack_and_penetration_items,
)


def _fixture(count):
    return PlumbingFixtureSpec(
        fixture_type="wc",fixture_mark="WC-SYNTHETIC",
        description="toilet",location="Room",count=count,
    )


def _run(kind, length, bore=100):
    return PlumbingPipeRunSpec(
        system_type=kind,nominal_dia_mm=bore,material="PVC-DWV",
        description="synthetic hydraulic source",length_m=length,
    )


@pytest.mark.parametrize("bad", [True, False, 1.1, "2", -1, 0, None, float("nan")])
def test_untyped_or_fractional_plumbing_fixture_symbol_count_never_measured(bad):
    assert calculate_fixture_items(_fixture(bad)) == []


def test_exact_original_plumbing_fixture_count_preserved_roughin_provisional():
    rows = calculate_fixture_items(_fixture(2))
    assert len(rows) == 2
    assert rows[0].quantity == rows[1].quantity == 2.0
    assert rows[0].quantity_status == "Measured"
    assert rows[1].quantity_status == "Provisional"
    assert rows[1].inclusion_status == "PROVISIONAL"


@pytest.mark.parametrize("bad", [
    True,False,"35",None,float("nan"),float("inf"),10**400,-10,0,
])
@pytest.mark.parametrize("fn,kind", [
    (calculate_drainage_items,"drainage"),
    (calculate_water_supply_items,"cold_water"),
    (calculate_stack_and_penetration_items,"stack"),
])
def test_bogus_hydraulic_run_metre_input_never_mints_measured_pipes(fn,kind,bad):
    assert fn(_run(kind,bad)) == []


@pytest.mark.parametrize("bad", [True,False,1.5,"100",-1,0,None])
def test_nominal_hydraulic_bore_requires_exact_positive_millimetres(bad):
    assert calculate_drainage_items(_run("drainage",35.0,bad)) == []


def test_source_sized_sewer_works_with_provisional_only_inspection_positions():
    rows=calculate_drainage_items(_run("drainage",35.0))
    assert len(rows)==2 and rows[0].quantity==35.0
    assert rows[0].quantity_status=="Measured"
    assert rows[1].quantity==2.0
    assert rows[1].quantity_status=="Provisional"
    assert rows[1].inclusion_status=="PROVISIONAL"


def test_vertical_pipe_has_original_run_but_not_invented_verified_fire_collars():
    rows=calculate_stack_and_penetration_items(_run("stack",9.0))
    assert len(rows)==2
    assert rows[0].quantity==9.0
    assert rows[0].quantity_status=="Measured"
    assert rows[1].quantity==3.0
    assert rows[1].quantity_status=="Provisional"
    assert rows[1].inclusion_status=="PROVISIONAL"
