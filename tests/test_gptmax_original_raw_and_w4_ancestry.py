"""Raw G17 overlapping source receipts are not count proof; W4 lineage is not host proof."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_original_raw_and_w4_ancestry import raw_and_w4_ancestry_audit

SHA = "a" * 64
ROOT = "source_snapshot_selected"
SCOPE = "wall-source:page-3"


def inputs():
    scope = {
        "document_id": "live-source:source",
        "revision_id": "source_revision_test",
        "source_sha256": SHA,
        "snapshot_id": ROOT,
        "page_id": "3",
    }
    r1 = {
        "raw_candidate_id": "raw1", "source_scope": scope,
        "aperture_bbox_pt": [0, 0, 5, 2],
        "source_observation_ids": ["a", "shared"],
    }
    r2 = {
        "raw_candidate_id": "raw2", "source_scope": scope,
        "aperture_bbox_pt": [8, 0, 12, 2],
        "source_observation_ids": ["b", "shared"],
    }
    w4 = {
        "wall_candidate_id": "wall1",
        "physical_identity": {
            "viewport_id": SCOPE,
            "source_primitive_ids": ["source_parent"],
            "edge_ids": ["split_1"],
        },
        "wall_candidate": {"centerline_pts": [[0.0, .3], [2.0, .0]]},
        "source_edge_fragments": [{
            "edge_id": "split_1",
            "source_primitive_ids": ["source_parent"],
            "geometry": [0.0, 0.0, 2.0, 0.0],
        }],
    }
    source = {
        "source_sha256": SHA, "snapshot_id": ROOT,
        "baseline_receipts": {
            "walls": [{
                **scope, "scope_complete": True,
                "decision_scope_id": SCOPE,
                "records": [w4],
            }],
            "canonical": [{
                "physical_opening_id": "physical_one",
                "source_sha256": SHA, "snapshot_id": ROOT,
            }],
            "hosts": [{
                "opening_identity_id": "physical_one",
                "host_wall_id": None, "record_id": None,
                "reason_codes": ["no_authenticated_host_wall_band"],
            }],
        },
        "baseline_source_audit": {
            "raw_registered_gaps": [r1, r2],
            "raster_candidate_closure": {
                "candidate_universe_complete": False,
                "raw_candidate_count": 2, "resolved_candidate_count": 0,
                "unresolved_candidate_ids": ["raw1", "raw2"],
                "unresolved_observation_ids": ["a", "b", "shared"],
            },
        },
        "candidate_source_audit": {
            "raster_candidate_closure": {
                "candidate_universe_complete": False,
                "raw_candidate_count": 2, "resolved_candidate_count": 1,
                "unresolved_candidate_ids": ["raw2"],
            },
        },
    }
    hostless = {
        "source_sha256": SHA, "snapshot_id": ROOT,
        "decision_scope_id": SCOPE,
        "cases": [{
            "physical_opening_id": "physical_one",
            "first_stage": "UNPROVEN_ORIGINAL_SOURCE_W4_STRUCTURAL_SIDE_MEMBERSHIP",
            "host_granted": False,
            "matched_source_observation_count": 6,
            "source_w4_endpoint_shortlist": [{"wall_candidate_id": "wall1"}],
        }],
    }
    return source, hostless


def audit(a, b):
    return raw_and_w4_ancestry_audit(
        a, b, source_sha256=SHA, snapshot_id=ROOT)


def test_shared_g17_source_observations_do_not_double_count():
    a, b = inputs()
    old = deepcopy((a, b))
    r = audit(a, b)
    assert r["original_raw_total"] == 2
    assert r["original_unresolved_count"] == 2
    assert r["isolated_shadow_unresolved_count"] == 1
    assert r["original_unresolved_observation_memberships"] == 4
    assert r["original_unique_unresolved_observations"] == 3
    assert r["shared_unresolved_source_observations"] == [{
        "source_observation_id": "shared",
        "raw_candidate_ids": ["raw1", "raw2"],
    }]
    assert all(not x for x in r["authority_grants"].values())
    assert (a, b) == old


def test_authentic_w4_split_lineage_reports_snap_but_does_not_grant_host():
    a, b = inputs()
    r = audit(a, b)
    chain = r["hostless_source_chains"][0]["w4_source_chains"][0]
    assert chain["split_edge_count"] == 1
    assert chain["max_original_source_to_w4_centerline_offset_pt"] == .3
    assert chain["source_primitive_ancestry_internally_consistent"] is True
    assert chain["missing_flank_membership_proven"] is False
    assert r["hostless_source_chains"][0]["host_or_frame_granted"] is False


def test_no_nearby_w4_shortlist_keeps_host_unknown():
    a, b = inputs()
    b["cases"][0]["source_w4_endpoint_shortlist"] = []
    r = audit(a, b)
    assert r["hostless_source_chains"][0]["source_w4_candidate_count"] == 0
    assert not any(r["authority_grants"].values())


def test_duplicate_prior_snapshot_raw_is_not_aliased():
    a, b = inputs()
    old = deepcopy(a["baseline_source_audit"]["raw_registered_gaps"][0])
    old["source_scope"]["snapshot_id"] = "source_snapshot_old"
    old["raw_candidate_id"] = "foreign_raw"
    a["baseline_source_audit"]["raw_registered_gaps"].insert(0, old)
    assert audit(a, b)["original_raw_total"] == 2


@pytest.mark.parametrize("change", [
    lambda a, b: a.update(snapshot_id="stale"),
    lambda a, b: b.update(snapshot_id="stale"),
    lambda a, b: a["baseline_receipts"]["walls"][0].update(scope_complete=False),
    lambda a, b: a["baseline_receipts"]["walls"][0]["records"][0]["source_edge_fragments"][0].update(edge_id="foreign"),
    lambda a, b: a["baseline_receipts"]["walls"][0]["records"][0]["source_edge_fragments"][0].update(source_primitive_ids=["foreign"]),
    lambda a, b: a["baseline_receipts"]["walls"][0]["records"][0]["source_edge_fragments"][0].update(geometry=[0, 0]),
    lambda a, b: a["baseline_source_audit"]["raster_candidate_closure"].update(unresolved_observation_ids=["a"]),
    lambda a, b: a["baseline_source_audit"]["raster_candidate_closure"].update(candidate_universe_complete=True),
    lambda a, b: a["candidate_source_audit"]["raster_candidate_closure"].update(unresolved_candidate_ids=["stale"]),
    lambda a, b: b["cases"][0].update(host_granted=True),
    lambda a, b: a["baseline_receipts"]["hosts"][0].update(host_wall_id="fictional"),
    lambda a, b: a["baseline_receipts"]["canonical"][0].update(snapshot_id="foreign"),
    lambda a, b: a["baseline_receipts"]["walls"][0]["records"][0]["source_edge_fragments"][0].update(geometry=[float("nan"), 0, 2, 0]),
    lambda a, b: b["cases"][0]["source_w4_endpoint_shortlist"].append({"wall_candidate_id": "foreign"}),
])
def test_corrupt_or_unearned_original_provenance_fails_closed(change):
    a, b = inputs()
    change(a, b)
    with pytest.raises((ValueError, KeyError)):
        audit(a, b)


def test_stable_under_original_raw_order_and_host_w4_shortlist_order():
    a, b = inputs()
    expected = audit(a, b)
    a["baseline_source_audit"]["raw_registered_gaps"].reverse()
    a["baseline_source_audit"]["raster_candidate_closure"]["unresolved_candidate_ids"].reverse()
    assert audit(a, b) == expected


def test_duplicate_original_raw_receipt_is_not_overwritten_by_dict():
    a, b = inputs()
    a["baseline_source_audit"]["raw_registered_gaps"].append(
        deepcopy(a["baseline_source_audit"]["raw_registered_gaps"][0]))
    with pytest.raises(ValueError, match="duplicate original raw candidate"):
        audit(a, b)


def test_forged_diagnostic_hostless_physical_id_is_not_source_authority():
    a, b = inputs()
    b["cases"][0]["physical_opening_id"] = "not_an_original_opening"
    with pytest.raises(ValueError, match="originally source-authenticated hostless"):
        audit(a, b)
