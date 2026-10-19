"""The 21-field commercial takeoff must price volume per cubic metre, not item."""
from pb_concreting_trade_authority import (
    ConcreteElementSpec,calculate_slab_concrete_items,calculate_footing_concrete_items,
)
import pb_takeoff_row_contract as contract


def _spec(kind,**changes):
    fields=dict(
        element_type=kind,element_id="synthetic-concrete",
        section="Substructure",description="synthetic construction quantity",
        area_m2=150.0,thickness_m=0.10,perimeter_lm=50.0,
    )
    fields.update(changes)
    return ConcreteElementSpec(**fields)


def test_concrete_volume_is_true_per_m3_unit_supported_by_commercial_editor():
    assert "m³" in contract.TAKEOFF_UNITS
    result=calculate_slab_concrete_items(_spec("slab"))
    supply=next(row for row in result if "Concrete supply & pump" in row.element)
    assert supply.unit=="m³"
    assert supply.quantity==15.0
    assert supply.unit!="item"
    mapped=supply.to_core_row(1,"2026-10-19T00:00:00")
    assert mapped["unit"]=="m³"
    assert mapped["quantity"]==15.0


def test_strip_footing_supply_uses_cubic_metre_not_item_rate():
    result=calculate_footing_concrete_items(_spec(
        "footing_strip",length_m=40.0,width_m=0.4,thickness_m=0.5,
    ))
    supply=next(row for row in result if "concrete supply" in row.element)
    assert supply.unit=="m³"
    assert supply.quantity==8.0


def test_default_ground_slab_dpm_allowance_not_source_verified():
    rows=calculate_slab_concrete_items(_spec("slab"))
    dpm=next(row for row in rows if "Damp-proof membrane" in row.element)
    assert dpm.quantity==165.0
    assert dpm.unit=="m²"
    assert dpm.quantity_status=="Provisional"
    assert dpm.inclusion_status=="PROVISIONAL"
    assert dpm.confidence=="Provisional"


def test_cubic_metres_do_not_become_countable_item_in_customer_rate_book():
    assert "m³" != "item"
    rows=calculate_slab_concrete_items(_spec("slab"))
    assert not any(r.unit=="item" for r in rows)
