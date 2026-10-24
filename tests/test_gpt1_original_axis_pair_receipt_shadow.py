"""No opening may reach source-owned axes review on equal area product alone."""
import pytest

from pb_opening_axis_ownership_shadow import assess_opening_axis_ownership_shadow
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows


def _review(**changes):
    args = dict(
        physical_opening_id="physical-source-opening",
        dimension_values_mm=(1200., 1800.),
        axis_order_resolved=False,
        width_record_id="original-width-receipt",
        height_record_id="original-height-receipt",
        width_m=1.2, height_m=1.8, area_m2=2.16,
        canonical_evidence_ids=("original-width-receipt", "original-height-receipt"),
        geometry_complete=True,
    )
    args.update(changes)
    return assess_opening_axis_ownership_shadow(**args)


def test_unordered_source_figured_pair_with_independent_axes_can_be_reviewed():
    result = _review()
    assert result["first_remaining_gate"] == "independent_gpt1_measurement_validation_required"
    assert result["axis_order_authenticated"] is True
    assert result["original_figured_label_order_source_resolved"] is False
    assert result["opening_area_publication_allowed"] is False
    assert not result["measurement_published"]


def test_swapped_independently_owned_canonical_axes_retain_unordered_pair():
    result = _review(width_m=1.8, height_m=1.2)
    assert result["axis_order_authenticated"]


def test_equal_area_product_different_axes_still_abstains():
    result = _review(width_m=0.9, height_m=2.4)
    assert result["first_remaining_gate"] == "independent_axes_disagree_with_figured_pair"
    assert result["axis_order_authenticated"] is False
    assert result["opening_area_publication_allowed"] is False


@pytest.mark.parametrize("changes,gate", [
    ({"geometry_complete": False}, "opening_geometry_axis_scope_unavailable"),
    ({"geometry_complete": "true"}, "opening_geometry_axis_scope_unavailable"),
    ({"canonical_evidence_ids": ("original-height-receipt",)}, "original_axis_receipts_unbound"),
    ({"canonical_evidence_ids": None}, "original_axis_receipts_unbound"),
    ({"width_record_id": True}, "width_height_axis_authority_unproven"),
    ({"height_record_id": "original-width-receipt"}, "width_height_axis_authority_unproven"),
    ({"width_record_id": " padded "}, "width_height_axis_authority_unproven"),
    ({"height_m": float("inf")}, "width_height_axis_authority_unproven"),
    ({"area_m2": 99.0}, "figured_area_product_disagrees_with_pair"),
    ({"dimension_values_mm": (1200.,)}, "single_figured_dimension_second_axis_unproven"),
    ({"dimension_values_mm": (1200., False)}, "source_figured_dimension_pair_unproven"),
])
def test_missing_or_foreign_axis_authority_fails_closed(changes, gate):
    d = _review(**changes)
    assert d["first_remaining_gate"] == gate
    assert not d["axis_order_authenticated"]
    assert not d["opening_area_publication_allowed"]


def test_label_false_string_not_treated_as_source_ordered():
    d = [{
        "physical_opening_id": "opening-A",
        "first_remaining_gate": "width_height_axis_authority_unproven",
        "prior_signed_quantity_id": None,
    }]
    c = {"opening-A": {
        "opening_kind": "door", "width_record_id": "w1",
        "height_record_id": "h1", "width_m": 1.2,
        "height_m": 1.8, "geometry_complete": True,
        "evidence_ids": ["w1","h1"],
    }}
    o = {"opening-A": {
        "original_label_dimension_result": {"evidence": {
            "dimension_values_mm": [1200,1800],
            "axis_order_resolved": "false",
            "area_m2": 2.16, "evidence_id": "fig-label",
        }},
    }}
    result = attach_kind_and_axis_shadows(
        opening_decisions=d, canonical_by_id=c, observe_rows_by_id=o,
    )
    shadow=result["openings"][0]["axis_shadow"]
    assert shadow["original_figured_label_order_source_resolved"] is False
    # Independently source-owned axes remain eligible for review even though
    # the callout itself cannot claim which number was printed first.
    assert shadow["axis_order_authenticated"] is True
    assert not result["measurement_published"]
    assert not result["benchmark_score_granted"]


def test_figured_dimension_list_not_mutated():
    pair=[1800.,1200.]
    evidence=["original-width-receipt","original-height-receipt"]
    r=_review(dimension_values_mm=pair,canonical_evidence_ids=evidence)
    assert r["axis_order_authenticated"]
    assert pair==[1800.,1200.]
    assert evidence==["original-width-receipt","original-height-receipt"]
