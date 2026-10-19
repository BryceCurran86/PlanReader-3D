"""Axis ownership shadow never invents a second dimension from width."""
from pb_opening_axis_ownership_shadow import (
    assess_opening_axis_ownership_shadow,
    refuse_area_from_width_only,
)


def test_single_width_abstains_without_inventing_height():
    report = refuse_area_from_width_only(
        physical_opening_id="opening-1", width_mm=820.0
    )
    assert report["first_remaining_gate"] == "single_figured_dimension_second_axis_unproven"
    assert report["invented_second_axis"] is False
    assert report["opening_area_publication_allowed"] is False
    assert report["measurement_published"] is False


def test_unordered_pair_with_area_still_blocks_axis_authority():
    report = assess_opening_axis_ownership_shadow(
        physical_opening_id="opening-2",
        dimension_values_mm=(1200.0, 1800.0),
        axis_order_resolved=False,
        width_record_id=None,
        height_record_id=None,
        width_m=None,
        height_m=None,
        area_m2=2.16,
    )
    assert report["first_remaining_gate"] == "width_height_axis_authority_unproven"
    assert report["axis_order_authenticated"] is False


def test_fully_owned_axes_still_require_gpt1_validation_and_do_not_publish():
    report = assess_opening_axis_ownership_shadow(
        physical_opening_id="opening-3",
        dimension_values_mm=(1200.0, 1800.0),
        axis_order_resolved=True,
        width_record_id="w",
        height_record_id="h",
        width_m=1.2,
        height_m=1.8,
        area_m2=2.16,
        canonical_evidence_ids=("w", "h"),
        geometry_complete=True,
    )
    assert report["first_remaining_gate"] == "independent_gpt1_measurement_validation_required"
    assert report["axis_order_authenticated"] is True
    assert report["opening_area_publication_allowed"] is False
    assert report["customer_seal_granted"] is False


def test_product_mismatch_fails_closed():
    report = assess_opening_axis_ownership_shadow(
        physical_opening_id="opening-4",
        dimension_values_mm=(1200.0, 1800.0),
        axis_order_resolved=True,
        width_record_id="w",
        height_record_id="h",
        width_m=1.2,
        height_m=1.8,
        area_m2=9.99,
        canonical_evidence_ids=("w", "h"),
        geometry_complete=True,
    )
    assert report["first_remaining_gate"] == "figured_area_product_disagrees_with_pair"
