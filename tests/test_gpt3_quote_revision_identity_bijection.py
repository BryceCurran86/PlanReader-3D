"""No self-hashed customer quote can erase or re-key signed physical identities."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from test_gpt3_verified_customer_quote import fixture
from tools.gpt3_verified_customer_quote import (
    build_verified_customer_quote, compare_verified_quotes,
)


def original_quote():
    sealed, customers, rates = fixture()
    return build_verified_customer_quote(sealed, customers, rates)


def rehash(quote):
    record = dict(quote)
    record.pop("quote_fingerprint", None)
    quote["quote_fingerprint"] = hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return quote


def test_original_eight_same_issuer_repriced_rates_are_rate_only():
    sealed, customers, rates = fixture()
    original = build_verified_customer_quote(sealed, customers, rates)
    rates["rates"][0]["material"] = "60.00"
    second = build_verified_customer_quote(sealed, customers, rates)
    result = compare_verified_quotes(original, second)
    assert result["issuer_comparison"] == "SAME_SIGNED_ISSUER"
    assert result["official_four_project_accuracy"] is None
    assert len(result["item_changes"]) == 8
    assert all(x["change"] == "CLIENT_RATE_OR_PRICING_CHANGED"
               for x in result["item_changes"])


def test_duplicate_quote_quantity_cannot_be_dropped_by_dict_comprehension():
    original = original_quote()
    altered = deepcopy(original)
    altered["items"].append(deepcopy(altered["items"][0]))
    altered["signed_quantity_count"] = 9
    rehash(altered)
    with pytest.raises(ValueError, match="duplicate signed source"):
        compare_verified_quotes(original, altered)


def test_claimed_count_cannot_disagree_with_actual_signed_items():
    original = original_quote()
    altered = deepcopy(original)
    altered["signed_quantity_count"] = 9
    rehash(altered)
    with pytest.raises(ValueError, match="count is inconsistent"):
        compare_verified_quotes(original, altered)


def test_empty_rehashed_source_quote_does_not_count_as_identical_issuer():
    original = original_quote()
    empty = deepcopy(original)
    empty["items"] = []
    empty["signed_quantity_count"] = 0
    rehash(empty)
    with pytest.raises(ValueError, match="actual signed source quantities"):
        compare_verified_quotes(original, empty)


@pytest.mark.parametrize(("key", "change"), [
    ("quantity_fingerprint", "0" * 64),
    ("source_sha256", "1" * 64),
    ("revision_id", "revision-fake"),
    ("source_page", "not-the-original-sheet"),
    ("family", "invented_construction_family"),
    ("semantic_key", "not-original"),
    ("object_identity_refs", ["fake-physical-floor"]),
])
def test_locally_rehashed_source_change_is_not_same_issuer(key, change):
    original = original_quote()
    altered = deepcopy(original)
    altered["items"][0][key] = change
    rehash(altered)
    result = compare_verified_quotes(original, altered)
    assert result["issuer_comparison"] == (
        "SOURCE_IDENTITY_CONFLICT_REQUIRES_INDEPENDENT_AUTHORITY"
    )
    assert result["item_changes"][0]["change"] == (
        "SOURCE_QUANTITY_CHANGED_REQUIRES_RESEAL"
    )


def test_same_line_count_rekeyed_physical_quantity_is_removed_and_added():
    original = original_quote()
    altered = deepcopy(original)
    altered["items"][0]["quantity_id"] = "new-physical-but-same-area"
    rehash(altered)
    result = compare_verified_quotes(original, altered)
    assert result["issuer_comparison"] == (
        "SOURCE_IDENTITY_CONFLICT_REQUIRES_INDEPENDENT_AUTHORITY"
    )
    assert [x["change"] for x in result["item_changes"]].count(
        "SIGNED_QUANTITY_ADDED_OR_REMOVED_REQUIRES_RESEAL"
    ) == 2
