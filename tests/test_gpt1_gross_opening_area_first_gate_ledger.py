"""Gross figured opening area and 3D whole-wall handoff are separate ledgers."""
from copy import deepcopy
import pytest

from pb_lot16_opening_receipt_refresh_shadow import refresh_opening_first_gate_receipt
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import ROOT, VIEW, fixture
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates


def _run(rows=None, canonical=None):
    first, second = fixture()
    return refresh_opening_first_gate_receipt(
        first if rows is None else rows,
        second if canonical is None else canonical,
        VIEW, source_root=ROOT,
    )


def test_figured_gross_area_first_gate_census_is_separate_from_3d():
    report = _run()
    assert report["gross_opening_area_first_gate_counts"] == {
        "independent_gpt1_opening_area_measurement_validation_required": 1,
        "source_figured_dimension_pair_unproven": 1,
        "structural_host_unavailable": 1,
    }
    assert report["original_physical_opening_count"] == 3
    assert len(report["gross_opening_area_review_candidates"]) == 1
    assert report["gross_opening_area_host_only_review_count"] == 0
    assert report["first_gate_counts"]["width_height_axis_authority_unproven"] == 1
    assert report["measurement_published"] is False
    assert report["benchmark_score_granted"] is False


def test_host_only_source_figure_can_be_reviewed_but_never_3d_or_firm():
    rows, canonical = fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    report = _run(rows, canonical)
    review = report["gross_opening_area_review_candidates"]
    assert len(review) == 1
    assert report["gross_opening_area_host_only_review_count"] == 1
    assert review[0]["first_remaining_gate"] == "whole_wall_frame_unavailable"
    assert review[0]["new_gpt1_candidate_handoff"] is False
    assert review[0]["customer_seal_granted"] is False
    assert report["measurement_published"] is False
    assert report["opening_count_granted"] is False


def test_missing_canonical_host_receipt_does_not_appear_as_area_ready():
    rows, canonical = fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    canonical[2]["evidence_ids"] = ["figured"]
    r=_run(rows,canonical)
    assert r["gross_opening_area_review_candidates"] == []
    assert r["gross_opening_area_first_gate_counts"]["original_structural_host_receipt_unbound"] == 1


def test_claimed_frame_without_owned_frame_receipt_cannot_be_area_ready():
    rows, canonical = fixture()
    canonical[2]["evidence_ids"] = ["figured", "binding-3"]
    r=_run(rows,canonical)
    assert r["gross_opening_area_review_candidates"] == []
    assert r["gross_opening_area_first_gate_counts"]["original_host_frame_receipt_unbound"] == 1


def test_previously_signed_source_area_never_reenters_gross_review():
    rows, canonical = fixture()
    rows[2]["quantity_id"] = "already-original-source-sealed"
    r=_run(rows,canonical)
    assert r["original_signed_area_quantities"] == 1
    assert r["gross_opening_area_review_candidates"] == []
    assert r["gross_opening_area_first_gate_counts"]["original_signed_area_already_retained"] == 1


def test_duplicate_or_foreign_producer_area_census_is_not_accepted(monkeypatch):
    rows, canonical = fixture()
    original = assess_gpt1_opening_candidates(rows, canonical, VIEW, source_root=ROOT)
    wrong = deepcopy(original)
    wrong["area_first_gate_counts"] = {"fake": 3}
    monkeypatch.setattr(
        "pb_lot16_opening_receipt_refresh_shadow.assess_gpt1_opening_candidates",
        lambda *args, **kwargs: wrong,
    )
    with pytest.raises(ValueError, match="census mismatch"):
        _run(rows, canonical)


def test_false_gross_area_ready_flag_cannot_mint_measurement(monkeypatch):
    rows, canonical = fixture()
    wrong=deepcopy(assess_gpt1_opening_candidates(rows,canonical,VIEW,source_root=ROOT))
    wrong["opening_decisions"][0]["new_gpt1_area_candidate_handoff"] = True
    monkeypatch.setattr(
        "pb_lot16_opening_receipt_refresh_shadow.assess_gpt1_opening_candidates",
        lambda *args, **kwargs: wrong,
    )
    with pytest.raises(RuntimeError, match="gross area first gate/ready claim disagreement"):
        _run(rows, canonical)


def test_area_review_candidate_universe_cannot_be_injected(monkeypatch):
    rows, canonical = fixture()
    wrong=deepcopy(assess_gpt1_opening_candidates(rows,canonical,VIEW,source_root=ROOT))
    wrong["gpt1_new_area_review_candidates"] = []
    monkeypatch.setattr(
        "pb_lot16_opening_receipt_refresh_shadow.assess_gpt1_opening_candidates",
        lambda *args, **kwargs: wrong,
    )
    with pytest.raises(ValueError, match="candidate universe mismatch"):
        _run(rows, canonical)


def test_order_invariance_and_no_mutation_of_source_owned_opening_rows():
    rows, canonical = fixture()
    original=deepcopy((rows,canonical))
    forward=_run(rows, canonical)
    reverse=_run(rows[::-1], canonical[::-1])
    assert forward==reverse
    assert (rows,canonical)==original
    assert forward["gross_opening_area_review_candidates"][0]["physical_opening_id"]=="physical-3"


@pytest.mark.parametrize("break_queue,expected", [
    (lambda q: q["opening_decisions"][0].update(source_sha256="f"*64),
     "inventory/root mismatch"),
    (lambda q: q.update(original_physical_opening_count=99),
     "original opening census disagreement"),
    (lambda q: q.update(original_authenticated_hosts=99),
     "original opening census disagreement"),
    (lambda q: q.update(original_complete_host_frames=99),
     "original opening census disagreement"),
    (lambda q: q.update(original_signed_area_quantities=99),
     "original opening census disagreement"),
    (lambda q: q.update(first_gate_counts={"fabricated":3}),
     "3D first-gate census mismatch"),
    (lambda q: q.update(gpt1_new_handoff_candidates=[q["opening_decisions"][0]]),
     "3D opening candidate universe mismatch"),
    (lambda q: q["opening_decisions"][0].update(new_gpt1_candidate_handoff=True),
     "3D first gate/ready claim disagreement"),
    (lambda q: q["opening_decisions"][2].update(new_gpt1_area_candidate_handoff=False),
     "gross area first gate/ready claim disagreement"),
    (lambda q: q["opening_decisions"][2].update(figured_area_only_frame_unavailable=True),
     "host-only figured area marker disagrees"),
])
def test_consumer_rejects_forged_source_and_3d_receipt_summaries(monkeypatch, break_queue, expected):
    rows, canonical = fixture()
    snapshot = deepcopy(assess_gpt1_opening_candidates(rows,canonical,VIEW,source_root=ROOT))
    break_queue(snapshot)
    monkeypatch.setattr(
        "pb_lot16_opening_receipt_refresh_shadow.assess_gpt1_opening_candidates",
        lambda *args, **kwargs: snapshot,
    )
    with pytest.raises((ValueError, RuntimeError), match=expected):
        _run(rows,canonical)


def test_two_decisions_for_one_physical_opening_are_not_a_larger_inventory(monkeypatch):
    rows, canonical = fixture()
    snapshot = deepcopy(assess_gpt1_opening_candidates(rows,canonical,VIEW,source_root=ROOT))
    snapshot["opening_decisions"][1]["physical_opening_id"] = snapshot["opening_decisions"][0]["physical_opening_id"]
    monkeypatch.setattr(
        "pb_lot16_opening_receipt_refresh_shadow.assess_gpt1_opening_candidates",
        lambda *args, **kwargs: snapshot,
    )
    with pytest.raises(ValueError, match="inventory/root mismatch"):
        _run(rows,canonical)
