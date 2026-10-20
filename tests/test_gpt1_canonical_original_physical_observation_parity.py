"""Original physical opening receipts must satisfy the real figured-area publisher."""
from copy import deepcopy

import pytest

from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _host_only():
    rows, c = fixture()
    rows[2]["frame_record"] = None
    c[2]["host_frame_record_id"] = None
    return rows, c


def test_producer_owned_original_physical_receipt_can_reach_area_review_only():
    rows, c = _host_only()
    before = deepcopy((rows, c))
    r = run(rows, c)
    d = r["opening_decisions"][2]
    assert d["original_physical_source_observation_receipts_bound"]
    assert d["new_gpt1_area_candidate_handoff"]
    assert not d["new_gpt1_candidate_handoff"]
    assert not d["measurement_published"]
    assert not r["signed_customer_publisher_activated"]
    assert before == (rows, c)


@pytest.mark.parametrize("mutate", [
    lambda r,c: c[2].pop("representative_observation_id"),
    lambda r,c: c[2].update(representative_observation_id="foreign-original"),
    lambda r,c: c[2].update(representative_observation_id=True),
    lambda r,c: c[2].update(representative_observation_id=" source-own-1 "),
    lambda r,c: c[2].update(source_observation_ids=None),
    lambda r,c: c[2].update(source_observation_ids=()),
    lambda r,c: c[2].update(source_observation_ids=("source-own-1","source-own-1")),
    lambda r,c: c[2].update(source_observation_ids=("source-own-1","unowned")),
    lambda r,c: c[2].update(viewport_id=None),
    lambda r,c: c[2].update(viewport_id=""),
    lambda r,c: c[2].update(viewport_id="  page:3  "),
    lambda r,c: c[2].update(evidence_ids=["figured","figured-word-3","binding-3"]),
    lambda r,c: r[2]["physical_existence_record"].update(
        source_observation_ids=("replayed-original",)),
])
def test_missing_stale_or_conflicting_canonical_physical_source_abstains(mutate):
    rows, c = _host_only()
    mutate(rows,c)
    result = run(rows,c)
    d = result["opening_decisions"][2]
    assert not d["original_physical_source_observation_receipts_bound"]
    if d["original_host_binding_receipt_bound"] and d["original_figured_label_source_scope_bound"]:
        assert d["opening_area_first_remaining_gate"] == (
            "original_physical_source_observation_receipts_unbound"
        )
    assert not d["new_gpt1_area_candidate_handoff"]
    assert not result["gpt1_new_area_review_candidates"]


def test_original_observation_set_is_unordered_but_representative_is_owned():
    rows,c = _host_only()
    rows[2]["physical_existence_record"]["source_observation_ids"] = (
        "source-second","source-own-1",
    )
    c[2]["source_observation_ids"] = ("source-own-1","source-second")
    c[2]["evidence_ids"].append("source-second")
    r = run(rows,c)
    assert r["opening_decisions"][2]["original_physical_source_observation_receipts_bound"]
    assert r["opening_decisions"][2]["new_gpt1_area_candidate_handoff"]


def test_previously_signed_area_never_reenters_new_review():
    rows,c = _host_only()
    rows[2]["quantity_id"] = "historical-signed-source-row"
    r=run(rows,c)
    assert r["original_signed_area_quantities"] == 1
    assert r["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "original_signed_area_already_retained"
    )
    assert not r["gpt1_new_area_review_candidates"]


def test_rejected_observation_does_not_change_canonical_source():
    rows,c = _host_only()
    before = deepcopy((rows,c))
    c[2]["representative_observation_id"] = "not-the-original"
    r=run(rows,c)
    assert r["opening_decisions"][2]["original_physical_source_observation_receipts_bound"] is False
    assert rows==before[0]
    assert c[0]==before[1][0]
    assert r["global_opening_count_granted"] is False
    assert r["signed_customer_publisher_activated"] is False
    assert all(row["opening_count_granted"] is False for row in r["opening_decisions"])
