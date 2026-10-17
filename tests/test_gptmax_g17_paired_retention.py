"""Strict original issuer and signed customer comparison; no inferred rekey."""
from copy import deepcopy
import pytest
from tools.diag_gptmax_unmeasured_flank_capture_shadow import (
    compare_original_g17_release_receipts,
)

def receipt():
    return {
        "hosts":[{"opening_identity_id":"p1","record_id":"h1","member_wall_candidate_ids":["w1"]},
                 {"opening_identity_id":"p2","record_id":None,"reason_codes":["no-wall"]}],
        "frames":[{"opening_identity_id":"p1","record_id":"f1"}],
        "canonical":[{"canonical_opening_id":"p1","area_m2":1.8}],
        "quantities":[{"quantity_id":"q1","fingerprint":"fp","trace_evidence_ids":["e1"]}],
        "sealed_run":{"fingerprint":"original","customer_run_id":"run1"},
        "customer_rows":[{"quantity_id":"q1","fingerprint":"old"}],
        "customer_verification":{"valid":True},
    }

def test_exact_source_customer_parity_is_only_strict_positive():
    a=receipt()
    p=compare_original_g17_release_receipts(a,deepcopy(a))
    assert p["all_original_issuer_receipts_exact"]
    assert not p["new_host_or_frame_authority_granted"]

@pytest.mark.parametrize("section,field,value",[
    ("hosts","record_id","new-host"),
    ("hosts","member_wall_candidate_ids",["borrowed"]),
    ("frames","record_id","new-frame"),
    ("canonical","area_m2",2.16),
    ("quantities","fingerprint","new-fingerprint"),
    ("quantities","trace_evidence_ids",["changed-issuer"]),
    ("customer_rows","fingerprint","new-customer"),
])
def test_changed_original_identity_must_be_reported(section,field,value):
    a=receipt(); b=deepcopy(a); b[section][0][field]=value
    p=compare_original_g17_release_receipts(a,b)
    assert not p["all_original_issuer_receipts_exact"]
    assert not p["signed_snapshot_rekey_approved"]

def test_old_abstained_identity_cannot_disappear():
    a=receipt(); b=deepcopy(a); b["hosts"].pop()
    p=compare_original_g17_release_receipts(a,b)
    assert p["original_authority"]["hosts"]["lost_original_ids"]==["p2"]
    assert not p["all_original_issuer_receipts_exact"]

def test_new_source_identity_does_not_grant_new_host():
    a=receipt(); b=deepcopy(a)
    b["hosts"].append({"opening_identity_id":"p3","record_id":"h3"})
    p=compare_original_g17_release_receipts(a,b)
    assert p["original_authority"]["hosts"]["new_ids"]==["p3"]
    assert not p["new_host_or_frame_authority_granted"]

@pytest.mark.parametrize("section",["hosts","frames","canonical","quantities"])
def test_duplicate_original_issuer_fails_closed(section):
    a=receipt(); a[section].append(deepcopy(a[section][0]))
    with pytest.raises(ValueError,match="duplicate"):
        compare_original_g17_release_receipts(a,receipt())
