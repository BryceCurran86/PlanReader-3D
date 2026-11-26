"""Runtime diagnostics must not alter production evidence or exceptions."""
import pytest

from tools import run_source_closed_project_handoff as handoff


@pytest.mark.parametrize("mode", (None, "stages", "cpu"))
def test_checkpoint_keeps_monotonic_time_and_is_opt_in(monkeypatch, capsys, mode):
    if mode is None:
        monkeypatch.delenv("PB_SOURCE_HANDOFF_PROFILE", raising=False)
    else:
        monkeypatch.setenv("PB_SOURCE_HANDOFF_PROFILE", mode)
    monkeypatch.setattr(handoff, "perf_counter", lambda: 8.25)
    assert handoff._runtime_checkpoint(5.0, "physical_claim") == 8.25
    output = capsys.readouterr().err
    assert output == ("" if mode is None else
                      "SOURCE_STAGE physical_claim elapsed_seconds=3.250000\n")


@pytest.mark.parametrize("mode", ("stages", "cpu"))
def test_cpu_profile_preserves_original_exception(monkeypatch, capsys, mode):
    monkeypatch.setenv("PB_SOURCE_HANDOFF_PROFILE", mode)
    original = RuntimeError("original failure")
    with pytest.raises(RuntimeError) as caught:
        with handoff._profile_source_handoff():
            raise original
    assert caught.value is original
    output = capsys.readouterr().err
    assert ("SOURCE_CPU_PROFILE" in output) == (mode == "cpu")
    assert "original failure" not in output


def test_cpu_profile_does_not_modify_returned_evidence(monkeypatch, capsys):
    monkeypatch.setenv("PB_SOURCE_HANDOFF_PROFILE", "cpu")
    payload = {"sealed": False, "customer_rows": []}
    with handoff._profile_source_handoff():
        result = payload
    assert result is payload
    assert "SOURCE_CPU_PROFILE" in capsys.readouterr().err
