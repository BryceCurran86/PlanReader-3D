import json
from pathlib import Path

import pytest

from tools import gpt3_owner_all_source_role_handoff as handoff
from tools import run_frozen120_owner_benchmark as runner


def test_scores_complete_projects_in_frozen_order_after_a_failure(tmp_path, monkeypatch):
    source = tmp_path / "sources"
    maps = tmp_path / "maps"
    output = tmp_path / "attempt"
    source.mkdir()
    maps.mkdir()
    sizes = dict(zip(handoff.PROJECTS, (2, 1, 1, 6), strict=True))
    monkeypatch.setattr(handoff, "original_roster", lambda project, root: [None] * sizes[project])
    calls = []

    def produce(**kwargs):
        project, directory = kwargs["project_id"], kwargs["output_dir"]
        assert kwargs["record_native_source_input_coverage"] is True
        assert kwargs["source_role_abstention_receipts"] is True
        assert kwargs["timeout_min"] == 20
        calls.append(project)
        if project == handoff.PROJECTS[0]:
            raise RuntimeError("unavailable source role")
        directory.mkdir(parents=True)
        (directory / "ALL_SOURCE_ROLES.sealed.json").write_text("{}")
        (directory / "ALL_SOURCE_ROLES.customer_rows.json").write_text("[]")
        return {
            "status": "COMPLETE",
            "native_source_input_coverage_verified": True,
            "source_role_coverage_verified": True,
            "customer_bijection_verified": project != handoff.PROJECTS[1],
        }

    def score(args):
        assert tuple(calls) == handoff.PROJECTS
        assert Path(args[args.index("--source-dir") + 1]) == source
        assert Path(args[args.index("--identity-map-dir") + 1]) == maps
        assert sorted(p.stem for p in (output / "sealed").iterdir()) == sorted(handoff.PROJECTS[2:])
        assert len(list((output / "customer").iterdir())) == 2
        assert (output / "attempt_status.json").is_file()
        return 2

    monkeypatch.setattr(handoff, "produce_all_source_roles", produce)
    monkeypatch.setattr(runner, "report_evidence", score)
    assert runner.run_benchmark(
        source_dir=source, identity_map_dir=maps, output_dir=output, timeout_min=20,
    ) == 2


def test_protected_output_is_rejected_before_source_replay(tmp_path, monkeypatch):
    source = tmp_path / "sources"
    source.mkdir()
    monkeypatch.setattr(handoff, "original_roster", lambda *_: pytest.fail("preflight started"))
    with pytest.raises(ValueError, match="protected evidence"):
        runner.run_benchmark(
            source_dir=source, identity_map_dir=tmp_path / "maps",
            output_dir=source / "attempt", timeout_min=20,
        )


def test_saved_run_rechecks_evidence_without_extracting_or_copying_score(tmp_path, monkeypatch):
    saved = tmp_path / "saved"
    (saved / "sealed").mkdir(parents=True)
    (saved / "customer").mkdir()
    old_score = saved / "frozen120_score.json"
    old_report = '{"publication_status":"PUBLISHED","coverage_accuracy":1.0}'
    old_score.write_text(old_report, encoding="utf-8")
    output = tmp_path / "rechecked"

    def unexpected(*args, **kwargs):
        pytest.fail("saved-run scoring started source extraction")

    monkeypatch.setattr(handoff, "original_roster", unexpected)
    monkeypatch.setattr(handoff, "produce_all_source_roles", unexpected)
    assert runner.main([
        "--source-dir", str(tmp_path / "sources"),
        "--identity-map-dir", str(tmp_path / "maps"),
        "--saved-run-dir", str(saved),
        "--output-dir", str(output),
    ]) == 2

    report = json.loads((output / "frozen120_score.json").read_text(encoding="utf-8"))
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["frozen_denominator"] == 120
    assert report["independently_verified_execution_count"] == 0
    assert report["coverage_accuracy"] is None
    assert old_score.read_text(encoding="utf-8") == old_report


def test_saved_run_protects_original_output_directory(tmp_path):
    saved = tmp_path / "saved"
    (saved / "sealed").mkdir(parents=True)
    (saved / "customer").mkdir()
    output = saved / "rechecked"
    with pytest.raises(ValueError, match="protected evidence"):
        runner.run_benchmark(
            source_dir=tmp_path / "sources", identity_map_dir=tmp_path / "maps",
            output_dir=output, timeout_min=20, saved_run_dir=saved,
        )
    assert not output.exists()


def test_local_launcher_checks_configured_inputs_without_starting_extraction(
    tmp_path, monkeypatch, capsys
):
    inputs = tmp_path / "originals"
    maps = tmp_path / "maps"
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"source_dir": str(inputs), "identity_map_dir": str(maps)}))

    def verified(source_dir, identity_map_dir):
        assert (source_dir, identity_map_dir) == (inputs, maps)
        return {"source_files_verified": 10, "identity_maps_present": 4}

    monkeypatch.setattr(runner, "_check_local_inputs", verified)
    monkeypatch.setattr(runner, "run_benchmark", lambda **kw: pytest.fail("extraction started"))
    assert runner.main(["benchmark", "--config", str(config), "--check-only"]) == 0
    assert json.loads(capsys.readouterr().out)["source_files_verified"] == 10


def test_hosted_run_fails_before_opening_any_original(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        runner, "_check_local_inputs", lambda *a: pytest.fail("opened private originals"),
    )
    with pytest.raises(SystemExit) as stopped:
        runner.main([
            "benchmark", "--source-dir", str(tmp_path / "sources"),
            "--identity-map-dir", str(tmp_path / "maps"),
            "--output-dir", str(tmp_path / "attempt"),
        ])
    assert stopped.value.code == 2
    assert "local only" in capsys.readouterr().err
    assert not (tmp_path / "attempt").exists()
