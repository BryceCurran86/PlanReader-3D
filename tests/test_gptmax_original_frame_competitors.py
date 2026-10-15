"""No artificial source/quantity authority from a read-only competitor census."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_original_frame_competitors import original_frame_competitor_census

SHA = "a" * 64
SNAP = "source_snapshot_test"
IDENTITY = "physical_opening_existence_test"
REASON = "opening_host_frame_aligned_fragment_distinctness_unproven"


def fixture():
    obs = [f"source_observation_{i}" for i in range(6)]
    records = []
    for id_, a, b in [
        ("left", (0, 0), (5, 0)),
        ("right", (9, 0), (14, 0)),
        ("other", (20, 0), (25, 0)),
    ]:
        records.append({
            "wall_candidate_id": id_,
            "physical_identity": {
                "viewport_id": "wall-source:page-1",
                "source_primitive_ids": ["source:" + id_],
                "edge_ids": ["split:" + id_],
            },
            "wall_candidate": {"centerline_pts": [a, b]},
        })
    return {
        "source_sha256": SHA,
        "snapshot_id": SNAP,
        "baseline_receipts": {
            "walls": [{
                "decision_scope_id": "wall-source:page-1",
                "document_id": "live-source:synthetic",
                "revision_id": "source_revision_test",
                "page_id": "1",
                "scope_complete": True,
                "source_sha256": SHA,
                "snapshot_id": SNAP,
                "records": records,
                "equivalence": {"pair_classifications": []},
            }],
            "canonical": [{
                "physical_opening_id": IDENTITY,
                "source_sha256": SHA,
                "snapshot_id": SNAP,
                "source_observation_ids": obs,
            }],
            "hosts": [{
                "opening_identity_id": IDENTITY,
                "status": "corroborated",
                "host_wall_id": "host",
                "member_wall_candidate_ids": ["left", "right"],
            }],
            "frames": [{
                "opening_identity_id": IDENTITY,
                "status": "abstained",
                "record_id": None,
                "reason_codes": [REASON],
            }],
        },
        "baseline_source_audit": {
            "raw_registered_gaps": [{
                "source_observation_ids": obs,
                "raw_candidate_id": "raw_selected",
                "aperture_bbox_pt": [5, -2, 9, 2],
                "source_scope": {
                    "document_id": "live-source:synthetic",
                    "revision_id": "source_revision_test",
                    "page_id": "1",
                    "source_sha256": SHA,
                    "snapshot_id": SNAP,
                },
            }],
        },
    }


def run(d):
    return original_frame_competitor_census(
        d, source_sha256=SHA, snapshot_id=SNAP,
        physical_opening_ids=(IDENTITY,),
    )


def test_unrecorded_fragment_is_never_distinct_or_an_authority_grant():
    d = fixture()
    before = deepcopy(d)
    r = run(d)
    assert r["unproven_noncomponent_fragment_count"] == 1
    assert r["unproven_noncomponent_fragments"][0]["wall_candidate_id"] == "other"
    assert {p["producer_relation"] for p in
            r["unproven_noncomponent_fragments"][0]["member_relations"]} == {"UNRECORDED"}
    assert all(not v for v in r["authority_grants"].values())
    assert d == before


def test_only_both_independent_positive_distinctness_pairs_remove_diagnostic_blocker():
    d = fixture()
    pairs = d["baseline_receipts"]["walls"][0]["equivalence"]["pair_classifications"]
    pairs.append(["other", "left", "distinct_physical_walls"])
    assert run(d)["unproven_noncomponent_fragment_count"] == 1
    pairs.append(["other", "right", "distinct_physical_walls"])
    r = run(d)
    assert r["unproven_noncomponent_fragment_count"] == 0
    assert all(not v for v in r["authority_grants"].values())
    pairs[1][2] = "ambiguous_physical_equivalence"
    assert run(d)["unproven_noncomponent_fragment_count"] == 1


def test_input_order_has_no_effect():
    d = fixture()
    a = run(d)
    d["baseline_receipts"]["walls"][0]["records"].reverse()
    assert run(d) == a


@pytest.mark.parametrize("alter", [
    lambda d: d.update(source_sha256="0" * 64),
    lambda d: d["baseline_receipts"]["walls"][0].update(scope_complete=False),
    lambda d: d["baseline_receipts"]["frames"][0].update(status="corroborated"),
    lambda d: d["baseline_receipts"]["hosts"][0].update(host_wall_id=None),
    lambda d: d["baseline_source_audit"]["raw_registered_gaps"][0].update(
        source_observation_ids=["first"]),
    lambda d: d["baseline_receipts"]["walls"][0]["records"].pop(0),
])
def test_corrupt_or_unproven_source_fails_closed(alter):
    d = fixture()
    alter(d)
    with pytest.raises((KeyError, ValueError)):
        run(d)


def test_exact_source_context_and_target_identity_required():
    d = fixture()
    with pytest.raises(ValueError):
        original_frame_competitor_census(
            d, source_sha256=SHA, snapshot_id=SNAP, physical_opening_ids=())
    with pytest.raises(ValueError):
        original_frame_competitor_census(
            d, source_sha256=SHA, snapshot_id="foreign_snapshot",
            physical_opening_ids=(IDENTITY,))


def test_unrelated_missing_record_never_grants_positive_authority():
    d = fixture()
    d["baseline_receipts"]["walls"][0]["records"].pop()
    r = run(d)
    assert not any(r["authority_grants"].values())
    assert r["unproven_noncomponent_fragment_count"] == 0


def test_duplicate_prior_source_snapshot_is_not_aliased_to_selected_root():
    d = fixture()
    older = deepcopy(d["baseline_source_audit"]["raw_registered_gaps"][0])
    older["raw_candidate_id"] = "raw_older_snapshot"
    older["source_scope"]["snapshot_id"] = "source_snapshot_old"
    older["aperture_bbox_pt"] = [5, 300, 9, 320]
    d["baseline_source_audit"]["raw_registered_gaps"].append(older)
    r = run(d)
    assert r["horizontal_stripe_y_bounds_pt"] == [-2, 2]
    assert r["target_hosted_unframed_openings"][0]["original_raw_candidate_ids"] == ["raw_selected"]
    assert r["target_hosted_unframed_openings"][0]["selected_source_root_only"] == SNAP
    assert not any(r["authority_grants"].values())
