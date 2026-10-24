"""A band beam without a printed section is not 1200 by 450."""
from pb_post_tension_trade_authority import PTExtractionSpec, calculate_pt_band_beam_items


def test_supplied_section_stays_and_a_missing_section_publishes_nothing() -> None:
    measured = calculate_pt_band_beam_items(
        PTExtractionSpec(
            element_type="pt_band_beam",
            element_id="BB",
            section="Structure",
            description="Band beam",
            length_m=10.0,
            width_m=1.2,
            thickness_m=0.45,
        )
    )
    assert measured[0].quantity == 10.0
    omitted = calculate_pt_band_beam_items(
        PTExtractionSpec(
            element_type="pt_band_beam",
            element_id="BB",
            section="Structure",
            description="Band beam",
            length_m=10.0,
        )
    )
    assert omitted == []
