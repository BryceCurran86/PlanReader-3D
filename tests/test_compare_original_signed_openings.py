"""Prevent loss of authenticated original opening receipts in follow-up runs."""
from dataclasses import replace
import pytest

from tools.compare_original_signed_openings import OpeningRetentionError, compare_signed_original_opening_retention
from tests.test_customer_output_verification import quantity, trace, authority
from pb_source_closed_run_export import seal_source_closed_run
from pb_quantity_takeoff_adapter import quantities_to_takeoff_output_rows


def _signed(identities, values=None, source=None):
    values = values or {}
    qs = []
    for entity in identities:
        q = quantity(f"qty-{entity}", entity, value=values.get(entity, 12.5))
        q = replace(q, family="opening_area", semantic_key=f"opening:{entity}")
        if source is not None:
            q = replace(q, metadata={**dict(q.metadata), "source_sha256": source})
        qs.append(q)
    traces = {q.quantity_id: trace(q) for q in qs}
    if source is not None:
        traces = {k: replace(v, source_sha256=source) for k, v in traces.items()}
    signed = seal_source_closed_run(qs, project_id="project-7", traces_by_quantity_id=traces)
    rows = quantities_to_takeoff_output_rows(
        qs, traces_by_quantity_id=traces,
        authorities_by_quantity_id={q.quantity_id: authority() for q in qs},
    )
    return signed, rows


def test_unchanged_source_seals_retained_without_benchmark_claim():
    old, rows = _signed(("door-1", "window-1"))
    report = compare_signed_original_opening_retention(old, rows, old, rows)
    assert report["identically_retained"] == 2
    assert report["complete_previous_receipt_retention"] is True
    assert report["official_score_granted"] is False


def test_dropped_signed_window_is_reported():
    old, old_rows = _signed(("door-1", "window-1"))
    current, rows = _signed(("door-1",))
    report = compare_signed_original_opening_retention(old, old_rows, current, rows)
    assert report["identically_retained"] == 1
    assert report["missing_existing_physical_openings"] == 1
    assert report["complete_previous_receipt_retention"] is False


def test_changed_figured_measurement_is_not_retained():
    old, rows = _signed(("door-1",))
    new, next_rows = _signed(("door-1",), values={"door-1": 10.5})
    report = compare_signed_original_opening_retention(old, rows, new, next_rows)
    assert report["changed_existing_physical_openings"] == 1
    assert report["identically_retained"] == 0


def test_new_source_distinct_opening_added_without_double_count():
    old, rows = _signed(("door-1",))
    new, next_rows = _signed(("door-1", "window-1"))
    report = compare_signed_original_opening_retention(old, rows, new, next_rows)
    assert report["new_physical_opening_areas"] == 1
    assert report["identically_retained"] == 1


def test_source_sha_drift_refuses_comparison():
    old, rows = _signed(("door-1",))
    drift, drift_rows = _signed(("door-1",), source="b" * 64)
    with pytest.raises(OpeningRetentionError, match="source/revision changed"):
        compare_signed_original_opening_retention(old, rows, drift, drift_rows)


def test_incomplete_customer_bijection_does_not_claim_retention():
    old, rows = _signed(("door-1",))
    with pytest.raises(Exception):
        compare_signed_original_opening_retention(old, (), old, rows)
