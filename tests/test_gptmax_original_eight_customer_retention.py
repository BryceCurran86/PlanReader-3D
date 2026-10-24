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
        customer_verification={
            "project_id":"original-source-retention",
            "sealed_quantity_count":8,
            "valid_quantity_count":8,
            "abstained_quantity_count":0,
            "customer_row_count":8,
            "verified_quantity_ids":[f"old-signed-q-{i}" for i in range(8)],
            "issuer":"original",
        },
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


@pytest.mark.parametrize("section,mutation", [
    ("verified_quantity_ids",lambda v:v[:-1]),
    ("verified_quantity_ids",lambda v:v[:-1]+["unapproved-extra"]),
    ("valid_quantity_count",lambda v:7),
    ("customer_row_count",lambda v:7),
    ("verified_quantity_ids",lambda v:["old-signed-q-0"]*8),
])
def test_equal_invalid_customer_verifier_cannot_claim_eight(section,mutation):
    a=records()
    a["customer_verification"][section]=mutation(
        a["customer_verification"][section])
    assert not compare(a,deepcopy(a))


def test_missing_verified_quantity_ids_fails_even_with_signed_area_values():
    a=records()
    del a["customer_verification"]["verified_quantity_ids"]
    assert not compare(a,deepcopy(a))


def test_correct_bijection_order_changes_only_when_both_receipts_agree():
    a=records()
    b=deepcopy(a)
    a["customer_verification"]["verified_quantity_ids"].reverse()
    b["customer_verification"]["verified_quantity_ids"].reverse()
    assert compare(a,b)
