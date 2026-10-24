"""A missing steel count is not one member."""
from pb_structural_steel_trade_authority import SteelMemberSpec, calculate_primary_member_items


def test_supplied_count_stays_and_a_missing_count_publishes_nothing() -> None:
    measured = calculate_primary_member_items(
        SteelMemberSpec(
            element_type="beam",
            element_id="B1",
            section_mark="310UB40.4",
            description="Beam",
            length_m=6.0,
            count=2,
            mass_kg_per_m=40.4,
        )
    )
    assert measured[0].quantity == 12.0
    omitted = calculate_primary_member_items(
        SteelMemberSpec(
            element_type="beam",
            element_id="B1",
            section_mark="310UB40.4",
            description="Beam",
            length_m=6.0,
            mass_kg_per_m=40.4,
        )
    )
    assert omitted == []
