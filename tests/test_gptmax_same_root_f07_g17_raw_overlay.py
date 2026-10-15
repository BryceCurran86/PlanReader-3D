"""Same-root G17/F07 source geometry is never physical-opening role authority."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_same_root_f07_g17_original import audited_same_root_raw_view_overlay


def view():
    return {
        "status": "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY",
        "selected_bbox_pt": [10.0, 10.0, 90.0, 90.0],
        "selected_view_id": "source_plan_view_original",
    }


def raw():
    return (
        {"candidate_id":"r1","source_observation_ids":["a","shared"],
         "aperture_bbox_pt":[20,20,40,40]},
        {"candidate_id":"r2","source_observation_ids":["b","shared"],
         "aperture_bbox_pt":[20,101,40,120]},
        {"candidate_id":"r3","source_observation_ids":["z"],
         "aperture_bbox_pt":[8,20,12,40]},
    )


def go(rows=None, v=None):
    r=raw() if rows is None else rows
    return audited_same_root_raw_view_overlay(
        original_unresolved_groups=r,
        closure_ids=tuple(x["candidate_id"] for x in r),
        view_result=view() if v is None else v,
    )


def test_positive_geometry_is_not_physical_type_or_count():
    input_rows=raw()
    before=deepcopy(input_rows)
    r=go(input_rows)
    assert r["status"]=="UNPUBLISHED_SAME_ROOT_F07_G17_RAW_GEOMETRY_AUDIT"
    assert r["raw_unresolved_count"]==3
    assert {x["raw_candidate_id"]:x["source_view_geometric_relation_only"]
            for x in r["source_view_spatial_classifications"]} == {
                "r1":"GEOMETRICALLY_INSIDE_SAME_ROOT_F07",
                "r2":"GEOMETRICALLY_DISJOINT_SAME_ROOT_F07",
                "r3":"INTERSECTS_F07_UNPROVEN_ROLE",
            }
    assert all(not x["source_owned_nonplan_role_proven"]
               and not x["independent_physical_opening_proven"]
               for x in r["source_view_spatial_classifications"])
    assert not r["physical_count_granted"] and not r["typed_nonplan_proven"]
    assert input_rows==before


def test_shared_observations_do_not_create_or_collapse_physical_openings():
    r=go()
    a,b,c=r["source_view_spatial_classifications"]
    assert "shared" in a["source_observation_ids"]
    assert "shared" in b["source_observation_ids"]
    assert a["raw_candidate_id"] != b["raw_candidate_id"]
    assert not r["physical_count_granted"]


def test_permutation_invariant_original_root_source_candidates():
    r=raw()
    assert go(r)["source_view_spatial_classifications"] == go(r[::-1])["source_view_spatial_classifications"]


def test_missing_or_competing_source_owned_plan_view_fails_closed():
    v=view();v["status"]="ABSTAIN"
    r=go(v=v)
    assert r["status"]=="ABSTAIN_ORIGINAL_SOURCE_F07_UNPROVEN"
    assert r["source_view_spatial_classifications"]==[]
    assert not r["physical_count_granted"]


def test_original_closure_set_mismatch_rejected():
    with pytest.raises(ValueError,match="inventory"):
        audited_same_root_raw_view_overlay(
            original_unresolved_groups=raw(),
            closure_ids=("r1","r2"),
            view_result=view())


@pytest.mark.parametrize("mutate",[
    lambda rows:rows[0].update(aperture_bbox_pt=[20,20,20,40]),
    lambda rows:rows[0].update(aperture_bbox_pt=[20,20,float("nan"),40]),
    lambda rows:rows[0].update(aperture_bbox_pt=None),
    lambda rows:rows[0].update(source_observation_ids=["a","a"]),
    lambda rows:rows[0].update(source_observation_ids=[]),
    lambda rows:rows[0].update(candidate_id="r2"),
])
def test_invalid_original_raster_source_receipts_fail_closed(mutate):
    rows=[deepcopy(x) for x in raw()]
    mutate(rows)
    with pytest.raises(ValueError):
        audited_same_root_raw_view_overlay(
            original_unresolved_groups=tuple(rows),
            closure_ids=("r1","r2","r3"),
            view_result=view())


def test_invalid_original_f07_geometry_fails_closed():
    v=view();v["selected_bbox_pt"]=[20,10,float("inf"),90]
    with pytest.raises(ValueError,match="F07"):
        go(v=v)
