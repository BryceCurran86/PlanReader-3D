"""Adverse source-owned candidate bijection proofs, never opening count grants."""
from __future__ import annotations

from copy import deepcopy
import pytest

from tools.verify_gptmax_raw_source_group_retention import (
    verify_raw_source_candidate_group_retention as verify,
)

SHA="1"*64


def _case():
    def stage(snapshot):
        return {
            "source_sha256": SHA,
            "primitive_safety_cap": 20_000,
            "snapshot_id": snapshot,
            "native_candidate_closures": [{
                "page_id": "3", "status": "corroborated",
                "raw_candidate_count": 3, "resolved_candidate_count": 1,
                "candidate_universe_complete": False,
                "unresolved_candidate_ids": ["native-"+snapshot+"-a", "native-"+snapshot+"-b"],
                "unresolved_observation_ids": ["obs-a", "obs-b", "obs-c", "obs-d"],
                "reason_codes": ["physical_opening_candidate_closure_unresolved"],
            }],
            "raster_candidate_closures": [{
                "page_id": "3", "status": "corroborated",
                "raw_candidate_count": 4, "resolved_candidate_count": 2,
                "candidate_universe_complete": False,
                "unresolved_candidate_ids": ["raster-"+snapshot+"-a", "raster-"+snapshot+"-b"],
                "unresolved_observation_ids": ["obs-ra", "obs-rb", "obs-rc"],
                "reason_codes": ["physical_opening_candidate_closure_unresolved"],
            }],
            "unresolved_candidate_source_groups": {
                "native": [{"page_id":"3", "groups":[
                    {"candidate_id":"native-"+snapshot+"-a","source_observation_ids":["obs-a","obs-b"],
                     "aperture_bbox_pt":None,"candidate_status":"unresolved_source_only",
                     "structural_pattern":"wall_gap_candidate"},
                    {"candidate_id":"native-"+snapshot+"-b","source_observation_ids":["obs-c","obs-d"],
                     "aperture_bbox_pt":None,"candidate_status":"unresolved_source_only",
                     "structural_pattern":"door_jamb_leaf_candidate"},
                ]}],
                "raster": [{"page_id":"3","groups":[
                    {"candidate_id":"raster-"+snapshot+"-a","source_observation_ids":["obs-ra","obs-rb"],
                     "aperture_bbox_pt":[1.0,2.0,3.0,4.0],
                     "candidate_status":"unresolved_source_only",
                     "structural_pattern":"raster_gap_candidate"},
                    {"candidate_id":"raster-"+snapshot+"-b","source_observation_ids":["obs-rb","obs-rc"],
                     "aperture_bbox_pt":[5.0,6.0,7.0,8.0],
                     "candidate_status":"unresolved_source_only",
                     "structural_pattern":"raster_gap_candidate"},
                ]}],
            },
        }
    return stage("old"),stage("new")


def test_opaque_snapshot_id_rekey_accepted_only_when_each_real_group_identical():
    old,new=_case()
    original=deepcopy((old,new))
    result=verify(old,new)
    assert result["verified_raw_source_membership"]
    assert result["native_unresolved_groups"]==2
    assert result["raster_unresolved_groups"]==2
    assert result["physical_hosts_granted"]==0
    assert result["opening_counts_granted"]==0
    assert result["benchmark_matches_claimed"]==0
    assert (old,new)==original


@pytest.mark.parametrize("corruption",[
    "source", "safety", "same_snapshot", "missing_native", "missing_raster",
    "wrong_candidate_owner", "different_observation", "different_pattern",
    "different_raster_aperture", "unowned_observation", "invented_height",
    "promoted_candidate", "completed_universe", "changed_raw_count",
    "changed_opening_status", "duplicate_source_group", "unknown_page",
])
def test_every_unproven_original_raw_candidate_source_change_is_refused(corruption):
    old,new=_case()
    if corruption=="source": new["source_sha256"]="2"*64
    if corruption=="safety": new["primitive_safety_cap"]=20001
    if corruption=="same_snapshot": new["snapshot_id"]="old"
    if corruption=="missing_native": del new["unresolved_candidate_source_groups"]["native"]
    if corruption=="missing_raster": del new["unresolved_candidate_source_groups"]["raster"]
    if corruption=="wrong_candidate_owner":
        new["unresolved_candidate_source_groups"]["native"][0]["groups"][0]["candidate_id"]="incorrect"
    if corruption=="different_observation":
        new["unresolved_candidate_source_groups"]["native"][0]["groups"][0]["source_observation_ids"]=["obs-a","obs-c"]
    if corruption=="different_pattern":
        new["unresolved_candidate_source_groups"]["native"][0]["groups"][0]["structural_pattern"]="window_jamb_pair_candidate"
    if corruption=="different_raster_aperture":
        new["unresolved_candidate_source_groups"]["raster"][0]["groups"][0]["aperture_bbox_pt"]=[1.,2.,3.,4.1]
    if corruption=="unowned_observation":
        new["unresolved_candidate_source_groups"]["raster"][0]["groups"][0]["source_observation_ids"]=["obs-ra","unknown"]
    if corruption=="invented_height":
        new["unresolved_candidate_source_groups"]["raster"][0]["groups"][0]["aperture_bbox_pt"]=[1.,2.,3.,4.,2040.]
    if corruption=="promoted_candidate":
        new["unresolved_candidate_source_groups"]["native"][0]["groups"][0]["candidate_status"]="firm"
    if corruption=="completed_universe":
        new["native_candidate_closures"][0]["candidate_universe_complete"]=True
    if corruption=="changed_raw_count":
        new["raster_candidate_closures"][0]["raw_candidate_count"]+=1
    if corruption=="changed_opening_status":
        new["native_candidate_closures"][0]["status"]="conflict"
    if corruption=="duplicate_source_group":
        new["unresolved_candidate_source_groups"]["native"][0]["groups"][1].update(
            source_observation_ids=["obs-a","obs-b"],structural_pattern="wall_gap_candidate")
    if corruption=="unknown_page":
        new["unresolved_candidate_source_groups"]["native"][0]["page_id"]="4"
    with pytest.raises(ValueError,match="raw source candidate group retention refused"):
        verify(old,new)
