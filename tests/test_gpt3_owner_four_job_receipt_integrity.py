"""Adversarial owner four-job RECEIPT checks, using only share-safe copies.

A mutation helper recomputes all synthetic SHA256SUMS and owner file hashes so
these tests exercise *semantic* gates, not merely the first file digest check.
This is neither reconstruction nor authentication of the owner's private PDFs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from tools import gpt3_owner_four_job_receipt_integrity as audit


_ROOT = (
    Path(__file__).resolve().parents[1]
    / "docs/engineering/four_job_runs/20261016_47c8031a"
)
_PROJECTS = (
    "au_qld_lot16_power", "au_qld_3laurel",
    "au_qld_maryborough_service_station",
    "au_qld_q5446_armstrong32_harlequin",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy(tmp_path: Path) -> Path:
    destination = tmp_path / "receipt"
    shutil.copytree(_ROOT, destination)
    return destination


def _write_json(root, relative, body):
    (root / relative).write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mutate(root, relative, callback):
    path = root / relative
    obj = json.loads(path.read_text(encoding="utf-8"))
    callback(obj)
    _write_json(root, relative, obj)


def _recalculate_synthetic_derived_receipts(root):
    # This is an intentionally self-consistent but NOT source-authenticated
    # forged test receipt, proving the semantic audit does not trust SHA alone.
    owner_path = root / "RUN_RECEIPT.json"
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    for entry in owner["files"]:
        p = root / entry["file"]
        if not p.is_file():
            continue
        entry["share_safe_sha256"] = _sha(p)
        entry["private_original_sha256"] = _sha(p)
        entry["bytes"] = p.stat().st_size
    _write_json(root, "RUN_RECEIPT.json", owner)
    original_entries = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    updated = []
    for entry in original_entries:
        _, relative = entry.split("  ", 1)
        updated.append(f"{_sha(root / relative)}  {relative}")
    (root / "SHA256SUMS").write_text("\n".join(updated) + "\n", encoding="utf-8")


def _expect_semantic_conflict(tmp_path, relative, change):
    root = _copy(tmp_path)
    _mutate(root, relative, change)
    _recalculate_synthetic_derived_receipts(root)
    with pytest.raises(ValueError):
        audit.verify_owner_four_job_receipts(root)


def test_real_archived_four_job_owner_receipts_are_rehashed_read_only():
    observed = audit.verify_owner_four_job_receipts(_ROOT)
    assert observed["schema_version"] == "gpt3-derived-owner-receipt-audit-v1"
    assert observed["original_document_count"] == 10
    assert observed["verified_derived_manifest_document_records"] == 10
    assert observed["independently_verified_share_safe_derived_file_count"] == 28
    assert observed["independently_verified_sha256sums_entries"] == 31
    assert observed["independently_rehashed_original_private_pdf_bytes"] is False
    assert observed["owner_reported_original_pdf_sha_verification"] is True
    assert observed["official_four_project_coverage_accuracy"] is None
    assert observed["official_publication_status"] == "UNPUBLISHED"
    assert observed["frozen_denominator"] == 120
    assert len(observed["projects"]) == 4
    by_id = {p["project_id"]: p for p in observed["projects"]}
    assert set(by_id) == set(_PROJECTS)
    assert by_id["au_qld_maryborough_service_station"]["process_status"] == "MEMORY_LIMIT"
    assert by_id["au_qld_maryborough_service_station"]["derived_sealed_quantity_count"] == 0
    assert by_id["au_qld_lot16_power"]["derived_sealed_quantity_count"] == 8
    assert by_id["au_qld_lot16_power"]["signed_run_verified_against_derived_bytes"]
    assert all(p["official_project_score"] is None for p in observed["projects"])


@pytest.mark.parametrize(
    "mutation",
    [
        ("owner-schema", "RUN_RECEIPT.json",
         lambda x: x.update(schema="unrecognized-receipt-type")),
        ("owner-revision-ref", "RUN_RECEIPT.json",
         lambda x: x.update(requested_ref="f" * 40)),
        ("owner-unpinned-head", "RUN_RECEIPT.json",
         lambda x: x.update(repo_head="invalid")),
        ("owner-source-total", "RUN_RECEIPT.json",
         lambda x: x.update(source_pdf_count=9)),
        ("owner-preflight-status", "RUN_RECEIPT.json",
         lambda x: x.update(source_preflight="FAILED")),
        ("owner-unpublished-flag", "RUN_RECEIPT.json",
         lambda x: x.update(full_suite_publication_status="PUBLISHED")),
        ("owner-forged-score", "RUN_RECEIPT.json",
         lambda x: x.update(official_four_project_coverage_accuracy=0.95)),
        ("owner-missing-process", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"].pop()),
        ("owner-duplicate-process", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][1].update(
             project_id=x["project_handoffs"][0]["project_id"])),
        ("owner-full-document-claim", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][0].update(single_document_handoff_only=False)),
        ("owner-false-success-exit", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][2].update(status="COMPLETED", exit_code=0)),
        ("owner-failed-completed-exit", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][0].update(exit_code=2)),
        ("source-score-grant", "SOURCE_SHA_VERIFICATION.json",
         lambda x: x.update(score_granted=True)),
        ("source-missing-document", "SOURCE_SHA_VERIFICATION.json",
         lambda x: x["rows"].pop()),
        ("source-duplicate-document", "SOURCE_SHA_VERIFICATION.json",
         lambda x: x["rows"][1].update(file_name=x["rows"][0]["file_name"],
                                        project_id=x["rows"][0]["project_id"])),
        ("source-nonverified-document", "SOURCE_SHA_VERIFICATION.json",
         lambda x: x["rows"][0].update(status="MISMATCH")),
        ("source-wrong-benchmark", "SOURCE_SHA_VERIFICATION.json",
         lambda x: x.update(benchmark_id="retired")),
        ("source-wrong-document-count", "SOURCE_SHA_VERIFICATION.json",
         lambda x: x.update(verified_document_count=9)),
        ("preflight-exit", "PREFLIGHT_STATUS.json",
         lambda x: x[0].update(exit_code=3)),
        ("preflight-duplicate-project", "PREFLIGHT_STATUS.json",
         lambda x: x[1].update(project_id=x[0]["project_id"])),
        ("preflight-source-role", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x["source_documents"][0].update(role="unknown")),
        ("preflight-source-sha", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x["source_documents"][0].update(actual_sha256="0" * 64)),
        ("preflight-source-size", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x["source_documents"][0].update(actual_size_bytes=1)),
        ("preflight-source-pages", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x["source_documents"][0].update(actual_page_count=999)),
        ("preflight-score-grant", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x.update(benchmark_score_granted=True)),
        ("preflight-commercial-grant", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x.update(commercial_quantity_publication_granted=True)),
        ("preflight-ceiling-grant", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x.update(rcp_or_metric_or_finish_authority_granted=True)),
        ("preflight-source-completion", "au_qld_lot16_power/source_package_preflight.json",
         lambda x: x.update(actual_source_package_runtime_complete=False)),
        ("production-wrong-project", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(project_id="wrong-project")),
        ("production-wrong-source-sha", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(source_sha256="f" * 64)),
        ("production-page-count", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(page_count=999)),
        ("production-score-granted", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(benchmark_score_granted=True)),
        ("production-customer-forged", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(customer_rows_verified=True)),
        ("production-customer-count", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(verified_customer_row_count=8)),
        ("production-run-id", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(combined_run_id="forged-v1-run-id")),
        ("production-quantity-count", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(combined_quantity_count=9)),
        ("production-family-count", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["family_counts"].update(opening_area=9)),
        ("production-family-id", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["family_run_ids"].update(opening_area="forged-family-run-id")),
        ("production-maryborough-sealed", "au_qld_maryborough_service_station/outputs/production_summary.json",
         lambda x: x.update(combined_run_file="forged-sealed-run")),
        ("production-maryborough-firm", "au_qld_maryborough_service_station/outputs/production_summary.json",
         lambda x: x.update(family_counts={"floor_finish_area": 4})),
        ("production-q5446-customer", "au_qld_q5446_armstrong32_harlequin/outputs/production_summary.json",
         lambda x: x.update(customer_rows_file="forged-commercial-output")),
        ("production-3laurel-signed", "au_qld_3laurel/outputs/production_summary.json",
         lambda x: x.update(combined_quantity_count=10)),
    ],
    ids=lambda value: value[0] if type(value) is tuple else None,
)
def test_forged_but_rehashed_original_owner_receipt_cannot_publish(tmp_path, mutation):
    _, relative, change = mutation
    _expect_semantic_conflict(tmp_path, relative, change)


def test_real_original_owner_receipt_tamper_fails_sha_without_resigning(tmp_path):
    root = _copy(tmp_path)
    target = root / "au_qld_lot16_power/outputs/au_qld_lot16_power.json"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        audit.verify_owner_four_job_receipts(root)


def test_persisted_v1_quantity_tamper_rejected_even_with_recalculated_archive_sha(tmp_path):
    root = _copy(tmp_path)
    relative = "au_qld_lot16_power/outputs/au_qld_lot16_power.json"
    _mutate(root, relative, lambda x: x["quantities"][0].update(value=55555))
    _recalculate_synthetic_derived_receipts(root)
    with pytest.raises(Exception):
        audit.verify_owner_four_job_receipts(root)


def test_source_path_traversal_in_owner_derived_index_is_rejected(tmp_path):
    root = _copy(tmp_path)
    _mutate(root, "RUN_RECEIPT.json", lambda x:
            x["files"][0].update(file="../confidential-source.pdf"))
    with pytest.raises(ValueError):
        audit.verify_owner_four_job_receipts(root)


def test_source_symlink_escape_from_archive_is_rejected(tmp_path):
    root = _copy(tmp_path)
    relative = "au_qld_lot16_power/source_package_preflight.json"
    original = root / relative
    replacement = tmp_path / "external-preflight.json"
    replacement.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(replacement)
    with pytest.raises(ValueError, match="symlink"):
        audit.verify_owner_four_job_receipts(root)


def test_archive_digest_cannot_hide_duplicate_sha256sums_entry(tmp_path):
    root = _copy(tmp_path)
    sha_file = root / "SHA256SUMS"
    lines = sha_file.read_text(encoding="utf-8").splitlines()
    sha_file.write_text("\n".join([*lines, lines[0]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate SHA256SUMS"):
        audit.verify_owner_four_job_receipts(root)


def test_archive_digest_cannot_hide_missing_sha256sums_entry(tmp_path):
    root = _copy(tmp_path)
    sha_file = root / "SHA256SUMS"
    lines = sha_file.read_text(encoding="utf-8").splitlines()
    sha_file.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="universe differs"):
        audit.verify_owner_four_job_receipts(root)


def test_cli_writes_unpublished_outside_receipt_directory_and_cannot_overwrite(tmp_path):
    out = tmp_path / "report.json"
    rc = audit.main([
        "--receipt-root", str(_ROOT), "--output", str(out),
    ])
    assert rc == 2
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["official_four_project_coverage_accuracy"] is None
    assert data["independently_rehashed_original_private_pdf_bytes"] is False
    with pytest.raises(ValueError, match="cannot overwrite"):
        audit.main([
            "--receipt-root", str(_ROOT),
            "--output", str(_ROOT / "RUN_RECEIPT.json"),
        ])
