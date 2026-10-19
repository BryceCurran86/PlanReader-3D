"""Source-exact old/new client quote revision comparison.

Every epoch is independently repriced from the corresponding signed V1,
customer rows and client rate book before any financial delta is reported.
Never transfer old signed customer approval across new physical quantities.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from tools.gpt3_replay_client_quote_from_signed_source import (
    verify_client_quote_source_replay,
)


def compare_two_replayed_quote_epochs(
    *, previous_signed: Mapping[str, Any],
    previous_customer: list[dict],
    previous_rates: Mapping[str, Any],
    previous_quote: Mapping[str, Any],
    current_signed: Mapping[str, Any],
    current_customer: list[dict],
    current_rates: Mapping[str, Any],
    current_quote: Mapping[str, Any],
) -> dict[str, Any]:
    """Conservative source-checked revision classification, no issuer inference."""
    old = verify_client_quote_source_replay(
        previous_signed, previous_customer, previous_rates, previous_quote,
    )
    new = verify_client_quote_source_replay(
        current_signed, current_customer, current_rates, current_quote,
    )
    if old["project_id"] != new["project_id"]:
        raise ValueError("quote revision must not compare different source projects")
    old_lines = {x["quantity_id"]: x for x in previous_quote["items"]}
    new_lines = {x["quantity_id"]: x for x in current_quote["items"]}
    unchanged_physical = (
        old["sealed_run_fingerprint"] == new["sealed_run_fingerprint"]
        and set(old_lines) == set(new_lines)
        and all(
            old_lines[qid]["quantity_fingerprint"]
            == new_lines[qid]["quantity_fingerprint"]
            for qid in old_lines
        )
    )
    equal_currency = previous_quote["currency"] == current_quote["currency"]
    fully_priced = (
        previous_quote["publication_status"] == "CLIENT_PRICED_QUOTE"
        and current_quote["publication_status"] == "CLIENT_PRICED_QUOTE"
    )
    if not unchanged_physical:
        decision = "SIGNED_SOURCE_EPOCH_CHANGED_REVIEW_REQUIRED"
    elif not equal_currency:
        decision = "CURRENCY_CHANGED_NO_FX_AUTHORITY"
    elif not fully_priced:
        decision = "UNPRICED_QUOTE_DELTA_UNAVAILABLE"
    else:
        decision = "SAME_V1_SOURCE_CLIENT_PRICE_REVISION"
    difference = None
    if decision == "SAME_V1_SOURCE_CLIENT_PRICE_REVISION":
        current_total = Decimal(current_quote["summary"]["grand_total"])
        previous_total = Decimal(previous_quote["summary"]["grand_total"])
        difference = format(current_total - previous_total, ".2f")
    return {
        "schema_version": "gpt3_two_epoch_customer_quote_replay.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "official_v2_accuracy": None,
        "project_id": old["project_id"],
        "previous_quote_fingerprint": old["quote_fingerprint"],
        "current_quote_fingerprint": new["quote_fingerprint"],
        "previous_source_run_fingerprint": old["sealed_run_fingerprint"],
        "current_source_run_fingerprint": new["sealed_run_fingerprint"],
        "physical_quantity_universe_unchanged": unchanged_physical,
        "same_currency": equal_currency,
        "both_quotes_completely_priced": fully_priced,
        "decision": decision,
        "verified_client_quote_grand_total_delta": difference,
        "source_quantity_ids_inferred_by_similarity": False,
    }
