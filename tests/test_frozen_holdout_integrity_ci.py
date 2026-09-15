"""CI wiring for frozen holdout integrity verifier."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_frozen_holdout_integrity_script_exits_clean_when_no_registered_projects() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(".").resolve())
    completed = subprocess.run(
        [sys.executable, "scripts/check_frozen_holdout_integrity.py"],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
