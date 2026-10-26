"""Fail-closed, no-leak diagnostics for owner-private original replay failures."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import gpt2_offline_replay_failure_classification as diag


@pytest.mark.parametrize(("code", "log", "expected"), [
    (125, "Docker daemon error: SECRET_CLIENT_BYTES", diag.CONTAINER_START_FAILURE),
    (126, "exec permission denied: SECRET_CLIENT_BYTES", diag.CONTAINER_EXEC_FAILURE),
    (127, "no executable: SECRET_CLIENT_BYTES", diag.CONTAINER_EXEC_FAILURE),
    (1, "FileNotFoundError: documents/sources/secret-client.pdf", diag.SOURCE_MOUNT_INACCESSIBLE),
    (1, "PermissionError: documents/sources/secret-client.pdf", diag.SOURCE_MOUNT_INACCESSIBLE),
    (1, "ModuleNotFoundError: No module named secret_module", diag.DEPENDENCY_IMPORT_FAILURE),
    (1, "ImportError: cannot import name private_object", diag.DEPENDENCY_IMPORT_FAILURE),
    (4, "ERROR collecting tests/test_x.py", diag.PYTEST_COLLECTION_FAILURE),
    (4, "pytest: error: unrecognized arguments: -x", diag.PYTEST_COLLECTION_FAILURE),
    (1, "FAILED tests/test_x.py::test_y - AssertionError: SECRET_VALUE", diag.SOURCE_TEST_ASSERTION_FAILURE),
    (1, "1 failed, 2 passed in 3.0s", diag.SOURCE_TEST_ASSERTION_FAILURE),
    (1, "SENSITIVE_CLIENT_CONTENT", diag.UNCLASSIFIED_FAILURE),
    (0, "1 passed in 3.0s", diag.NO_FAILURE),
])
def test_exact_safe_reason_only(code, log, expected):
    result = diag.classify_private_failure(code, log)
    assert result == expected
    assert result in diag.PUBLIC_REASON_CODES
    assert "secret" not in result.lower()


@pytest.mark.parametrize("invalid", [True, -1, 1.5, "1", None])
def test_exit_codes_must_be_integral_nonnegative(invalid):
    with pytest.raises(ValueError):
        diag.classify_private_failure(invalid, "PRIVATE")


@pytest.mark.parametrize("private", [
    "Original PDF secret token=ghp_12345",
    "error:: sneaky newline\\nORIGINAL_50000_BYTES",
    "FAILED tests/private.py::original EXTRACTED_PLAN_TEXT",
    "ModuleNotFoundError: SECRET_PRIVATE_MODULE",
])
def test_cli_never_echoes_originals_even_if_private_log_contains_arbitrary_text(tmp_path, capsys, private):
    log = tmp_path / "original-private-data.log"
    log.write_text(private, encoding="utf-8")
    assert diag.main(["--private-log", str(log), "--exit-code", "1"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.strip() in diag.PUBLIC_REASON_CODES
    assert private not in output.out
    assert "PRIVATE" not in output.out
    assert len(output.out) < 80


def test_cli_missing_private_log_never_exposes_path(tmp_path, capsys):
    secret = tmp_path / "confidential-original-pdf-path.pdf"
    assert diag.main(["--private-log", str(secret), "--exit-code", "1"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.strip() == diag.UNCLASSIFIED_FAILURE
    assert str(secret) not in output.out


def test_category_is_not_source_pass_or_quantity_authority():
    assert diag.NO_FAILURE != "original_source_verified"
    assert all("firm" not in reason and "score" not in reason and "passed" not in reason
               for reason in diag.PUBLIC_REASON_CODES)


def test_source_mount_marker_only_matters_in_failure_context():
    assert diag.classify_private_failure(
        1, "some other path missing: /tmp/test.dat"
    ) == diag.UNCLASSIFIED_FAILURE
    assert diag.classify_private_failure(
        1, "FileNotFoundError: documents/sources/private.pdf"
    ) == diag.SOURCE_MOUNT_INACCESSIBLE
