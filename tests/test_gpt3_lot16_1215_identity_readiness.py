from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

import tools.diag_gpt3_lot16_1215_identity_readiness as module


def _fixture():
    source = {
        "source_sha256": module.SOURCE_SHA256,
        "opening_identity_text_receipts": [{
            "opening_identity_id": module.TARGET_PHYSICAL_ID,
            "figured_label_evidence_id": "label-1215",
            "label_bbox_pdf_pt": [622.4407, 430.6606, 661.0096, 438.4881],
            "location_is_reauthenticated_source_receipt": True,
            "source_text_observation_ids": ["obs-a", "obs-b", "obs-c"],
            "source_text_integrity_receipts": [
                {
                    "trusted": True,
                    "source_sha256": module.SOURCE_SHA256,
                    "page_id": "3",
                    "parent_observation_id": "obs-a",
                },
                {
                    "trusted": True,
                    "source_sha256": module.SOURCE_SHA256,
                    "page_id": "3",
                    "parent_observation_id": "obs-b",
                },
                {
                    "trusted": True,
                    "source_sha256": module.SOURCE_SHA256,
                    "page_id": "3",
                    "parent_observation_id": "obs-c",
                },
            ],
        }],
    }
    universe = {
        "project_id": module.PROJECT,
        "external_openings": [
            {
                "object_ref": module.TARGET_OBJECT_REF,
                "description": "audit-only text",
                "attributes": {
                    "source_bbox_pdf_pt": [622.4, 430.7, 661.0, 438.5],
                },
            },
            {
                "object_ref": "other-opening",
                "attributes": {
                    "source_bbox_pdf_pt": [100.0, 100.0, 120.0, 110.0],
                },
            },
        ],
    }
    manifest = {
        "project_id": module.PROJECT,
        "source_documents": [{"sha256": module.SOURCE_SHA256}],
        "verified_takeoff_items": [{
            "item_id": module.TARGET_ITEM_ID,
            "expected_object_refs": [module.TARGET_OBJECT_REF],
            "denominator_eligible": True,
        }],
    }
    sealed = {
        "project_id": module.PROJECT,
        "source_sha256s": [module.SOURCE_SHA256],
        "quantities": [{
            "quantity_id": "existing-seven-only",
            "object_identity_refs": ["another-physical-opening"],
        }],
    }
    identity_map = {
        "project_id": module.PROJECT,
        "bindings": [{
            "benchmark_item_id": "another-item",
            "production_object_identity_refs": ["another-physical-opening"],
        }],
    }
    return source, universe, manifest, sealed, identity_map


def _report():
    return module.build_readiness_report(
        source_report=_fixture()[0],
        object_universe=_fixture()[1],
        source_manifest=_fixture()[2],
        sealed_run=_fixture()[3],
        active_identity_map=_fixture()[4],
    )


def test_exact_original_location_proves_identity_readiness_only():
    report = _report()
    assert report["source_location_equal_at_frozen_precision"] is True
    assert report["source_location_unique_in_frozen_external_openings"] is True
    assert report["identity_ready_for_future_sealed_quantity"] is True
    assert report["target_currently_present_in_sealed_run"] is False
    assert report["target_currently_present_in_active_identity_map"] is False
    assert report["active_identity_map_modified"] is False
    assert report["benchmark_score_granted"] is False
    assert report["benchmark_accuracy"] is None
    assert report["status"] == "IDENTITY_READY_QUANTITY_UNSEALED"
    assert report["numeric_quantity_similarity_used"] is False
    assert report["name_or_description_similarity_used"] is False
    assert report["ordinal_or_nearest_matching_used"] is False


def test_location_must_match_at_frozen_recording_precision():
    source, universe, manifest, sealed, identity_map = _fixture()
    source["opening_identity_text_receipts"][0]["label_bbox_pdf_pt"][0] = 622.55
    with pytest.raises(ValueError, match="does not equal frozen"):
        module.build_readiness_report(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


def test_frozen_location_must_be_unique():
    source, universe, manifest, sealed, identity_map = _fixture()
    universe["external_openings"].append({
        "object_ref": "competing-frozen-opening",
        "attributes": {"source_bbox_pdf_pt": [622.4, 430.7, 661.0, 438.5]},
    })
    with pytest.raises(ValueError, match="not unique"):
        module.build_readiness_report(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


@pytest.mark.parametrize("location", ["sealed", "map"])
def test_readiness_stops_once_target_becomes_active(location):
    source, universe, manifest, sealed, identity_map = _fixture()
    if location == "sealed":
        sealed["quantities"].append({
            "quantity_id": "new-target",
            "object_identity_refs": [module.TARGET_PHYSICAL_ID],
        })
    else:
        identity_map["bindings"].append({
            "benchmark_item_id": module.TARGET_ITEM_ID,
            "production_object_identity_refs": [module.TARGET_PHYSICAL_ID],
        })
    with pytest.raises(ValueError, match="readiness diagnostic is stale"):
        module.build_readiness_report(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


@pytest.mark.parametrize(
    "fault",
    ["sha", "untrusted", "wrong_page", "duplicate_parent", "wrong_item_ref"],
)
def test_source_and_frozen_ancestry_fail_closed(fault):
    source, universe, manifest, sealed, identity_map = _fixture()
    if fault == "sha":
        source["source_sha256"] = "f" * 64
    elif fault == "untrusted":
        source["opening_identity_text_receipts"][0][
            "source_text_integrity_receipts"
        ][0]["trusted"] = False
    elif fault == "wrong_page":
        source["opening_identity_text_receipts"][0][
            "source_text_integrity_receipts"
        ][0]["page_id"] = "4"
    elif fault == "duplicate_parent":
        receipts = source["opening_identity_text_receipts"][0][
            "source_text_integrity_receipts"
        ]
        receipts[1]["parent_observation_id"] = receipts[0]["parent_observation_id"]
    else:
        manifest["verified_takeoff_items"][0]["expected_object_refs"] = [
            "different-object"
        ]
    with pytest.raises(ValueError):
        module.build_readiness_report(
            source_report=source,
            object_universe=universe,
            source_manifest=manifest,
            sealed_run=sealed,
            active_identity_map=identity_map,
        )


def test_diagnostic_never_runs_evaluator_or_rewrites_identity_map():
    source = inspect.getsource(module)
    forbidden = (
        "expected_quantity",
        "evaluate_project_v2",
        "run_exact_project_reconciliation",
        "reconcile_sealed_run_v2",
        "matched_within_tolerance",
        "precision_adjusted_accuracy",
    )
    for token in forbidden:
        assert token not in source
