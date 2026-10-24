"""Unrecorded proximity never becomes physical host or quantity evidence."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_original_hostless_source_census import original_hostless_source_census

SHA = "f" * 64
ROOT = "source_snapshot_demo"
IDENTITY = "physical_opening_existence_demo"


def fixture():
    observations = [f"source_observation_{n}" for n in range(6)]
    context = {
        "snapshot_id": ROOT, "source_sha256": SHA,
        "document_id": "live-source:demo", "revision_id": "source_revision_demo",
        "page_id": "3",
    }
    return {
        "source_sha256": SHA, "snapshot_id": ROOT,
        "baseline_receipts": {
            "walls": [{
                **context, "decision_scope_id": "wall-source:page-3",
                "scope_complete": True,
                "records": [{
                    "wall_candidate_id": "wall-a",
                    "physical_identity": {
                        "viewport_id": "wall-source:page-3",
                        "source_primitive_ids": ["raster_segment:source:101"],
                        "edge_ids": ["split_123"],
                    },
                    "wall_candidate": {
                        "centerline_pts": [[0, 5], [10, 5]],
                    },
                }],
            }],
            "canonical": [{
                "physical_opening_id": IDENTITY,
                "source_observation_ids": observations,
                "source_sha256": SHA, "snapshot_id": ROOT,
            }],
            "hosts": [{
                "opening_identity_id": IDENTITY,
                "record_id": None, "host_wall_id": None,
                "reason_codes": ["no_authenticated_host_wall_band",
                                 "raster_source_band_left_source_primitive_unmapped"],
            }],
        },
        "baseline_source_audit": {
            "raw_registered_gaps": [{
                "raw_candidate_id": "raw-current",
                "source_scope": context,
                "source_observation_ids": observations,
                "aperture_bbox_pt": [10, 3, 25, 7],
            }],
        },
    }


def run(d):
    return original_hostless_source_census(
        d, source_sha256=SHA, snapshot_id=ROOT,
        physical_opening_ids=(IDENTITY,),
    )


def test_positive_geometry_is_only_candidate_not_source_host():
    d = fixture()
    before = deepcopy(d)
    r = run(d)
    assert r["status"] == "UNPUBLISHED_SOURCE_HOSTLESS_DIAGNOSTIC"
    assert r["original_selected_root_raw_candidate_count"] == 1
    assert r["cases"][0]["shortlist_count"] == 1
    assert r["cases"][0]["source_w4_endpoint_shortlist"][0]["wall_candidate_id"] == "wall-a"
    assert r["cases"][0]["source_w4_endpoint_shortlist"][0]["structural_host_granted"] is False
    assert not any(r["authority_grants"].values())
    assert d == before


def test_old_source_root_is_not_current_gap():
    d = fixture()
    prior = deepcopy(d["baseline_source_audit"]["raw_registered_gaps"][0])
    prior["source_scope"]["snapshot_id"] = "source_snapshot_old"
    prior["raw_candidate_id"] = "raw-old"
    prior["aperture_bbox_pt"] = [100, 100, 125, 104]
    d["baseline_source_audit"]["raw_registered_gaps"].insert(0, prior)
    r = run(d)
    assert r["original_selected_root_raw_candidate_count"] == 1
    assert r["cases"][0]["source_raw_candidate_id"] == "raw-current"


def test_missing_or_competing_root_gap_abstains():
    d = fixture()
    d["baseline_source_audit"]["raw_registered_gaps"].append(
        deepcopy(d["baseline_source_audit"]["raw_registered_gaps"][0]))
    with pytest.raises(ValueError, match="competing"):
        run(d)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(snapshot_id="wrong"),
    lambda d: d["baseline_receipts"]["walls"][0].update(scope_complete=False),
    lambda d: d["baseline_receipts"]["hosts"][0].update(host_wall_id="unsafe"),
    lambda d: d["baseline_receipts"]["canonical"][0].update(snapshot_id="stale"),
    lambda d: d["baseline_receipts"]["walls"][0]["records"].append(
        deepcopy(d["baseline_receipts"]["walls"][0]["records"][0])),
    lambda d: d["baseline_source_audit"]["raw_registered_gaps"][0].update(
        source_observation_ids=["one"]),
])
def test_corrupt_root_wall_host_or_observations_fail_closed(mutate):
    d = fixture()
    mutate(d)
    with pytest.raises(ValueError):
        run(d)


def test_order_and_bounded_radius():
    d = fixture()
    r = run(d)
    assert r == run(deepcopy(d))
    with pytest.raises(ValueError, match="radius"):
        original_hostless_source_census(
            d, source_sha256=SHA, snapshot_id=ROOT,
            physical_opening_ids=(IDENTITY,), radius_pt=20,
        )
    with pytest.raises(ValueError, match="unique"):
        original_hostless_source_census(
            d, source_sha256=SHA, snapshot_id=ROOT,
            physical_opening_ids=(IDENTITY, IDENTITY),
        )
