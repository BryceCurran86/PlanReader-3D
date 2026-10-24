"""Generic construction-framing assumptions are not original Measured takeoffs."""
from __future__ import annotations
import pytest
from pb_carpentry_trade_authority import (
    CarpentryElementSpec,calculate_wall_framing_items
)
def _s(**kw):
    args=dict(element_type="wall_frame",element_id="source-neutral-wall",
        description="wall",length_m=12.0,height_m=2.7,stud_spacing_mm=450,
        openings=[{"width":1.8,"height":1.2}])
    args.update(kw)
    return CarpentryElementSpec(**args)

def test_positive_wall_framing_numeric_candidates_preserved_provisional():
    rows=calculate_wall_framing_items(_s())
    assert [r.quantity for r in rows]==[32.4,36.0,32.0,12.0]
    assert all(r.quantity_status=="Provisional" for r in rows)
    assert all(r.inclusion_status=="PROVISIONAL" for r in rows)

@pytest.mark.parametrize("bad",[True,False,"12",float("nan"),float("inf"),10**400,0,-1])
def test_nonphysical_wall_run_is_not_source_measured(bad):
    assert calculate_wall_framing_items(_s(length_m=bad))==[]

@pytest.mark.parametrize("bad",[True,False,450.5,"450",0,-450,None])
def test_stud_spacing_cannot_be_inferred_or_coerced_from_untyped_spec(bad):
    assert calculate_wall_framing_items(_s(stud_spacing_mm=bad))==[]

@pytest.mark.parametrize("openings",[[{}],[{"width":1.8}],[{"height":1.2}],
     [{"width":1.8,"height":3.0}],[{"width":True,"height":1.2}],
     [{"width":1.8,"height":"1.2"}],[None]])
def test_unresolved_structural_openings_cannot_issue_stud_counts(openings):
    assert calculate_wall_framing_items(_s(openings=openings))==[]

def test_unmodelled_openings_do_not_default_to_one():
    rows=calculate_wall_framing_items(_s(openings=[]))
    assert rows[2].quantity==30
    assert all(r.inclusion_status=="PROVISIONAL" for r in rows)
