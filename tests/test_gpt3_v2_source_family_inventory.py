"""Count authenticated sealed quantities by family without inventing V2 matches."""
from __future__ import annotations

from pathlib import Path

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_source_closed_run_export import seal_source_closed_run
from scripts.report_full_plan_v2_readiness import _source_authenticated_family_inventory
from test_gpt3_produced_items_original_source import _source_run
from test_source_closed_run_export import quantity, trace


def _single_source_run(tmp_path):
    _pdf, original_seal, _sha, _quantity, _trace = _source_run(tmp_path)
    sealed_root = tmp_path / "sealed"
    destination = sealed_root / "project-a" / "sealed_run.json"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(original_seal.read_bytes())
    receipt = load_verified_sealed_run(destination)
    return sealed_root, destination, receipt.fingerprint


def test_exact_signed_source_inventory_counts_actual_family_and_unit_only(tmp_path):
    root, _path, fingerprint = _single_source_run(tmp_path)
    inventory, status = _source_authenticated_family_inventory(
        root, "project-a", source_sha_verified=True,
        sealed_run_verified=True, expected_seal_fingerprint=fingerprint,
    )
    assert inventory == [{
        "family": "room_area", "unit": "m2",
        "non_abstained_signed_quantity_count": 1,
        "abstained_signed_quantity_count": 0,
    }]
    assert status == "SOURCE_SHA_AND_SIGNED_RUN_VERIFIED_UNSCORED"


def test_no_verified_original_pdf_cannot_yield_source_authenticated_inventory(tmp_path):
    root, _path, fingerprint = _single_source_run(tmp_path)
    for source_ok, seal_ok, receipt in (
        (False, True, fingerprint), (True, False, fingerprint), (True, True, None),
    ):
        inventory, status = _source_authenticated_family_inventory(
            root, "project-a", source_sha_verified=source_ok,
            sealed_run_verified=seal_ok, expected_seal_fingerprint=receipt,
        )
        assert inventory == []
        assert status == "SOURCE_OR_SEAL_NOT_VERIFIED"


def test_changed_or_swapped_seal_cannot_inherit_previous_inventory(tmp_path):
    root, path, fingerprint = _single_source_run(tmp_path)
    path.write_bytes(b'{"project_id":"project-a","quantities":[]}')
    inventory, status = _source_authenticated_family_inventory(
        root, "project-a", source_sha_verified=True,
        sealed_run_verified=True, expected_seal_fingerprint=fingerprint,
    )
    assert inventory == []
    assert status == "SIGNED_RUN_CHANGED_OR_INVALID"


def test_abstained_source_family_never_becomes_numeric_or_benchmark_match(tmp_path):
    q = quantity(
        quantity_id="qty-unmeasured", family="floor_area",
        semantic_key="floor.unmeasured.area", value=None, abstained=True,
        blocking_reasons=("source_metric_unavailable",), status="abstained",
        input_entity_ids=(), evidence_ids=(),
    )
    run = seal_source_closed_run(
        [q], project_id="project-a",
        traces_by_quantity_id={
            q.quantity_id: trace(canonical_entity_ids=(), evidence_ids=()),
        },
    )
    root = tmp_path / "sealed"
    target = root / "project-a" / "sealed_run.json"
    target.parent.mkdir(parents=True)
    target.write_text(run.to_json(), encoding="utf-8")
    inventory, status = _source_authenticated_family_inventory(
        root, "project-a", source_sha_verified=True,
        sealed_run_verified=True, expected_seal_fingerprint=run.fingerprint,
    )
    assert status == "SOURCE_SHA_AND_SIGNED_RUN_VERIFIED_UNSCORED"
    assert inventory == [{
        "family": "floor_area", "unit": "m2",
        "non_abstained_signed_quantity_count": 0,
        "abstained_signed_quantity_count": 1,
    }]
