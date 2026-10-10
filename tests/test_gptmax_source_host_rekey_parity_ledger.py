"""Source-vs-snapshot host identity audit; never approves rekeyed receipts."""
from copy import deepcopy
import pytest

from tools.gptmax_source_host_rekey_parity_ledger import compare_source_host_rekeys


def report():
    oid="physical_opening_existence_abc"
    wid="wall_a"
    return {
        "source_sha256":"a"*64,
        "selected_geometry_page_ids":["3"],
        "primitive_safety_cap":20_000,
        "opening_bindings":[{
            "opening_identity_id":oid, "page_id":"3", "status":"corroborated",
            "host_wall_id":"group_old", "record_id":"host_receipt_old",
            "member_wall_candidate_ids":[wid],
            "reason_codes":["opening_host_binding_resolved","raster_whole_wall_host_resolved"],
        }],
        "host_frames":[{
            "opening_identity_id":oid, "host_wall_id":"group_old",
            "record_id":"frame_receipt_old",
            "reason_codes":["opening_host_frame_resolved"],
        }],
        "resolved_host_frame_evidence":[{
            "opening_identity_id":oid,
            "record_id":"frame_receipt_old",
            "whole_wall_frame_id":"old_snapshot_frame",
            "host_wall_id":"group_old",
            "host_binding_record_id":"host_receipt_old",
            "selector":{"snapshot_id":"old_snapshot"},
            "origin_pt":[10.5,10.],"axis_unit":[1.,0.],"normal_unit":[0.,1.],
            "whole_wall_length_pt":60.,"whole_wall_candidate_ids":[wid],
            "wall_thickness_pt":4.,
        }],
        "source_owned_wall_scope_results":[{
            "source_sha256":"a"*64,
            "page_id":"3","status":"corroborated","scope_complete":True,
            "records":[{
                "wall_candidate_id":wid,
                "physical_identity":{
                    "candidate_identity_id":"wall2_same_source_and_path",
                    "status":"corroborated","blocking_reasons":[],
                    "source_primitive_ids":["raster_segment:source:1.0.0:123"],
                    "path_fingerprint":[[10.,10.],[70.,10.]],
                    "edge_ids":["split_1"],
                },
                "wall_candidate":{
                    "centerline_pts":[[10.,10.],[70.,10.]],
                    "reason_codes":["source_proven"],
                    "representation":"single_line","status":"candidate",
                    "end_node_ids":["old_node_1","old_node_2"],
                    "face_a_segment_ids":["split_1"],
                },
                "source_edge_fragments":[{
                    "edge_id":"split_1","geometry":[10.,10.,70.,10.],
                    "source_primitive_ids":["raster_segment:source:1.0.0:123"],
                }],
            }],
        }],
    }


def rekey():
    before=report()
    after=deepcopy(before)
    after["opening_bindings"][0].update(
        host_wall_id="group_new",record_id="host_receipt_new")
    after["host_frames"][0].update(
        host_wall_id="group_new",record_id="frame_receipt_new")
    after["resolved_host_frame_evidence"][0].update(
        host_wall_id="group_new",
        record_id="frame_receipt_new",
        whole_wall_frame_id="new_snapshot_frame",
        host_binding_record_id="host_receipt_new",
        selector={"snapshot_id":"new_snapshot"},
    )
    # The W2 splitter's sequence number changes when valid independent
    # primitives are added. Its actual source path/parent remain identical.
    r=after["source_owned_wall_scope_results"][0]["records"][0]
    r["physical_identity"]["edge_ids"]=["split_999"]
    r["source_edge_fragments"][0]["edge_id"]="split_999"
    r["wall_candidate"]["end_node_ids"]=["junction_10","junction_20"]
    r["wall_candidate"]["face_a_segment_ids"]=["split_999"]
    return before,after


def test_actual_source_rekey_pattern_is_unapproved_even_with_same_v2_wall():
    before,after=rekey()
    original=deepcopy((before,after))
    r=compare_source_host_rekeys(before,after)
    assert r["rekey_classification_counts"]=={
        "UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY":1
    }
    assert r["source_comparison_rows"][0]["reason_codes"]==[
        "PRIOR_RECEIPT_IDENTITY_REKEY_UNAPPROVED"
    ]
    assert not r["official_host_receipt_identity_acceptance"]
    assert not r["opening_count_or_metric_publication_allowed"]
    assert r["benchmark_accuracy"] is None
    assert (before,after)==original


def test_exact_source_and_receipts_retained():
    x=report()
    r=compare_source_host_rekeys(x,deepcopy(x))
    assert r["rekey_classification_counts"]=={"EXACT_PRIOR_RECEIPTS_RETAINED":1}
    assert r["official_host_receipt_identity_acceptance"] is False


@pytest.mark.parametrize("damage",[
    "member_change","source_v2_change","source_original_primitive_change",
    "source_path_change","source_fragment_geom_change",
    "wall_centerline_change","host_unavailable","frame_unavailable",
    "frame_geom_change","host_reason_change","frame_reason_change",
])
def test_changed_or_missing_positive_original_source_never_called_snapshot_only(damage):
    a,b=rekey()
    opening=b["opening_bindings"][0]
    frames=b["host_frames"][0]
    record=b["source_owned_wall_scope_results"][0]["records"][0]
    if damage=="member_change":
        opening["member_wall_candidate_ids"]=["wall_b"]
    elif damage=="source_v2_change":
        record["physical_identity"]["candidate_identity_id"]="wall2_different"
    elif damage=="source_original_primitive_change":
        record["physical_identity"]["source_primitive_ids"]=["different"]
    elif damage=="source_path_change":
        record["physical_identity"]["path_fingerprint"]=[[10.,10.],[69.,10.]]
    elif damage=="source_fragment_geom_change":
        record["source_edge_fragments"][0]["geometry"]=[10.,10.,69.,10.]
    elif damage=="wall_centerline_change":
        record["wall_candidate"]["centerline_pts"]=[[10.,10.],[69.,10.]]
    elif damage=="host_unavailable":
        opening.update(host_wall_id=None,record_id=None)
    elif damage=="frame_unavailable":
        frames["record_id"]=None
    elif damage=="frame_geom_change":
        b["resolved_host_frame_evidence"][0]["whole_wall_length_pt"]=59.
    elif damage=="host_reason_change":
        opening["reason_codes"]=["new_host_reason"]
    else:
        frames["reason_codes"]=["opening_host_frame_rekey"]
    r=compare_source_host_rekeys(a,b)
    assert r["rekey_classification_counts"]=={
        "ORIGINAL_SOURCE_PROOF_CHANGED_OR_LOST":1
    }
    assert not r["official_host_receipt_identity_acceptance"]


@pytest.mark.parametrize("damage",[
    "other_source_sha","other_page","wrong_cap","missing_scope",
    "uncorroborated_scope","partial_wall_scope","duplicate_physical",
    "missing_frame_owner","duplicate_W4_wall","missing_original_opening",
    "unverified_source_sha",
])
def test_untrustworthy_original_source_reports_fail_closed(damage):
    a,b=rekey()
    if damage=="other_source_sha":
        b["source_sha256"]="b"*64
        b["source_owned_wall_scope_results"][0]["source_sha256"]="b"*64
    elif damage=="other_page": b["selected_geometry_page_ids"]=["4"]
    elif damage=="wrong_cap": b["primitive_safety_cap"]=20_001
    elif damage=="missing_scope": b["source_owned_wall_scope_results"]=[]
    elif damage=="uncorroborated_scope":
        b["source_owned_wall_scope_results"][0]["status"]="abstained"
    elif damage=="partial_wall_scope":
        b["source_owned_wall_scope_results"][0]["scope_complete"]=False
    elif damage=="duplicate_physical":
        b["opening_bindings"].append(deepcopy(b["opening_bindings"][0]))
    elif damage=="missing_frame_owner": b["host_frames"]=[]
    elif damage=="duplicate_W4_wall":
        b["source_owned_wall_scope_results"][0]["records"].append(
            deepcopy(b["source_owned_wall_scope_results"][0]["records"][0]))
    elif damage=="missing_original_opening": b["opening_bindings"]=[]
    else: b["source_sha256"]="not_sha"
    with pytest.raises(ValueError):
        compare_source_host_rekeys(a,b)


def test_real_production_unframed_original_is_not_upgraded_to_metric_frame():
    a,b=rekey()
    a["host_frames"][0].update(record_id=None, reason_codes=["whole_wall_unproven"])
    b["host_frames"][0].update(record_id=None, reason_codes=["whole_wall_unproven"])
    a["resolved_host_frame_evidence"]=[]
    b["resolved_host_frame_evidence"]=[]
    out=compare_source_host_rekeys(a,b)
    assert out["rekey_classification_counts"]=={
        "UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY":1
    }
    assert out["source_comparison_rows"][0]["commercial_publication_permission"]=="NOT_ESTABLISHED"


def test_newly_authenticated_source_host_is_not_prior_receipt_equivalence():
    a,b=rekey()
    a["opening_bindings"][0].update(host_wall_id=None,record_id=None,
        member_wall_candidate_ids=[],
        reason_codes=["no_authenticated_host_wall_band"])
    a["host_frames"][0].update(record_id=None,reason_codes=["host_unavailable"])
    a["resolved_host_frame_evidence"]=[]
    out=compare_source_host_rekeys(a,b)
    assert out["source_comparison_rows"]==[]
    assert out["prior_authenticated_host_count"]==0
    assert out["candidate_authenticated_host_count"]==1
