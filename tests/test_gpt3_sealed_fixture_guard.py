"""Adversarial review-only GPT3 archive tests: 100 independently mutated receipts.

The fixed source fixture is NOT benchmark truth, and mutations never change it.
After each mutation the test reissues SHA256SUMS to prove that checksum-only
validation does not substitute for the signed V1/customer/identity contracts.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from tools.diag_gpt3_sealed_fixture_guard import (
    EvidencePackageError,
    FILES,
    verify_archived_package,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015"
CUSTOMER = "production/verified_customer_rows.json"
MAPPING = "identity_map_with_1215.json"
REPORT = "exact_project_report.json"


def _copy(tmp_path: Path) -> Path:
    destination = tmp_path / "package"
    shutil.copytree(FIXTURE, destination)
    return destination


def _resign_manifest_only(root: Path, filename: str, payload) -> None:
    path = root / filename
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = (root / "SHA256SUMS").read_text().splitlines()
    digest = sha256(path.read_bytes()).hexdigest()
    rewritten = [
        f"{digest} *{filename}" if line.endswith(" *" + filename) else line
        for line in lines
    ]
    (root / "SHA256SUMS").write_text("\n".join(rewritten) + "\n")


CUSTOMER_MUTATIONS = ("quantity", "quantity_id", "inclusion_status", "source_sha256")
MAP_MUTATIONS = ("production_family", "production_object_identity_refs", "benchmark_item_id")
REPORT_MUTATIONS = ("quantity_id", "value", "lineage_ok", "abstained")
REPORT_META = (
    "project_id", "sealed_run_fingerprint", "source_sha256s",
    "source_sha_verified", "reconciliation_complete", "denominator",
    "matched_within_tolerance", "missed", "matched_outside_tolerance",
    "partial", "unresolved", "unsupported_extra",
)
CASES = (
    [("customer", index, field) for field in CUSTOMER_MUTATIONS for index in range(8)]
    + [("mapping", index, field) for field in MAP_MUTATIONS for index in range(8)]
    + [("report", index, field) for field in REPORT_MUTATIONS for index in range(8)]
    + [("metadata", 0, field) for field in REPORT_META]
)
assert len(CASES) == 100


def _mutate(case: tuple[str, int, str], root: Path) -> None:
    group, index, field = case
    file = {"customer": CUSTOMER, "mapping": MAPPING,
            "report": REPORT, "metadata": REPORT}[group]
    data = json.loads((root / file).read_text())
    if group == "customer":
        row = data[index]
        if field == "quantity":
            row[field] += 0.25
        elif field == "quantity_id":
            row[field] = "foreign-gpt3-customer-quantity"
        elif field == "inclusion_status":
            row[field] = "APPROVED"
        else:
            row[field] = "f" * 64
    elif group == "mapping":
        row = data["bindings"][index]
        if field == "production_family":
            row[field] = "wall_length"
        elif field == "production_object_identity_refs":
            row[field] = ["foreign-physical-opening-identity"]
        else:
            row[field] = data["bindings"][1 if index == 0 else 0][field]
    elif group == "report":
        row = data["produced_items"][index]
        if field == "quantity_id":
            row[field] = "foreign-produced-item"
        elif field == "value":
            row[field] += 0.25
        elif field == "lineage_ok":
            row[field] = False
        else:
            row[field] = True
    else:
        replacements = {
            "project_id": "foreign-project",
            "sealed_run_fingerprint": "f" * 64,
            "source_sha256s": ["f" * 64],
            "source_sha_verified": False,
            "reconciliation_complete": False,
            "denominator": 28,
            "matched_within_tolerance": 9,
            "missed": 18,
            "matched_outside_tolerance": 1,
            "partial": 1,
            "unresolved": 1,
            "unsupported_extra": 1,
        }
        data[field] = replacements[field]
    _resign_manifest_only(root, file, data)


def test_original_fixture_reports_only_an_unsigned_review():
    review = verify_archived_package(FIXTURE)
    assert review["status"] == "UNSIGNED_REVIEW_ONLY"
    assert review["signed_v2_scope_granted"] is False
    assert review["full_suite_score_granted"] is False
    assert review["customer_commercial_approval_granted"] is False
    assert review["signed_quantity_count"] == review["verified_customer_row_count"] == 8
    assert review["unique_postseal_identity_bindings"] == 8


@pytest.mark.parametrize(
    "case", CASES,
    ids=[f"{group}-{index}-{field}" for group, index, field in CASES],
)
def test_100_distinct_resigned_manifest_tamper_variants_fail_closed(case, tmp_path):
    root = _copy(tmp_path)
    _mutate(case, root)
    with pytest.raises(EvidencePackageError):
        verify_archived_package(root)


@pytest.mark.parametrize("filename", FILES)
def test_mutation_with_old_sha_manifest_is_rejected(filename, tmp_path):
    root = _copy(tmp_path)
    with (root / filename).open("ab") as output:
        output.write(b" ")
    with pytest.raises(EvidencePackageError, match="SHA mismatch"):
        verify_archived_package(root)


@pytest.mark.parametrize("unsafe", [
    "../../escape.json",
    "/tmp/absolute-source.json",
    "production/../source_sealed_run.json",
    "production\\source_sealed_run.json",
    "production/source_sealed_run.json",
])
def test_unknown_or_duplicate_digest_manifest_path_is_rejected(unsafe, tmp_path):
    root = _copy(tmp_path)
    with (root / "SHA256SUMS").open("a") as output:
        output.write("f" * 64 + " *" + unsafe + "\n")
    with pytest.raises(EvidencePackageError, match="unknown or duplicate"):
        verify_archived_package(root)


def test_fixture_root_symlink_is_refused(tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(FIXTURE, target_is_directory=True)
    with pytest.raises(EvidencePackageError, match="real directory"):
        verify_archived_package(alias)


@pytest.mark.parametrize("filename", FILES)
def test_symlinked_evidence_file_is_refused(filename, tmp_path):
    root = _copy(tmp_path)
    link = root / filename
    real = tmp_path / "original"
    real.write_bytes(link.read_bytes())
    link.unlink()
    link.symlink_to(real)
    with pytest.raises(EvidencePackageError, match="symlink"):
        verify_archived_package(root)


def test_input_order_of_customer_rows_does_not_affect_signed_bijection(tmp_path):
    root = _copy(tmp_path)
    customers = json.loads((root / CUSTOMER).read_text())
    _resign_manifest_only(root, CUSTOMER, list(reversed(customers)))
    review = verify_archived_package(root)
    assert review["status"] == "UNSIGNED_REVIEW_ONLY"
    assert review["signed_quantity_count"] == 8


def test_input_order_of_postseal_bindings_does_not_create_new_authority(tmp_path):
    root = _copy(tmp_path)
    mapping = json.loads((root / MAPPING).read_text())
    mapping["bindings"].reverse()
    _resign_manifest_only(root, MAPPING, mapping)
    review = verify_archived_package(root)
    assert review["signed_v2_scope_granted"] is False
    assert review["unique_postseal_identity_bindings"] == 8
