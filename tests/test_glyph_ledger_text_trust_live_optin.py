"""The glyph-ledger text trust must be reachable from the live entry points, default OFF, independent of the finish-text opt-in.

SourceVisibilityProducer(source_glyph_ledger_text_trust=True) trusts words whose only blocker is the glyph proof, through sealed raster
corroboration. These tests are synthetic and only observe what reaches the producer; no OCR runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

import pb_live_physical_net_wall_integration as live
from tools import run_source_closed_project_handoff as handoff

FLAG = "source_glyph_ledger_text_trust"


class _Stop(Exception):
    """Raised by a spy once the interesting call has been recorded."""


def _pdf(tmp_path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=300, height=300)
    page.insert_text((40, 80), "ROOM", fontsize=12)
    path = tmp_path / "source.pdf"
    document.save(path)
    document.close()
    return path


def _producer_spy(monkeypatch):
    recorded: list[dict] = []

    class Spy:
        def __init__(self, **kwargs):
            recorded.append(kwargs)
            raise _Stop()

    monkeypatch.setattr(live, "SourceVisibilityProducer", Spy)
    return recorded


@pytest.mark.parametrize("bad", [1, 0, "yes", None, 1.0])
def test_the_flag_must_be_an_explicit_boolean_before_any_source_work(tmp_path, monkeypatch, bad):
    recorded = _producer_spy(monkeypatch)
    source = _pdf(tmp_path)
    for entry in (live.collect_live_physical_net_wall_claim, live._collect_live_physical_net_wall_claim):
        with pytest.raises(ValueError, match="explicit boolean"):
            entry(source, **{FLAG: bad})
    assert recorded == []


def test_default_and_explicit_false_never_pass_the_flag_to_the_producer(tmp_path, monkeypatch):
    recorded = _producer_spy(monkeypatch)
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path))
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path), **{FLAG: False})
    assert all(FLAG not in kwargs for kwargs in recorded) and len(recorded) == 2


def test_opt_in_reaches_the_source_producer_without_the_finish_text_flag(tmp_path, monkeypatch):
    recorded = _producer_spy(monkeypatch)
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path), **{FLAG: True})
    assert recorded[0][FLAG] is True
    assert "source_native_finish_text_shadow" not in recorded[0]


def test_both_flags_are_independent_and_can_be_combined(tmp_path, monkeypatch):
    recorded = _producer_spy(monkeypatch)
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(
            _pdf(tmp_path), source_native_finish_text_shadow=True, **{FLAG: True})
    assert recorded[0][FLAG] is True and recorded[0]["source_native_finish_text_shadow"] is True
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path), source_native_finish_text_shadow=True)
    assert FLAG not in recorded[1] and recorded[1]["source_native_finish_text_shadow"] is True


def test_the_public_wrapper_forwards_only_when_on(tmp_path, monkeypatch):
    seen: list[dict] = []

    def fake(path, **kwargs):
        seen.append(kwargs)
        return "claim"

    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", fake)
    live.collect_live_physical_net_wall_claim(tmp_path / "x.pdf")
    live.collect_live_physical_net_wall_claim(tmp_path / "x.pdf", **{FLAG: True})
    assert FLAG not in seen[0]
    assert seen[1][FLAG] is True


def _handoff_claim_spy(monkeypatch):
    seen: list[dict] = []

    def spy(*args, **kwargs):
        seen.append(kwargs)
        raise _Stop()

    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0,), (), 1))
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", spy)
    return seen


def _run_handoff(tmp_path, **extra):
    return handoff.generate_project_handoff(
        pdf_path=_pdf(tmp_path), project_id="project-1", workspace_id=1,
        output_dir=tmp_path / "out", family_group="core", **extra,
    )


def test_handoff_default_does_not_forward_or_record_the_flag(tmp_path, monkeypatch):
    seen = _handoff_claim_spy(monkeypatch)
    with pytest.raises(_Stop):
        _run_handoff(tmp_path)
    assert FLAG not in seen[0]
    summary = json.loads((tmp_path / "out" / "production_summary.json").read_text())
    assert FLAG not in summary


def test_handoff_opt_in_is_forwarded_and_recorded(tmp_path, monkeypatch):
    seen = _handoff_claim_spy(monkeypatch)
    with pytest.raises(_Stop):
        _run_handoff(tmp_path, **{FLAG: True})
    assert seen[0][FLAG] is True
    summary = json.loads((tmp_path / "out" / "production_summary.json").read_text())
    assert summary[FLAG] is True
    assert summary["benchmark_score_granted"] is False


@pytest.mark.parametrize("bad", [1, "true", None])
def test_handoff_rejects_a_non_boolean_flag_before_touching_the_output_directory(tmp_path, monkeypatch, bad):
    _handoff_claim_spy(monkeypatch)
    with pytest.raises(ValueError, match="explicit boolean"):
        _run_handoff(tmp_path, **{FLAG: bad})
    assert not (tmp_path / "out").exists()


def test_cli_flag_defaults_off_and_is_a_plain_switch():
    parser = handoff._parser()
    base = ["--pdf", "x.pdf", "--project-id", "p", "--output-dir", "o"]
    assert parser.parse_args(base).source_glyph_ledger_text_trust is False
    assert parser.parse_args([*base, "--source-glyph-ledger-text-trust"]).source_glyph_ledger_text_trust is True
