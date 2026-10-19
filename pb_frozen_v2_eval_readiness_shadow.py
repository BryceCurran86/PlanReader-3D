"""Mission items 29–30 — frozen V2 eval readiness; never run without sealed output.

Refuses to claim score improvement. Does not invoke the evaluator or read gold.
"""
from __future__ import annotations

from typing import Any


def assess_frozen_v2_eval_readiness_shadow(
    *,
    sealed_source_output_present: bool,
    prior_signed_identities_retained: bool,
    owner_authorised_new_rows: bool,
    evaluator_truth_unchanged: bool,
) -> dict[str, Any]:
    if not sealed_source_output_present:
        gate = "eval_blocked_sealed_source_output_missing"
    elif not prior_signed_identities_retained:
        gate = "eval_blocked_prior_signed_identity_loss"
    elif not evaluator_truth_unchanged:
        gate = "eval_blocked_frozen_truth_or_tolerance_change"
    elif not owner_authorised_new_rows and sealed_source_output_present:
        # Eval of unchanged sealed baseline is allowed only as retention check,
        # not as a score-improvement claim.
        gate = "eval_retention_check_only_no_score_claim"
    else:
        gate = "frozen_v2_eval_review_only"
    return {
        "first_remaining_gate": gate,
        "evaluator_invoked": False,
        "gold_values_consumed": False,
        "truth_or_tolerances_modified": False,
        "score_improvement_claimed": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
