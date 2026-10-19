from pb_source_closed_seal_readiness_shadow import assess_source_closed_seal_readiness_shadow


def test_seal_requires_owner_promotion_even_when_firm():
    r = assess_source_closed_seal_readiness_shadow(
        quantity_id="q-new",
        authority_status="firm",
        source_lineage_complete=True,
        dedupe_clear=True,
        prior_signed_ids_retained=True,
        owner_promotion_approved=False,
    )
    assert r["first_remaining_gate"] == "seal_blocked_owner_promotion_required"
    assert r["seal_activated"] is False
    assert r["customer_rows_mutated"] is False


def test_ready_for_review_still_does_not_seal():
    r = assess_source_closed_seal_readiness_shadow(
        quantity_id="q-new",
        authority_status="firm",
        source_lineage_complete=True,
        dedupe_clear=True,
        prior_signed_ids_retained=True,
        owner_promotion_approved=True,
    )
    assert r["first_remaining_gate"] == "source_closed_seal_review_only"
    assert r["seal_activated"] is False
