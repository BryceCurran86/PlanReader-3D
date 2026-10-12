"""Source stage diagnostic wrapper never changes producer decisions or receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.diag_source_closed_stage_journal as diag


def _events(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text().splitlines() if line
    ]


def test_stage_journal_returns_identical_object_and_restores_original(tmp_path, monkeypatch):
    actual = object()
    invoked = []

    def real_producer(*args, **kwargs):
        invoked.append((args, kwargs))
        return actual

    monkeypatch.setattr(diag.integration, "compose_live_canonical_rooms", real_producer)
    path = tmp_path / "stage.jsonl"
    with diag.StageJournalContext(path) as journal:
        with diag.journal_source_stages(journal):
            observed = diag.integration.compose_live_canonical_rooms("source", trusted=True)
            assert observed is actual
        assert diag.integration.compose_live_canonical_rooms is real_producer
    assert invoked == [(("source",), {"trusted": True})]
    entries = [x for x in _events(path) if x["stage"] == "compose_live_canonical_rooms"]
    assert [x["event"] for x in entries] == ["entered", "completed"]
    assert all(x["diagnostic_only"] is True for x in entries)
    assert entries[0]["call_id"] == entries[1]["call_id"]
    assert entries[1]["elapsed_ms"] >= 0


def test_stage_journal_reraises_exact_producer_failure_and_restores(tmp_path, monkeypatch):
    error = RuntimeError("authentic_source_conflict")

    def denied(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(diag.integration, "compose_live_canonical_walls", denied)
    path = tmp_path / "error.jsonl"
    with diag.StageJournalContext(path) as journal:
        with pytest.raises(RuntimeError) as caught:
            with diag.journal_source_stages(journal):
                diag.integration.compose_live_canonical_walls(None)
        assert caught.value is error
        assert diag.integration.compose_live_canonical_walls is denied
    events = [x for x in _events(path) if x["stage"] == "compose_live_canonical_walls"]
    assert [x["event"] for x in events] == ["entered", "failed"]
    assert events[1]["error_type"] == "RuntimeError"


def test_stage_journal_output_never_overwrites_previous_evidence(tmp_path):
    path = tmp_path / "already.jsonl"
    path.write_text("original evidence\n")
    with pytest.raises(FileExistsError):
        diag.StageJournal(path)
    assert path.read_text() == "original evidence\n"


def test_wrong_pdf_sha_is_rejected_before_starting_stage_or_sealed_output(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"trusted-original-source-placeholder")
    out = tmp_path / "run"
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(diag, "generate_project_handoff", lambda **kwargs: pytest.fail("source run begun"))
    monkeypatch.setattr(diag, "Path", Path)
    monkeypatch.setattr("sys.argv", [
        "tools/diag_source_closed_stage_journal.py", "--pdf", str(pdf),
        "--expected-sha256", "b" * 64, "--project-id", "project",
        "--output-dir", str(out), "--journal", str(journal),
    ])
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() != "b" * 64
    with pytest.raises(ValueError, match="original source SHA"):
        diag.main()
    assert not out.exists()
    assert not journal.exists()
