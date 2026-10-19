"""Exact unit notation differences may not block client-owned cost pricing."""
from __future__ import annotations

import pytest

from tools.gpt3_verified_customer_quote import (
    _equivalent_pricing_unit, build_verified_customer_quote,
)
from test_gpt3_verified_customer_quote import fixture


@pytest.mark.parametrize(("raw", "canonical"), [
    ("m²", "m2"), ("sqm", "m2"), ("m2", "m2"),
    ("m³", "m3"), ("m3", "m3"),
    ("lm", "m"), ("m", "m"),
    ("ea", "ea"), ("each", "ea"), ("nr", "ea"),
    ("no", "ea"), ("no.", "ea"), ("number", "ea"),
])
def test_exact_physical_dimension_notation_aliases(raw, canonical):
    assert _equivalent_pricing_unit(raw) == canonical


def test_archived_eight_original_signed_areas_price_with_m_squared_rate_notation():
    sealed, customers, rates = fixture()
    baseline = build_verified_customer_quote(sealed, customers, rates)
    rates["rates"][0]["unit"] = "m²"
    adjusted = build_verified_customer_quote(sealed, customers, rates)
    assert adjusted["publication_status"] == "CLIENT_PRICED_QUOTE"
    assert adjusted["signed_quantity_count"] == baseline["signed_quantity_count"] == 8
    assert adjusted["summary"]["grand_total"] == baseline["summary"]["grand_total"]
    assert [x["quantity_fingerprint"] for x in adjusted["items"]] == [
        x["quantity_fingerprint"] for x in baseline["items"]
    ]
    assert adjusted["official_four_project_accuracy"] is None


def test_same_client_rate_with_both_area_spellings_is_rejected_as_duplicate():
    sealed, customers, rates = fixture()
    alias = dict(rates["rates"][0])
    alias["unit"] = "sqm"
    rates["rates"].append(alias)
    with pytest.raises(ValueError, match="duplicate client rate card"):
        build_verified_customer_quote(sealed, customers, rates)


def test_wrong_dimensional_rate_cannot_price_original_signed_m2_as_linear_m():
    sealed, customers, rates = fixture()
    rates["rates"][0]["unit"] = "lm"
    report = build_verified_customer_quote(sealed, customers, rates)
    assert report["unpriced_quantity_count"] == 8
    assert report["publication_status"] == "INCOMPLETE_UNPRICED_QUANTITIES"
    assert report["summary"]["grand_total"] is None
