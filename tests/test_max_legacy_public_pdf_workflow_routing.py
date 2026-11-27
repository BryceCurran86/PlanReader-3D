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
    assert "documents/sources/" in str(data[original])
    assert "if" not in data[focused]
    assert data[focused]["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    assert any("pytest" in s.get("run", "") and "if" not in s for s in data[focused]["steps"])

# Batch two: preserve every step before the original replay boundary.
BATCH_TWO = [
    ("diag-gpt2-page7-remaining-label-face-ownership.yml", "source-face-physical-ownership", "Source-owned native room text vs authentic physical face first gate"),
    ("diag-gpt2-page7-split-label-wall-separators.yml", "source-face-physical-ownership", "Source-owned native room text vs authentic physical face first gate"),
    ("diag-gpt2-page7-source-room-label-owners.yml", "source-face-physical-ownership", "Prove source-owned floor plan wall and room faces"),
    ("test-gpt2-original-page11-schedule-frame-ownership.yml", "source-schedule-frame-gate", "Original Maryborough source SHA page11 physical plan vs schedule"),
    ("test-gpt2-source-double-plan-border.yml", "source-double-plan-border", "Identify strict source frame first rejection without relaxing authority"),
    ("test-source-plan-material-occurrences.yml", "source-plan-material-proof", "Both immutable originals and preserved consumer gates"),
    ("test-gpt2-b01-real-vertical-titles.yml", "maryborough-vertical-source", None),
    ("test-gpt2-page7-physical-faces-after-frame.yml", "source-face-physical-ownership", "Prove source-owned floor plan wall and room faces"),
    ("test-gptmax-producer-g17-wall-shadow.yml", "original-source-retention", None),
    ("diag-gpt2-page7-room-figured-witnesses.yml", "source-face-physical-ownership", "Prove source-owned floor plan wall and room faces"),
    ("diag-gpt2-b01-semantic-regions.yml", "maryborough-semantic-regions", None),
    ("diag-gpt2-original-ft3-native-frame-scope.yml", "original", None),
    ("test-source-owned-physical-plan-view.yml", "source-view-proof", "Both immutable original source proofs and downstream consumption"),
    ("test-gptmax-original-g17-shadow-cells.yml", "original-lot16-retention", None),
    ("test-gptmax-interior-dimension-tick-source.yml", "original-lot16", None),
]


@pytest.mark.parametrize("filename,job,boundary", BATCH_TWO)
def test_batch_two_original_replay_boundary(filename, job, boundary):
    data = jobs(filename)
    steps = data[job]["steps"]
    assert_notice(steps)
    notice_index = next(i for i, s in enumerate(steps) if NOTICE in s.get("run", ""))
    assert all(s.get("if") == OFF for s in steps[notice_index + 1:])
    if boundary is None:
        assert notice_index == 0
    else:
        assert steps[notice_index + 1]["name"] == boundary
        assert notice_index > 0
        assert all(s.get("if") != OFF for s in steps[:notice_index])
    for sibling, config in data.items():
        if sibling != job:
            assert config.get("if") != OFF
            assert all(s.get("if") != OFF for s in config.get("steps", []))
