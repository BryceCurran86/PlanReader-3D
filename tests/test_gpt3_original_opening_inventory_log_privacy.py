"""Source-neutral contract: original Lot16 opening/customer replay never logs private evidence.

These tests do not authenticate a private PDF or mint FIRM/customer/score authority.
They verify the existing owner/main-only original replay retains its original
eight signed/customer assertions while suppressing producer and verifier logs.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/gpt3-original-opening-customer-inventory.yml"
)


def _private_log_contract(raw: str) -> bool:
    try:
        doc = yaml.safe_load(raw)
        assert isinstance(doc, dict)
        jobs = doc["jobs"]
        source = jobs["original-source"]
        gate = source["if"]
        assert "github.event_name == 'workflow_dispatch'" in gate
        assert "github.ref == 'refs/heads/main'" in gate
        assert "github.actor == 'BryceCurran86'" in gate
        steps = source["steps"]
        named = {step.get("name"): step for step in steps if step.get("name")}
        assert not any("actions/upload-artifact" in s.get("uses", "") for s in steps)
        checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
        assert checkout["with"]["ref"] == "${{ github.sha }}"
        assert checkout["with"]["persist-credentials"] is False
        provision = named["Provision original sources"]
        assert provision["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
        assert "1. Construction Plans - Lot 16 Power (REV E).pdf" in provision["with"]["names"]

        classify = named["Classify original source"]
        assert classify["if"] == "always()"
        preflight = classify["run"]
        assert "python3 -m tools.gpt3_original_source_preflight" in preflight
        assert "--output artifacts/original-source-preflight.json >/dev/null 2>&1" in preflight
        assert "if ! python3" in preflight
        assert 'echo "ORIGINAL_LOT16_SOURCE_PREFLIGHT_BLOCKED" >&2' in preflight
        assert "exit 1" in preflight

        replay = named["Original Lot16 eight signed opening-area and commercial parity"]["run"]
        assert "set -euo pipefail" in replay
        assert "umask 077" in replay
        assert 'PRIVATE_LOG="$(mktemp "${RUNNER_TEMP}/gpt3-original-opening-inventory.XXXXXX")"' in replay
        assert "exec 3>&1 4>&2" in replay
        assert "trap cleanup_private_log EXIT" in replay
        assert 'exec >"$PRIVATE_LOG" 2>&1' in replay
        assert 'rm -f "$PRIVATE_LOG"' in replay
        assert 'if [ "$status" -ne 0 ]; then' in replay
        assert '"ORIGINAL_LOT16_EIGHT_REPLAY_BLOCKED" >&4' in replay
        assert '"ORIGINAL_LOT16_EIGHT_RETAINED" >&3' in replay
        assert "tools.run_gpt3_lot16_original_sealed_score_input" in replay
        assert "tools.gpt3_original_source_preflight" in replay
        assert "verify_sealed_customer_output(sealed,rows)" in replay
        assert "assert len(sealed.quantities)==8" in replay
        assert "receipt.valid_quantity_count==8 and receipt.customer_row_count==8" in replay
        assert "receipt.verified_quantity_ids==tuple(sorted(q.quantity_id for q in sealed.quantities))" in replay
        assert 'q.family=="opening_area" and q.lineage_ok and not q.abstained' in replay
        assert "python scripts/check_full_plan_v2_integrity.py" in replay
        assert "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844" in replay
        assert "tee " not in replay
        assert "cat \"$PRIVATE_LOG\"" not in replay
        cleanup = named["Destroy private originals and unpublished source reports"]
        assert cleanup["if"] == "always()"
        assert "rm -rf documents/sources artifacts" in cleanup["run"]
    except (AssertionError, KeyError, IndexError, TypeError, ValueError, yaml.YAMLError):
        return False
    return True


def test_original_opening_customer_replay_is_private_and_fail_closed() -> None:
    assert _private_log_contract(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("before", "after"), [
    ('github.event_name == \'workflow_dispatch\'', 'github.event_name == \'pull_request\''),
    ("github.ref == 'refs/heads/main'", "github.ref != 'refs/heads/main'"),
    ("github.actor == 'BryceCurran86'", "github.actor != 'BryceCurran86'"),
    ("persist-credentials: false", "persist-credentials: true"),
    ("umask 077", "umask 022"),
    ("trap cleanup_private_log EXIT", "true # cleanup disabled"),
    ('exec >"$PRIVATE_LOG" 2>&1', 'exec > /dev/null'),
    ('rm -f "$PRIVATE_LOG"', 'true # keep private log'),
    ('"ORIGINAL_LOT16_EIGHT_REPLAY_BLOCKED" >&4',
     '"ORIGINAL_LOT16_EIGHT_REPLAY_BLOCKED" >&2'),
    ("--output artifacts/original-source-preflight.json >/dev/null 2>&1",
     "--output artifacts/original-source-preflight.json"),
    ("assert len(sealed.quantities)==8", "assert len(sealed.quantities)>=0"),
    ("receipt.valid_quantity_count==8 and receipt.customer_row_count==8",
     "receipt.valid_quantity_count>=0 and receipt.customer_row_count>=0"),
    ("python scripts/check_full_plan_v2_integrity.py",
     "echo skipped_frozen_integrity"),
    ("if: always()\n        shell: bash\n        run: |",
     "if: success()\n        shell: bash\n        run: |"),
])
def test_source_privacy_and_eight_row_authority_mutations_fail(before: str, after: str) -> None:
    original = WORKFLOW.read_text(encoding="utf-8")
    assert before in original
    changed = original.replace(before, after, 1)
    assert changed != original
    assert not _private_log_contract(changed)


def test_raw_original_logs_cannot_be_reintroduced() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _private_log_contract(raw)
    modified = raw.replace(
        'exec >"$PRIVATE_LOG" 2>&1',
        'exec >"$PRIVATE_LOG" 2>&1\n          cat "$PRIVATE_LOG" >&3',
        1,
    )
    assert not _private_log_contract(modified)
