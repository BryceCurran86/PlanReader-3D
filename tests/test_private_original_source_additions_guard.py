"""A source-only PR must never upload owner/client original payloads."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_private_original_source_additions import (
    blocked_source_additions,
)

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "check_private_original_source_additions.py"


@pytest.mark.parametrize("path", [
    "documents/sources/Architectural.pdf",
    "documents/sources/Room.png",
    "documents/sources/private_survey.dwg",
    "benchmarks/sources/original.pdf",
    "DOCUMENTS\\SOURCES\\original.PDF",
    "documents/sources/nested/original.jpg",
])
def test_original_customer_source_additions_are_blocked(path):
    assert blocked_source_additions([path]) == (path,)


@pytest.mark.parametrize("path", [
    "benchmarks/frozen_holdout/full_plan_v2/projects/example/source_manifest.json",
    "docs/PRIVATE_ORIGINAL_SOURCES.md",
    "tests/fixtures/synthetic_plan.pdf",
    ".gitignore",
    "documents/README.md",
])
def test_hash_manifests_and_synthetic_test_fixtures_remain_allowed(path):
    assert blocked_source_additions([path]) == ()


@pytest.mark.parametrize("path", [
    "/documents/sources/x.pdf",
    "documents/../documents/sources/x.pdf",
    "documents//sources/x.pdf",
    "C:\\documents\\sources\\x.pdf",
    "",
])
def test_malformed_scope_never_bypasses_private_source_guard(path):
    with pytest.raises(ValueError):
        blocked_source_additions([path])


def test_git_diff_null_delimited_original_file_with_spaces_is_blocked():
    changed = b"docs/a.md\\0documents/sources/Original Drawing.pdf\\0"
    p = subprocess.run(
        [sys.executable, str(GUARD)],
        input=changed.replace(b"\\0", b"\x00"),
        capture_output=True,
    )
    assert p.returncode == 1
    assert b"Original Drawing.pdf" in p.stderr


def test_private_source_deletions_are_not_in_added_modified_renamed_path_list():
    # CI supplies git diff --diff-filter=AMRC; deletion-only change gives
    # an EMPTY filename stream and is allowed for confidential removal.
    p = subprocess.run(
        [sys.executable, str(GUARD)],
        input=b"",
        capture_output=True,
    )
    assert p.returncode == 0


def test_original_source_normal_changes_pass_in_separate_non_source_pr():
    p = subprocess.run(
        [sys.executable, str(GUARD)],
        input=b"pb_room_area_quantity.py\x00tests/test_synthetic.py\x00",
        capture_output=True,
    )
    assert p.returncode == 0



@pytest.mark.parametrize("path", [
    ".env", ".ENV", ".env.production", "app/.env.local",
    "credentials/private.pem", "certs/client.PFX", "secrets/cert.p12",
    "secrets/client.p8", "credentials/runtime.jks",
    "config/id_rsa", "config/id_ed25519", "client/.npmrc",
    "work/source-originals/Original_Drawings.pdf",
    "output/.private-sources/client_survey.dwg",
    "OUTPUT\\.PRIVATE-SOURCES\\client_details.pdf",
])
def test_public_push_rejects_secret_key_and_private_source_alias_paths(path):
    assert blocked_source_additions([path]) == (path,)


@pytest.mark.parametrize("path", [
    ".env.example", "docs/example.env.txt", ".github/workflows/ci.yml",
    "tests/fixtures/synthetic_benchmark_plan.pdf",
    "benchmarks/frozen_holdout/full_plan_v2/projects/demo/source_manifest.json",
    "tests/fixtures/fake-private-source-rejection.json",
    "docs/PRIVATE_ORIGINAL_SOURCES.md",
])
def test_future_public_source_guard_keeps_safe_manifests_and_synthetic_tests(path):
    assert blocked_source_additions([path]) == ()


def test_null_delimited_cli_blocked_secret_and_allowed_manifest(tmp_path):
    changed = (
        b"benchmarks/frozen_holdout/full_plan_v2/projects/p/source_manifest.json\x00"
        b"app/.env.production\x00"
    )
    result = subprocess.run([sys.executable, str(GUARD)],
                            input=changed, capture_output=True)
    assert result.returncode == 1
    assert b".env.production" in result.stderr
    assert b"source_manifest.json" not in result.stderr
