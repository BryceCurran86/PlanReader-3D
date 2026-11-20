"""Evidence-only opening issuer rejection counts must never grant area or benchmark authority."""
from dataclasses import replace
import pytest

from pb_original_opening_area_gate_diagnostics import audit_original_opening_area_gates
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening


def test_actual_issuer_decisions_match_count_only_diagnostics():
    valid = _opening()
    unknown = replace(_opening(canonical_id="opening-2"), opening_kind=None)
    missing_host = replace(_opening(canonical_id="opening-3"), host_wall_id=None)
    missing_area = replace(_opening(canonical_id="opening-4"), area_m2=None)
    quantity = _opening_quantity(valid)
    assert quantity is not None
    report = audit_original_opening_area_gates(
        (valid, unknown, missing_host, missing_area), (quantity,),
    )
    assert report["source_opening_candidate_count"] == 4
    assert report["published_opening_area_count"] == 1
    assert report["observable_gate_counts"] == {
        "opening_kind_unresolved": 1,
        "opening_host_wall_missing": 1,
        "positive_measured_area_missing": 1,
        "source_issued_and_retained": 1,
    }
    assert report["measurement_authorized"] is False
    assert report["official_benchmark_scored"] is False
    assert "opening-1" not in str(report)


def test_figured_area_record_must_exist_before_canonical_issuer_accepts():
    sample = replace(_opening(), figured_area_record_id=None)
    report = audit_original_opening_area_gates((sample,), ())
    assert report["observable_gate_counts"] == {"figured_area_receipt_missing": 1}


def test_duplicate_physical_candidates_fail_audit():
    sample = _opening()
    with pytest.raises(ValueError, match="duplicate canonical source"):
        audit_original_opening_area_gates((sample, sample), (_opening_quantity(sample),))


def test_false_published_quantity_without_original_physical_object_fails():
    sample = _opening()
    with pytest.raises(ValueError, match="without canonical owner"):
        audit_original_opening_area_gates((), (_opening_quantity(sample),))


def test_replayed_duplicate_published_quantity_fails():
    sample = _opening()
    quantity = _opening_quantity(sample)
    with pytest.raises(ValueError, match="unique typed"):
        audit_original_opening_area_gates((sample,), (quantity, quantity))


def test_unproven_geometry_axes_are_not_issued():
    sample = replace(
        _opening(), area_basis="resolved_opening_geometry",
        opening_void_record_id="void-1", geometry_complete=False,
    )
    report = audit_original_opening_area_gates((sample,), ())
    assert report["observable_gate_counts"] == {"geometry_axes_unproven": 1}
