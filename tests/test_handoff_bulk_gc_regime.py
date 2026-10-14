"""The handoff runner pauses the cyclic collector for one source run, and only for that run."""
from __future__ import annotations

import gc

import pytest

import tools.run_source_closed_project_handoff as handoff


@pytest.fixture(autouse=True)
def _restore_gc_state():
    was_enabled = gc.isenabled()
    yield
    if was_enabled:
        gc.enable()
    else:
        gc.disable()


def test_collector_is_paused_inside_and_restored_after(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.enable()
    with handoff._bulk_source_gc_regime():
        assert not gc.isenabled()
    assert gc.isenabled()


def test_collector_is_restored_after_an_error(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.enable()
    with pytest.raises(RuntimeError, match="boom"), handoff._bulk_source_gc_regime():
        assert not gc.isenabled()
        raise RuntimeError("boom")
    assert gc.isenabled()


def test_environment_opt_out_keeps_the_collector_enabled(monkeypatch):
    monkeypatch.setenv("PB_KEEP_CYCLIC_GC", "1")
    gc.enable()
    with handoff._bulk_source_gc_regime():
        assert gc.isenabled()
    assert gc.isenabled()


def test_a_caller_that_already_disabled_the_collector_is_not_overridden(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.disable()
    with handoff._bulk_source_gc_regime():
        assert not gc.isenabled()
    assert not gc.isenabled()


def test_nested_regimes_restore_only_at_the_outermost_exit(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.enable()
    with handoff._bulk_source_gc_regime():
        with handoff._bulk_source_gc_regime():
            assert not gc.isenabled()
        assert not gc.isenabled()
    assert gc.isenabled()


def _stub_inputs(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%stub\n")
    seen = {}

    def locked(**kwargs):
        seen["collector_enabled"] = gc.isenabled()
        seen["lock_exists"] = (kwargs["output_dir"] / ".source_closed_handoff.lock").exists()
        if seen.get("raise"):
            raise RuntimeError("stub failure")
        return {"status": "stub"}

    monkeypatch.setattr(handoff, "_generate_project_handoff_locked", locked)
    return pdf, seen


def test_generate_project_handoff_runs_inside_the_regime(tmp_path, monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.enable()
    pdf, seen = _stub_inputs(tmp_path, monkeypatch)
    out = tmp_path / "out"
    result = handoff.generate_project_handoff(
        pdf_path=pdf, project_id="proj", workspace_id=1, output_dir=out
    )
    assert result == {"status": "stub"}
    assert seen == {"collector_enabled": False, "lock_exists": True}
    assert gc.isenabled()
    assert not (out / ".source_closed_handoff.lock").exists()


def test_generate_project_handoff_restores_the_collector_when_the_run_fails(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.enable()
    pdf, seen = _stub_inputs(tmp_path, monkeypatch)
    seen["raise"] = True
    out = tmp_path / "out"
    with pytest.raises(RuntimeError, match="stub failure"):
        handoff.generate_project_handoff(
            pdf_path=pdf, project_id="proj", workspace_id=1, output_dir=out
        )
    assert seen["collector_enabled"] is False
    assert gc.isenabled()
    assert not (out / ".source_closed_handoff.lock").exists()


def test_invalid_inputs_never_reach_the_regime(tmp_path, monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    gc.enable()
    entered = []
    monkeypatch.setattr(
        handoff,
        "_bulk_source_gc_regime",
        lambda: entered.append("entered") or handoff.contextlib.nullcontext(),
    )
    with pytest.raises(FileNotFoundError):
        handoff.generate_project_handoff(
            pdf_path=tmp_path / "missing.pdf",
            project_id="proj",
            workspace_id=1,
            output_dir=tmp_path / "out",
        )
    assert entered == []
    assert gc.isenabled()


@pytest.mark.parametrize("value,expected", [
    (None, "staged"), ("disabled", "disabled"), ("staged", "staged"),
    ("default", "default"), ("STAGED", "staged"), (" staged ", "staged"),
    ("nonsense", "staged"), ("", "staged"),
])
def test_mode_selection(monkeypatch, value, expected):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    if value is None:
        monkeypatch.delenv("PB_CYCLIC_GC_MODE", raising=False)
    else:
        monkeypatch.setenv("PB_CYCLIC_GC_MODE", value)
    assert handoff._cyclic_gc_mode() == expected


def test_keep_switch_wins_over_the_mode(monkeypatch):
    monkeypatch.setenv("PB_CYCLIC_GC_MODE", "staged")
    monkeypatch.setenv("PB_KEEP_CYCLIC_GC", "1")
    assert handoff._cyclic_gc_mode() == "default"


def test_default_mode_leaves_the_collector_alone(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    monkeypatch.setenv("PB_CYCLIC_GC_MODE", "default")
    gc.enable()
    with handoff._bulk_source_gc_regime():
        assert gc.isenabled()


def test_stage_boundary_collects_only_under_the_staged_regime(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    calls = []
    monkeypatch.setattr(handoff.gc, "collect", lambda *a, **k: calls.append("collect") or 0)
    gc.enable()
    handoff._gc_stage_boundary()
    assert calls == []
    for mode, expected in (("disabled", 0), ("staged", 1)):
        monkeypatch.setenv("PB_CYCLIC_GC_MODE", mode)
        calls.clear()
        with handoff._bulk_source_gc_regime():
            assert not gc.isenabled()
            handoff._gc_stage_boundary()
            handoff._gc_stage_boundary()
        assert len(calls) == expected * 2
        assert gc.isenabled()
    calls.clear()
    handoff._gc_stage_boundary()
    assert calls == [], "the staged mode must not leak outside its regime"


def test_the_unset_default_is_staged_and_collects_at_stage_boundaries(monkeypatch):
    monkeypatch.delenv("PB_KEEP_CYCLIC_GC", raising=False)
    monkeypatch.delenv("PB_CYCLIC_GC_MODE", raising=False)
    calls = []
    monkeypatch.setattr(handoff.gc, "collect", lambda *a, **k: calls.append("collect") or 0)
    gc.enable()
    with handoff._bulk_source_gc_regime():
        assert not gc.isenabled()
        handoff._gc_stage_boundary()
    assert calls == ["collect"]
    assert gc.isenabled()


def test_both_major_stages_are_followed_by_a_stage_boundary():
    """A collector call must be followed immediately by _gc_stage_boundary() in the same block."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(handoff._generate_project_handoff_locked).lstrip())
    wanted = {"collect_live_physical_net_wall_claim", "collect_live_ceiling_lining_claims"}
    followed = set()
    for node in ast.walk(tree):
        for block in (getattr(node, "body", None), getattr(node, "orelse", None), getattr(node, "finalbody", None)):
            if not isinstance(block, list):
                continue
            for index, statement in enumerate(block[:-1]):
                value = getattr(statement, "value", None)
                if isinstance(statement, ast.Assign) and isinstance(value, ast.Call):
                    name = getattr(value.func, "id", None)
                    nxt = block[index + 1]
                    if (
                        name in wanted
                        and isinstance(nxt, ast.Expr)
                        and isinstance(nxt.value, ast.Call)
                        and getattr(nxt.value.func, "id", None) == "_gc_stage_boundary"
                    ):
                        followed.add(name)
    assert followed == wanted
