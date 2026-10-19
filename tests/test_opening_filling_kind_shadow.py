from pb_opening_filling_kind_shadow import assess_opening_filling_kind_shadow


def test_gap_without_kind_abstains():
    r = assess_opening_filling_kind_shadow(
        physical_opening_id="o1", opening_kind=None
    )
    assert r["first_remaining_gate"] == "opening_filling_kind_unproven"
    assert r["filling_kind_source_supported"] is False


def test_kind_token_without_evidence_ids_abstains():
    r = assess_opening_filling_kind_shadow(
        physical_opening_id="o1", opening_kind="door"
    )
    assert r["first_remaining_gate"] == "opening_filling_kind_evidence_unproven"


def test_kind_with_evidence_still_does_not_publish_measurement():
    r = assess_opening_filling_kind_shadow(
        physical_opening_id="o1",
        opening_kind="window",
        source_kind_evidence_ids=("schedule-row-1",),
    )
    assert r["filling_kind_source_supported"] is True
    assert r["measurement_published"] is False
