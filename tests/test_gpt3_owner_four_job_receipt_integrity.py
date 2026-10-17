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
    assert by_id["au_qld_maryborough_service_station"][
        "earliest_verified_project_execution_gate"
    ] == "owner_process_stopped:MEMORY_LIMIT"
    assert by_id["au_qld_3laurel"]["earliest_verified_project_execution_gate"] == (
        "source_producer_unsealed:no_sealable_quantities"
    )
    assert by_id["au_qld_q5446_armstrong32_harlequin"][
        "earliest_verified_project_execution_gate"
    ] == "source_producer_unsealed:source_complexity_blocked"
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


def test_confidential_original_pdf_must_not_be_present_even_unindexed(tmp_path):
    root = _copy(tmp_path)
    (root / "private-original-plan.pdf").write_bytes(b"%PDF-synthetic-private-not-for-public")
    with pytest.raises(ValueError, match="private original PDF"):
        audit.verify_owner_four_job_receipts(root)


@pytest.mark.parametrize(
    "mutation",
    [
        ("source-at-start-project", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(project_id="another-project")),
        ("source-at-start-sha", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(source_sha256_at_start="f"*64)),
        ("source-at-start-page-count", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(source_page_count=12)),
        ("source-at-start-page-omission", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x["execution_page_numbers"].pop()),
        ("source-at-start-boolean-page", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x["execution_page_numbers"].__setitem__(0, True)),
        ("source-at-start-sealed-claim", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(sealed_run_file="forged-original-seal")),
        ("source-at-start-complete-coverage", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(complete_source_coverage_proven=True)),
        ("source-at-start-fake-score", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(benchmark_score_granted=True)),
        ("source-at-start-topology-change", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(topology_mode="different-source-scope")),
        ("source-at-start-family-change", "au_qld_lot16_power/outputs/source_attempt_preflight.json",
         lambda x: x.update(family_group="opening_area_only")),
        ("production-original-pages-short", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["execution_pages"].pop()),
        ("production-semantic-pages-short", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["semantic_execution_pages"].pop()),
        ("production-reordered-pages", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["execution_pages"].reverse()),
        ("production-topology-page-invalid", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["topology_pages"].append(99)),
        ("production-support-page-invalid", "au_qld_maryborough_service_station/outputs/production_summary.json",
         lambda x: x["room_area_support_pages"].append(33)),
        ("production-wall-page-conflicting", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["canonical_wall_source_pages"].append(42)),
        ("production-duplicate-topology", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["topology_pages"].append(x["topology_pages"][0])),
        ("production-partial-page-unknown", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(source_positive_partial_page=-1)),
        ("production-boolean-page", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["topology_pages"].__setitem__(0, True)),
        ("production-negative-wall-count", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(unresolved_wall_candidate_count=-1)),
        ("production-bool-canonical-count", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["canonical_counts"].update(walls=True)),
        ("production-false-firm-canonical-wall", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(canonical_wall_status="firm")),
        ("production-false-approved-claim", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(claim_status="approved")),
        ("production-duplicate-source-reason", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["claim_reason_codes"].append(x["claim_reason_codes"][0])),
        ("production-blank-source-reason", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["canonical_wall_reason_codes"].append("")),
        ("production-wrong-topology-mode", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(topology_mode="unscoped-all-pages")),
        ("production-source-name-forgery", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(source_path=x["source_path"].replace(
             "1. Construction Plans - Lot 16 Power (REV E).pdf",
             "another-project.pdf"))),
        ("production-source-cross-project", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(source_path=x["source_path"].replace(
             "\\au_qld_lot16_power\\", "\\au_qld_maryborough_service_station\\"))),
        ("production-combined-wrong-project", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(combined_run_file=x["combined_run_file"].replace(
             "\\project_outputs\\au_qld_lot16_power\\",
             "\\project_outputs\\au_qld_3laurel\\"))),
        ("production-family-wrong-project", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["family_run_files"].update(opening_area=x[
             "family_run_files"]["opening_area"].replace(
                 "\\project_outputs\\au_qld_lot16_power\\",
                 "\\project_outputs\\au_qld_3laurel\\"))),
        ("production-family-foreign-kind", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x["family_run_files"].update(opening_area=x[
             "family_run_files"]["opening_area"].replace(
                 "opening_area.sealed.json", "opening_count.sealed.json"))),
    ],
    ids=lambda value: value[0] if type(value) is tuple else None,
)
def test_source_at_start_and_scope_binding_reject_even_rehashed_forgery(
    tmp_path, mutation,
):
    _, relative, change = mutation
    _expect_semantic_conflict(tmp_path, relative, change)


def test_clean_scope_guards_preserve_owner_maryborough_memory_abstention():
    audit_result = audit.verify_owner_four_job_receipts(_ROOT)
    by_id = {row["project_id"]: row for row in audit_result["projects"]}
    assert by_id["au_qld_maryborough_service_station"][
        "earliest_verified_project_execution_gate"
    ] == "owner_process_stopped:MEMORY_LIMIT"
    assert by_id["au_qld_q5446_armstrong32_harlequin"][
        "earliest_verified_project_execution_gate"
    ] == "source_producer_unsealed:source_complexity_blocked"
    assert audit_result["official_four_project_coverage_accuracy"] is None


def test_unindexed_non_pdf_source_record_is_also_not_share_safe(tmp_path):
    root = _copy(tmp_path)
    (root / "private-field-notes.txt").write_text(
        "synthetic file not in provenance archive", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unindexed artifact"):
        audit.verify_owner_four_job_receipts(root)


def test_cross_semantic_signed_claims_are_retained_for_source_review_not_merged():
    from types import SimpleNamespace
    def row(qid, family, objects):
        return SimpleNamespace(
            quantity_id=qid,
            family=family,
            source_sha256="f" * 64,
            revision_id="original-revision-1",
            object_identity_refs=tuple(objects),
        )
    claims = audit._cross_semantic_source_claims([
        row("q1", "floor_area", ["floor-A"]),
        row("q2", "floor_finish_area", ["floor-A"]),
        row("q3", "opening_area", ["opening-B"]),
    ])
    assert len(claims) == 1
    assert claims[0]["canonical_object_refs"] == ["floor-A"]
    assert claims[0]["signed_quantity_ids"] == ["q1", "q2"]
    assert claims[0]["quantity_families"] == ["floor_area", "floor_finish_area"]
    assert claims[0]["source_review_required"] is True


def test_two_independent_source_revisions_are_not_cross_semantic_conflated():
    from types import SimpleNamespace
    original = SimpleNamespace(
        quantity_id="q1", family="floor_area",
        source_sha256="f" * 64, revision_id="original-revision",
        object_identity_refs=("floor-A",),
    )
    newer = SimpleNamespace(
        quantity_id="q2", family="floor_finish_area",
        source_sha256="f" * 64, revision_id="changed-revision",
        object_identity_refs=("floor-A",),
    )
    assert audit._cross_semantic_source_claims([original, newer]) == []


def test_historical_original_lot16_eight_has_no_crosssemantic_false_alert():
    receipt = audit.verify_owner_four_job_receipts(_ROOT)
    assertions = receipt["cross_semantic_signed_object_claims_for_review"]
    assert assertions["au_qld_lot16_power"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        ("owner-session-bad", "RUN_RECEIPT.json",
         lambda x: x.update(session="../../confidential")),
        ("owner-preflight-foreign-path", "PREFLIGHT_STATUS.json",
         lambda x: x[0].update(report=x[0]["report"].replace(
             "au_qld_lot16_power.json", "au_qld_3laurel.json"))),
        ("owner-preflight-wrong-session", "PREFLIGHT_STATUS.json",
         lambda x: x[0].update(report=x[0]["report"].replace(
             "20261016_172712", "20261016_172713"))),
        ("owner-preflight-unredacted", "PREFLIGHT_STATUS.json",
         lambda x: x[0].update(report="C:\\Users\\private\\project.json")),
        ("owner-output-folder-other-project", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][0].update(
             output_folder=x["project_handoffs"][0]["output_folder"].replace(
                 "\\project_outputs\\au_qld_lot16_power",
                 "\\project_outputs\\au_qld_3laurel"))),
        ("owner-output-folder-bad-session", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][0].update(
             output_folder=x["project_handoffs"][0]["output_folder"].replace(
                 "20261016_172712", "20261016_172715"))),
        ("owner-output-folder-not-redacted", "RUN_RECEIPT.json",
         lambda x: x["project_handoffs"][0].update(output_folder="C:\\private\\lot16")),
        ("producer-sealed-source-status", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(status="candidate")),
        ("producer-unsealed-fake-status", "au_qld_3laurel/outputs/production_summary.json",
         lambda x: x.update(status="sealed")),
        ("producer-unsealed-fake-runid", "au_qld_3laurel/outputs/production_summary.json",
         lambda x: x.update(combined_run_id="source_closed_run_forged")),
        ("producer-family-positive-no-receipt", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(family_run_files={}, family_run_ids={})),
        ("producer-family-name-mismatch", "au_qld_lot16_power/outputs/production_summary.json",
         lambda x: x.update(family_run_files={"opening_count":
               x["family_run_files"]["opening_area"]},
               family_run_ids={"opening_count":x["family_run_ids"]["opening_area"]})),
    ],
    ids=lambda x: x[0] if type(x) is tuple else None,
)
def test_owner_execution_session_and_seal_family_universe_negatives(
    tmp_path, mutation,
):
    _, relative, change = mutation
    _expect_semantic_conflict(tmp_path, relative, change)


def test_original_signed_lot16_customer_and_family_are_not_relabelled_firm():
    audit_result = audit.verify_owner_four_job_receipts(_ROOT)
    assert audit_result["official_four_project_precision_adjusted_accuracy"] is None
    by_project = {row["project_id"]: row for row in audit_result["projects"]}
    lot16 = by_project["au_qld_lot16_power"]
    assert lot16["derived_sealed_quantity_count"] == 8
    assert lot16["verified_customer_rows_in_run"] == 0
    assert lot16["earliest_verified_project_execution_gate"] == (
        "multidocument_original_source_production_not_complete"
    )
    assert lot16["original_source_package_document_count"] == 2
    assert lot16["producer_primary_source_document_count"] == 1
    assert lot16["fresh_customer_bijection_verified"] is False
    assert set(audit_result["cross_semantic_signed_object_claims_for_review"]) == set(_PROJECTS)
    assert all(audit_result["cross_semantic_signed_object_claims_for_review"][pid] == []
               for pid in _PROJECTS)


def test_cross_semantic_claims_ignore_raw_evidence_order_not_identity():
    from types import SimpleNamespace
    def record(qid, family, refs):
        return SimpleNamespace(
            quantity_id=qid, family=family, source_sha256="f"*64,
            revision_id="rev", object_identity_refs=refs,
        )
    claims = audit._cross_semantic_source_claims([
        record("a", "floor_area", ("B", "A")),
        record("b", "floor_finish_area", ("A", "B")),
    ])
    assert len(claims) == 1
    assert claims[0]["signed_quantity_ids"] == ["a", "b"]
    assert claims[0]["canonical_object_refs"] == ["A", "B"]


def test_unindexed_symlink_to_private_folder_is_rejected_even_if_no_file_is_indexed(tmp_path):
    root = _copy(tmp_path)
    outside = tmp_path / "unrelated-private-folder"
    outside.mkdir()
    (outside / "sensitive.txt").write_text("synthetic not actual client material", encoding="utf-8")
    (root / "external-source-folder").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="untrusted symlink"):
        audit.verify_owner_four_job_receipts(root)


def test_original_owner_archive_has_exact_unindexed_byte_policy():
    policy = _ROOT / ".gitattributes"
    assert policy.read_bytes() == b"* -text\n"
    audit_result = audit.verify_owner_four_job_receipts(_ROOT)
    assert audit_result["independently_verified_share_safe_derived_file_count"] == 28
    assert audit_result["independently_verified_sha256sums_entries"] == 31


@pytest.mark.parametrize("raw", [b"* text\n", b"* -text", b"* -text\n# rogue\n", b""])
def test_modified_unindexed_gitattributes_policy_is_rejected(tmp_path, raw):
    root = _copy(tmp_path)
    (root / ".gitattributes").write_bytes(raw)
    with pytest.raises(ValueError, match="byte-preservation policy"):
        audit.verify_owner_four_job_receipts(root)


def test_other_unindexed_git_like_policy_is_not_whitelisted(tmp_path):
    root = _copy(tmp_path)
    (root / ".gitignore").write_text("private-files\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unindexed artifact"):
        audit.verify_owner_four_job_receipts(root)


def test_owner_lot16_live_v1_is_checked_against_historical_customer_provenance():
    result = audit.verify_owner_four_job_receipts(_ROOT)
    comparison = result["historical_lot16_v1_source_customer_retention"]
    assert comparison["historical_quantity_count"] == 8
    assert comparison["candidate_quantity_count"] == 8
    assert comparison["archived_customer_verified"] is True
    assert comparison["candidate_customer_verified"] is False
    assert comparison["safe_to_reuse_archived_customers_with_candidate"] is False
    assert comparison["source_issuer_scope_attestation_proven"] is False
    assert comparison["new_firm_quantities_authorized"] == 0
    assert comparison["receipt_status_counts"] == {
        "SNAPSHOT_RECEIPT_REKEY_UNATTESTED": 8
    }
    assert result["official_four_project_coverage_accuracy"] is None


def test_owner_lot16_snapshot_rekeys_never_implicitly_authorize_commercial_reuse():
    result = audit.verify_owner_four_job_receipts(_ROOT)
    replay = result["historical_lot16_v1_source_customer_retention"]
    assert len(replay["quantity_differences"]) == 8
    assert all(row["issuer_attestation_required"] for row in replay["quantity_differences"])
    assert not replay["historical_v1_byte_exact"]
    assert replay["publication_status"] == "DIAGNOSTIC_UNPUBLISHED"


def test_original_source_preflight_does_not_masquerade_as_all_pdf_producer_execution():
    receipt = audit.verify_owner_four_job_receipts(_ROOT)
    rows = {row["project_id"]: row for row in receipt["projects"]}
    assert rows["au_qld_lot16_power"]["original_source_package_document_count"] == 2
    assert rows["au_qld_lot16_power"]["producer_primary_source_document_count"] == 1
    assert rows["au_qld_lot16_power"]["earliest_verified_project_execution_gate"] == (
        "multidocument_original_source_production_not_complete"
    )
    assert rows["au_qld_q5446_armstrong32_harlequin"][
        "original_source_package_document_count"
    ] == 6
    assert rows["au_qld_q5446_armstrong32_harlequin"][
        "earliest_verified_project_execution_gate"
    ] == "source_producer_unsealed:source_complexity_blocked"
    assert rows["au_qld_maryborough_service_station"][
        "earliest_verified_project_execution_gate"
    ] == "owner_process_stopped:MEMORY_LIMIT"
    assert receipt["official_four_project_coverage_accuracy"] is None


def test_original_four_projects_produce_distinct_source_first_authority_gates():
    result = audit.verify_owner_four_job_receipts(_ROOT)
    rows = {row["project_id"]: row for row in result["projects"]}
    assert result["official_publication_status"] == "UNPUBLISHED"
    assert rows["au_qld_lot16_power"]["remaining_gates_in_execution_order"][0] == (
        "multidocument_original_source_production_not_complete"
    )
    assert rows["au_qld_lot16_power"]["authority_stage_statuses"][
        "signed_v1_quantity_receipt"
    ] == "VERIFIED_DERIVED_BYTES"
    assert rows["au_qld_3laurel"]["remaining_gates_in_execution_order"][0] == (
        "source_producer_unsealed:no_sealable_quantities"
    )
    assert rows["au_qld_maryborough_service_station"][
        "remaining_gates_in_execution_order"
    ][0] == "owner_process_stopped:MEMORY_LIMIT"
    assert rows["au_qld_maryborough_service_station"][
        "authority_stage_statuses"
    ]["producer_process_completion"] == "BLOCKED"
    assert rows["au_qld_q5446_armstrong32_harlequin"][
        "remaining_gates_in_execution_order"
    ][0] == "source_producer_unsealed:source_complexity_blocked"
    assert all(row["remaining_gate_count"] == len(row["remaining_gates_in_execution_order"])
               for row in result["projects"])
    assert all(row["authority_stage_statuses"]["official_v2_project_score"]
               == "NOT_EVALUATED" for row in result["projects"])


def test_old_original_owner_source_sha_preflight_is_not_independent_private_pdf_rehash():
    result = audit.verify_owner_four_job_receipts(_ROOT)
    for project in result["projects"]:
        status = project["authority_stage_statuses"]
        assert status["owner_original_pdf_sha_preflight"] == "OWNER_REPORTED_VERIFIED"
        assert status["independent_private_pdf_sha_rehash"] == "NOT_PERFORMED"
        assert status["physical_identity_map"] == "NOT_SUPPLIED_IN_OWNER_RECEIPT"
        assert status["fresh_customer_bijection"] == "NOT_VERIFIED"
        assert status["frozen_project_manifest"] == "INCOMPLETE"
        assert project["official_project_score"] is None


def test_owner_receipt_diagnostic_can_repeat_only_its_own_report(tmp_path):
    report = tmp_path / "readiness.json"
    args = ["--receipt-root", str(_ROOT), "--output", str(report)]
    assert audit.main(args) == 2
    original = report.read_bytes()
    assert audit.main(args) == 2
    assert report.read_bytes() == original


def test_owner_receipt_diagnostic_must_never_overwrite_customer_or_binary(tmp_path):
    evidence = tmp_path / "customer_rows.json"
    original = b'{"customer_quantity_id":"original-stays"}\n'
    evidence.write_bytes(original)
    with pytest.raises(ValueError, match="cannot replace unrelated evidence"):
        audit.main([
            "--receipt-root", str(_ROOT), "--output", str(evidence),
        ])
    assert evidence.read_bytes() == original
    evidence.write_bytes(b"sealed-binary-do-not-replace")
    with pytest.raises(ValueError, match="cannot replace unrelated evidence"):
        audit.main(["--receipt-root", str(_ROOT), "--output", str(evidence)])
    assert evidence.read_bytes() == b"sealed-binary-do-not-replace"


def test_owner_receipt_diagnostic_rejects_existing_symlink_even_outside_sources(tmp_path):
    target = tmp_path / "original_synthetic_customer.json"
    target.write_text("DO NOT TOUCH", encoding="utf-8")
    alias = tmp_path / "alias.json"
    alias.symlink_to(target)
    with pytest.raises(ValueError, match="cannot follow output symlinks"):
        audit.main([
            "--receipt-root", str(_ROOT), "--output", str(alias),
        ])
    assert target.read_text(encoding="utf-8") == "DO NOT TOUCH"


def test_3laurel_completed_source_page_traversal_is_not_source_closed_authority():
    receipt = audit.verify_owner_four_job_receipts(_ROOT)
    by_id = {entry["project_id"]: entry for entry in receipt["projects"]}
    laurel = by_id["au_qld_3laurel"]
    assert laurel["producer_process_completed"] is True
    assert laurel["authority_stage_statuses"]["all_original_documents_processed"] == (
        "ONE_SOURCE_ALL_PAGES_EXECUTED_NOT_AUTHENTICATED"
    )
    assert laurel["authority_stage_statuses"]["signed_v1_quantity_receipt"] == (
        "NOT_AVAILABLE"
    )
    assert laurel["four_job_official_target_item_results_available"] is False
    assert laurel["official_project_score"] is None


def test_owner_audit_fingerprint_pins_unchanged_old_eight_and_frozen_source_files():
    result = audit.verify_owner_four_job_receipts(_ROOT)
    originals = result["historical_lot16_v1_and_customer_file_sha256s"]
    archive = (
        Path(__file__).resolve().parents[1]
        / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    )
    assert set(originals) == {"source_sealed_run.json", "verified_customer_rows.json"}
    assert originals == {name: _sha(archive / name) for name in originals}
    frozen = result["frozen_source_evaluator_file_sha256s"]
    assert len(frozen) == 11
    assert all(len(digest) == 64 for digest in frozen.values())
    assert "evaluator.py" in frozen
    assert "sealed_reconciliation.py" in frozen
    assert "manifest.json" in frozen
    assert "projects/au_qld_lot16_power/source_manifest.json" in frozen
    assert "projects/au_qld_lot16_power/reference_takeoff.json" in frozen
    assert len([key for key in frozen if key.endswith("/reference_takeoff.json")]) == 4
    assert len(result["reconciled_derived_artifact_fingerprint"]) == 64
    assert result["official_four_project_coverage_accuracy"] is None


def test_owner_audit_changes_fingerprint_when_untrusted_derived_receipts_are_rehashed(tmp_path):
    before = audit.verify_owner_four_job_receipts(_ROOT)
    root = _copy(tmp_path)
    original = "au_qld_lot16_power/outputs/production_summary.json"
    _mutate(root, original, lambda x: x["claim_reason_codes"].append(
        "synthetic_new_source_reason_not_a_quantity"
    ))
    _recalculate_synthetic_derived_receipts(root)
    after = audit.verify_owner_four_job_receipts(root)
    assert before["reconciled_derived_artifact_fingerprint"] != (
        after["reconciled_derived_artifact_fingerprint"]
    )
    assert before["historical_lot16_v1_and_customer_file_sha256s"] == (
        after["historical_lot16_v1_and_customer_file_sha256s"]
    )
    assert after["official_publication_status"] == "UNPUBLISHED"


def test_owner_diagnostic_cannot_write_into_historical_lot16_signed_archive():
    archive = audit._HISTORICAL_LOT16_ROOT
    target = archive / "SOURCE_RECONCILIATION_DIAGNOSTIC_DO_NOT_CREATE.json"
    assert not target.exists()
    with pytest.raises(ValueError, match="cannot overwrite evidence"):
        audit.main([
            "--receipt-root", str(_ROOT), "--output", str(target),
        ])
    assert not target.exists()


def test_owner_diagnostic_cannot_replace_historical_lot16_signed_customer_rows():
    original = audit._HISTORICAL_LOT16_ROOT / "verified_customer_rows.json"
    digest_before = _sha(original)
    with pytest.raises(ValueError, match="cannot overwrite evidence"):
        audit.main([
            "--receipt-root", str(_ROOT), "--output", str(original),
        ])
    assert _sha(original) == digest_before
