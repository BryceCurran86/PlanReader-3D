"""Original eight signed output proof cannot be a numeric row-only claim."""
from copy import deepcopy
import pytest

from tools.diag_gptmax_unmeasured_flank_capture_shadow import (
    _original_eight_firm_customer_retention,
    compare_original_g17_release_receipts,
)


def records():
    q=[{"quantity_id":f"old-signed-q-{i}","area_m2":1.8,
        "issuer_snapshot":"same-original"} for i in range(8)]
    return dict(
        walls=[{"decision_scope_id":"wall-source:page-3","snapshot_id":"s1",
                "records":[{"wall_candidate_id":"w1","source_primitive_ids":["left"]}]}],
        hosts=[{"opening_identity_id":"physical-1","record_id":"host-original"}],
        frames=[{"opening_identity_id":"physical-1","record_id":"frame-original"}],
        canonical=[{"canonical_opening_id":"canonical-1","area_m2":1.8}],
        quantities=q, customer_rows=deepcopy(q),
        sealed_run={"signature":"complete-original-eight"},
        customer_verification={"valid":True,"issuer":"original"},
    )


def compare(a,b):
    return _original_eight_firm_customer_retention(
        a,b,compare_original_g17_release_receipts(a,b))


def test_all_eight_with_exact_old_original_customer_and_w4_retain():
    a=records()
    assert compare(a,deepcopy(a))


def test_numeric_areas_equal_but_source_identity_rekey_fails():
    a=records();b=deepcopy(a)
    b["quantities"][0]["issuer_snapshot"]="reissued"
    assert not compare(a,b)


@pytest.mark.parametrize("section,field,value",[
    ("walls","snapshot_id","reissued-w4"),
    ("hosts","record_id","borrowed-neighbour-host"),
    ("frames","record_id","new-unsourced-frame"),
    ("canonical","canonical_opening_id","changed-canonical"), 
    ("sealed_run","signature","different-original-customer-seal"),
    ("customer_verification","issuer","different-attestation"),
])
def test_customer_or_source_receipt_churn_never_claims_old_eight(section,field,value):
    a=records();b=deepcopy(a)
    if isinstance(b[section],list):
        b[section][0][field]=value
    else:
        b[section][field]=value
    assert not compare(a,b)


def test_cannot_claim_eight_if_fewer_original_signed_receipts_exist():
    a=records();a["quantities"].pop()
    b=deepcopy(a)
    assert not compare(a,b)


def test_added_new_quantity_does_not_erase_original_but_is_not_firm_authority():
    a=records();b=deepcopy(a)
    b["quantities"].append({"quantity_id":"new-potential-2127",
                            "area_m2":5.67})
    assert compare(a,b)
    p=compare_original_g17_release_receipts(a,b)
    assert not p["new_gpt1_metric_authority_granted"]
    assert not p["new_benchmark_match_granted"]
