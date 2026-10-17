"""Strict original issuer and signed customer comparison; no inferred rekey."""
from copy import deepcopy
import pytest
from tools.diag_gptmax_unmeasured_flank_capture_shadow import (
    compare_original_g17_release_receipts,
)

def receipt():
    return {
        "walls":[{"decision_scope_id":"wall-source:page-3",
                  "snapshot_id":"first-issuer",
                  "records":[{"wall_candidate_id":"wall-1",
                              "original_source_ids":["a","b"]}],
                  "scope_complete":True,
                  "equivalence":{"pair_classifications":[["w1","w2","AMBIGUOUS"]]}},
                {"decision_scope_id":"wall-source:viewport:3:origin",
                  "records":[{"wall_candidate_id":"wall-viewport-1"}],
                  "scope_complete":True}],
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


def test_paired_origins_use_exact_same_source_locator_and_page(monkeypatch):
    # No source authority may be compared across different input locators.
    # The only intended experiment variable is the alternative G17 policy.
    import tools.diag_gptmax_unmeasured_flank_capture_shadow as module

    class Captured(Exception):
        pass

    receipts=[]
    class Producer:
        def __init__(self, **kwargs):
            pass
        def ingest_native_pdf_bytes(self, **kwargs):
            receipts.append(kwargs)
            raise Captured()

    monkeypatch.setattr(module, "SourceVisibilityProducer", Producer)
    for changed in (False,True):
        with pytest.raises(Captured):
            module._one_source_policy(b"one-original", "a"*64, shadow=changed)
    assert len(receipts)==2
    assert receipts[0] == receipts[1]
    assert receipts[0]["page_ids"] == (3,)
    assert receipts[0]["source_locator"] == "memory://gptmax-original-lot16-page-3.pdf"


def test_original_page_w4_issuer_change_alone_blocks_retention():
    a=receipt()
    b=deepcopy(a)
    b["walls"][0]["records"][0]["original_source_ids"]=["other"]
    p=compare_original_g17_release_receipts(a,b)
    assert not p["all_original_issuer_receipts_exact"]
    assert p["original_authority"]["walls"]["changed_original_ids"]==[
        "wall-source:page-3"]
    assert not p["new_host_or_frame_authority_granted"]


def test_original_w4_equivalence_change_blocks_even_with_old_customer_rows():
    a=receipt()
    b=deepcopy(a)
    b["walls"][0]["equivalence"]["pair_classifications"]=[["w1","w2","SAME"]]
    p=compare_original_g17_release_receipts(a,b)
    assert p["signed_customer_exact"]["customer_rows"]
    assert not p["all_original_issuer_receipts_exact"]


def test_original_f07_scope_cannot_disappear_without_a_release_flag():
    a=receipt()
    b=deepcopy(a)
    b["walls"].pop()
    p=compare_original_g17_release_receipts(a,b)
    assert p["original_authority"]["walls"]["lost_original_ids"]==[
        "wall-source:viewport:3:origin"]
    assert not p["all_original_issuer_receipts_exact"]


def test_new_shadow_w4_scope_never_waives_original_scope_parity():
    a=receipt()
    b=deepcopy(a)
    b["walls"].append({"decision_scope_id":"wall-source:shadow:3",
                       "scope_complete":False, "records":[{"wall_candidate_id":"new"}]})
    p=compare_original_g17_release_receipts(a,b)
    assert p["original_authority"]["walls"]["new_ids"]==["wall-source:shadow:3"]
    assert p["original_authority"]["walls"]["original_exact"]
    assert not p["new_host_or_frame_authority_granted"]
