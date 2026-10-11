"""Original-source page diagnostic must fail closed and never claim scoring."""
from __future__ import annotations

import json
import subprocess
import sys

import fitz
import pytest

from tools.diag_v2_bounded_source_page import _watch, main


def _pdf(path):
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path


def test_bounded_diagnostic_marks_child_failure_as_unsealed(tmp_path):
    path = _pdf(tmp_path / "s.pdf")
    out = tmp_path / "audit.json"
    # Avoid running the expensive production extractor in the unit test:
    # explicitly observe a failed child, never replace it with a quantity.
    from unittest.mock import patch

    class Failed:
        pid = 123
        def poll(self):
            return 4
        def wait(self, timeout=None):
            return 4
    with patch("tools.diag_v2_bounded_source_page.subprocess.Popen", return_value=Failed()):
        assert main(["--pdf", str(path), "--page-index", "0", "--output", str(out)]) == 0
    result = json.loads(out.read_text())
    assert result["benchmark_score_granted"] is False
    assert result["complete_source_coverage_proven"] is False
    assert result["sealed_run_file"] is None
    assert result["pages"][0]["outcome"] == "CHILD_FAILED"


def test_timeout_kills_child_without_publishing_claim(tmp_path):
    process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(10)"],
                               start_new_session=True)
    result = _watch(process, timeout_seconds=0.05, rss_limit_mb=200)
    assert result["outcome"] == "TIMEOUT"
    assert result["exit_code"] != 0


@pytest.mark.parametrize("page", ["-1", "1"])
def test_diagnostic_rejects_page_outside_source(tmp_path, page):
    path = _pdf(tmp_path / "s.pdf")
    with pytest.raises(SystemExit):
        main(["--pdf", str(path), "--page-index", page])


def test_diagnostic_rejects_wrong_source_hash(tmp_path):
    path = _pdf(tmp_path / "s.pdf")
    with pytest.raises(ValueError, match="SHA mismatch"):
        main(["--pdf", str(path), "--page-index", "0",
              "--expected-sha256", "a" * 64])
