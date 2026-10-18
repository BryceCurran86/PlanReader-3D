"""A missing electrical count is not one fitting."""
from pb_electrical_trade_authority import ElectricalDeviceSpec, calculate_lighting_items


def test_supplied_count_stays_and_a_missing_count_publishes_nothing() -> None:
    measured = calculate_lighting_items(
        ElectricalDeviceSpec(
            device_type="light",
            device_mark="L1",
            description="Downlight",
            location="Living",
            count=8,
        )
    )
    assert measured[0].quantity == 8.0
    omitted = calculate_lighting_items(
        ElectricalDeviceSpec(
            device_type="light",
            device_mark="L1",
            description="Downlight",
            location="Living",
        )
    )
    assert omitted == []
