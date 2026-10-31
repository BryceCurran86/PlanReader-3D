"""Original source semantic-kind receipts are not interchangeable with dimensions."""
from copy import deepcopy
import pytest

from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows


def _items(identity="op-1", kind="door"):
    decisions = [{
        "physical_opening_id": identity,
        "first_remaining_gate": "opening_filling_kind_unproven",
        "prior_signed_quantity_id": None,
    }]
    canon = {identity: {
        "opening_kind": kind,
        "structural_pattern": "corroborated_door_jamb_leaf",
        "evidence_ids": ["physical-source-1", "figured-area-1"],
        "width_record_id": None, "height_record_id": None,
        "width_m": None, "height_m": None,
    }}
    observations = {identity: {
        "original_label_dimension_result": {"evidence": {
            "dimension_values_mm": [1200, 1800],
            "axis_order_resolved": False, "area_m2": 2.16,
            "evidence_id": "figured-area-1",
        }}
    }}
    return decisions, canon, observations


def _run(d, c, o):
    return attach_kind_and_axis_shadows(
        opening_decisions=d, canonical_by_id=c, observe_rows_by_id=o,
    )


def test_figured_dimension_receipt_is_never_a_door_kind_receipt():
    d,c,o = _items()
    report = _run(d,c,o)
    record = report["openings"][0]["kind_shadow"]
    assert record["opening_kind"] == "door"
    assert record["source_kind_evidence_ids"] == []
    assert record["first_remaining_gate"] == "opening_filling_kind_evidence_unproven"
    assert not record["filling_kind_source_supported"]
    assert not report["measurement_published"]


def test_caller_supplied_kind_id_outside_canonical_evidence_abstains():
    d,c,o = _items()
    c["op-1"]["opening_kind_evidence_id"] = "unowned-kind-id"
    record = _run(d,c,o)["openings"][0]["kind_shadow"]
    assert record["source_kind_evidence_ids"] == []
    assert not record["filling_kind_source_supported"]


@pytest.mark.parametrize("bad", [True, 20, " kind-1 ", ""])
def test_untyped_noncanonical_semantic_receipt_cannot_be_promoted(bad):
    d,c,o = _items()
    c["op-1"]["opening_kind_evidence_id"] = bad
    c["op-1"]["evidence_ids"].append("kind-1")
    record = _run(d,c,o)["openings"][0]["kind_shadow"]
    assert not record["filling_kind_source_supported"]


def test_typed_semantic_kind_id_in_original_evidence_is_review_supported_only():
    d,c,o = _items()
    c["op-1"]["opening_kind_evidence_id"] = "source-kind-1"
    c["op-1"]["evidence_ids"].append("source-kind-1")
    record = _run(d,c,o)["openings"][0]["kind_shadow"]
    assert record["source_kind_evidence_ids"] == ["source-kind-1"]
    assert record["filling_kind_source_supported"]
    assert record["measurement_published"] is False


def test_opening_type_mark_receipt_can_be_independent_of_figure_receipt():
    d,c,o = _items()
    c["op-1"]["type_mark_evidence_id"] = "source-mark-1"
    c["op-1"]["evidence_ids"].append("source-mark-1")
    record = _run(d,c,o)["openings"][0]["kind_shadow"]
    assert record["source_kind_evidence_ids"] == ["source-mark-1"]
    assert record["filling_kind_source_supported"]


def test_same_kind_evidence_twice_deduplicates_without_double_counting():
    d,c,o = _items()
    c["op-1"].update(opening_kind_evidence_id="kind-1",
                     type_mark_evidence_id="kind-1")
    c["op-1"]["evidence_ids"].append("kind-1")
    report = _run(d,c,o)
    assert report["kind_gate_counts"] == {"opening_filling_kind_source_supported": 1}
    assert report["openings"][0]["kind_shadow"]["source_kind_evidence_ids"] == ["kind-1"]


def test_duplicate_decisions_cannot_count_one_opening_twice():
    d,c,o = _items()
    with pytest.raises(ValueError, match="inventory mismatch"):
        _run(d+d,c,o)


def test_missing_or_extra_source_opening_cannot_hide_in_shadow():
    d,c,o = _items()
    with pytest.raises(ValueError, match="inventory mismatch"):
        _run(d,{},o)
    with pytest.raises(ValueError, match="inventory mismatch"):
        _run(d,c,{})
    with pytest.raises(ValueError, match="inventory mismatch"):
        _run(d,c,{**o, "foreign": o["op-1"]})


def test_order_invariance_and_no_input_mutation():
    d,c,o = _items()
    d2,c2,o2 = _items("op-2", "window")
    c2["op-2"]["opening_kind_evidence_id"] = "kind-2"
    c2["op-2"]["evidence_ids"].append("kind-2")
    combined_d=d+d2
    combined_c={**c,**c2}
    combined_o={**o,**o2}
    original=deepcopy((combined_d,combined_c,combined_o))
    result=_run(combined_d,combined_c,combined_o)
    reversed_result=_run(list(reversed(combined_d)),combined_c,combined_o)
    assert result==reversed_result
    assert (combined_d,combined_c,combined_o)==original
    assert result["opening_count"] == 2
    assert not result["measurement_published"]
    assert not result["benchmark_score_granted"]
