from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

import tools.diag_gpt3_lot16_external_identity_readiness as module


def _source_row(physical: str, bbox):
    obs = f"obs-{physical}"
    evidence = f"label-{physical}"
    return {
        "opening_identity_id": physical,
        "label_bbox_pdf_pt": list(bbox),
        "location_is_reauthenticated_source_receipt": True,
        "source_text_observation_ids": [obs],
        "source_text_integrity_receipts": [{
            "trusted": True,
            "source_sha256": module.SOURCE_SHA256,
            "page_id": "3",
            "parent_observation_id": obs,
        }],
        "figured_label_evidence_id": evidence,
    }, {
        "physical_opening_id": physical,
        "figured_area_record_id": evidence,
        "host_binding_record_id": "host",
        "host_frame_record_id": None,
        "width_record_id": None,
        "height_record_id": None,
    }


def _fixture():
    active_src, active_can = _source_row("physical-active", [10, 20, 30, 40])
    pending_src, pending_can = _source_row("physical-pending", [50, 60, 70, 80])
    other_src, other_can = _source_row("physical-other", [90, 90, 100, 100])
    source = {
        "source_sha256": module.SOURCE_SHA256,
        "opening_identity_text_receipts": [
            active_src,
            pending_src,
            other_src,
        ],
        "canonical_openings": [active_can, pending_can, other_can],
    }
    universe = {
        "project_id": module.PROJECT,
        "external_openings": [
            {
                "object_ref": "external:active",
                "attributes": {
                    "source_bbox_pdf_pt": [10.0, 20.0, 30.0, 40.0],
                },
            },
            {
                "object_ref": "external:pending",
                "attributes": {
                    "source_bbox_pdf_pt": [50.0, 60.0, 70.0, 80.0],
                },
            },
        ],
    }
    manifest = {
        "project_id": module.PROJECT,
        "source_documents": [{"sha256": module.SOURCE_SHA256}],
        "verified_takeoff_items": [
            {
                "item_id": "item-active",
                "expected_object_refs": ["external:active"],
                "denominator_eligible": True,
            },
            {
                "item_id": "item-pending",
                "expected_object_refs": ["external:pending"],
                "denominator_eligible": True,
            },
        ],
    }
    sealed = {
        "project_id": module.PROJECT,
        "source_sha256s": [module.SOURCE_SHA256],
        "quantities": [{
            "quantity_id": "q-active",
            "object_identity_refs": ["physical-active"],
        }],
    }
    active_map = {
        "project_id": module.PROJECT,
        "bindings": [{
            "benchmark_item_id": "item-active",
            "production_object_identity_refs": ["physical-active"],
        }],
    }
    return source, universe, manifest, sealed, active_map


def _scan(*, mutate=None):
    source, universe, manifest, sealed, active_map = _fixture()
    values = [source, universe, manifest, sealed, active_map]
    if mutate is not None:
        mutate(*values)
    return module.scan_external_identity_readiness(
        source_report=source,
        object_universe=universe,
        source_manifest=manifest,
        sealed_run=sealed,
        active_identity_map=active_map,
    )


def test_scan_audits_active_and_keeps_unsealed_exact_match_pending():
    report = _scan()
    assert report["status"] == "EXTERNAL_IDENTITY_READINESS_AUDIT_COMPLETE"
    assert report["active_exact_identity_count"] == 1
    assert report["pending_identity_count"] == 1
    assert report["newly_sealed_unmapped_count"] == 0
    assert report["active_exact_identities"][0]["physical_opening_id"] == (
        "physical-active"
    )
    pending = report["pending_identities"][0]
    assert pending["physical_opening_id"] == "physical-pending"
    assert pending["benchmark_item_id"] == "item-pending"
    assert pending["status"] == "IDENTITY_READY_QUANTITY_UNSEALED"
    assert report["active_identity_map_modified"] is False
    assert report["benchmark_score_granted"] is False
    assert report["benchmark_accuracy"] is None
    assert report["evaluator_invoked"] is False


def test_newly_sealed_exact_identity_is_surfaced_not_activated():
    def mutate(source, universe, manifest, sealed, active_map):
        sealed["quantities"].append({
            "quantity_id": "q-pending",
            "object_identity_refs": ["physical-pending"],
        })

    report = _scan(mutate=mutate)
    assert report["active_exact_identity_count"] == 1
    assert report["pending_identity_count"] == 0
    assert report["newly_sealed_unmapped_count"] == 1
    row = report["newly_sealed_unmapped_identities"][0]
    assert row["physical_opening_id"] == "physical-pending"
    assert row["benchmark_item_id"] == "item-pending"
    assert row["status"] == "SEALED_UNMAPPED_IDENTITY_READY"
    assert report["active_identity_map_modified"] is False
    assert report["benchmark_score_granted"] is False


def test_source_location_outside_frozen_precision_is_not_nearest_matched():
    def mutate(source, universe, manifest, sealed, active_map):
        source["opening_identity_text_receipts"][1]["label_bbox_pdf_pt"][0] = 50.06

    report = _scan(mutate=mutate)
    assert report["pending_identity_count"] == 0
    assert report["ordinal_or_nearest_matching_used"] is False


def test_active_identity_map_must_be_backed_by_signed_quantity():
    def mutate(source, universe, manifest, sealed, active_map):
        sealed["quantities"] = []

    with pytest.raises(ValueError, match="absent from signed run"):
        _scan(mutate=mutate)


def test_active_exact_source_identity_cannot_be_swapped():
    def mutate(source, universe, manifest, sealed, active_map):
        active_map["bindings"][0]["production_object_identity_refs"] = [
            "physical-pending"
        ]
        sealed["quantities"].append({
            "quantity_id": "q-pending",
            "object_identity_refs": ["physical-pending"],
        })

    with pytest.raises(ValueError, match="contradicts signed state"):
        _scan(mutate=mutate)


def test_duplicate_frozen_external_source_location_fails_closed():
    def mutate(source, universe, manifest, sealed, active_map):
        universe["external_openings"].append({
            "object_ref": "external:duplicate",
            "attributes": {
                "source_bbox_pdf_pt": [10.0, 20.0, 30.0, 40.0],
            },
        })

    with pytest.raises(ValueError, match="not unique"):
        _scan(mutate=mutate)


@pytest.mark.parametrize("fault", ["untrusted", "foreign_sha", "wrong_page"])
def test_source_text_receipts_must_remain_original_and_trusted(fault):
    def mutate(source, universe, manifest, sealed, active_map):
        receipt = source["opening_identity_text_receipts"][1][
            "source_text_integrity_receipts"
        ][0]
        if fault == "untrusted":
            receipt["trusted"] = False
        elif fault == "foreign_sha":
            receipt["source_sha256"] = "f" * 64
        else:
            receipt["page_id"] = "4"

    with pytest.raises(ValueError, match="untrusted or foreign"):
        _scan(mutate=mutate)


def test_canonical_opening_must_preserve_exact_label_evidence():
    def mutate(source, universe, manifest, sealed, active_map):
        source["canonical_openings"][1]["figured_area_record_id"] = "other-label"

    with pytest.raises(ValueError, match="preserve source label evidence"):
        _scan(mutate=mutate)


def test_diagnostic_contains_no_quantity_similarity_or_evaluator_path():
    source = inspect.getsource(module)
    for forbidden in (
        "expected_quantity",
        "evaluate_project_v2",
        "run_exact_project_reconciliation",
        "reconcile_sealed_run_v2",
        "matched_within_tolerance",
        "precision_adjusted_accuracy",
        "description_similarity(",
        "nearest(",
    ):
        assert forbidden not in source
