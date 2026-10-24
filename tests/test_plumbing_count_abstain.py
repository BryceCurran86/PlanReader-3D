"""A missing fixture count is not one basin."""
from pb_plumbing_trade_authority import PlumbingFixtureSpec, calculate_fixture_items


def test_supplied_count_stays_and_a_missing_count_publishes_nothing() -> None:
    measured = calculate_fixture_items(
        PlumbingFixtureSpec(
            fixture_type="basin",
            fixture_mark="BASIN-01",
            description="Basin",
            location="Ensuite",
            count=2,
        )
    )
    assert measured[0].quantity == 2.0
    omitted = calculate_fixture_items(
        PlumbingFixtureSpec(
            fixture_type="basin",
            fixture_mark="BASIN-01",
            description="Basin",
            location="Ensuite",
        )
    )
    assert omitted == []
