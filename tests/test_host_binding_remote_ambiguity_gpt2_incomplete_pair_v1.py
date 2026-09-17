"""Producer-owned equivalence consistency controls for host ambiguity repair.

TEST-ONLY / DO NOT MERGE.

These checks prove which contradiction states can actually arrive from the sealed
physical-wall equivalence producer. Host-repair acceptance must be based on these
producer-reachable states, not malformed hand-built resolution objects.
"""
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    resolve_physical_wall_equivalence,
)

from tests.test_host_binding_remote_ambiguity_gpt2_redteam_v1 import _record


def test_ambiguous_edge_dominates_same_link_across_one_upstream_component() -> None:
    """Legitimate contradiction monotonicity: SAME cannot erase an AMBIGUOUS edge."""
    first = _record(
        "first",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:shared",
    )
    proven_same = _record(
        "proven-same",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:shared",
    )
    foreign = _record(
        "foreign",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:foreign",
    )

    resolution = resolve_physical_wall_equivalence(
        (
            first.physical_identity,
            proven_same.physical_identity,
            foreign.physical_identity,
        )
    )

    # SAME(first, proven-same) exists pairwise, but AMBIGUOUS links to foreign
    # contaminate the connected component. No SAME representative may publish.
    pair_map = {
        (left, right): classification
        for left, right, classification in resolution.pair_classifications
    }
    assert pair_map[("first", "proven-same")] == PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value
    assert any(
        classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value
        for classification in pair_map.values()
    )
    assert resolution.equivalence_groups == ()
    assert set(resolution.ambiguous_wall_ids) == {"first", "proven-same", "foreign"}
    assert resolution.representative_wall_ids == ()


def test_every_upstream_ambiguous_wall_id_has_an_ambiguous_pair_explanation() -> None:
    first = _record("first", (-100.0, -5.0), (0.0, -5.0), source_id="source:first")
    second = _record("second", (200.0, -5.0), (260.0, -5.0), source_id="source:second")
    resolution = resolve_physical_wall_equivalence(
        (first.physical_identity, second.physical_identity)
    )

    ambiguous_pairs = [
        {left, right}
        for left, right, classification in resolution.pair_classifications
        if classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value
    ]
    assert ambiguous_pairs
    for wall_id in resolution.ambiguous_wall_ids:
        assert any(wall_id in pair for pair in ambiguous_pairs)
