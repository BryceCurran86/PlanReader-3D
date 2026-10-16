"""No 2-axis sheet-scale diagnostic may mint or bypass room measurement."""
import copy

from pb_figured_dimension_scale_consistency_shadow import (
    source_figured_scale_shadow,
)


def _source_pair(hid, vid, *, h_mm=1000., h_span=100., v_mm=500., v_span=50.):
    return {
        "horizontal_dimension_id": f"original-h:{hid}",
        "horizontal_value_mm": h_mm,
        "horizontal_endpoints_pt": ((5., 6.), (5.+h_span, 6.)),
        "horizontal_source_witness_ids": (f"h-tick:{hid}:left", f"h-tick:{hid}:right"),
        "horizontal_witness_segments": ((5., 6., 5., 9.), (5.+h_span, 6., 5.+h_span, 9.)),
        "vertical_dimension_id": f"original-v:{vid}",
        "vertical_value_mm": v_mm,
        "vertical_endpoints_pt": ((2., 10.), (2., 10.+v_span)),
        "vertical_source_witness_ids": (f"v-tick:{vid}:top", f"v-tick:{vid}:bottom"),
        "vertical_witness_segments": ((2., 10., 6., 10.), (2., 10.+v_span, 6., 10.+v_span)),
        "room_label": "EXAMPLE",
    }


def _audit():
    rows = [_source_pair("A", "C"), _source_pair("B", "C"),
            _source_pair("A", "D"), _source_pair("B", "D")]
    return {
        "attempted_pairs": len(rows),
        "intersecting_pairs": 0,
        "failed_pair_samples": rows,
    }


def test_two_independent_original_axes_only_create_shadow_candidate():
    original = _audit()
    before = copy.deepcopy(original)
    result = source_figured_scale_shadow(original)
    assert original == before
    assert result["first_unclosed_gate"] == "source_figured_scale_shadow_consistent_not_authority"
    assert result["horizontal_unique_source_dimension_count"] == 2
    assert result["vertical_unique_source_dimension_count"] == 2
    assert result["ratio_candidate_mm_per_pdf_point"] == 10.0
    for key in ("physical_scale_authority_granted",
                "room_area_authority_granted", "source_room_to_dimension_owner_proven",
                "commercial_projection_allowed", "quantity_published"):
        assert result[key] is False


def test_counterfeit_repeated_pair_not_two_independent_sources():
    row = _source_pair("A", "C")
    result = source_figured_scale_shadow({
        "attempted_pairs": 4, "intersecting_pairs": 0,
        "failed_pair_samples": [row, row, row, row],
    })
    assert result["ratio_candidate_mm_per_pdf_point"] is None


def test_mismatched_independent_axis_scale_blocks_shadow_ratio():
    ledger = _audit()
    ledger["failed_pair_samples"][3]["vertical_value_mm"] = 900.
    # Same original dimension ID, contradictory per-sample receipt is conflict.
    result = source_figured_scale_shadow(ledger)
    assert result["ratio_candidate_mm_per_pdf_point"] is None
    assert result["first_unclosed_gate"] == "source_figured_scale_shadow_conflict"


def test_two_distinct_source_ratios_do_not_get_averaged_into_authority():
    ledger = _audit()
    for row in ledger["failed_pair_samples"]:
        if row["vertical_dimension_id"] == "original-v:D":
            row["vertical_value_mm"] = 800.
    result = source_figured_scale_shadow(ledger)
    assert result["ratio_candidate_mm_per_pdf_point"] is None
    assert result["first_unclosed_gate"] == "source_figured_scale_shadow_conflict"


def test_duplicate_source_witness_across_orthogonal_axes_fails():
    ledger = _audit()
    for row in ledger["failed_pair_samples"]:
        if row["vertical_dimension_id"] == "original-v:D":
            row["vertical_source_witness_ids"] = (
                "h-tick:A:left", "v-tick:D:bottom"
            )
    result = source_figured_scale_shadow(ledger)
    assert result["ratio_candidate_mm_per_pdf_point"] is None


def test_incomplete_bounded_original_audit_never_claims_consistency():
    ledger = _audit()
    ledger["attempted_pairs"] = 9
    result = source_figured_scale_shadow(ledger)
    assert result["ratio_candidate_mm_per_pdf_point"] is None
    assert result["first_unclosed_gate"] == "source_figured_scale_shadow_unavailable"


def test_boolean_values_and_improper_source_axes_are_rejected():
    for variant in ("bool", "diagonal", "nan"):
        ledger = _audit()
        row = ledger["failed_pair_samples"][0]
        if variant == "bool":
            row["horizontal_value_mm"] = True
        if variant == "diagonal":
            row["horizontal_endpoints_pt"] = ((5., 6.), (105., 9.))
        if variant == "nan":
            row["horizontal_value_mm"] = float("nan")
        result = source_figured_scale_shadow(ledger)
        assert result["ratio_candidate_mm_per_pdf_point"] is None
        assert result["physical_scale_authority_granted"] is False
