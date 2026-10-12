"""Original PDF bytes, not matching artifact hash strings, gate exact V2 scoring."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import run_gpt3_original_byte_gated_exact_project as module


def _fixtures(tmp_path, monkeypatch, *, status="INCOMPLETE"):
    frozen = tmp_path / "frozen-v2"
    manifest_file = frozen / "projects" / "source-project" / "source_manifest.json"
    manifest_file.parent.mkdir(parents=True)
    original = tmp_path / "sources" / "original.pdf"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"%PDF-actual-source-pinned")
    receipt = hashlib.sha256(original.read_bytes()).hexdigest()
    manifest = {
        "project_id": "source-project",
        "status": status,
        "source_package_complete": True,
        "source_documents": [{
            "name": "original.pdf", "sha256": receipt,
            "size_bytes": original.stat().st_size, "page_count": 1,
        }],
        "reason_codes": ["physical_object_universe_incomplete"] if status != "VERIFIED" else [],
    }
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    sealed = tmp_path / "sealed.json"
    sealed.write_text(json.dumps({"source_sha256s": [receipt]}), encoding="utf-8")
    identity = tmp_path / "identity_map.json"
    identity.write_text(json.dumps({"source_sha256s": [receipt]}), encoding="utf-8")
    monkeypatch.setattr(module, "FROZEN_ROOT", frozen)
    return manifest_file, original, sealed, identity, receipt


def _report(manifest, original, sealed, identity, *, original_files=None):
    return module.build_original_byte_gated_project_report(
        manifest_path=manifest, sealed_run_path=sealed,
        identity_map_path=identity,
        original_files=[original] if original_files is None else original_files,
    )


def test_authentic_source_with_incomplete_manifest_never_invokes_frozen_evaluator(tmp_path, monkeypatch):
    manifest, original, sealed, identity, expected_sha = _fixtures(tmp_path, monkeypatch)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("frozen evaluator called on incomplete source universe")
    monkeypatch.setattr(module, "_unchanged_frozen_exact_report", forbidden)
    report = _report(manifest, original, sealed, identity)
    assert report["source_sha256s"] == [expected_sha]
    assert report["original_source_sha_verified"] is True
    assert report["project_evaluation"] is None
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["reconciliation_complete"] is False
    assert report["reason_codes"] == [
        "frozen_project_universe_incomplete", "physical_object_universe_incomplete",
    ]


def test_not_supplying_actual_original_pdf_never_mints_source_proof(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(tmp_path, monkeypatch)
    report = _report(manifest, original, sealed, identity, original_files=[])
    assert report["original_source_sha_verified"] is False
    assert report["source_sha256s"] == []
    assert report["project_evaluation"] is None


def test_hash_string_claim_cannot_authorize_modified_pdf_bytes(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(tmp_path, monkeypatch)
    original.write_bytes(b"%PDF-other-original-same-filename")
    result = _report(manifest, original, sealed, identity)
    assert "original_source_size_mismatch:original.pdf" in result["reason_codes"]
    assert result["original_source_sha_verified"] is False
    assert result["project_evaluation"] is None


def test_forged_external_manifest_cannot_substitute_for_frozen_truth(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(tmp_path, monkeypatch)
    outside = tmp_path / "fake_manifest.json"
    outside.write_bytes(manifest.read_bytes())
    with pytest.raises(ValueError, match="exact frozen Full Plan V2"):
        _report(outside, original, sealed, identity)


def test_complete_source_project_invokes_existing_report_only_after_byte_validation(tmp_path, monkeypatch):
    manifest, original, sealed, identity, sha = _fixtures(
        tmp_path, monkeypatch, status="VERIFIED",
    )
    called = []
    def exact_report(m, s, i):
        assert m == manifest and s == sealed and i == identity
        assert hashlib.sha256(original.read_bytes()).hexdigest() == sha
        called.append(True)
        return {
            "project_id": "source-project", "source_sha_verified": True,
            "reconciliation_complete": True,
            "denominator": 1, "matched_within_tolerance": 1,
        }
    monkeypatch.setattr(module, "_unchanged_frozen_exact_report", exact_report)
    report = _report(manifest, original, sealed, identity)
    assert called == [True]
    assert report["original_source_sha_verified"] is True
    assert report["reconciliation_complete"] is True
    assert report["project_evaluation"]["matched_within_tolerance"] == 1
    assert report["score_claim"] is False
    assert report["publication_status"] == "PROJECT_ONLY_FOUR_PROJECT_SUITE_UNPUBLISHED"


def test_original_pdf_rotated_during_exact_report_must_not_publish(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(
        tmp_path, monkeypatch, status="VERIFIED",
    )
    def rotating(_manifest, _seal, _identity):
        original.write_bytes(b"%PDF-tampered-during-evaluator")
        return {
            "project_id": "source-project", "source_sha_verified": True,
            "reconciliation_complete": True,
        }
    monkeypatch.setattr(module, "_unchanged_frozen_exact_report", rotating)
    report = _report(manifest, original, sealed, identity)
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["original_source_sha_verified"] is False
    assert report["project_evaluation"] is None


def test_signed_map_rotated_during_evaluation_never_inherits_receipt(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(
        tmp_path, monkeypatch, status="VERIFIED",
    )
    def rotating(_manifest, _seal, _identity):
        identity.write_bytes(b"changed identity map")
        return {
            "project_id": "source-project", "source_sha_verified": True,
            "reconciliation_complete": True,
        }
    monkeypatch.setattr(module, "_unchanged_frozen_exact_report", rotating)
    report = _report(manifest, original, sealed, identity)
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["project_evaluation"] is None
    assert report["reason_codes"] == ["source_or_signed_artifact_changed_during_reconciliation"]


def test_project_gate_output_never_overwrites_frozen_reference(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(tmp_path, monkeypatch)
    frozen_reference = module.FROZEN_ROOT / "reference_takeoff.json"
    frozen_reference.write_bytes(b"unchanged gold")
    with pytest.raises(ValueError, match="may not overwrite"):
        module.main([
            "--manifest", str(manifest), "--source", str(original),
            "--sealed-run", str(sealed), "--identity-map", str(identity),
            "--output", str(frozen_reference),
        ])
    assert frozen_reference.read_bytes() == b"unchanged gold"


@pytest.mark.parametrize("side", ["sealed", "identity"])
def test_partial_signed_source_envelope_cannot_pass_original_byte_gate(tmp_path, monkeypatch, side):
    manifest, original, sealed, identity, _sha = _fixtures(
        tmp_path, monkeypatch, status="VERIFIED",
    )
    artifact = sealed if side == "sealed" else identity
    artifact.write_text(json.dumps({"source_sha256s": []}), encoding="utf-8")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("frozen evaluator must never see incomplete signed source package")
    monkeypatch.setattr(module, "_unchanged_frozen_exact_report", forbidden)
    report = _report(manifest, original, sealed, identity)
    assert report["original_source_sha_verified"] is True
    assert report["project_evaluation"] is None
    assert report["reason_codes"] == ["signed_production_source_package_incomplete"]


def test_malformed_unhashable_signed_source_sha_array_fails_closed(tmp_path, monkeypatch):
    manifest, original, sealed, identity, _sha = _fixtures(
        tmp_path, monkeypatch, status="VERIFIED",
    )
    identity.write_text(json.dumps({"source_sha256s": [{"sha256": "fake"}]}), encoding="utf-8")
    report = _report(manifest, original, sealed, identity)
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["reason_codes"] == ["signed_production_source_package_incomplete"]


def test_actual_unchanged_maryborough_original_pdf_sha_is_real_but_still_unscored(monkeypatch):
    # This is the actual committed Maryborough source, not a benchmark-gold
    # fixture or a synthetic 10m² quantity.
    root = Path(__file__).resolve().parents[1]
    original = root / "documents" / "sources" / "Arch_Combined_Maryborough_Service_Station.pdf"
    manifest = (
        root / "benchmarks" / "frozen_holdout" / "full_plan_v2"
        / "projects" / "au_qld_maryborough_service_station" / "source_manifest.json"
    )
    assert original.is_file(), "real original Maryborough PDF source is unavailable in CI"
    assert manifest.is_file(), "frozen V2 Maryborough source manifest is missing"
    expected_source_sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == expected_source_sha
    def forbidden(*_args, **_kwargs):
        raise AssertionError("incomplete Maryborough source universe must never be scored")
    monkeypatch.setattr(module, "_unchanged_frozen_exact_report", forbidden)
    # The real source exists, but production signed run/identity-map is not
    # supplied here and the manifest remains INCOMPLETE. Never invent one.
    report = module.build_original_byte_gated_project_report(
        manifest_path=manifest,
        sealed_run_path=root / "nonexistent-maryborough-sealed-run.json",
        identity_map_path=root / "nonexistent-maryborough-identity-map.json",
        original_files=[original],
    )
    assert report["source_sha256s"] == [expected_source_sha]
    assert report["original_source_sha_verified"] is True
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["project_evaluation"] is None
    assert report["reconciliation_complete"] is False
