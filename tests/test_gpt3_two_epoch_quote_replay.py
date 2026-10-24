"""One client price delta is safe only across independently replayed same-V1 quotes."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from tools.gpt3_two_epoch_quote_replay import compare_two_replayed_quote_epochs
from tools.gpt3_verified_customer_quote import build_verified_customer_quote
from test_gpt3_verified_customer_quote import fixture
from test_gpt3_signed_v1_customer_epoch_drift import _epochs
from test_gpt3_preview_scope_gated_customer_quote import _rates


def _base():
    sealed, customer, old_rates = fixture()
    old_quote = build_verified_customer_quote(sealed, customer, old_rates)
    return sealed, customer, old_rates, old_quote


def _check(*, old, new):
    return compare_two_replayed_quote_epochs(
        previous_signed=old[0], previous_customer=old[1],
        previous_rates=old[2], previous_quote=old[3],
        current_signed=new[0], current_customer=new[1],
        current_rates=new[2], current_quote=new[3],
    )


def test_client_only_rate_revision_has_exact_source_identity_and_money_delta():
    old = _base()
    newer_rates = deepcopy(old[2])
    newer_rates["rates"][0]["material"] = "50.00"
    current = (*old[:2], newer_rates,
               build_verified_customer_quote(*old[:2], newer_rates))
    report = _check(old=old, new=current)
    assert report["decision"] == "SAME_V1_SOURCE_CLIENT_PRICE_REVISION"
    assert report["physical_quantity_universe_unchanged"]
    assert report["source_quantity_ids_inferred_by_similarity"] is False
    assert report["verified_client_quote_grand_total_delta"] is not None
    assert report["official_v2_accuracy"] is None


def test_client_currency_change_does_not_fabricate_forex_price_delta():
    old = _base()
    new_rates = deepcopy(old[2])
    new_rates["currency"] = "USD"
    new_quote = build_verified_customer_quote(old[0], old[1], new_rates)
    report = _check(old=old, new=(old[0], old[1], new_rates, new_quote))
    assert report["decision"] == "CURRENCY_CHANGED_NO_FX_AUTHORITY"
    assert report["verified_client_quote_grand_total_delta"] is None


def test_missing_client_rate_prevents_comparable_grand_total():
    old = _base()
    current_rates = deepcopy(old[2])
    current_rates["rates"] = []
    new_quote = build_verified_customer_quote(old[0], old[1], current_rates)
    report = _check(
        old=old, new=(old[0], old[1], current_rates, new_quote),
    )
    assert report["decision"] == "UNPRICED_QUOTE_DELTA_UNAVAILABLE"
    assert report["verified_client_quote_grand_total_delta"] is None


def test_changed_signed_source_quantities_never_inherit_client_rate_approval(tmp_path):
    (old_file, old_customers), (new_file, new_customers) = _epochs(tmp_path)
    old_source = json.loads(old_file.read_text())
    new_source = json.loads(new_file.read_text())
    old_rows = json.loads(old_customers.read_text())
    new_rows = json.loads(new_customers.read_text())
    rates = _rates()
    old_quote = build_verified_customer_quote(old_source, old_rows, rates)
    new_quote = build_verified_customer_quote(new_source, new_rows, rates)
    result = _check(
        old=(old_source, old_rows, rates, old_quote),
        new=(new_source, new_rows, rates, new_quote),
    )
    assert result["decision"] == "SIGNED_SOURCE_EPOCH_CHANGED_REVIEW_REQUIRED"
    assert not result["physical_quantity_universe_unchanged"]
    assert result["verified_client_quote_grand_total_delta"] is None


def test_prior_quote_rehashed_source_value_fails_exact_replay_before_delta():
    old = _base()
    bad = deepcopy(old[3])
    bad["items"][0]["sell_amount"] = "999.00"
    with pytest.raises(ValueError, match="does not reproduce"):
        _check(old=old, new=(old[0], old[1], old[2], bad))
