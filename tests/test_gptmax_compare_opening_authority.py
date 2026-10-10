"""Adversarial exact-identity regression checks for source-opening audits."""
from copy import deepcopy

import pytest

from tools.gptmax_compare_opening_authority import compare_reports


SHA = "a" * 64


def report():
    return {
        "source_sha256": SHA, "selected_geometry_page_ids": ["3"],
        "all_source_pages_requested": True, "primitive_safety_cap": 20000,
        "opening_bindings": [
            {"opening_identity_id": "door1", "host_wall_id": "wall-a",
             "record_id": "host-a", "reason_codes": []},
            {"opening_identity_id": "door2", "host_wall_id": None,
             "record_id": None, "reason_codes": ["no_authenticated_host_wall_band"]},
        ],
        "host_frame_traces": [
            {"opening_identity_id": "door1", "record_id": "frame-a",
             "reason_codes": []},
            {"opening_identity_id": "door2", "record_id": None,
             "reason_codes": ["frame_unavailable"]},
        ],
    }


def test_exact_parity_survives_order_and_ignored_metadata():
    first, second = report(), report()
    second["opening_bindings"].reverse()
    second["host_frame_traces"].reverse()
    second["revision_id"] = "detector_version_change"
    audit = compare_reports(first, second)
    assert audit["retention_pass"]
    assert audit["benchmark_accuracy"] is None


def test_host_gain_cannot_mask_lost_existing_host_or_frame():
    old, new = report(), report()
    new["opening_bindings"][0].update(host_wall_id=None, record_id=None,
                                       reason_codes=["raster_source_band_left_source_primitive_unmapped"])
    new["host_frame_traces"][0].update(record_id=None,
                                       reason_codes=["connected_edge_unproven"])
    new["opening_bindings"][1].update(host_wall_id="wall-b", record_id="host-b")
    new["host_frame_traces"][1]["record_id"] = "frame-b"
    audit = compare_reports(old, new)
    assert not audit["retention_pass"]
    assert audit["count_summary"]["baseline_hosts"] == audit["count_summary"]["candidate_hosts"]
    assert audit["count_summary"]["baseline_frames"] == audit["count_summary"]["candidate_frames"]
    assert audit["lost_proof_records"][0]["changes"] == [
        "host_lost", "host_receipt_lost", "source_frame_lost"]
    assert len(audit["new_proof_records"]) == 1


@pytest.mark.parametrize("key,new_value", [
    ("host_wall_id", "wall-other"), ("record_id", "host-other")])
def test_host_rekey_needs_exact_source_review(key, new_value):
    old, new = report(), report()
    new["opening_bindings"][0][key] = new_value
    audit = compare_reports(old, new)
    assert not audit["retention_pass"]
    assert audit["changed_proof_records_needing_review"]


def test_frame_rekey_is_not_silent_pass():
    old, new = report(), report()
    new["host_frame_traces"][0]["record_id"] = "other-frame"
    assert not compare_reports(old, new)["retention_pass"]


def test_physical_identity_loss_cannot_be_offset_by_new_identity():
    old, new = report(), report()
    new["opening_bindings"][0]["opening_identity_id"] = "door3"
    new["host_frame_traces"][0]["opening_identity_id"] = "door3"
    result = compare_reports(old, new)
    assert result["missing_physical_openings"] == ["door1"]
    assert result["added_physical_openings"] == ["door3"]
    assert not result["retention_pass"]


@pytest.mark.parametrize("damage", ["sha", "pages", "source_pages", "cap", "duplicate",
                                      "unmatched_frames", "missing_id"])
def test_incompatible_source_or_malformed_universe_fails_closed(damage):
    old, new = report(), report()
    if damage == "sha": new["source_sha256"] = "b"*64
    elif damage == "pages": new["selected_geometry_page_ids"] = ["4"]
    elif damage == "source_pages": new["all_source_pages_requested"] = False
    elif damage == "cap": new["primitive_safety_cap"] = 99999
    elif damage == "duplicate": new["opening_bindings"].append(deepcopy(new["opening_bindings"][0]))
    elif damage == "unmatched_frames": new["host_frame_traces"].pop()
    else: new["opening_bindings"][0]["opening_identity_id"] = ""
    with pytest.raises(ValueError):
        compare_reports(old, new)


def test_unknown_hosts_are_not_filled_in_by_diagnostic():
    old = report()
    audit = compare_reports(old, deepcopy(old))
    assert audit["retention_pass"]
    assert audit["count_summary"]["candidate_hosts"] == 1
    assert audit["count_summary"]["candidate_frames"] == 1
    assert old["opening_bindings"][1]["host_wall_id"] is None
