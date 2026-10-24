"""Structural steel tonnage is a physical rate unit, not an item count."""
from __future__ import annotations
import pytest
from pb_structural_steel_trade_authority import (
    SteelMemberSpec,calculate_primary_member_items,
    calculate_purlin_and_girt_items,calculate_bracing_items,
    calculate_connection_fittings_allowance,
)
import pb_takeoff_row_contract as contract
from pb_quantity_takeoff_adapter import _unit_is_valid


def _s(**kw):
    data=dict(element_type="beam",element_id="source-neutral",
              section_mark="310UB40.4",description="beam",
              count=4,length_m=7.5,mass_kg_per_m=40.4,
              surface_area_m2_per_m=0.99)
    data.update(kw)
    return SteelMemberSpec(**data)


def test_steel_tonnage_canonical_editor_and_commercial_accept_exact_1_212_t():
    rows=calculate_primary_member_items(_s())
    assert "t" in contract.TAKEOFF_UNITS
    assert _unit_is_valid("t")
    mass=next(x for x in rows if x.unit=="t")
    assert mass.quantity==1.212
    assert mass.quantity_status=="Provisional"
    mapped=mass.to_core_row(1,"2026-10-19T18:00:00")
    assert mapped["unit"]=="t"
    assert mapped["quantity"]==1.212


def test_missing_source_section_mass_does_not_invent_tonnage():
    rows=calculate_primary_member_items(_s(mass_kg_per_m=0.0))
    assert len(rows)==2
    assert all(x.unit!="t" for x in rows)
    assert any(x.unit=="lm" for x in rows)


@pytest.mark.parametrize("bad",[True,False,1.5,"4",0,-1,None])
def test_steel_member_count_must_be_source_integer(bad):
    assert calculate_primary_member_items(_s(count=bad))==[]
    assert calculate_purlin_and_girt_items(_s(
        element_type="purlin",count=bad
    ))==[]
    assert calculate_bracing_items(_s(
        element_type="bracing",count=bad
    ))==[]


@pytest.mark.parametrize("bad",[True,False,"40.4",float("inf"),float("nan"),10**400,-1])
def test_bogus_primary_mass_is_never_minted_as_tonnes(bad):
    rows=calculate_primary_member_items(_s(mass_kg_per_m=bad))
    assert all(x.unit!="t" for x in rows)


def test_default_connections_are_provisional_tonnes_with_no_item_rate():
    row=calculate_connection_fittings_allowance([_s()],1,"now")
    assert row is not None
    assert row["unit"]=="t"
    assert row["quantity"]==0.121
    assert row["quantity_status"]=="Provisional"
    assert row["inclusion_status"]=="PROVISIONAL"


def test_incomplete_member_of_primary_universe_blocks_connection_allowance():
    assert calculate_connection_fittings_allowance([
        _s(),_s(element_id="source-missing-weight",mass_kg_per_m=0.0)
    ],1,"now") is None


@pytest.mark.parametrize("percent",[True,False,-5.0,0.0,101.0,"10",float("nan"),float("inf")])
def test_untyped_or_extreme_connection_allowance_cannot_mint_tonnes(percent):
    assert calculate_connection_fittings_allowance([_s()],1,"now",percent) is None
