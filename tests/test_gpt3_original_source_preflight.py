"""Missing originals are SOURCE_BLOCKED; wrong bytes fail closed; never succeed."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from tools.gpt3_original_source_preflight import (
    ORIGINAL_PDF_ABSENT,
    SOURCE_BLOCKED,
    SOURCE_MISMATCH,
    SOURCE_PRESENT,
    classify_original_source_preflight,
    main,
)

EXPECTED = "a" * 64
ROOT = Path(__file__).resolve().parents[1]
LOT16_WORKFLOW = ROOT / ".github/workflows/score-gpt3-lot16-1215-opening-local.yml"
MARY_WORKFLOW = ROOT / ".github/workflows/test-gpt3-maryborough-original-floor-score-input.yml"
LOT16_SEAL_WORKFLOW = ROOT / ".github/workflows/test-gpt3-lot16-original-sealed-score-input.yml"
LOT16_PDF = "1. Construction Plans - Lot 16 Power (REV E).pdf"
MARY_PDF = "Arch_Combined_Maryborough_Service_Station.pdf"
REMAINING_ORIGINAL_JOBS = (
    (ROOT / ".github/workflows/diag-gpt3-lot16-1215-identity-readiness.yml", LOT16_PDF, False),
    (ROOT / ".github/workflows/diag-gpt3-lot16-internal-870-identity-readiness.yml", LOT16_PDF, False),
    (ROOT / ".github/workflows/diag-gpt3-maryborough-ft3-source-firstgate.yml", MARY_PDF, False),
    (ROOT / ".github/workflows/gpt3-original-opening-customer-inventory.yml", LOT16_PDF, False),
    (ROOT / ".github/workflows/test-gpt3-1215-opening-local-retention.yml", LOT16_PDF, True),
    (ROOT / ".github/workflows/test-gpt3-1215-paired-customer-retention.yml", LOT16_PDF, True),
    (ROOT / ".github/workflows/test-gpt3-1215-room-face-owned-retention.yml", LOT16_PDF, True),
    (ROOT / ".github/workflows/test-gpt3-native-dimension-original-source-cache.yml", LOT16_PDF, True),
    (ROOT / ".github/workflows/test-gpt3-original-scope-v1-consumer.yml", LOT16_PDF, False),
    (ROOT / ".github/workflows/test-gpt3-raster-source-discovery.yml", LOT16_PDF, True),
    (ROOT / ".github/workflows/test-gpt3-source-frame-proof.yml", LOT16_PDF, True),
)


def test_missing_pdf_is_source_blocked_not_success(tmp_path: Path) -> None:
    missing = tmp_path / "absent.pdf"
    receipt = classify_original_source_preflight(missing, EXPECTED)
    assert receipt["status"] == SOURCE_BLOCKED
    assert receipt["reason"] == ORIGINAL_PDF_ABSENT
    assert receipt["benchmark_score_granted"] is False
    assert receipt["original_source_verified"] is False
    assert main(["--pdf", str(missing), "--expected-sha256", EXPECTED]) == 2


def test_wrong_digest_fails_closed(tmp_path: Path) -> None:
    pdf = tmp_path / "plan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    receipt = classify_original_source_preflight(pdf, EXPECTED)
    assert receipt["status"] == SOURCE_MISMATCH
    assert receipt["original_source_verified"] is False
    assert receipt["benchmark_score_granted"] is False
    assert main(["--pdf", str(pdf), "--expected-sha256", EXPECTED]) == 1


def test_matching_digest_is_present_only(tmp_path: Path) -> None:
    pdf = tmp_path / "plan.pdf"
    payload = b"%PDF-1.4 matching-bytes"
    pdf.write_bytes(payload)
    digest = sha256(payload).hexdigest()
    receipt = classify_original_source_preflight(pdf, digest)
    assert receipt["status"] == SOURCE_PRESENT
    assert receipt["original_source_verified"] is True
    assert receipt["benchmark_score_granted"] is False
    assert main(["--pdf", str(pdf), "--expected-sha256", digest]) == 0


def test_invalid_expected_digest_is_rejected(tmp_path: Path) -> None:
    pdf = tmp_path / "plan.pdf"
    pdf.write_bytes(b"x")
    with pytest.raises(ValueError):
        classify_original_source_preflight(pdf, "not-a-sha")


def _assert_provision_before_preflight(path: Path, pdf_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    provision = text.index("uses: ./.github/actions/provision-original-sources")
    preflight = text.index("python -m tools.gpt3_original_source_preflight")
    assert provision < preflight
    assert pdf_name in text
    assert "allow-missing: true" not in text
    assert "allow-missing: 'true'" not in text
    assert "secrets.ORIGINAL_SOURCES_TOKEN" in text


def test_lot16_original_source_job_provisions_then_classifies() -> None:
    _assert_provision_before_preflight(
        LOT16_WORKFLOW,
        "1. Construction Plans - Lot 16 Power (REV E).pdf",
    )


def test_maryborough_original_source_job_provisions_then_classifies() -> None:
    _assert_provision_before_preflight(
        MARY_WORKFLOW,
        "Arch_Combined_Maryborough_Service_Station.pdf",
    )


def test_lot16_sealed_original_job_provisions_then_classifies() -> None:
    text = LOT16_SEAL_WORKFLOW.read_text(encoding="utf-8")
    provision = text.index("uses: ./.github/actions/provision-original-sources")
    classify = text.index("classify_original_source_preflight")
    assert provision < classify
    assert "1. Construction Plans - Lot 16 Power (REV E).pdf" in text
    assert "allow-missing: true" not in text
    assert "secrets.ORIGINAL_SOURCES_TOKEN" in text


@pytest.mark.parametrize("path,pdf_name,copies_into_worktree", REMAINING_ORIGINAL_JOBS)
def test_remaining_gpt3_original_jobs_provision_then_classify(
    path: Path, pdf_name: str, copies_into_worktree: bool
) -> None:
    _assert_provision_before_preflight(path, pdf_name)
    text = path.read_text(encoding="utf-8")
    if copies_into_worktree:
        copy_at = text.index("python scripts/copy_provisioned_originals_into_worktree.py")
        provision = text.index("uses: ./.github/actions/provision-original-sources")
        assert provision < copy_at
    else:
        assert "python scripts/copy_provisioned_originals_into_worktree.py" not in text


def test_four_project_fail_closed_inventory_is_not_provisioned() -> None:
    text = (
        ROOT / ".github/workflows/test-gpt3-four-project-evidence.yml"
    ).read_text(encoding="utf-8")
    assert "provision-original-sources" not in text
    assert "original_source_not_supplied_in_this_execution" in text
    assert "python -m tools.gpt3_original_source_preflight" not in text
