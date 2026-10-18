"""A missing wall height is not 2.70 m of framing."""
from pb_carpentry_trade_authority import CarpentryElementSpec, calculate_wall_framing_items


def test_printed_height_stays_and_a_missing_height_publishes_nothing() -> None:
    measured = calculate_wall_framing_items(
        CarpentryElementSpec(
            element_type="wall_frame",
            element_id="FRAME_01",
            description="External frame",
            length_m=12.0,
            height_m=2.7,
        )
    )
    assert measured
    assert measured[0].quantity == 32.4
    omitted = calculate_wall_framing_items(
        CarpentryElementSpec(
            element_type="wall_frame",
            element_id="FRAME_02",
            description="External frame",
            length_m=12.0,
        )
    )
    assert omitted == []
