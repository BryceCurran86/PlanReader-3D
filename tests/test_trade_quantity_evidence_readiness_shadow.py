import pytest

from pb_trade_quantity_evidence_readiness_shadow import (
    assess_trade_quantity_evidence_readiness_shadow,
)


@pytest.mark.parametrize("trade", [
    "painting", "plastering", "tiling", "concreting", "carpentry", "plumbing", "electrical",
])
def test_each_trade_abstains_without_evidence(trade):
    r = assess_trade_quantity_evidence_readiness_shadow(trade=trade)
    assert r["first_remaining_gate"] == f"{trade}_evidence_unavailable"
    assert r["default_rate_or_area_invented"] is False
    assert r["measurement_published"] is False


def test_trade_with_evidence_still_review_only_until_authority():
    r = assess_trade_quantity_evidence_readiness_shadow(
        trade="tiling",
        evidence_ids=("finish-occ-1",),
        quantity_authority_status=None,
    )
    assert r["first_remaining_gate"] == "tiling_quantity_authority_unproven"


def test_authorised_trade_row_remains_unpublished():
    r = assess_trade_quantity_evidence_readiness_shadow(
        trade="painting",
        evidence_ids=("wall-face-1",),
        quantity_authority_status="firm",
    )
    assert r["first_remaining_gate"] == "painting_quantity_review_only"
    assert r["customer_seal_granted"] is False
