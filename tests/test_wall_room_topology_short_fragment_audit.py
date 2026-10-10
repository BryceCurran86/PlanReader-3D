"""Proof-aware W2 short source fragment audit: zero geometry authority."""
from copy import deepcopy
import math
import pytest

from pb_wall_room_topology_short_fragment_audit import audit_short_source_fragments


def fragment(fid="split_1", coords=(10.,10.,11.22,10.), *, parent=None):
    if parent is None:
        parent=(10.,10.,30.,10.)
    primitive_id="raster_segment:real-source-sha:1.0.0:1585"
    return {
        "id":fid,
        "x1":coords[0],"y1":coords[1],
        "x2":coords[2],"y2":coords[3],
        "primitive_lineage":{
            "source_primitive_ids":[primitive_id],
            "source_records":[{
                "id":primitive_id,"page_coords_present":True,
                "x1":parent[0],"y1":parent[1],
                "x2":parent[2],"y2":parent[3],
            }],
        },
    }


def graph(fid="split_1", *, a=(10.,10.), b=(11.22,10.), raw=True, merged=False):
    snapped={
        "nodes":[{"id":0,"x":a[0],"y":a[1]},
                 {"id":1,"x":b[0],"y":b[1]}],
        "edges":[{"id":fid,"a":0,"b":1}] if raw else [],
    }
    merged_graph={"edges":[
        {"id":"merged_split_1_split_2",
         "collinear_merge_leaf_edge_ids":[fid,"split_2"]}
    ]} if merged else {"edges":[{"id":fid}]} if raw else {"edges":[]}
    return snapped, merged_graph


def audit(fragments, snapped, merged):
    return audit_short_source_fragments(fragments,snapped,merged,max_length_pt=2.5)


def test_positive_source_one_point_two_two_fragment_retained_without_mutation():
    f=fragment()
    s,m=graph()
    original=deepcopy((f,s,m))
    result=audit([f],s,m)
    assert result["w2_retention_reason_counts"]=={"RETAINED_RAW_EDGE":1}
    assert result["original_positive_source_short_fragments"][0]["original_source_length_pt"]==pytest.approx(1.22)
    assert result["original_positive_source_short_fragments"][0]["max_endpoint_snap_displacement_pt"]==0
    assert (f,s,m)==original
    assert not result["physical_host_publication_allowed"]
    assert not result["opening_count_publication_allowed"]
    assert result["benchmark_accuracy"] is None


def test_true_w2_snap_collapse_retains_source_proof_but_never_restores_edge():
    f=fragment(coords=(10.,10.,11.9,10.))
    s,m=graph(raw=False)
    result=audit([f],s,m)
    assert result["w2_retention_reason_counts"]=={"SNAP_COLLAPSED":1}
    witness=result["original_positive_source_short_fragments"][0]
    assert witness["max_endpoint_snap_displacement_pt"] is None
    assert witness["original_source_geometry_pt"]==[10.,10.,11.9,10.]
    assert witness["wall_host_authority"]=="NOT_PROVEN_BY_THIS_AUDIT"
    assert not s["edges"]


def test_source_fragment_collinear_merge_keeps_exact_leaf_ancestry():
    f=fragment()
    s,m=graph(merged=True)
    r=audit([f],s,m)
    assert r["w2_retention_reason_counts"]=={"COLLINEAR_MERGED":1}


def test_displaced_source_endpoints_are_observed_not_snapped_again():
    f=fragment()
    s,m=graph(a=(10.3,10.),b=(11.22,10.))
    original=deepcopy(s)
    r=audit([f],s,m)
    assert r["original_positive_source_short_fragments"][0][
        "max_endpoint_snap_displacement_pt"]==pytest.approx(.3)
    assert s==original


@pytest.mark.parametrize("change", [
    "unknown_parent", "multi_parent","different_parent","false_source_page",
    "uncorroborated_short_gap","source_off_axis","wrong_parent_end",
])
def test_missing_or_conflicting_source_parent_cannot_become_host_witness(change):
    f=fragment()
    lin=f["primitive_lineage"]
    if change=="unknown_parent": lin["source_records"]=[]
    elif change=="multi_parent":
        lin["source_primitive_ids"].append("unrelated-positive-parent")
    elif change=="different_parent":
        lin["source_records"][0]["id"]="unrelated"
    elif change=="false_source_page":
        lin["source_records"][0]["page_coords_present"]=False
    elif change=="uncorroborated_short_gap":
        lin["source_primitive_ids"]=[]
    elif change=="source_off_axis":
        lin["source_records"][0]["y1"]=11.
    else:
        lin["source_records"][0]["x2"]=10.5
    s,m=graph()
    result=audit([f],s,m)
    assert result["observed_positive_source_short_fragment_count"]==0
    assert result["w2_retention_reason_counts"]=={"UNPROVEN_SOURCE_PARENT_SKIPPED":1}
    assert not result["physical_host_publication_allowed"]


@pytest.mark.parametrize("bad", [
    float("nan"),float("inf"),0.,-1.,True,None,
])
def test_invalid_observation_length_fails_closed(bad):
    s,m=graph()
    with pytest.raises(ValueError):
        audit_short_source_fragments([fragment()],s,m,max_length_pt=bad)


@pytest.mark.parametrize("change",["duplicate_id","nonfinite","missing_geometry","invalid_final_leaf","snap_missing_node","collapsed_reappears_as_merge"])
def test_corrupted_w2_inventory_fails_closed(change):
    f=fragment()
    s,m=graph()
    inventory=[f]
    if change=="duplicate_id":
        inventory.append(deepcopy(f))
    elif change=="nonfinite":
        f["x1"]=float("nan")
    elif change=="missing_geometry":
        del f["x1"]
    elif change=="invalid_final_leaf":
        m["edges"][0]["collinear_merge_leaf_edge_ids"]=[None]
    elif change=="snap_missing_node":
        s["nodes"].pop()
    else:
        s["edges"]=[]
        m["edges"][0]["collinear_merge_leaf_edge_ids"]=[f["id"]]
    with pytest.raises(ValueError):
        audit(inventory,s,m)


def test_full_length_original_line_does_not_claim_short_fragment_authority():
    f=fragment(coords=(10.,10.,20.,10.))
    s,m=graph()
    result=audit([f],s,m)
    assert result["original_positive_source_short_fragments"]==[]
    assert result["observed_positive_source_short_fragment_count"]==0


def test_real_short_vertical_end_remains_observation_not_missing_gap_closure():
    f=fragment("split_324",(582.6,531.25,584.5,531.25),parent=(500.,531.25,584.5,531.25))
    s,m=graph("split_324",a=(582.6,531.25),b=(582.8,531.25))
    r=audit([f],s,m)
    assert r["observed_positive_source_short_fragment_count"]==1
    w=r["original_positive_source_short_fragments"][0]
    assert w["max_endpoint_snap_displacement_pt"]==pytest.approx(1.7)
    assert w["source_gap_closure"]=="NOT_PROVEN_BY_THIS_AUDIT"
    assert not r["metric_quantity_publication_allowed"]
