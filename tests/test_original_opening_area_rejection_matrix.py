"""The real source issuer's 180 candidates require kind-specific rejection evidence."""
from dataclasses import replace
from pb_original_opening_area_gate_diagnostics import audit_original_opening_area_gates
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening


def test_window_vs_door_rejection_matrix_keeps_customer_authority_false():
    windows = (_opening(canonical_id="window-a"), _opening(canonical_id="window-b"))
    door = replace(_opening(canonical_id="door-a"), opening_kind="door", area_m2=None)
    report = audit_original_opening_area_gates(
        (*windows, door), tuple(_opening_quantity(o) for o in windows),
    )
    assert report["source_kind_counts"] == {"window": 2, "door": 1}
    assert report["first_gate_by_opening_kind"]["window"] == {"source_issued_and_retained": 2}
    assert report["first_gate_by_opening_kind"]["door"] == {"positive_measured_area_missing": 1}
    assert report["measurement_authorized"] is False

def test_private_source_metric_basis_never_enters_summary():
    original = _opening(canonical_id="private-original")
    malformed = replace(original, area_basis="CUSTOMER SECRET REFER TO CALLOUT")
    report = audit_original_opening_area_gates((malformed,), ())
    assert report["source_metric_basis_counts"] == {"unrecognized_or_missing": 1}
    assert "SECRET" not in str(report)
    assert "private-original" not in str(report)
    assert report["official_benchmark_scored"] is False

def test_source_issuer_casefold_kind_must_not_look_like_unresolved_opening():
    opening = replace(_opening(), opening_kind="WINDOW")
    report = audit_original_opening_area_gates((opening,), ())
    assert report["source_kind_counts"] == {"window": 1}
    assert report["first_gate_by_opening_kind"]["window"] == {
        "canonical_quantity_not_retained": 1,
    }

def test_per_kind_counts_reconcile_to_exact_source_candidate_count():
    candidates = (
        _opening(canonical_id="one"),
        replace(_opening(canonical_id="two"), opening_kind=None),
        replace(_opening(canonical_id="three"), area_m2=None),
    )
    report = audit_original_opening_area_gates(candidates, (_opening_quantity(candidates[0]),))
    assert sum(report["source_kind_counts"].values()) == 3
    assert sum(report["observable_gate_counts"].values()) == 3
    assert sum(sum(x.values()) for x in report["first_gate_by_opening_kind"].values()) == 3
