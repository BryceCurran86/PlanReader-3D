"""Hosted CI must not run the six legacy original-PDF commands.
This tests routing only, never original-source acceptance.
"""
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
OFF = "${{ false }}"
NOTICE = "NOT RUN_LOCAL_REQUIRED"

MIXED = {
    "test-gptmax-page-opening-proof-cache.yml": "source-proof",
    "test-gptmax-snap-collapsed-source.yml": "source-proof",
    "test-gptmax-exact-split-parent-lineage-shadow.yml": "original-source",
    "test-gpt2-original-source-owned-w4-shadow.yml": "focused-original-maryborough",
}
PURE = {
    "test-gptmax-original-candidate-membership.yml": ("original-lot16-p3", "exact-membership"),
    "test-gptmax-w4-collision-source-identity.yml": ("exact-original-source-parity", "focused"),
}


def jobs(filename):
    return yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))["jobs"]


def assert_notice(steps):
    notices = [s for s in steps if NOTICE in s.get("run", "")]
    assert len(notices) == 1
    assert "if" not in notices[0]
    assert "not a passing source verification" in notices[0]["run"]


@pytest.mark.parametrize("filename,job", MIXED.items())
def test_mixed_jobs_keep_real_regressions_and_defer_original(filename, job):
    steps = jobs(filename)[job]["steps"]
    assert_notice(steps)
    originals = [s for s in steps if "documents/sources/" in str(s)]
    assert originals
    assert all(s.get("if") == OFF for s in originals)
    assert any("pytest" in s.get("run", "") and "if" not in s for s in steps)
    assert all(s.get("if") == OFF for s in steps if "upload-artifact" in s.get("uses", ""))


@pytest.mark.parametrize("filename,pair", PURE.items())
def test_original_only_jobs_do_no_work_except_notice(filename, pair):
    original, focused = pair
    data = jobs(filename)
    steps = data[original]["steps"]
    assert_notice(steps)
    assert all(s.get("if") == OFF for s in steps if NOTICE not in s.get("run", ""))
    assert any("documents/sources/" in str(s) for s in steps)
    assert "if" not in data[focused]
    assert data[focused]["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    assert any("pytest" in s.get("run", "") and "if" not in s for s in data[focused]["steps"])
