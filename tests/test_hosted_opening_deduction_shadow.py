from pb_hosted_opening_deduction_shadow import assess_hosted_opening_deduction_shadow


def test_gap_without_host_cannot_deduct():
    r = assess_hosted_opening_deduction_shadow(
        wall_id="w1",
        opening_id="o1",
        host_binding_record_id=None,
        void_record_id="void-1",
        opening_area_m2=2.16,
        opening_area_authority="firm",
    )
    assert r["first_remaining_gate"] == "deduction_host_binding_unproven"
    assert r["gap_width_used_as_authority"] is False
    assert r["deduction_authority_granted"] is False


def test_complete_chain_still_review_only():
    r = assess_hosted_opening_deduction_shadow(
        wall_id="w1",
        opening_id="o1",
        host_binding_record_id="host-1",
        void_record_id="void-1",
        opening_area_m2=2.16,
        opening_area_authority="firm",
    )
    assert r["first_remaining_gate"] == "hosted_opening_deduction_review_only"
    assert r["deduction_authority_granted"] is False
