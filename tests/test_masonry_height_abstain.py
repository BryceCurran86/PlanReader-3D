"""A missing masonry height is not 2.70 m of brickwork."""
from pb_masonry_trade_authority import MasonryWallSpec, calculate_brickwork_items


def test_printed_height_stays_and_a_missing_height_publishes_nothing() -> None:
    measured = calculate_brickwork_items(
        MasonryWallSpec(
            element_id="W1",
            wall_type="brickwork_veneer",
            description="External brick",
            length_m=10.0,
            height_m=2.7,
        )
    )
    assert measured
    assert measured[0].quantity == 27.0
    omitted = calculate_brickwork_items(
        MasonryWallSpec(
            element_id="W2",
            wall_type="brickwork_veneer",
            description="External brick",
            length_m=10.0,
        )
    )
    assert omitted == []
