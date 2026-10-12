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


def test_original_source_changed_during_handoff_fails_diagnostic_after_run(tmp_path, monkeypatch):
    original = b"exact-original-pdf-bytes"
    source = tmp_path / "source.pdf"
    source.write_bytes(original)
    expected = hashlib.sha256(original).hexdigest()
    journal = tmp_path / "stage.jsonl"
    out = tmp_path / "run"

    def fake_original_handoff(**kwargs):
        assert kwargs["pdf_path"] == source
        source.write_bytes(b"tampered-source-after-snapshot")
        return {"status": "sealed", "source_sha256": expected}

    monkeypatch.setattr(diag, "generate_project_handoff", fake_original_handoff)
    monkeypatch.setattr("sys.argv", [
        "stage-profile", "--pdf", str(source),
        "--expected-sha256", expected,
        "--project-id", "source-project", "--output-dir", str(out),
        "--journal", str(journal),
    ])
    with pytest.raises(RuntimeError, match="source identity changed"):
        diag.main()
    assert journal.exists()
    events = _events(journal)
    assert events[0]["event"] == "sha_verified"
    assert all(event["diagnostic_only"] for event in events)


def test_original_wall_page_and_raster_substage_observation_changes_no_producer_result(
    tmp_path, monkeypatch,
):
    wall_result = object()
    raster_result = object()
    calls = []

    def original_wall_build(*args, **kwargs):
        calls.append(("wall", args, kwargs))
        return wall_result

    def original_raster_augment(self, *args, **kwargs):
        calls.append(("raster", args, kwargs))
        return raster_result

    monkeypatch.setattr(diag.wall_candidates, "_build_scope_result", original_wall_build)
    monkeypatch.setattr(
        diag.integration.SourceVisibilityProducer,
        "augment_with_raster_visible_segments",
        original_raster_augment,
    )
    source = object.__new__(diag.integration.SourceVisibilityProducer)
    journal_path = tmp_path / "source-substages.jsonl"

    with diag.StageJournalContext(journal_path) as journal:
        with diag.journal_source_stages(journal):
            assert source.augment_with_raster_visible_segments(
                "rev", page_ids=("7", "30")
            ) is raster_result
            assert diag.wall_candidates._build_scope_result(
                page_id="7", source_bytes=b"unchanged-original-source"
            ) is wall_result
        assert diag.wall_candidates._build_scope_result is original_wall_build
        assert (
            diag.integration.SourceVisibilityProducer.augment_with_raster_visible_segments
            is original_raster_augment
        )

    assert calls == [
        ("raster", ("rev",), {"page_ids": ("7", "30")}),
        ("wall", (), {"page_id": "7", "source_bytes": b"unchanged-original-source"}),
    ]
    entries = _events(journal_path)
    assert [row["event"] for row in entries] == [
        "entered", "completed", "entered", "completed"
    ]
    assert [row["stage"] for row in entries] == [
        "SourceVisibilityProducer.augment_with_raster_visible_segments",
        "SourceVisibilityProducer.augment_with_raster_visible_segments",
        "physical_wall_candidate_page_build",
        "physical_wall_candidate_page_build",
    ]
    assert [row.get("source_page_id") for row in entries] == [
        None, None, "7", "7"
    ]
    assert all(row["diagnostic_only"] is True for row in entries)


def test_wall_page_failure_is_logged_without_fallback_or_mutating_exception(
    tmp_path, monkeypatch,
):
    failure = ValueError("original-wall-source-opposition-unavailable")

    def denied_page_build(**kwargs):
        raise failure

    monkeypatch.setattr(
        diag.wall_candidates, "_build_scope_result", denied_page_build
    )
    journal_path = tmp_path / "failed-wall-page.jsonl"
    with diag.StageJournalContext(journal_path) as journal:
        with pytest.raises(ValueError) as caught:
            with diag.journal_source_stages(journal):
                diag.wall_candidates._build_scope_result(page_id="30")
        assert caught.value is failure
        assert diag.wall_candidates._build_scope_result is denied_page_build

    events = _events(journal_path)
    assert [e["event"] for e in events] == ["entered", "failed"]
    assert [e["source_page_id"] for e in events] == ["30", "30"]
    assert events[1]["error_type"] == "ValueError"
