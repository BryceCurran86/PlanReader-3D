from pb_opening_universe_completeness_shadow import (
    assess_opening_universe_completeness_shadow,
    refuse_merge_distinct_openings_by_label,
)


def test_incomplete_universe_never_grants_count():
    r = assess_opening_universe_completeness_shadow(
        instance_ids=("a", "b"), universe_complete=False
    )
    assert r["first_remaining_gate"] == "opening_universe_incomplete"
    assert r["opening_count_granted"] is False


def test_duplicate_ids_block_count():
    r = assess_opening_universe_completeness_shadow(
        instance_ids=("a", "a"), universe_complete=True
    )
    assert r["first_remaining_gate"] == "opening_universe_duplicate_instance_ids"


def test_matching_labels_do_not_merge_distinct_openings():
    r = refuse_merge_distinct_openings_by_label(
        openings=(
            {"physical_opening_id": "p1", "printed_label": "D01"},
            {"physical_opening_id": "p2", "printed_label": "D01"},
        )
    )
    assert r["merged_physical_ids"] == []
    assert r["label_collisions"]["D01"] == ["p1", "p2"]
    assert r["opening_count_granted"] is False
