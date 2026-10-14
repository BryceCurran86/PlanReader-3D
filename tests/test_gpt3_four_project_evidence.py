"""The four-project reporting path must never convert missing source into zero."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import report_gpt3_four_project_evidence as module


def _dirs(tmp_path: Path) -> dict:
    return {
        "source_dir": tmp_path / "source",
        "sealed_dir": tmp_path / "sealed",
        "identity_map_dir": tmp_path / "identity",
        "customer_dir": tmp_path / "customer",
    }


def test_missing_original_sources_keep_all_120_items_unpublished(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unavailable source may not invoke frozen evaluator")
    monkeypatch.setattr(module, "evaluate_suite_v2", forbidden)
    result = module.build_four_project_evidence_ledger(**_dirs(tmp_path))
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["official_suite_result"] is None
    assert result["coverage_accuracy"] is None
    assert result["precision_adjusted_accuracy"] is None
    assert result["required_project_count"] == 4
    assert result["frozen_denominator"] == 120
    assert len(result["projects"]) == 4
    assert sorted(x["denominator"] for x in result["projects"]) == [6, 24, 27, 63]
    for project in result["projects"]:
        assert project["publication_status"] == "UNAVAILABLE"
        assert project["source_sha_verified"] is False
        assert project["customer_bijection_verified"] is False
        assert project["reconciliation_complete"] is False
        assert project["exact_project_report"] is None


def test_present_but_corrupt_original_bytes_report_conflict_not_zero(tmp_path):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    project_root = dirs["source_dir"] / manifest.project_id
    project_root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (project_root / doc.name).write_bytes(b"%PDF-fake-not-original")
    result = module.build_four_project_evidence_ledger(**dirs)
    observed = next(x for x in result["projects"] if x["project_id"] == manifest.project_id)
    assert observed["publication_status"] == "CONFLICT"
    assert observed["source_sha_verified"] is False
    assert observed["reconciliation_complete"] is False
    assert observed["exact_project_report"] is None
    assert any(
        reason.startswith("original_source_size_mismatch:")
        or reason.startswith("original_source_sha_mismatch:")
        for reason in observed["reason_codes"]
    )
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["coverage_accuracy"] is None


def test_verified_source_without_signed_run_stays_unavailable(tmp_path, monkeypatch):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    project_root = dirs["source_dir"] / manifest.project_id
    project_root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (project_root / doc.name).write_bytes(b"%PDF-test-fixture")
    # The source gate is simulated ONLY to exercise the downstream absence.
    # No real SHA proof or quantity is created from these test-only bytes.
    monkeypatch.setattr(
        module, "_original_sha_gate",
        lambda raw, paths: (True, [], [d.sha256 for d in manifest.source_documents]),
    )
    result = module.build_four_project_evidence_ledger(**dirs)
    observed = next(x for x in result["projects"] if x["project_id"] == manifest.project_id)
    assert observed["source_sha_verified"] is True
    assert observed["publication_status"] == "UNAVAILABLE"
    assert "signed_production_evidence_unavailable" in observed["reason_codes"]
    assert observed["customer_bijection_verified"] is False
    assert observed["exact_project_report"] is None
    assert result["official_suite_result"] is None


def test_malformed_customer_rows_fail_closed(tmp_path):
    path = tmp_path / "customer.json"
    path.write_text('[{"quantity_id": "q1"}, {"quantity_id": ""}]', encoding="utf-8")
    with pytest.raises(ValueError, match="canonical quantity identity"):
        module._json_customer_rows(path)
    path.write_text('{"quantity_id": "q1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        module._json_customer_rows(path)


def test_malformed_signed_evidence_fails_closed(tmp_path):
    path = tmp_path / "signed.json"
    path.write_text('[]', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        module._json_object(path)


def test_source_byte_change_between_preflight_and_score_fails(tmp_path):
    import hashlib
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-real-original")
    initial = original.read_bytes()
    digest = hashlib.sha256(initial).hexdigest()
    manifest = {
        "source_documents": [{
            "name": "original.pdf", "sha256": digest,
            "size_bytes": len(initial),
        }],
    }
    frozen = tmp_path / "manifest.json"
    frozen.write_text('{"immutable": true}', encoding="utf-8")
    initial_files = {frozen: module._sha256(frozen)}
    module._assert_inputs_unchanged(
        manifest=manifest, originals=[original],
        expected_hashes=[digest], signed_hashes=initial_files,
    )
    original.write_bytes(b"%PDF-fake-original")
    with pytest.raises(ValueError, match="original source changed"):
        module._assert_inputs_unchanged(
            manifest=manifest, originals=[original],
            expected_hashes=[digest], signed_hashes=initial_files,
        )


def test_signed_customer_or_frozen_manifest_change_after_score_fails(tmp_path):
    import hashlib
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-fixed-source")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    manifest = {
        "source_documents": [{
            "name": "original.pdf", "sha256": digest,
            "size_bytes": original.stat().st_size,
        }],
    }
    signed = [tmp_path / item for item in (
        "source_manifest.json", "sealed.json", "identity.json", "customer.json"
    )]
    for path in signed:
        path.write_text('{"valid":true}', encoding="utf-8")
    fingerprints = {path: module._sha256(path) for path in signed}
    for modified in signed:
        modified.write_text('{"valid":false}', encoding="utf-8")
        with pytest.raises(ValueError, match="changed during reconciliation"):
            module._assert_inputs_unchanged(
                manifest=manifest, originals=[original],
                expected_hashes=[digest], signed_hashes=fingerprints,
            )
        modified.write_text('{"valid":true}', encoding="utf-8")
    module._assert_inputs_unchanged(
        manifest=manifest, originals=[original],
        expected_hashes=[digest], signed_hashes=fingerprints,
    )


def test_report_destination_cannot_overwrite_signed_inputs_or_alias(tmp_path):
    dirs = _dirs(tmp_path)
    input_path = dirs["sealed_dir"] / "signed-run.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("unchanged signed bytes", encoding="utf-8")
    args = [
        "--source-dir", str(dirs["source_dir"]),
        "--sealed-dir", str(dirs["sealed_dir"]),
        "--identity-map-dir", str(dirs["identity_map_dir"]),
        "--customer-dir", str(dirs["customer_dir"]),
    ]
    with pytest.raises(ValueError, match="may not overwrite evidence"):
        module.main([*args, "--output", str(input_path)])
    assert input_path.read_text(encoding="utf-8") == "unchanged signed bytes"

    alias = tmp_path / "alias-to-signed"
    alias.symlink_to(dirs["sealed_dir"], target_is_directory=True)
    with pytest.raises(ValueError, match="may not overwrite evidence"):
        module.main([*args, "--output", str(alias / "new-report.json")])
    assert not (dirs["sealed_dir"] / "new-report.json").exists()

    # Never allow a diagnostic to overwrite frozen benchmark truth.
    with pytest.raises(ValueError, match="may not overwrite evidence"):
        module.main([
            *args, "--output",
            str(module.FROZEN_ROOT / "manifest.json"),
        ])


def test_read_only_report_writes_safely_outside_inputs(tmp_path):
    dirs = _dirs(tmp_path)
    output = tmp_path / "reports" / "inventory.json"
    code = module.main([
        "--source-dir", str(dirs["source_dir"]),
        "--sealed-dir", str(dirs["sealed_dir"]),
        "--identity-map-dir", str(dirs["identity_map_dir"]),
        "--customer-dir", str(dirs["customer_dir"]),
        "--output", str(output),
    ])
    assert code == 2
    import json
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert parsed["frozen_denominator"] == 120
    assert parsed["publication_status"] == "UNPUBLISHED"
