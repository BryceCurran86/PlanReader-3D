from pb_bifold_filling_kind_shadow import assess_bifold_filling_kind_shadow


def test_gap_alone_does_not_create_bifold_kind():
    r = assess_bifold_filling_kind_shadow(
        physical_opening_id="o-bifold",
        gap_geometry_present=True,
    )
    assert r["first_remaining_gate"] == "bifold_plan_filling_role_unproven"
    assert r["gap_geometry_used_as_kind"] is False
    assert r["opening_kind_granted"] is False


def test_plan_role_without_type_identity_abstains():
    r = assess_bifold_filling_kind_shadow(
        physical_opening_id="o-bifold",
        plan_filling_role_evidence_ids=("plan-word-1",),
    )
    assert r["first_remaining_gate"] == "bifold_type_identity_unproven"


def test_full_evidence_still_review_only():
    r = assess_bifold_filling_kind_shadow(
        physical_opening_id="o-bifold",
        plan_filling_role_evidence_ids=("plan-word-1",),
        manufacturer_or_elevation_evidence_ids=("elev-sched-1",),
    )
    assert r["first_remaining_gate"] == "bifold_filling_kind_review_only"
    assert r["measurement_published"] is False
