"""Independent source veto counts reveal blockers hidden behind first failure."""
from dataclasses import replace
from pb_original_opening_area_gate_diagnostics import audit_original_opening_area_gates
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening


def test_multiple_independent_vetoes_are_all_counted_not_only_first():
    a = replace(
        _opening(canonical_id="private-a"), opening_kind=None,
        host_wall_id=None, host_binding_record_id=None,
        host_frame_record_id=None, area_m2=None, area_basis=None,
    )
    report=audit_original_opening_area_gates((a,), ())
    assert report["observable_gate_counts"]=={"opening_kind_unresolved":1}
    assert report["independent_prerequisites_unproved"]=={
        "source_opening_kind_unproved":1,
        "source_physical_wall_host_unproved":1,
        "source_wall_host_receipt_unproved":1,
        "source_numeric_area_unproved":1,
        "source_metric_basis_unproved":1,
    }
    assert report["official_benchmark_scored"] is False
    assert "private-a" not in str(report)


def test_source_typed_door_missing_only_host_has_two_specific_vetoes():
    x=replace(
        _opening(canonical_id="private-b", kind="door"),
        host_wall_id=None, host_binding_record_id=None,
        host_frame_record_id=None,
    )
    r=audit_original_opening_area_gates((x,), ())
    assert r["source_kind_counts"]=={"door":1}
    assert r["independent_prerequisites_by_kind"]["door"]=={
        "source_physical_wall_host_unproved":1,
        "source_wall_host_receipt_unproved":1,
    }
    assert r["observable_gate_counts"]=={"opening_host_wall_missing":1}


def test_real_issued_source_opening_has_no_missing_prerequisites():
    x=_opening()
    q=_opening_quantity(x)
    assert q is not None
    r=audit_original_opening_area_gates((x,), (q,))
    assert r["independent_prerequisites_unproved"]=={}
    assert r["independent_prerequisites_by_kind"]["window"]=={}
    assert r["published_opening_area_count"]==1


def test_legend_or_missing_representative_source_witness_is_explicitly_unproved():
    x=replace(_opening(canonical_id="private-c"), source_observation_ids=())
    r=audit_original_opening_area_gates((x,), ())
    assert r["independent_prerequisites_unproved"]=={
        "source_representative_observation_unproved":1
    }
    assert r["measurement_authorized"] is False


def test_counts_can_exceed_candidates_because_vetoes_are_independent():
    a=replace(
        _opening(canonical_id="private-a"), opening_kind=None,
        host_wall_id=None, area_m2=None,
    )
    b=replace(_opening(canonical_id="private-b"),opening_kind="door",host_wall_id=None)
    r=audit_original_opening_area_gates((a,b), ())
    assert r["source_opening_candidate_count"]==2
    assert r["independent_prerequisites_unproved"]["source_physical_wall_host_unproved"]==2
    assert r["independent_prerequisites_unproved"]["source_opening_kind_unproved"]==1
    assert r["independent_prerequisites_unproved"]["source_numeric_area_unproved"]==1
    assert sum(r["observable_gate_counts"].values())==2
