from pathlib import Path

import pytest

from tools import run_frozen120_owner_benchmark as runner


def test_scores_complete_projects_in_frozen_order_after_a_failure(tmp_path, monkeypatch):
    source = tmp_path / "sources"
    maps = tmp_path / "maps"
    output = tmp_path / "attempt"
    source.mkdir()
    maps.mkdir()
    sizes = dict(zip(runner.PROJECTS, (2, 1, 1, 6), strict=True))
    monkeypatch.setattr(runner, "original_roster", lambda project, root: [None] * sizes[project])
    calls = []

    def produce(**kwargs):
        project, directory = kwargs["project_id"], kwargs["output_dir"]
        assert kwargs["record_native_source_input_coverage"] is True
        assert kwargs["source_role_abstention_receipts"] is True
        assert kwargs["timeout_min"] == 20
        calls.append(project)
        if project == runner.PROJECTS[0]:
            raise RuntimeError("unavailable source role")
        directory.mkdir(parents=True)
        (directory / "ALL_SOURCE_ROLES.sealed.json").write_text("{}")
        (directory / "ALL_SOURCE_ROLES.customer_rows.json").write_text("[]")
        return {
            "status": "COMPLETE",
            "native_source_input_coverage_verified": True,
            "source_role_coverage_verified": True,
            "customer_bijection_verified": project != runner.PROJECTS[1],
        }

    def score(args):
        assert tuple(calls) == runner.PROJECTS
        assert Path(args[args.index("--source-dir") + 1]) == source
        assert Path(args[args.index("--identity-map-dir") + 1]) == maps
        assert sorted(p.stem for p in (output / "sealed").iterdir()) == sorted(runner.PROJECTS[2:])
        assert len(list((output / "customer").iterdir())) == 2
        assert (output / "attempt_status.json").is_file()
        return 2

    monkeypatch.setattr(runner, "produce_all_source_roles", produce)
    monkeypatch.setattr(runner, "report_evidence", score)
    assert runner.run_benchmark(
        source_dir=source, identity_map_dir=maps, output_dir=output, timeout_min=20,
    ) == 2


def test_protected_output_is_rejected_before_source_replay(tmp_path, monkeypatch):
    source = tmp_path / "sources"
    source.mkdir()
    monkeypatch.setattr(runner, "original_roster", lambda *_: pytest.fail("preflight started"))
    with pytest.raises(ValueError, match="protected evidence"):
        runner.run_benchmark(
            source_dir=source, identity_map_dir=tmp_path / "maps",
            output_dir=source / "attempt", timeout_min=20,
        )
