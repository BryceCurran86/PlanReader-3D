from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_unhosted_host_identity_original_attach import (
    attach_host_identity_to_unhosted_ancestry,
)


def test_empty_ancestry_candidates_report_host_unavailable():
    report = attach_host_identity_to_unhosted_ancestry([
        {
            "physical_opening_id": "op-u",
            "host_granted": False,
            "host_reason_codes": ("no_authenticated_host_wall_band",),
            "source_g17_observations": [{
                "exact_source_ref_w4_candidates": [],
                "authenticated_source_parents": [],
            }],
        },
    ])
    row = report["openings"][0]
    assert row["exact_source_w4_candidate_count"] == 0
    assert row["host_identity_shadow"]["disposition"] == "structural_host_unavailable"
    assert row["host_granted"] is False


def test_multiple_candidates_retain_all_without_nearest():
    Class = PhysicalEquivalenceClass
    report = attach_host_identity_to_unhosted_ancestry(
        [{
            "physical_opening_id": "op-m",
            "host_granted": False,
            "source_g17_observations": [{
                "exact_source_ref_w4_candidates": [
                    {"wall_candidate_id": "w-b"},
                    {"wall_candidate_id": "w-a"},
                ],
                "authenticated_source_parents": [{
                    "exact_source_ref_w4_candidates": [
                        {"wall_candidate_id": "w-a"},
                        {"wall_candidate_id": "w-c"},
                    ],
                }],
            }],
        }],
        pair_classifications=[
            ("w-a", "w-b", Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value),
            ("w-a", "w-c", Class.DISTINCT_PHYSICAL_WALLS.value),
            ("w-b", "w-c", Class.DISTINCT_PHYSICAL_WALLS.value),
        ],
    )
    identity = report["openings"][0]["host_identity_shadow"]
    assert identity["retained_candidate_wall_ids"] == ["w-a", "w-b", "w-c"]
    assert identity["disposition"] == "ambiguous_physical_wall_equivalence_for_host"
    assert identity["elected_host_wall_id"] is None
    assert identity["nearest_or_first_used"] is False
