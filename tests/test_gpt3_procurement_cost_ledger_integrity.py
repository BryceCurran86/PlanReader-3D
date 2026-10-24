"""Supplier procurement cannot inherit a rehashed inconsistent client quote ledger."""
from __future__ import annotations

from copy import deepcopy

import pytest

from test_gpt3_client_procurement import fixtures
from tools.gpt3_client_procurement_awards import (
    build_procurement_plan, _hash,
)


def _prepare():
    source, rows, quote, book = fixtures()
    return source, rows, quote, book


def _reissue(fake, book):
    fake["quote_fingerprint"] = _hash(fake, "quote_fingerprint")
    book["quote_fingerprint"] = fake["quote_fingerprint"]
    return fake, book


def test_original_archived_eight_source_quote_still_produces_unsent_po_drafts():
    source, rows, quote, book = _prepare()
    plan = build_procurement_plan(quote, source, rows, book)
    assert len(plan["purchase_order_drafts"]) == 1
    assert plan["order_transmitted"] is False
    assert plan["official_four_project_accuracy"] is None
    assert plan["material_requirement_authenticated_from_drawings"] is False


@pytest.mark.parametrize("field", ("material", "labour", "plant", "subcontract"))
def test_forged_single_cost_component_cannot_enter_client_procurement(field):
    source, rows, quote, book = _prepare()
    fake = deepcopy(quote)
    fake["items"][0]["cost_components"][field] = "9999.00"
    _reissue(fake, book)
    with pytest.raises(ValueError, match="component costs"):
        build_procurement_plan(fake, source, rows, book)


def test_modified_line_total_without_matching_components_is_rejected():
    source, rows, quote, book = _prepare()
    fake = deepcopy(quote)
    fake["items"][0]["cost_amount"] = "9999.00"
    _reissue(fake, book)
    with pytest.raises(ValueError, match="component costs"):
        build_procurement_plan(fake, source, rows, book)


def test_fake_markup_cannot_inflate_sell_value_on_source_quote():
    source, rows, quote, book = _prepare()
    fake = deepcopy(quote)
    fake["items"][0]["markup_pct"] = "100.00"
    _reissue(fake, book)
    with pytest.raises(ValueError, match="cost/markup disagree"):
        build_procurement_plan(fake, source, rows, book)


def test_rehashed_grand_total_cannot_become_procurement_authority():
    source, rows, quote, book = _prepare()
    fake = deepcopy(quote)
    fake["summary"]["grand_total"] = "999999.00"
    _reissue(fake, book)
    with pytest.raises(ValueError, match="grand total"):
        build_procurement_plan(fake, source, rows, book)


def test_rehashed_line_sell_cannot_forge_cash_after_source_identity_passes():
    source, rows, quote, book = _prepare()
    fake = deepcopy(quote)
    fake["items"][0]["sell_amount"] = "9999.00"
    _reissue(fake, book)
    with pytest.raises(ValueError, match="priced subtotal|cost/markup"):
        build_procurement_plan(fake, source, rows, book)


def test_procurement_cost_components_always_reconcile_exactly_to_cents():
    source, rows, quote, book = _prepare()
    for line in quote["items"]:
        assert sum(
            __import__("decimal").Decimal(v)
            for v in line["cost_components"].values()
        ) == __import__("decimal").Decimal(line["cost_amount"])
    assert build_procurement_plan(quote, source, rows, book)["official_four_project_accuracy"] is None
