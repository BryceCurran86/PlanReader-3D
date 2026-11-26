import json
from pathlib import Path

import pytest

from tools import gpt3_owner_all_source_role_handoff as handoff
from tools import run_frozen120_owner_benchmark as runner


@pytest.mark.parametrize("missing_customer_receipt", (False, True))
def test_scores_complete_projects_in_frozen_order_after_a_failure(
    tmp_path, monkeypatch, missing_customer_receipt,
):
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
        first_project = project == handoff.PROJECTS[0]
        if first_project and not missing_customer_receipt:
            raise RuntimeError("unavailable source role")
        directory.mkdir(parents=True)
        (directory / "ALL_SOURCE_ROLES.sealed.json").write_text("{}")
        if not first_project:
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
        status = json.loads((output / "attempt_status.json").read_text(encoding="utf-8"))
        first = status["projects"][0]
        assert first["status"] == "ROLE_REPLAY_FAILED"
        assert first["failure_type"] == ("FileNotFoundError" if missing_customer_receipt else "RuntimeError")
        if missing_customer_receipt:
            role_seal = output / "production" / handoff.PROJECTS[0] / "ALL_SOURCE_ROLES.sealed.json"
            assert role_seal.read_text() == "{}"
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


@pytest.mark.parametrize("replace_first_copy", (False, True))
def test_failed_second_publish_removes_only_the_launcher_copy(tmp_path, monkeypatch, replace_first_copy):
    role = tmp_path / "role"
    role.mkdir()
    (role / "ALL_SOURCE_ROLES.sealed.json").write_bytes(b"sealed evidence")
    (role / "ALL_SOURCE_ROLES.customer_rows.json").write_bytes(b"customer evidence")
    sealed = tmp_path / "sealed.json"
    customer = tmp_path / "customer.json"
    publish = runner.publish_staged_file

    def competing_writer(stage, target):
        if target == customer:
            if replace_first_copy:
                competing_seal = tmp_path / "competing-seal"
                competing_seal.write_bytes(b"competing seal")
                competing_seal.replace(sealed)
            customer.write_bytes(b"competing customer rows")
        publish(stage, target)

    monkeypatch.setattr(runner, "publish_staged_file", competing_writer)
    with pytest.raises(FileExistsError):
        runner._publish_project_evidence(role, sealed, customer)

    assert customer.read_bytes() == b"competing customer rows"
    if replace_first_copy:
        assert sealed.read_bytes() == b"competing seal"
    else:
        assert not sealed.exists()
    assert not list(tmp_path.glob(".replay-*.tmp"))


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


def test_parallel_projects_are_bounded_and_published_in_frozen_order(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    source, maps, output = (tmp_path / name for name in ("sources", "maps", "attempt"))
    source.mkdir()
    maps.mkdir()
    sizes = dict(zip(handoff.PROJECTS, (2, 1, 1, 6), strict=True))
    monkeypatch.setattr(handoff, "original_roster", lambda project, root: [None] * sizes[project])
    barrier = Barrier(2, timeout=10)
    lock = Lock()
    active = 0
    peak = 0
    calls = []

    # Exercise orchestration with mock producers only; production uses spawn,
    # never threads for PDF decoding.
    def pool(*, max_workers, mp_context):
        assert max_workers == 2
        assert mp_context.get_start_method() == "spawn"
        return ThreadPoolExecutor(max_workers=max_workers)

    def produce(**kwargs):
        nonlocal active, peak
        project, directory = kwargs["project_id"], kwargs["output_dir"]
        with lock:
            active += 1
            peak = max(peak, active)
            calls.append(project)
        try:
            barrier.wait()
            if project == handoff.PROJECTS[0]:
                raise RuntimeError("failed source role")
            directory.mkdir(parents=True)
            (directory / "ALL_SOURCE_ROLES.sealed.json").write_text("{}")
            (directory / "ALL_SOURCE_ROLES.customer_rows.json").write_text("[]")
            return {"status": "COMPLETE",
                    "native_source_input_coverage_verified": True,
                    "source_role_coverage_verified": True,
                    "customer_bijection_verified": True}
        finally:
            with lock:
                active -= 1

    def score(args):
        status = json.loads((output / "attempt_status.json").read_text())
        assert [p["project_id"] for p in status["projects"]] == list(handoff.PROJECTS)
        assert status["projects"][0]["status"] == "ROLE_REPLAY_FAILED"
        assert len(list((output / "sealed").iterdir())) == 3
        assert len(list((output / "customer").iterdir())) == 3
        return 2

    monkeypatch.setattr(runner, "ProcessPoolExecutor", pool)
    monkeypatch.setattr(handoff, "produce_all_source_roles", produce)
    monkeypatch.setattr(runner, "report_evidence", score)
    assert runner.run_benchmark(
        source_dir=source, identity_map_dir=maps, output_dir=output,
        timeout_min=20, project_workers=2,
    ) == 2
    assert peak == 2
    assert sorted(calls) == sorted(handoff.PROJECTS)


@pytest.mark.parametrize("workers", (0, 3, True))
def test_unsafe_project_worker_counts_rejected(tmp_path, workers):
    with pytest.raises(ValueError, match="project_workers"):
        runner.run_benchmark(
            source_dir=tmp_path / "sources", identity_map_dir=tmp_path / "maps",
            output_dir=tmp_path / "attempt", timeout_min=20, project_workers=workers,
        )


def test_portable_input_bundle(tmp_path, monkeypatch, capsys):
    bundle = tmp_path / 'bundle'
    (bundle / 'sources').mkdir(parents=True)
    (bundle / 'identity-maps').mkdir()
    def verified(source, maps):
        assert source == bundle / 'sources'
        assert maps == bundle / 'identity-maps'
        return {'source_files_verified': 10, 'identity_maps_present': 4}
    monkeypatch.setattr(runner, '_check_local_inputs', verified)
    assert runner.main(['--input-bundle', str(bundle), '--check-only']) == 0


def test_archive_identity_rejects_modified_or_extra_files(tmp_path, monkeypatch):
    import hashlib
    import zipfile
    root = tmp_path / 'app'
    root.mkdir()
    script = root / 'app.py'
    script.write_bytes(b'original')
    archive = tmp_path / 'app.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.write(script, 'app/app.py')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(runner, '_REPO', root)
    assert runner._archive_identity(archive, digest) == 'archive-sha256:' + digest
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        runner._archive_identity(archive, '0' * 64)
    script.write_bytes(b'changed')
    with pytest.raises(ValueError, match='differs'):
        runner._archive_identity(archive, digest)
    script.write_bytes(b'original')
    (root / 'extra.py').write_bytes(b'extra')
    with pytest.raises(ValueError, match='unexpected files'):
        runner._archive_identity(archive, digest)


def test_ambiguous_discovery_fails_closed(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    with pytest.raises(ValueError, match='multiple directories'):
        runner._discover_directory(None, [a, b], 'inputs')


def test_linux_network_denial_inherited_by_child():
    import subprocess
    import sys
    import os
    import ctypes.util
    if sys.platform != 'linux' or not ctypes.util.find_library('seccomp'):
        pytest.skip('Linux libseccomp required')
    code = '''
from tools.benchmark_process_isolation import install_network_denial
import sys, subprocess
install_network_denial()
subprocess.run([sys.executable, '-B', '-c', 'from tools.benchmark_process_isolation import verify_network_denial; verify_network_denial()'], check=True)
'''
    # This subprocess uses no originals or benchmark execution. Exercise the
    # kernel mechanism independently of the hosted-run refusal (tested below).
    env = dict(os.environ)
    env.pop('GITHUB_ACTIONS', None)
    subprocess.run([sys.executable, '-B', '-c', code], check=True, env=env)


def test_linux_isolation_refuses_hosted_execution(monkeypatch):
    from tools import benchmark_process_isolation as isolation
    monkeypatch.setattr(isolation.sys, 'platform', 'linux')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    with pytest.raises(ValueError, match='local only'):
        isolation.install_network_denial()


def test_linux_network_denial_inherited_by_spawned_project_workers():
    import ctypes.util
    import os
    import subprocess
    import sys

    if sys.platform != "linux" or not ctypes.util.find_library("seccomp"):
        pytest.skip("Linux libseccomp required")
    code = """
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from tools.benchmark_process_isolation import install_network_denial, verify_network_denial
install_network_denial()
with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as pool:
    futures = [pool.submit(verify_network_denial) for _ in range(4)]
    for future in futures:
        assert future.result(timeout=20) is None
verify_network_denial()
"""
    # Synthetic kernel-only test; never open sources or start the benchmark.
    env = dict(os.environ)
    env.pop("GITHUB_ACTIONS", None)
    subprocess.run([sys.executable, "-B", "-c", code], check=True, env=env, timeout=45)
