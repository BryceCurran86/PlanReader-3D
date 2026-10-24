"""An empty valid V1 source seal is not a complete priced construction project."""
from __future__ import annotations

from pb_source_closed_run_export import (
    seal_source_closed_run, sealed_source_closed_run_from_dict,
)
from tools.gpt3_verified_customer_quote import build_verified_customer_quote
from test_gpt3_verified_customer_quote import fixture


def test_zero_authenticated_source_quantities_never_becomes_zero_dollar_quote():
    old, customers, rates = fixture()
    sealed = seal_source_closed_run(
        [], project_id=old["project_id"], traces_by_quantity_id={},
    )
    sealed_source_closed_run_from_dict(sealed.to_dict())
    quote = build_verified_customer_quote(sealed.to_dict(), [], rates)
    assert quote["signed_quantity_count"] == 0
    assert quote["unpriced_quantity_count"] == 0
    assert quote["publication_status"] == "NO_VERIFIED_SOURCE_QUANTITIES"
    assert quote["summary"]["grand_total"] is None
    assert quote["official_four_project_accuracy"] is None
    assert not quote["items"]


def test_manual_only_allowance_does_not_authenticate_missing_source_quantity():
    old, customers, rates = fixture()
    sealed = seal_source_closed_run(
        [], project_id=old["project_id"], traces_by_quantity_id={},
    )
    rates["include_manual_allowances"] = True
    quote = build_verified_customer_quote(sealed.to_dict(), [
        {"description": "estimator manual note", "quantity": 1},
    ], rates)
    assert quote["manual_allowances_included"] is True
    assert quote["manual_projection_rows_outside_signed_bijection"] == 1
    assert quote["publication_status"] == "NO_VERIFIED_SOURCE_QUANTITIES"
    assert quote["summary"]["grand_total"] is None


def test_genuine_original_lot16_eight_source_quantities_still_publish_priced_quote():
    sealed, customers, rates = fixture()
    quote = build_verified_customer_quote(sealed, customers, rates)
    assert quote["publication_status"] == "CLIENT_PRICED_QUOTE"
    assert quote["signed_quantity_count"] == 8
    assert quote["summary"]["grand_total"] is not None
