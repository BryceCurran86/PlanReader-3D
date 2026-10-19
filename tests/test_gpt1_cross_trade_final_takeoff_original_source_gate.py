"""Final customer row must not launder type-cast or unowned quantities."""
from dataclasses import replace
import pytest
from pb_cross_trade_geometry_reuse import DerivedTradeQuantity,to_takeoff_rows
from pb_takeoff_row_contract import TakeoffRowContractError

def _q(**changes):
    data=dict(trade_scope="masonry",section="External",element="Wall",
       location="wall-1",substrate="brick",quantity=12.5,unit="m²",
       host_object_id="wall-1",host_object_type="WALL",
       derivation_formula="original metric wall net area",
       host_evidence_ids=("ev-wall",),spec_evidence_ids=("ev-brick",))
    data.update(changes)
    return DerivedTradeQuantity(**data)

def test_original_evidence_bearing_row_keeps_metric_m2_and_owner():
    row=to_takeoff_rows(9,[_q()])[0]
    assert row[0]==9 and row[6]==12.5 and row[7]=="m²"

@pytest.mark.parametrize("value",[True,False,"12.5",b"12.5",None,float("nan"),float("inf"),10**400])
def test_untyped_original_derived_quantity_cannot_be_constructed(value):
    with pytest.raises(ValueError):
        _q(quantity=value)

@pytest.mark.parametrize("workspace",[True,False,0,-1,1.0,"1",None])
def test_untyped_customer_workspace_does_not_get_source_issued_rows(workspace):
    with pytest.raises(TakeoffRowContractError):
        to_takeoff_rows(workspace,[_q()])

@pytest.mark.parametrize("bad",[
 (),("ev-a","ev-a"),(" ev-a",),("ev-a ",),(True,),(None,),("ev-a",True)
])
def test_final_customer_row_rejects_host_provenance_normalisation(bad):
    with pytest.raises(TakeoffRowContractError):
        to_takeoff_rows(1,[_q(host_evidence_ids=bad)])

def test_zero_length_derived_quantity_cannot_be_charged_as_row():
    with pytest.raises(TakeoffRowContractError):
        to_takeoff_rows(1,[_q(quantity=0.0)])
