"""A previously published ABSTAIN representative cannot be force-reused."""
import pytest

from tools.diag_gptmax_original_selector_policy_matrix import (
    summarize_source_selection,
    original_selector_policy_matrix,
)

PHYSICAL = "physical_opening_existence_a"
A = "source_observation_119"
B = "source_observation_399"


def row(identity, positive=True, record=PHYSICAL):
    return {
        "source_observation_id": identity,
        "proven_exact_target_record": positive,
        "disposition_existence_record_id": record,
    }


def test_only_original_positive_existing_identity_can_be_chosen():
    r = summarize_source_selection([row(B),row(A)], PHYSICAL)
    assert r["recomputed_representative_id"] == A
    assert r["eligible_source_observation_ids"] == [A,B]
    assert not r["recomputed_selection_grants_authority"]


def test_removed_proven_candidate_must_not_be_pinned_as_representative():
    r = summarize_source_selection([row(A,False),row(B,True)], PHYSICAL)
    assert r["recomputed_representative_id"] == B
    assert r["eligible_source_observation_ids"] == [B]
    assert not r["recomputed_selection_grants_authority"]


def test_wrong_existing_physical_identity_is_not_positive():
    r = summarize_source_selection([row(A,record="physical_opening_existence_other")],PHYSICAL)
    assert r["recomputed_representative_id"] is None


def test_none_of_source_support_is_proof_of_existence_without_independent_disposition():
    r = summarize_source_selection([row(A,False),row(B,False)],PHYSICAL)
    assert r["recomputed_representative_id"] is None


def test_permutation_has_no_effect_on_selected_source_proof():
    first = summarize_source_selection([row(B),row(A)],PHYSICAL)
    last = summarize_source_selection([row(A),row(B)],PHYSICAL)
    assert first == last


def test_duplicate_source_selector_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        summarize_source_selection([row(A),row(A)],PHYSICAL)


@pytest.mark.parametrize("pdf,page,sha,target",[
    (b"", "3", "a"*64, PHYSICAL),
    (b"immutable", "0", "a"*64, PHYSICAL),
    (b"immutable", "03", "a"*64, PHYSICAL),
    (b"immutable", "3", "a"*64, PHYSICAL),
    (b"immutable", "3", "a"*64, "wrong"),
])
def test_corrupt_source_or_scope_rejected_before_original_policy_replay(pdf,page,sha,target):
    with pytest.raises((ValueError,TypeError)):
        original_selector_policy_matrix(
            pdf,page_id=page,expected_sha256=sha,existing_physical_id=target)
