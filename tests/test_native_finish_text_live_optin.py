"""The merged native-text source proof must be reachable from the live entry points, default OFF.

SourceVisibilityProducer(source_native_finish_text_shadow=True) is the opt-in to the original-PDF
source-byte -> ToUnicode -> symbol-GID chain plus the raw no-active-clip proof. Before this wiring no
live entry point could turn it on, so subset-font CAD text stayed untrusted. These tests are synthetic.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import fitz
import pytest

import pb_live_physical_net_wall_integration as live
from tools import run_source_closed_project_handoff as handoff

ROOT = Path(__file__).resolve().parents[1]


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
            entry(source, source_native_finish_text_shadow=bad)
    assert recorded == []


def test_default_never_passes_the_flag_to_the_producer(tmp_path, monkeypatch):
    recorded = _producer_spy(monkeypatch)
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path))
    assert recorded == [{
        "producer_method": "live-physical-net-wall",
        "producer_version": live.LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    }]


def test_explicit_false_is_the_same_as_the_default(tmp_path, monkeypatch):
    recorded = _producer_spy(monkeypatch)
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path), source_native_finish_text_shadow=False)
    assert "source_native_finish_text_shadow" not in recorded[0]


def test_opt_in_reaches_the_source_producer_through_the_public_entry(tmp_path, monkeypatch):
    recorded = _producer_spy(monkeypatch)
    with pytest.raises(_Stop):
        live.collect_live_physical_net_wall_claim(_pdf(tmp_path), source_native_finish_text_shadow=True)
    assert recorded[0]["source_native_finish_text_shadow"] is True


def test_every_source_producer_in_the_live_chain_receives_the_same_kwargs():
    tree = ast.parse((ROOT / "pb_live_physical_net_wall_integration.py").read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "SourceVisibilityProducer"
    ]
    assert len(calls) == 2  # geometry source and the independent surface-semantic source
    for call in calls:
        unpacked = [kw.value.id for kw in call.keywords if kw.arg is None and isinstance(kw.value, ast.Name)]
        assert unpacked == ["native_text_kwargs"], ast.dump(call)[:200]


def test_the_public_wrapper_forwards_only_when_on(tmp_path, monkeypatch):
    seen: list[dict] = []

    def fake(path, **kwargs):
        seen.append(kwargs)
        return "claim"

    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", fake)
    assert live.collect_live_physical_net_wall_claim(tmp_path / "x.pdf") == "claim"
    assert live.collect_live_physical_net_wall_claim(tmp_path / "x.pdf", source_native_finish_text_shadow=True) == "claim"
    assert "source_native_finish_text_shadow" not in seen[0]
    assert seen[1]["source_native_finish_text_shadow"] is True


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
    assert "source_native_finish_text_shadow" not in seen[0]
    summary = json.loads((tmp_path / "out" / "production_summary.json").read_text())
    assert "source_native_finish_text_shadow" not in summary


def test_handoff_opt_in_is_forwarded_and_recorded(tmp_path, monkeypatch):
    seen = _handoff_claim_spy(monkeypatch)
    with pytest.raises(_Stop):
        _run_handoff(tmp_path, source_native_finish_text_shadow=True)
    assert seen[0]["source_native_finish_text_shadow"] is True
    summary = json.loads((tmp_path / "out" / "production_summary.json").read_text())
    assert summary["source_native_finish_text_shadow"] is True
    assert summary["benchmark_score_granted"] is False


@pytest.mark.parametrize("bad", [1, "true", None])
def test_handoff_rejects_a_non_boolean_flag_before_touching_the_output_directory(tmp_path, monkeypatch, bad):
    _handoff_claim_spy(monkeypatch)
    with pytest.raises(ValueError, match="explicit boolean"):
        _run_handoff(tmp_path, source_native_finish_text_shadow=bad)
    assert not (tmp_path / "out").exists()


def test_cli_flag_defaults_off_and_is_a_plain_switch():
    parser = handoff._parser()
    base = ["--pdf", "x.pdf", "--project-id", "p", "--output-dir", "o"]
    assert parser.parse_args(base).source_native_finish_text_shadow is False
    assert parser.parse_args([*base, "--source-native-finish-text-shadow"]).source_native_finish_text_shadow is True


def test_fonttools_is_declared_because_the_proof_silently_abstains_without_it():
    lines = [line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    pins = [line for line in lines if line.lower().startswith("fonttools")]
    assert len(pins) == 1 and pins[0].startswith("fonttools==")
