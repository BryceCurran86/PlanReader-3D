from pb_frozen_v2_eval_readiness_shadow import assess_frozen_v2_eval_readiness_shadow
from pb_whole_wall_frame_readiness_shadow import assess_whole_wall_frame_readiness_shadow
from tools.diag_cursor_quantity_recovery_mission_ledger import mission_ledger


def test_aligned_fragment_reason_blocks_frame_consumption():
    r = assess_whole_wall_frame_readiness_shadow(
        physical_opening_id="o1",
        host_record_id="h1",
        frame_record_id=None,
        frame_reason_codes=("opening_host_frame_aligned_fragment_distinctness_unproven",),
    )
    assert r["first_remaining_gate"] == "whole_wall_frame_aligned_fragment_distinctness_unproven"
    assert r["proximity_completion_used"] is False


def test_eval_refuses_without_sealed_output_and_never_claims_score():
    r = assess_frozen_v2_eval_readiness_shadow(
        sealed_source_output_present=False,
        prior_signed_identities_retained=True,
        owner_authorised_new_rows=False,
        evaluator_truth_unchanged=True,
    )
    assert r["first_remaining_gate"] == "eval_blocked_sealed_source_output_missing"
    assert r["evaluator_invoked"] is False
    assert r["score_improvement_claimed"] is False
    assert r["gold_values_consumed"] is False


def test_mission_ledger_is_shadow_only():
    ledger = mission_ledger()
    assert ledger["shadow_only"] is True
    assert ledger["benchmark_score_granted"] is False
    assert any(p["number"] == 3356 for p in ledger["prs"])
