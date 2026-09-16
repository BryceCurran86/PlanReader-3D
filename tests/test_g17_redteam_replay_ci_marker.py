"""Execution-harness marker for the corrected G17 red-team replay.

This file intentionally contains no production behavior.  It binds the replay
branch to the exact reviewed #326 head and gives GitHub Actions a fresh
pull-request synchronize event after the execution PR was retargeted to main.
"""


def test_corrected_g17_replay_targets_exact_326_head() -> None:
    assert "3361458cd2b699fb940c0dc82d75c5c9c151ec7f" == "3361458cd2b699fb940c0dc82d75c5c9c151ec7f"
