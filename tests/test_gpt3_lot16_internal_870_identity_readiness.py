from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

import tools.diag_gpt3_lot16_internal_870_identity_readiness as module


def _source_row(physical: str, bbox, *, host=False, frame=False):
    obs = f"obs-{physical[-4:]}"
    evidence = f"label-{physical[-4:]}"
    return {
        "opening_identity_id": physical,
        "figured_label_evidence_id": evidence,
        "label_bbox_pdf_pt": list(bbox),
        "location_is_reauthenticated_source_receipt": True,
        "source_text_observation_ids": [obs],
        "source_text_integrity_receipts": [{
            "trusted": True,
            "source_sha256": module.SOURCE_SHA256,
            "page_id": "3",
            "parent_observation_id": obs,
        }],
    }, {
        "physical_opening_id": physical,
        "figured_area_record_id": evidence,
        "host_binding_record_id": "host" if host else None,
        "host_frame_record_id": "frame" if frame else None,
        "width_record_id": None,
        "height_record_id": None,
    }


def _fixture():
    row_a, can_a = _source_row(
        "physical_opening_existence_a",
        [10.04, 20.04, 30.04, 40.04],
        host=True,
    )
    row_b, can_b = _source_row(
        "physical_opening_existence_b",
        [50.02, 60.02, 70.02, 80.02],
        host=True,
        frame=True,
    )
    row_unmatched, can_unmatched = _source_row(
        "physical_opening_existence_external",
        [90.0, 90.0, 100.0, 100.0],
    )
    source = {
        "source_sha256": module.SOURCE_SHA256,
        "opening_identity_text_receipts": [row_a, row_b, row_unmatched],
        "canonical_openings": [can_a, can_b, can_unmatched],
    }
    universe = {
        "project_id": module.PROJECT,
        "internal_room_access_openings": [
            {
                "object_ref": "internal:a",
                "attributes": {"source_bbox_pdf_pt": [10.0, 20.0, 30.0, 40.0]},
            },
            {
                "object_ref": "internal:b",
                "attributes": {"source_bbox_pdf_pt": [50.0, 60.0, 70.0, 80.0]},
            },
        ],
    }
    manifest = {
        "project_id": module.PROJECT,
        "source_documents": [{"sha256": module.SOURCE_SHA256}],
        "verified_takeoff_items": [
            {
                "item_id": "item-a",
                "expected_object_refs": ["internal:a"],
                "denominator_eligible": True,
            },
            {
                "item_id": "item-b",
                "expected_object_refs": ["internal:b"],
                "denominator_eligible": True,
            },
        ],
    }
    sealed = {
        "project_id": module.PROJECT,
        "source_sha256s": [module.SOURCE_SHA256],
        "quantities": [{
            "quantity_id": "existing-seven-only",
            "object_identity_refs": ["different-physical"],
        }],
    }
    identity_map = {
        "project_id": module.PROJECT,
        "bindings": [{
            "benchmark_item_id": "different-item",
            "production_object_identity_refs": ["different-physical"],
        }],
    }
    return source, universe, manifest, sealed, identity_map


def _report():
    source, universe, manifest, sealed, identity_map = _fixture()
    return module.build_pending_identity_ledger(
        source_report=source,
        object_universe=universe,
        source_manifest=manifest,
        sealed_run=sealed,
        active_identity_map=identity_map,
    )


def test_exact_locations_create_pending_identity_readiness_only():
    report = _report()
    assert report["pending_identity_count"] == 2
    assert report["benchmark_score_granted"] is False
    assert report["benchmark_accuracy"] is None
    assert report["active_identity_map_modified"] is False
    assert report["status"] == "PENDING_IDENTITIES_READY_QUANTITIES_UNSEALED"
    by_ref = {
        row["benchmark_object_ref"]: row
        for row in report["pending_identities"]
    }
    assert set(by_ref) == {"internal:a", "internal:b"}
    assert by_ref["internal:a"]["host_binding_present"] is True
    assert by_ref["internal:a"]["host_frame_present"] is False
    assert by_ref["internal:b"]["host_binding_present"] is True
    assert by_ref["internal:b"]["host_frame_present"] is True
    assert all(
        row["status"] == "IDENTITY_READY_QUANTITY_UNSEALED"
        for row in by_ref.values()
    )


def test_unmatched_source_location_is_not_forced_to_nearest_frozen_object():
    report = _report()
    physical = {
        row["physical_opening_id"]
        for row in report["pending_identities"]
    }
    assert "physical_opening_existence_external" not in physical
    assert report["ordinal_or_nearest_matching_used"] is False


def test_duplicate_frozen_location_fails_closed():
    source, universe, manifest, sealed, identity_map = _fixture()
    universe["internal_room_access_openings"].append({
        "object_ref": "internal:duplicate",
        "attributes": {"source_bbox_pdf_pt": [10.0, 20.0, 30.0, 40.0]},
    })
    with pytest.raises(ValueError, match="not unique"):
        module.build_pending_identity_ledger(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


@pytest.mark.parametrize("active", ["sealed", "physical_map", "item_map"])
def test_pending_ledger_becomes_stale_once_identity_is_active(active):
    source, universe, manifest, sealed, identity_map = _fixture()
    if active == "sealed":
        sealed["quantities"].append({
            "quantity_id": "new-a",
            "object_identity_refs": ["physical_opening_existence_a"],
        })
    elif active == "physical_map":
        identity_map["bindings"].append({
            "benchmark_item_id": "new-item",
            "production_object_identity_refs": ["physical_opening_existence_a"],
        })
    else:
        identity_map["bindings"].append({
            "benchmark_item_id": "item-a",
            "production_object_identity_refs": ["different-physical-2"],
        })
    with pytest.raises(ValueError, match="ledger is stale"):
        module.build_pending_identity_ledger(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


@pytest.mark.parametrize(
    "fault",
    ["source_sha", "untrusted", "wrong_page", "duplicate_parent", "label_drift"],
)
def test_original_source_ancestry_and_label_evidence_fail_closed(fault):
    source, universe, manifest, sealed, identity_map = _fixture()
    row = source["opening_identity_text_receipts"][0]
    if fault == "source_sha":
        source["source_sha256"] = "f" * 64
    elif fault == "untrusted":
        row["source_text_integrity_receipts"][0]["trusted"] = False
    elif fault == "wrong_page":
        row["source_text_integrity_receipts"][0]["page_id"] = "4"
    elif fault == "duplicate_parent":
        row["source_text_observation_ids"].append(row["source_text_observation_ids"][0])
    else:
        source["canonical_openings"][0]["figured_area_record_id"] = "different-label"
    with pytest.raises(ValueError):
        module.build_pending_identity_ledger(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


def test_exact_location_outside_frozen_precision_does_not_match():
    source, universe, manifest, sealed, identity_map = _fixture()
    source["opening_identity_text_receipts"][0]["label_bbox_pdf_pt"][0] = 10.06
    report = module.build_pending_identity_ledger(
        source_report=source,
        object_universe=universe,
        source_manifest=manifest,
        sealed_run=sealed,
        active_identity_map=identity_map,
    )
    assert report["pending_identity_count"] == 1
    assert report["pending_identities"][0]["benchmark_object_ref"] == "internal:b"


def test_diagnostic_never_uses_values_names_or_evaluator():
    source = inspect.getsource(module)
    forbidden = (
        "expected_quantity",
        "evaluate_project_v2",
        "run_exact_project_reconciliation",
        "reconcile_sealed_run_v2",
        "matched_within_tolerance",
        "precision_adjusted_accuracy",
        "SequenceMatcher",
        "difflib",
        "nearest(",
    )
    for token in forbidden:
        assert token not in source
