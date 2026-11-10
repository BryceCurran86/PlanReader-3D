"""Tests for the short PlanReader agent-feedback loop (never original PDFs)."""
from types import SimpleNamespace
import subprocess

import pytest

from tools.agent_fast_gate import LANES, build_command, execute, main


@pytest.fixture
def root(tmp_path):
    for lane in LANES.values():
        for name in lane.tests:
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("def test_example(): assert True\n")
    return tmp_path


def test_lanes_are_fixed_and_source_neutral(root):
    assert set(LANES) == {
        "claude-corner", "claude-pier", "claude-door-height",
        "antigravity-office", "gptmax-customer",
    }
    for lane, spec in LANES.items():
        command = build_command(lane, root, python="py")
        assert command[:4] == ("py", "-B", "-m", "pytest")
        assert "not original" in " ".join(command)
        assert "not private" in " ".join(command)
        assert all(t.startswith("tests/") and t.endswith(".py") for t in spec.tests)
        assert not any("/sources/" in arg for arg in command)


def test_missing_tests_block_instead_of_skipping(root):
    (root / LANES["claude-corner"].tests[0]).unlink()
    with pytest.raises(FileNotFoundError, match="Lane code is not on this branch"):
        build_command("claude-corner", root)


def test_unknown_lane_rejected(root):
    with pytest.raises(ValueError, match="unknown lane"):
        build_command("not-a-lane", root)


def test_green_never_grants_original_customer_or_score(root):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    result = execute("claude-corner", root, python="py", runner=runner)
    assert result["result"] == "PASSED"
    assert all(result[key] is False for key in (
        "private_original_verified",
        "signed_customer_retention_verified",
        "full_dual_python_ci_verified",
        "frozen120_score_granted",
        "release_approved",
    ))
    command, options = calls[0]
    assert options["cwd"] == root
    assert options["check"] is False
    assert options["timeout"] == 600
    assert options["env"]["PLANREADER_PRIVATE_ORIGINAL_POLICY"] == "skip_missing_in_public_ci"
    assert options["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "-k" in command


def test_failures_propagate(root):
    outcome = execute(
        "claude-door-height", root,
        runner=lambda *args, **kw: SimpleNamespace(returncode=3),
    )
    assert outcome["result"] == "FAILED"
    assert outcome["exit_code"] == 3
    assert outcome["release_approved"] is False


def test_timeout_propagates(root):
    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    outcome = execute("antigravity-office", root, runner=runner)
    assert outcome["result"] == "TIMEOUT"
    assert outcome["exit_code"] == 124


@pytest.mark.parametrize("timeout", [False, True, None, 0, 3601, -1, 1.1, "5"])
def test_invalid_timeouts_rejected(timeout, root):
    with pytest.raises(ValueError):
        execute("claude-pier", root, timeout_seconds=timeout)


def test_dry_run_never_changes_source_or_claims_release(root, capsys):
    assert main(["--lane", "gptmax-customer", "--root", str(root), "--dry-run"]) == 0
    text = capsys.readouterr().out
    assert '"release_approved": false' in text
    assert '"source_neutral_only": true' in text
    assert '"pytest"' in text
