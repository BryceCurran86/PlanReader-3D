from pb_opening_host_identity_shadow import build_opening_host_identity_shadow
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class


def test_no_candidates_abstain():
    r = build_opening_host_identity_shadow(
        physical_opening_id="o1", candidate_wall_ids=()
    )
    assert r["disposition"] == "structural_host_unavailable"
    assert r["elected_host_wall_id"] is None
    assert r["host_granted"] is False


def test_unique_candidate_observed_but_not_granted():
    r = build_opening_host_identity_shadow(
        physical_opening_id="o1", candidate_wall_ids=("wall-a",)
    )
    assert r["disposition"] == "unique_structural_host_candidate_observed"
    assert r["host_granted"] is False
    assert r["nearest_or_first_used"] is False


def test_ambiguous_pair_retains_both_without_election():
    r = build_opening_host_identity_shadow(
        physical_opening_id="o1",
        candidate_wall_ids=("wall-b", "wall-a"),
        pair_classifications=(
            ("wall-a", "wall-b", Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value),
        ),
    )
    assert r["disposition"] == "ambiguous_physical_wall_equivalence_for_host"
    assert r["retained_candidate_wall_ids"] == ["wall-a", "wall-b"]
    assert r["elected_host_wall_id"] is None


def test_missing_pair_relation_fails_closed():
    r = build_opening_host_identity_shadow(
        physical_opening_id="o1",
        candidate_wall_ids=("wall-a", "wall-b"),
    )
    assert r["disposition"] == "physical_wall_equivalence_required_for_host"


def test_input_order_invariance():
    args = dict(
        physical_opening_id="o1",
        candidate_wall_ids=("wall-b", "wall-a"),
        pair_classifications=(
            ("wall-a", "wall-b", Class.DISTINCT_PHYSICAL_WALLS.value),
        ),
    )
    first = build_opening_host_identity_shadow(**args)
    second = build_opening_host_identity_shadow(
        physical_opening_id="o1",
        candidate_wall_ids=("wall-a", "wall-b"),
        pair_classifications=args["pair_classifications"],
    )
    assert first == second
    assert first["disposition"] == "multiple_structural_host_candidates_retained"
