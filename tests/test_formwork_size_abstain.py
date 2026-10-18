"""Missing formwork sizes are not standard column or wall sizes."""
from pb_formwork_trade_authority import (
    FormworkElementSpec,
    calculate_column_formwork_items,
    calculate_wall_formwork_items,
)


def test_supplied_sizes_stay_and_missing_sizes_publish_nothing() -> None:
    measured = calculate_column_formwork_items(
        FormworkElementSpec(
            element_type="column",
            element_id="COL",
            section="Structure",
            description="Columns",
            count=2,
            width_m=0.4,
            depth_m=0.4,
            height_m=3.0,
        )
    )
    assert measured[0].quantity == 9.6
    omitted = calculate_column_formwork_items(
        FormworkElementSpec(
            element_type="column",
            element_id="COL",
            section="Structure",
            description="Columns",
            count=2,
            height_m=3.0,
        )
    )
    assert omitted == []
    no_height = calculate_wall_formwork_items(
        FormworkElementSpec(
            element_type="wall",
            element_id="WALL",
            section="Structure",
            description="Wall",
            length_m=10.0,
        )
    )
    assert no_height == []
