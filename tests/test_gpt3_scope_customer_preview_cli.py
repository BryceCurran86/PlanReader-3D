"""Executable GPT3 scope preview never changes V1 source/customer bytes."""
from __future__ import annotations

import hashlib
import json

import pytest

from tools.verify_gpt3_scope_customer_preview import (
    build_scope_customer_preview_report, main,
)
from test_gpt3_scope_customer_receipt_parity import _fixtures


def _inputs(tmp_path):
    sealed, sidecar, rows = _fixtures()
    original = {
        "sealed": json.dumps(sealed.to_dict(), sort_keys=True),
        "sidecar": json.dumps(sidecar, sort_keys=True),
        "customer": json.dumps(rows, sort_keys=True),
    }
    paths = {
        key: tmp_path / f"{key}.json" for key in original
    }
    for key, path in paths.items():
        path.write_text(original[key], encoding="utf-8")
    return paths


def _args(paths, output):
    return [
        "--sealed-run", str(paths["sealed"]),
        "--scope-sidecar", str(paths["sidecar"]),
        "--customer-rows", str(paths["customer"]),
        "--output", str(output),
    ]


def _hashes(paths):
    return {key: hashlib.sha256(path.read_bytes()).hexdigest()
            for key, path in paths.items()}


def test_cli_writes_one_source_neutral_preview_without_changing_evidence(tmp_path):
    paths = _inputs(tmp_path)
    before = _hashes(paths)
    output = tmp_path / "result.json"
    assert main(_args(paths, output)) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["source_authenticated"] is False
    assert report["original_pdf_issuer_scope_authenticated"] is False
    assert report["source_scope_parity_verified"] is True
    assert report["official_v2_coverage_accuracy"] is None
    assert report["sealed_quantity_count"] == 2
    assert report["preview_scope_record_count"] == 2
    assert report["input_artifact_sha256s"] == {
        "sealed_v1": before["sealed"],
        "preview_sidecar": before["sidecar"],
        "customer_rows": before["customer"],
    }
    assert _hashes(paths) == before


def test_preview_file_cannot_replace_existing_report(tmp_path):
    paths = _inputs(tmp_path)
    output = tmp_path / "immutable.json"
    output.write_text("previous report", encoding="utf-8")
    with pytest.raises(FileExistsError, match="new path"):
        main(_args(paths, output))
    assert output.read_text(encoding="utf-8") == "previous report"


@pytest.mark.parametrize("target", ("sealed", "sidecar", "customer"))
def test_preview_cannot_overwrite_any_signed_input(tmp_path, target):
    paths = _inputs(tmp_path)
    original = _hashes(paths)
    with pytest.raises(ValueError, match="protected evidence"):
        main(_args(paths, paths[target]))
    assert _hashes(paths) == original


@pytest.mark.parametrize("target", ("sealed", "sidecar", "customer"))
def test_corrupted_input_fails_without_diagnostic_or_source_mutation(tmp_path, target):
    paths = _inputs(tmp_path)
    path = paths[target]
    data = json.loads(path.read_text(encoding="utf-8"))
    if target == "sealed":
        data["project_id"] = "wrong-project"
    elif target == "sidecar":
        data["scope_records"][0]["decision_scope_id"] = "wrong-scope"
    else:
        data[0]["quantity"] = 999.0
    path.write_text(json.dumps(data), encoding="utf-8")
    before = _hashes(paths)
    output = tmp_path / "should-not-exist.json"
    with pytest.raises((ValueError, RuntimeError)):
        main(_args(paths, output))
    assert not output.exists()
    assert _hashes(paths) == before


def test_preview_accepts_notes_only_legacy_persisted_customer_rows(tmp_path):
    paths = _inputs(tmp_path)
    rows = json.loads(paths["customer"].read_text(encoding="utf-8"))
    for row in rows:
        row.pop("quantity_id", None)
        row.pop("commercial_projection_provenance", None)
    paths["customer"].write_text(json.dumps(rows), encoding="utf-8")
    report = build_scope_customer_preview_report(
        sealed_path=paths["sealed"],
        sidecar_path=paths["sidecar"],
        customer_path=paths["customer"],
    )
    assert report["source_scope_parity_verified"] is True
    assert report["publication_status"] == "UNPUBLISHED"


def test_preview_rejects_duplicate_nested_json_without_touching_customer(tmp_path):
    paths = _inputs(tmp_path)
    path = paths["sidecar"]
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"schema_version":', '"schema_version": "forged", "schema_version":', 1,
        ),
        encoding="utf-8",
    )
    before = _hashes(paths)
    with pytest.raises(ValueError, match="duplicate key"):
        build_scope_customer_preview_report(
            sealed_path=paths["sealed"],
            sidecar_path=paths["sidecar"],
            customer_path=paths["customer"],
        )
    assert _hashes(paths) == before
