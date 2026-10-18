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


# --- pinned name / exact-bytes rules (synthetic manifest, never real originals) ---

import hashlib
import json

from scripts.check_private_original_source_additions import (
    PINNED_MANIFEST_GLOB,
    load_pinned_originals,
    source_addition_findings,
)

_PINNED_NAME = "Synthetic Client Plans (REV Z).pdf"
_PINNED_BYTES = b"%PDF-1.7 synthetic stand-in for a pinned original\n" * 20


def _write_manifest(root: Path, entries, project="p1"):
    folder = root / PINNED_MANIFEST_GLOB.rsplit("/", 1)[0].replace("*", project)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source_manifest.json").write_text(
        json.dumps({"source_documents": entries}), encoding="utf-8"
    )


def _entry(name=_PINNED_NAME, data=_PINNED_BYTES):
    return {
        "name": name,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


@pytest.fixture
def tree(tmp_path):
    _write_manifest(tmp_path, [_entry()])
    return tmp_path


def _run_cli(root: Path, *paths: str):
    changed = b"".join(p.encode() + b"\x00" for p in paths)
    return subprocess.run(
        [sys.executable, str(GUARD), "--root", str(root)],
        input=changed, capture_output=True,
    )


def test_renamed_original_bytes_are_blocked_at_any_path(tree):
    (tree / "tests" / "fixtures").mkdir(parents=True)
    (tree / "tests" / "fixtures" / "x.pdf").write_bytes(_PINNED_BYTES)
    pinned = load_pinned_originals(tree)
    assert source_addition_findings(
        ["tests/fixtures/x.pdf"], pinned=pinned, root=tree
    ) == (("tests/fixtures/x.pdf", "bytes of a pinned original source document"),)
    result = _run_cli(tree, "tests/fixtures/x.pdf")
    assert result.returncode == 1
    assert b"tests/fixtures/x.pdf" in result.stderr


@pytest.mark.parametrize("path", [
    f"docs/engineering/x/{_PINNED_NAME}",
    f"docs/{_PINNED_NAME.upper()}",
    "DOCS\\" + _PINNED_NAME.lower(),
])
def test_pinned_original_name_is_blocked_even_when_not_in_the_tree(tree, path):
    pinned = load_pinned_originals(tree)
    assert blocked_source_additions([path], pinned=pinned, root=tree) == (path,)
    assert _run_cli(tree, path).returncode == 1


def test_same_size_different_bytes_is_allowed(tree):
    other = bytes(len(_PINNED_BYTES))
    (tree / "tests").mkdir()
    (tree / "tests" / "same_size.pdf").write_bytes(other)
    pinned = load_pinned_originals(tree)
    assert blocked_source_additions(
        ["tests/same_size.pdf"], pinned=pinned, root=tree
    ) == ()
    assert _run_cli(tree, "tests/same_size.pdf").returncode == 0


def test_only_size_equal_files_are_hashed(tree, monkeypatch):
    import scripts.check_private_original_source_additions as guard

    (tree / "tests").mkdir()
    (tree / "tests" / "small.pdf").write_bytes(b"synthetic")
    (tree / "tests" / "match.pdf").write_bytes(_PINNED_BYTES)
    hashed = []
    real = guard._file_sha256
    monkeypatch.setattr(guard, "_file_sha256", lambda p: hashed.append(p.name) or real(p))
    pinned = load_pinned_originals(tree)
    blocked_source_additions(
        ["tests/small.pdf", "tests/match.pdf"], pinned=pinned, root=tree
    )
    assert hashed == ["match.pdf"]


def test_path_absent_from_tree_or_symlink_is_not_hashed(tree):
    pinned = load_pinned_originals(tree)
    assert blocked_source_additions(
        ["tests/never_checked_out.pdf"], pinned=pinned, root=tree
    ) == ()


def test_synthetic_fixture_pdfs_stay_allowed_with_pinned_rules(tree):
    (tree / "tests" / "fixtures").mkdir(parents=True)
    (tree / "tests" / "fixtures" / "synthetic_plan.pdf").write_bytes(b"%PDF-1.4 fake")
    assert _run_cli(tree, "tests/fixtures/synthetic_plan.pdf", "docs/a.md").returncode == 0


def test_path_only_rules_unchanged_without_pinned_set():
    # Library callers that pass no pinned set keep the original path-only rules.
    assert blocked_source_additions([f"docs/{_PINNED_NAME}"]) == ()
    assert blocked_source_additions(["documents/sources/a.pdf"]) == ("documents/sources/a.pdf",)


@pytest.mark.parametrize("make", [
    lambda root: None,  # no manifest at all
    lambda root: _write_manifest(root, []),  # pins nothing
    lambda root: _write_manifest(root, [dict(_entry(), sha256="not-a-digest")]),
    lambda root: _write_manifest(root, [dict(_entry(), size_bytes=0)]),
    lambda root: _write_manifest(root, [dict(_entry(), name="a/b.pdf")]),
    lambda root: _write_manifest(root, ["not-a-dict"]),
    lambda root: (_write_manifest(root, [_entry()]),
                  (root / PINNED_MANIFEST_GLOB.rsplit("/", 1)[0].replace("*", "p1")
                   / "source_manifest.json").write_text("{broken", encoding="utf-8")),
])
def test_unreadable_or_empty_manifests_fail_closed(tmp_path, make):
    make(tmp_path)
    with pytest.raises(ValueError):
        load_pinned_originals(tmp_path)
    result = _run_cli(tmp_path, "docs/a.md")
    assert result.returncode == 1
    assert b"gate failed" in result.stderr


def test_deletion_only_change_needs_no_manifest(tmp_path):
    assert _run_cli(tmp_path).returncode == 0


def test_real_frozen_manifests_pin_well_formed_originals_and_no_tracked_file_matches():
    pinned = load_pinned_originals(ROOT)
    assert pinned.names and pinned.sha256_by_size
    try:
        listing = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    tracked = [item.decode("utf-8") for item in listing.split(b"\x00") if item]
    assert blocked_source_additions(tracked, pinned=pinned, root=ROOT) == ()
