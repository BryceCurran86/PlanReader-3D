"""The benchmark / source-PDF protections must not be bypassable by renaming or by touching a file the narrow predicate does not name.

Two always-on CI gates protect the frozen benchmark:

* ``scripts/check_v2_truth_separation.py`` - production code and benchmark-defining files must not change in the same PR;
* ``scripts/check_full_plan_v2_integrity.py`` - the frozen manifests must be internally consistent and the pinned documents intact.

Before this change a one-bit edit of an original source PDF passed both, and scorer code, an identity map or a source PDF could change in the
same PR as production code.  These tests keep that closed.  Nothing here reads a benchmark value; only paths, SHA-256 pins and sizes.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

from scripts.check_v2_truth_separation import (
    check_paths,
    find_separation_violation,
    is_benchmark_defining_file,
    is_v2_truth_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_integrity_script():
    """Import the integrity script in isolation.

    ``tests/benchmarks`` is a test package that shadows the real top-level ``benchmarks`` package once ``tests/`` is on ``sys.path``,
    and the script imports ``benchmarks.frozen_holdout`` at module level.  Load it with the repository root first and restore ``sys.modules``
    afterwards so neither this test nor the rest of the suite sees the other's ``benchmarks``.
    """
    stash = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "benchmarks" or k.startswith("benchmarks.")}
    sys.path.insert(0, str(REPO_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "_check_full_plan_v2_integrity_under_test", REPO_ROOT / "scripts" / "check_full_plan_v2_integrity.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(REPO_ROOT))
        for k in [k for k in sys.modules if k == "benchmarks" or k.startswith("benchmarks.")]:
            del sys.modules[k]
        sys.modules.update(stash)
    return module


_integrity = _load_integrity_script()
DEFAULT_ROOT = REPO_ROOT / _integrity.DEFAULT_ROOT
DEFAULT_SOURCE_DIR = _integrity.DEFAULT_SOURCE_DIR
load_suite_manifests = _integrity.load_suite_manifests
source_document_failures = _integrity.source_document_failures
validate_suite = _integrity.validate_suite

V2 = "benchmarks/frozen_holdout/full_plan_v2"
PRODUCTION = "pb_physical_opening_authority.py"


# ---------------------------------------------------------------------------------------------------------------------------
# separation gate
# ---------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "benchmark_file",
    [
        f"{V2}/projects/au_qld_lot16_power/object_universe.json",  # the six named truth files stay protected
        f"{V2}/manifest.json",
        f"{V2}/run_exact_project_reconciliation.py",  # scorer / reconciler code
        f"{V2}/run_development_scoreboard.py",
        f"{V2}/projects/au_qld_lot16_power/identity_map.json",  # truth-adjacent file the narrow predicate does not name
        f"{V2}/projects/au_qld_lot16_power/anything_else.json",
        "documents/sources/Q5446_Standard_Plans_V1_20220320.pdf",  # original source PDFs
        "documents/sources/a brand new source.PDF",  # case-insensitive suffix
        "Documents/Sources/Another.pdf",  # case-insensitive directory
        r"documents\sources\windows_path.pdf",  # Windows separators
    ],
)
def test_benchmark_defining_file_cannot_change_with_production_code(benchmark_file):
    assert is_benchmark_defining_file(benchmark_file)
    with pytest.raises(SystemExit, match="separation gate failed"):
        check_paths([benchmark_file, PRODUCTION])
    truth, production = find_separation_violation([PRODUCTION, benchmark_file])
    assert truth and production == [PRODUCTION]


@pytest.mark.parametrize(
    "changed",
    [
        [f"{V2}/run_exact_project_reconciliation.py", "tests/test_x.py", "docs/note.md"],  # benchmark change alone is allowed (own PR)
        ["documents/sources/Q5446_Standard_Plans_V1_20220320.pdf", "docs/note.md"],
        [PRODUCTION, "tests/test_x.py", "docs/note.md", ".github/workflows/ci.yml"],  # production alone
        ["documents/sources/readme.txt", PRODUCTION],  # not a PDF
        ["docs/figure.pdf", PRODUCTION],  # a PDF outside documents/sources
        ["documents/other/file.pdf", PRODUCTION],
        ["benchmarks/public_tenders/example/expected_boq_summary.json", PRODUCTION],  # legacy tree, not the V2 root
        ["benchmarks/frozen_holdout/legacy_project/.holdout_lock.json", PRODUCTION],
    ],
)
def test_allowed_combinations_stay_allowed(changed):
    check_paths(changed)  # must not raise


def test_narrow_truth_predicate_is_unchanged():
    assert is_v2_truth_file(f"{V2}/projects/p/reference_takeoff.json")
    assert not is_v2_truth_file(f"{V2}/run_exact_project_reconciliation.py")
    assert not is_v2_truth_file("documents/sources/x.pdf")
    # the wide predicate is a strict superset of the narrow one
    for path in (f"{V2}/manifest.json", f"{V2}/projects/p/object_universe.json", f"{V2}/projects/p/source_manifest.json"):
        assert is_v2_truth_file(path) and is_benchmark_defining_file(path)


# ---------------------------------------------------------------------------------------------------------------------------
# integrity: pinned source documents present in the repository must be byte-exact
# ---------------------------------------------------------------------------------------------------------------------------


def _manifest_with_present_source():
    for manifest in load_suite_manifests(DEFAULT_ROOT):
        for source in manifest.source_documents:
            if (DEFAULT_SOURCE_DIR / source.name).is_file():
                return manifest, source
    pytest.skip("no pinned source document is present in this checkout")


def test_real_repository_sources_match_their_pins():
    assert validate_suite() == []
    assert source_document_failures(load_suite_manifests(DEFAULT_ROOT)) == []


def test_changed_source_bytes_fail_closed(tmp_path):
    manifest, source = _manifest_with_present_source()
    data = bytearray((DEFAULT_SOURCE_DIR / source.name).read_bytes())
    data[-20] ^= 0x01  # one bit
    (tmp_path / source.name).write_bytes(bytes(data))
    failures = source_document_failures(load_suite_manifests(DEFAULT_ROOT), tmp_path)
    assert any(source.name in f and "SHA mismatch" in f for f in failures), failures
    assert not any("size mismatch" in f and source.name in f for f in failures)  # same length: only the SHA differs
    # end to end through the gate entry point
    assert any(source.name in f for f in validate_suite(DEFAULT_ROOT, tmp_path))


def test_truncated_and_padded_sources_fail_on_size_and_sha(tmp_path):
    _manifest, source = _manifest_with_present_source()
    real = (DEFAULT_SOURCE_DIR / source.name).read_bytes()
    for name, data in (("truncated", real[:-1]), ("padded", real + b"\n")):
        directory = tmp_path / name
        directory.mkdir()
        (directory / source.name).write_bytes(data)
        failures = source_document_failures(load_suite_manifests(DEFAULT_ROOT), directory)
        assert any("size mismatch" in f and source.name in f for f in failures), (name, failures)
        assert any("SHA mismatch" in f and source.name in f for f in failures), (name, failures)


def test_exact_copy_missing_files_and_unpinned_files_are_ignored(tmp_path):
    _manifest, source = _manifest_with_present_source()
    shutil.copyfile(DEFAULT_SOURCE_DIR / source.name, tmp_path / source.name)  # byte-exact copy of a pinned file
    (tmp_path / "not_in_any_manifest.pdf").write_bytes(b"%PDF-1.4 anything")  # unpinned file: nothing to compare
    assert source_document_failures(load_suite_manifests(DEFAULT_ROOT), tmp_path) == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert source_document_failures(load_suite_manifests(DEFAULT_ROOT), empty) == []  # pinned but not distributed


def test_pin_is_the_sha256_of_the_real_bytes_not_a_name_match():
    manifest, source = _manifest_with_present_source()
    data = (DEFAULT_SOURCE_DIR / source.name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == source.sha256 and len(data) == source.size_bytes
