"""Source-face parity must fail even when aggregate host/frame counts rise."""
from copy import deepcopy

import pytest

from tools.gptmax_compare_source_face_retention import compare_source_face_reports


def source_report():
    return {
        "source_sha256": "1" * 64,
        "selected_geometry_page_ids": ["3"],
        "primitive_safety_cap": 20000,
        "opening_bindings": [
            {"opening_identity_id": "physical-1", "host_wall_id": "host-1",
             "record_id": "host-receipt-1", "reason_codes": []},
            {"opening_identity_id": "physical-2", "host_wall_id": None,
             "record_id": None, "reason_codes": ["unavailable"]},
        ],
        "host_frames": [
            {"opening_identity_id": "physical-1", "record_id": "frame-1", "reason_codes": []},
            {"opening_identity_id": "physical-2", "record_id": None, "reason_codes": []},
        ],
    }


def test_exact_parity_retains_source_and_no_publication():
    old=source_report()
    new=deepcopy(old)
    new["opening_bindings"].reverse()
    new["host_frames"].reverse()
    r=compare_source_face_reports(old,new)
    assert r["retention_pass"]
    assert r["count_summary"]["baseline_hosts"] == 1
    assert r["count_summary"]["candidate_frames"] == 1
    assert r["benchmark_accuracy"] is None
    assert r["quantity_publication_permitted"] is False


def test_new_host_frame_may_not_cancel_existing_proof_loss():
    old,new=source_report(),source_report()
    new["opening_bindings"][0].update(host_wall_id=None,record_id=None)
    new["host_frames"][0]["record_id"] = None
    new["opening_bindings"][1].update(host_wall_id="new-host",record_id="new-host-receipt")
    new["host_frames"][1]["record_id"] = "new-frame"
    r=compare_source_face_reports(old,new)
    assert not r["retention_pass"]
    assert r["count_summary"]["baseline_hosts"] == r["count_summary"]["candidate_hosts"]
    assert r["count_summary"]["baseline_frames"] == r["count_summary"]["candidate_frames"]
    assert len(r["lost_proof_records"]) == 1
    assert len(r["new_proof_records"]) == 1


@pytest.mark.parametrize("kind", ["host_rekey","host_receipt_rekey","frame_receipt_rekey"])
def test_host_or_frame_owner_rekey_is_not_silent(kind):
    old,new=source_report(),source_report()
    if kind == "host_rekey": new["opening_bindings"][0]["host_wall_id"] = "other"
    elif kind == "host_receipt_rekey": new["opening_bindings"][0]["record_id"] = "other"
    else: new["host_frames"][0]["record_id"] = "other"
    r=compare_source_face_reports(old,new)
    assert not r["retention_pass"]
    assert r["changed_proof_records_needing_review"]


@pytest.mark.parametrize("damage",[
    "source_sha","page","cap","duplicate_physical","duplicate_frame",
    "missing_frame","ambiguous_shape","missing_frames","missing_bindings",
])
def test_incompatible_producer_reports_fail_closed(damage):
    old,new=source_report(),source_report()
    if damage == "source_sha": new["source_sha256"] = "2"*64
    elif damage == "page": new["selected_geometry_page_ids"] = ["4"]
    elif damage == "cap": new["primitive_safety_cap"] = 20001
    elif damage == "duplicate_physical": new["opening_bindings"].append(deepcopy(new["opening_bindings"][0]))
    elif damage == "duplicate_frame": new["host_frames"].append(deepcopy(new["host_frames"][0]))
    elif damage == "missing_frame": new["host_frames"].pop()
    elif damage == "ambiguous_shape": new["host_frame_traces"] = []
    elif damage == "missing_frames": del new["host_frames"]
    else: del new["opening_bindings"]
    with pytest.raises(ValueError):
        compare_source_face_reports(old,new)


def test_physical_opening_identity_loss_fails_despite_replacement():
    old,new=source_report(),source_report()
    new["opening_bindings"][0]["opening_identity_id"]="physical-3"
    new["host_frames"][0]["opening_identity_id"]="physical-3"
    r=compare_source_face_reports(old,new)
    assert not r["retention_pass"]
    assert r["missing_physical_openings"]==["physical-1"]
