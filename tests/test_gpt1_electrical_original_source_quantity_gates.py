"""Synthetic electrical takeoff authority completeness tests."""
import pytest
from pb_electrical_trade_authority import (
    ElectricalDeviceSpec,ElectricalContainmentSpec,
    calculate_switchboard_items,calculate_lighting_items,
    calculate_power_items,calculate_data_items,calculate_containment_items,
)


def _device(kind="light",count=2,mark="L-SYNTHETIC",dedicated=False):
    return ElectricalDeviceSpec(
        device_type=kind,device_mark=mark,description="fixture",
        location="Room",count=count,is_dedicated_circuit=dedicated,
    )


def _run(length=35.0,size="25mm conduit",kind="conduit"):
    return ElectricalContainmentSpec(
        containment_type=kind,size_desc=size,description="synthetic",
        length_m=length,
    )


@pytest.mark.parametrize("bad", [True,False,1.5,0,-1,"2",None,float("nan"),float("inf")])
@pytest.mark.parametrize("fn,kind", [
    (calculate_switchboard_items,"switchboard"),
    (calculate_lighting_items,"light"),
    (calculate_power_items,"gpo"),
    (calculate_data_items,"data"),
])
def test_untyped_fractional_or_missing_electrical_source_count_never_minted(fn,kind,bad):
    assert fn(_device(kind=kind,count=bad)) == []


@pytest.mark.parametrize("invalid", [""," L1","L1 ",True,None])
def test_original_device_mark_must_be_exact_not_coerced(invalid):
    assert calculate_lighting_items(_device(mark=invalid)) == []


def test_exact_original_electrical_device_count_remains_measured():
    assert calculate_lighting_items(_device()).__len__() == 1
    assert calculate_lighting_items(_device())[0].quantity == 2.0
    assert calculate_power_items(_device(kind="gpo"))[0].quantity == 2.0


def test_cross_trade_electrical_alias_cannot_switch_device_semantic_kind():
    assert calculate_switchboard_items(_device(kind="light")) == []
    assert calculate_lighting_items(_device(kind="data")) == []
    assert calculate_power_items(_device(kind="light")) == []
    assert calculate_data_items(_device(kind="gpo")) == []


@pytest.mark.parametrize("dedicated", ["true",1,None,0])
def test_forged_dedicated_circuit_flag_cannot_promote_specialist_connection(dedicated):
    assert calculate_power_items(_device(kind="gpo",dedicated=dedicated)) == []


@pytest.mark.parametrize("bad", [True,False,"35",float("nan"),float("inf"),10**400,0,-2,None])
def test_untyped_cable_containment_length_never_measured_as_m(bad):
    assert calculate_containment_items(_run(length=bad)) == []


@pytest.mark.parametrize("bad", ["",True,None])
def test_missing_original_containment_size_descriptor_abstains(bad):
    assert calculate_containment_items(_run(size=bad)) == []


def test_genuine_cable_containment_source_keeps_linear_measurement():
    result=calculate_containment_items(_run())
    assert len(result)==1
    assert result[0].quantity==35.0
    assert result[0].unit=="lm"
