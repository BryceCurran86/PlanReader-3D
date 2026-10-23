"""Synthetic metamorphic checks for frozen-V2 eval refuse-closed shadow."""
from __future__ import annotations

from pb_door_height_owner_gate_shadow import assess_door_height_owner_gate_shadow
from pb_frozen_v2_eval_readiness_shadow import assess_frozen_v2_eval_readiness_shadow


def test_frozen_v2_refuses_without_owner_authorisation():
    row = assess_frozen_v2_eval_readiness_shadow(
        sealed_source_output_present=True,
        prior_signed_identities_retained=True,
        owner_authorised_new_rows=False,
        evaluator_truth_unchanged=True,
    )
    assert row["benchmark_score_granted"] is False
    assert row["evaluator_invoked"] is False
    assert row["score_improvement_claimed"] is False
    assert row["first_remaining_gate"] == "eval_retention_check_only_no_score_claim"


def test_frozen_v2_input_order_invariant():
    a = assess_frozen_v2_eval_readiness_shadow(
        sealed_source_output_present=True,
        prior_signed_identities_retained=True,
        owner_authorised_new_rows=False,
        evaluator_truth_unchanged=True,
    )
    b = assess_frozen_v2_eval_readiness_shadow(
        evaluator_truth_unchanged=True,
        owner_authorised_new_rows=False,
        prior_signed_identities_retained=True,
        sealed_source_output_present=True,
    )
    assert a["first_remaining_gate"] == b["first_remaining_gate"]


def test_door_height_user_approved_still_requires_owned_height():
    row = assess_door_height_owner_gate_shadow(
        physical_opening_id="synthetic:door",
        owned_height_evidence_ids=(),
        owned_height_mm=None,
        user_approved_height=True,
        label_width_only_mm=900.0,
    )
    assert row["invented_second_axis_mm"] is None
    assert row["measurement_published"] is False
    # USER_APPROVED without owned height value must not invent mm.
    assert row["owned_height_mm"] is None
