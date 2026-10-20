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
