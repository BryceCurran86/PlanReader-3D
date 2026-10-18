"""Missing concrete sizes are not standard footing or column sizes."""
from pb_concreting_trade_authority import (
    ConcreteElementSpec,
    calculate_column_concrete_items,
    calculate_footing_concrete_items,
)


def test_supplied_column_stays_and_a_missing_size_publishes_nothing() -> None:
    measured = calculate_column_concrete_items(
        ConcreteElementSpec(
            element_type="column",
            element_id="C1",
            section="Structure",
            description="Columns",
            count=2,
            width_m=0.35,
            length_m=0.35,
            height_m=2.7,
        )
    )
    assert measured[0].quantity == 2.0
    omitted = calculate_column_concrete_items(
        ConcreteElementSpec(
            element_type="column",
            element_id="C1",
            section="Structure",
            description="Columns",
            count=2,
            height_m=2.7,
        )
    )
    assert omitted == []
    pier = calculate_footing_concrete_items(
        ConcreteElementSpec(
            element_type="bored_pier",
            element_id="P1",
            section="Substructure",
            description="Piers",
            count=4,
        )
    )
    assert pier == []
