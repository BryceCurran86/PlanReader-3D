"""Required CI remains intact; manual consolidation cannot fake a score.

Avoid a new PyYAML runtime dependency: these guards inspect the original
GitHub Actions file text and exact top-level structural markers. The Actions
runner is the authoritative workflow schema validator.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


def source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def job(name: str) -> str:
    text = source().split("\njobs:\n", 1)[1]
    marker = f"  {name}:\n"
    assert text.count(marker) == 1
    tail = text.split(marker, 1)[1]
    next_job = re.search(r"(?m)^  [a-z][a-z0-9_-]*:\s*$", tail)
    return tail[:next_job.start()] if next_job else tail


def test_public_required_ci_trigger_and_check_context_stay_unchanged():
    text = source()
    assert text.startswith("name: CI\n")
    assert "  push:\n    branches: [main]" in text
    assert "  pull_request:\n    branches: [main]" in text
    full = job("test")
    assert "python-version: [\"3.13\", \"3.14\"]" in full
    assert "github.event_name != 'workflow_dispatch'" in full
    assert "needs: shard" in full
    assert "always()" in full
    assert 'run: test "$SHARD_RESULT" = success' in full
    assert "Verify every collected test executed exactly once across four shards" in full
    # The full suite still runs the whole tests/ tree; "-rs" (list skipped tests) was added with the public-CI
    # private-original policy (#2989), so allow it without allowing a narrower selection.
    assert re.search(r"PYTHONPATH=\. pytest -q(?: -rs)? tests/(?:\s|$)", full)
    for guard in ("check_private_original_source_additions.py",
                  "check_provider_gold_isolation.py",
                  "check_full_plan_v2_integrity.py",
                  "check_v2_truth_separation.py"):
        assert guard in full


def test_manual_suites_do_not_create_duplicate_automatic_triggers():
    text = source()
    assert text.count("  workflow_dispatch:") == 1
    assert "    inputs:\n      suite:" in text
    assert "        default: full" in text
    for mode in ("full", "focused", "readiness"):
        assert f"          - {mode}" in text
    assert "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text
    assert "  group: ci-${{ github.event.pull_request.number || github.run_id }}" in text
    assert "cancel-in-progress: true" not in text
    assert len(re.findall(r"(?m)^  (?:test|focused|readiness):$", text)) == 3
    assert "workflow_dispatch" in job("focused")
    assert "runs-on: ubuntu-latest" in job("focused")


def test_source_neutral_readiness_has_no_client_secrets_or_score_claim():
    text = source()
    for name in ("focused", "readiness"):
        section = job(name)
        assert "workflow_dispatch" in section
        assert "permissions:\n      contents: read" in section
    assert "ORIGINAL_SOURCES_TOKEN" not in text
    assert "pull_request_target" not in text
    assert "upload-artifact" not in job("focused") + job("readiness")
    assert text.count("uses: actions/upload-artifact@v4") == 1
    assert "path: ${{ runner.temp }}/receipt.json" in job("shard")
    assert "UNPUBLISHED" in text
    assert "coverage_accuracy" in text
    assert "precision_adjusted_accuracy" in text
    assert 'sum(p["denominator"] for p in projects) == 120' in text
    assert 'p["coverage_accuracy"] is None' in text


def test_focus_is_not_an_alternative_to_required_full_ci():
    full, focused = job("test"), job("focused")
    assert "inputs.suite == 'full'" in full
    assert "inputs.suite == 'focused'" in focused
    assert "test_ci_coordinated_entrypoint.py" in focused
    assert "test_full_plan_v2_readiness_report.py" in focused
    assert "test_opening_host_source_candidate_witness.py" in focused


def test_full_ci_compiles_outside_source_archives_and_does_not_write_test_bytecode():
    """The archived derived owner package intentionally rejects ANY unindexed pyc."""
    full = job("test")
    assert "python -m compileall -q ." in full
    assert "PYTHONPYCACHEPREFIX: ${{ runner.temp }}/planreader-pycache" in full
    assert 'PYTHONDONTWRITEBYTECODE: "1"' in full
    assert "PLANREADER_PRIVATE_ORIGINAL_POLICY: skip_missing_in_public_ci" in full
    assert "PYTHONPYCACHEPREFIX: ." not in full
    assert "PYTHONPYCACHEPREFIX: documents/" not in full


FASTPATH = ROOT / ".github/workflows/performance-fastpath.yml"


def _concurrency_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.count("\nconcurrency:\n") == 1
    return text.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]


def test_only_superseded_pull_request_runs_are_cancelled_never_main_pushes_or_manual_runs():
    """A cancelled main-push run leaves a merge with no required verdict; the repo convention cancels PR runs only."""
    for path, prefix in ((WORKFLOW, "ci"), (FASTPATH, "performance-fastpath")):
        block = _concurrency_block(path)
        assert f"  group: {prefix}-${{{{ github.event.pull_request.number || github.run_id }}}}\n" in block, path.name
        assert "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n" in block, path.name
        # a ref- or sha-scoped group would make one main push cancel (or queue behind) another
        assert "github.ref" not in block and "github.sha" not in block, path.name
        assert "cancel-in-progress: true" not in path.read_text(encoding="utf-8"), path.name


def test_fastpath_still_runs_on_pull_requests_and_main_pushes_only():
    text = FASTPATH.read_text(encoding="utf-8")
    assert "  pull_request:\n    branches: [main]\n  push:\n    branches: [main]\n" in text
    assert "pull_request_target" not in text

def test_parallel_full_ci_keeps_all_tests_and_nightly_release_guard():
    text = source()
    full = job("test")
    assert "  schedule:\n" in text
    assert "--dist loadfile --durations=30" in full
    assert "PYTEST_ADDOPTS:" in full
    assert "options: ['0', '2', '4', '8']" in text
    assert "PYTHONPATH=. pytest -q -rs tests/" in full
    assert "requirements-ci-v1228.txt" in full
    assert "fail-fast: false" in full
    assert "pytest-xdist>=3.8,<4" in (ROOT / "requirements-ci-v1228.txt").read_text(encoding="utf-8")


def test_scoped_development_workflow_cannot_replace_required_ci():
    dev = (ROOT / ".github/workflows/vr-development-fast-feedback.yml").read_text(encoding="utf-8")
    assert "name: VR development feedback (not release CI)" in dev
    assert "branches: ['vr/**']" in dev
    assert "tests/editable_3d/" in dev
    assert "git diff --no-renames --name-only -z" in dev
    assert "pull_request:" not in dev
    assert "needs.scope.outputs.scope == 'vr-only'" in dev
    assert "not full regression" in dev

def test_automatic_full_release_requires_complete_isolated_shards():
    full, shard = job("test"), job("shard")
    assert "if: ${{ github.event_name != 'workflow_dispatch' }}" in shard
    assert "python-version: ['3.13', '3.14']" in shard
    assert "index: [0, 1, 2, 3]" in shard
    assert "fail-fast: false" in shard
    assert "python -m pytest -p scripts.ci_pytest_shard -q -rs --durations=20 tests/" in shard
    assert "check_private_original_source_additions.py" in shard
    assert "check_v2_truth_separation.py" in shard
    assert "if-no-files-found: error" in shard
    assert 'PLANREADER_CI_SHARDS: \'4\'' in shard
    assert 'pattern: shard-${{ matrix.python-version }}-*' in full
    assert 'python scripts/ci_pytest_shard.py "$RUNNER_TEMP/shards" 4' in full
    assert full.index("Require every automatic shard to succeed") < full.index("Download only full-suite shard receipts")
    assert full.index("Verify every collected test executed exactly once across four shards") < full.index("Smoke test (envelope")
    assert "if: github.event_name == 'workflow_dispatch'" in full
