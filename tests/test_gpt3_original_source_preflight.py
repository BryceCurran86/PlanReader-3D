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
    always = text.index("if: always()", provision)
    preflight = text.index("python3 -m tools.gpt3_original_source_preflight", provision)
    assert provision < always < preflight
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
    _assert_provision_before_preflight(
        LOT16_SEAL_WORKFLOW,
        "1. Construction Plans - Lot 16 Power (REV E).pdf",
    )
    text = LOT16_SEAL_WORKFLOW.read_text(encoding="utf-8")
    always = text.index("if: always()")
    producer = text.index("tools.run_gpt3_lot16_original_sealed_score_input")
    assert always < producer


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


def test_selected_two_originals_classify_always_runs() -> None:
    _assert_provision_before_preflight(
        ROOT / ".github/workflows/score-gpt3-selected-two-original-projects.yml",
        LOT16_PDF,
    )
    text = (
        ROOT / ".github/workflows/score-gpt3-selected-two-original-projects.yml"
    ).read_text(encoding="utf-8")
    assert MARY_PDF in text


def test_four_project_fail_closed_inventory_is_not_provisioned() -> None:
    text = (
        ROOT / ".github/workflows/test-gpt3-four-project-evidence.yml"
    ).read_text(encoding="utf-8")
    assert "provision-original-sources" not in text
    assert "original_source_not_supplied_in_this_execution" in text
    assert "python -m tools.gpt3_original_source_preflight" not in text


def test_preflight_receipt_output_create_only_and_source_unchanged(tmp_path: Path) -> None:
    """Source-backed status may create a new report, never overwrite one."""
    source = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-private-original")
    digest = sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "reports" / "source-check.json"
    assert main(["--pdf", str(source), "--expected-sha256", digest,
                 "--output", str(destination)]) == 0
    before = destination.read_bytes()
    assert b'"status": "SOURCE_PRESENT"' in before
    with pytest.raises(FileExistsError):
        main(["--pdf", str(source), "--expected-sha256", digest,
              "--output", str(destination)])
    assert destination.read_bytes() == before
    assert source.read_bytes() == b"%PDF-private-original"
    assert not list(destination.parent.glob(".gpt3-original-report-*.tmp"))


def test_preexisting_and_alias_destinations_fail_before_private_original_read(
    tmp_path: Path, monkeypatch,
) -> None:
    from tools import gpt3_original_source_preflight as preflight
    original = tmp_path / "source.pdf"
    original.write_bytes(b"%PDF-original-private-bytes")
    signed = tmp_path / "signed.json"
    signed.write_text('{"protected":"yes"}', encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(signed)
    def forbidden(*args, **kwargs):
        raise AssertionError("private original read before output preflight")
    monkeypatch.setattr(preflight, "classify_original_source_preflight", forbidden)
    for target in (signed, link, original):
        with pytest.raises((FileExistsError, ValueError)):
            preflight.main(["--pdf", str(original),
                            "--expected-sha256", "a" * 64,
                            "--output", str(target)])
    assert original.read_bytes() == b"%PDF-original-private-bytes"
    assert signed.read_text(encoding="utf-8") == '{"protected":"yes"}'


def test_frozen_and_approved_archive_roots_never_accept_new_preflight_report() -> None:
    from tools import gpt3_original_source_preflight as preflight
    repo = Path(preflight.__file__).resolve().parents[1]
    for path in (
        repo / "benchmarks/frozen_holdout/full_plan_v2/unsafe-preflight.json",
        repo / "docs/engineering/unsafe-preflight.json",
        repo / "documents/sources/unsafe-preflight.json",
    ):
        assert not path.exists()
        with pytest.raises(ValueError, match="protected evidence"):
            preflight.main([
                "--pdf", str(repo / "documents/sources/private-missing.pdf"),
                "--expected-sha256", "a" * 64,
                "--output", str(path),
            ])
        assert not path.exists()


def test_competing_writer_does_not_get_overwritten_by_source_preflight(
    tmp_path: Path, monkeypatch,
) -> None:
    from tools import gpt3_safe_original_report_output as publish
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.5")
    output = tmp_path / "report.json"
    actual_link = publish.os.link
    def conflicting_link(source, dest):
        Path(dest).write_text('{"someone_else":"owns_this"}', encoding="utf-8")
        return actual_link(source, dest)
    monkeypatch.setattr(publish.os, "link", conflicting_link)
    with pytest.raises(FileExistsError):
        main(["--pdf", str(original),
              "--expected-sha256", sha256(original.read_bytes()).hexdigest(),
              "--output", str(output)])
    assert output.read_text(encoding="utf-8") == '{"someone_else":"owns_this"}'
    assert original.read_bytes() == b"%PDF-1.5"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_original_mutation_while_staging_removes_unpublished_source_present(
    tmp_path: Path, monkeypatch,
) -> None:
    from tools import gpt3_safe_original_report_output as publish
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-original")
    expected = sha256(original.read_bytes()).hexdigest()
    output = tmp_path / "report.json"
    actual_link = publish.os.link
    def mutate_before_publish(source, dest):
        original.write_bytes(b"%PDF-mutated")
        return actual_link(source, dest)
    monkeypatch.setattr(publish.os, "link", mutate_before_publish)
    with pytest.raises(ValueError, match="original source changed"):
        main(["--pdf", str(original), "--expected-sha256", expected,
              "--output", str(output)])
    assert not output.exists()
    assert original.read_bytes() == b"%PDF-mutated"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_missing_original_receipt_refuses_race_with_new_source(
    tmp_path: Path, monkeypatch,
) -> None:
    from tools import gpt3_safe_original_report_output as publish
    original = tmp_path / "missing.pdf"
    output = tmp_path / "report.json"
    actual_link = publish.os.link
    def create_source_before_publish(source, dest):
        original.write_bytes(b"%PDF-new")
        return actual_link(source, dest)
    monkeypatch.setattr(publish.os, "link", create_source_before_publish)
    with pytest.raises(ValueError, match="original source appeared"):
        main(["--pdf", str(original), "--expected-sha256", "a" * 64,
              "--output", str(output)])
    assert not output.exists()
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


@pytest.mark.parametrize("kind", ["directory", "symlink", "dangling_symlink"])
def test_nonregular_original_path_is_not_misreported_as_missing(
    tmp_path: Path, kind: str,
) -> None:
    original = tmp_path / "original.pdf"
    if kind == "directory":
        original.mkdir()
    else:
        target = tmp_path / "other.pdf"
        if kind == "symlink":
            target.write_bytes(b"%PDF-unrelated")
        original.symlink_to(target)
    with pytest.raises(ValueError, match="not a regular file"):
        classify_original_source_preflight(original, EXPECTED)
    assert original.is_symlink() or original.is_dir()


@pytest.mark.parametrize("failure", [PermissionError, OSError])
@pytest.mark.parametrize("initially_present", [False, True])
def test_uninspectable_original_cannot_become_source_blocked(
    tmp_path: Path, monkeypatch, failure, initially_present: bool,
) -> None:
    from tools import gpt3_original_source_preflight as preflight
    original = tmp_path / "private-original.pdf"
    if initially_present:
        original.write_bytes(b"%PDF-unchanged")
    real_lstat = Path.lstat

    def deny_source(self, *args, **kwargs):
        if self == original:
            raise failure("inaccessible original or parent")
        return real_lstat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", deny_source)
    with pytest.raises(ValueError, match="original source path cannot be inspected"):
        classify_original_source_preflight(original, EXPECTED)
    receipt = {
        "status": SOURCE_PRESENT if initially_present else SOURCE_BLOCKED,
        "actual_sha256": sha256(b"%PDF-unchanged").hexdigest(),
    }
    with pytest.raises(ValueError, match="original source path cannot be inspected"):
        preflight._assert_receipt_source_unchanged(original, receipt)


@pytest.mark.parametrize("replacement", ["directory", "dangling_symlink"])
def test_missing_source_nonregular_race_rolls_back_diagnostic(
    tmp_path: Path, monkeypatch, replacement: str,
) -> None:
    from tools import gpt3_safe_original_report_output as publish
    original = tmp_path / "missing-original.pdf"
    output = tmp_path / "report.json"
    actual_link = publish.os.link

    def replace_source_after_link(staged, destination):
        actual_link(staged, destination)
        if replacement == "directory":
            original.mkdir()
        else:
            original.symlink_to(tmp_path / "absent-target.pdf")

    monkeypatch.setattr(publish.os, "link", replace_source_after_link)
    with pytest.raises(ValueError, match="not a regular file"):
        main(["--pdf", str(original), "--expected-sha256", EXPECTED,
              "--output", str(output)])
    assert not output.exists()
    assert original.is_dir() if replacement == "directory" else original.is_symlink()
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_present_source_replaced_with_same_digest_symlink_cannot_publish(
    tmp_path: Path, monkeypatch,
) -> None:
    from tools import gpt3_safe_original_report_output as publish
    original = tmp_path / "original.pdf"
    identical = tmp_path / "identical.pdf"
    payload = b"%PDF-original-unchanged"
    original.write_bytes(payload)
    identical.write_bytes(payload)
    output = tmp_path / "report.json"
    actual_link = publish.os.link

    def replace_source_after_link(staged, destination):
        actual_link(staged, destination)
        original.unlink()
        original.symlink_to(identical)

    monkeypatch.setattr(publish.os, "link", replace_source_after_link)
    with pytest.raises(ValueError, match="not a regular file"):
        main(["--pdf", str(original),
              "--expected-sha256", sha256(payload).hexdigest(),
              "--output", str(output)])
    assert not output.exists()
    assert identical.read_bytes() == payload
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))
