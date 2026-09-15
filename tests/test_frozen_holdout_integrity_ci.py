"""CI wiring for frozen holdout integrity verifier."""
from __future__ import annotations

import subprocess
import sys


def test_frozen_holdout_integrity_script_exits_clean_when_no_registered_projects() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_frozen_holdout_integrity.py"],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
