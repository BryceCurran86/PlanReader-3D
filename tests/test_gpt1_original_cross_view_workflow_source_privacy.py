"""Source-neutral privacy contract for the two original GPT1 cross-view jobs.

The real source diagnostics must remain SHA-verified and fail closed, but
native PDF geometry, text and exceptions must never reach public Actions
logs or downloadable artifacts. These tests need no private original PDF.
"""
from __future__ import annotations

from pathlib import Path
import re

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/diag-gpt1-original-cross-view-grid.yml"
)


def _jobs() -> tuple[str, str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    first, second = text.split("  original-room-mark-registration:", 1)
    return first, second


def test_original_source_checks_are_not_bypassed() -> None:
    first, second = _jobs()
    for job in (first, second):
        assert "sha256sum --check" in job
        assert "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007" in job
        assert "if ! timeout " in job
        assert "exit 1" in job
        assert "diagnostic_only" in job
        assert "commercial_projection_allowed" in job
        assert "source_sha_verified" in job
        assert "original_source_checks_passed" in job
    assert "--first-page 7 --second-page 11" in first
    assert 'data["source_native_vector_grid_candidate"] is True' in first
    assert 'data["source_native_text_grid_candidate"] is True' in first
    assert 'data["first_unclosed_gate"]==' in first
    assert "--room-page 7 --material-page 11" in second
    assert "--code FT3" in second
    assert 'r["published_floor_finish_quantities"]==0' in second
    assert 'r["physical_room_crossview_equivalence_proven"] is False' in second
    assert 'r["material_occurrence_source_trusted"] is False' in second


def test_both_diagnostics_keep_original_derived_json_in_private_runner_temp() -> None:
    first, second = _jobs()
    for job in (first, second):
        assert 'PRIVATE_OUT="$(mktemp -d "${RUNNER_TEMP}/' in job
        assert "export PRIVATE_OUT" in job
        assert """trap 'rm -rf "$PRIVATE_OUT"' EXIT""" in job
        assert "> /dev/null 2>&1" in job
        assert "| tee " not in job
        assert "console.log" not in job
        assert "if: always()" not in job
    assert '--output "$PRIVATE_OUT/native_grid_candidate.json"' in first
    assert 'Path(os.environ["PRIVATE_OUT"])/"native_grid_candidate.json"' in first
    assert '--output "$PRIVATE_OUT/original_room_mark_registration.json"' in second
    assert 'Path(os.environ["PRIVATE_OUT"])/"original_room_mark_registration.json"' in second


def test_artifacts_are_bounded_source_neutral_receipts_only() -> None:
    first, second = _jobs()
    for job in (first, second):
        assert job.count("actions/upload-artifact@v4") == 1
        assert "if: success()" in job
        upload = job.split("      - uses: actions/upload-artifact@v4", 1)[1]
        paths = re.findall(r"(?m)^\s+path:\s*(\S+)\s*$", upload)
        assert len(paths) == 1
        assert paths[0].endswith("/receipt.json")
        assert "native_grid_candidate.json" not in upload
        assert "original_room_mark_registration.json" not in upload
        assert "console.log" not in upload
        assert "retention-days: 14" in upload
        for key in ("schema_version", "source_sha_verified",
                    "original_source_checks_passed", "diagnostic_only",
                    "commercial_projection_allowed"):
            assert f'"{key}"' in job
    assert '"floor_finish_quantity_issued":False' in first
    assert '"floor_finish_quantity_issued":False' in second


def test_diagnostic_errors_cannot_echo_original_source_payloads() -> None:
    first, second = _jobs()
    assert "ORIGINAL_GRID_PRIVATE_DIAGNOSTIC_FAILED" in first
    assert "ORIGINAL_ROOM_MARK_PRIVATE_DIAGNOSTIC_FAILED" in second
    assert 'data["first_unclosed_gate"]' in first
    assert 'data.get("first_grid_vector_gate")' not in first
    assert ', data["first_unclosed_gate"]' not in first
    assert "print(json.dumps(data" not in first
    assert "print(json.dumps(r" not in second
    assert "set -euo pipefail" in first
    assert "set -euo pipefail" in second


def test_minimal_token_scope_and_exact_head_are_preserved() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read\n" in text
    assert "pull_request:\n    branches: [main]" in text
    assert "github.event.pull_request.head.sha || github.sha" in text
    assert "test \"$(git rev-parse HEAD)\" = \"$EXPECTED_SHA\"" in text
    assert text.count("actions/upload-artifact@v4") == 2
