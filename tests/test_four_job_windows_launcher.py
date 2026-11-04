"""The owner-side launcher is a harness: it must verify bytes, bound runtime and never leak local paths."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from tools import four_job_windows_launcher as launcher


def _kit(root: Path, *, damage: str | None = None) -> Path:
    docs = []
    for index, project in enumerate(launcher.PROJECTS):
        name = f"doc{index}.pdf"
        payload = f"%PDF synthetic {index}".encode()
        folder = root / "sources" / project
        folder.mkdir(parents=True)
        (folder / name).write_bytes(payload)
        docs.append({"project_id": project, "manifest_name": name,
                     "expected_size_bytes": len(payload),
                     "original_sha256": hashlib.sha256(payload).hexdigest()})
    # The inventory needs ten entries; add six more documents under the first project folders.
    for index in range(4, 10):
        project = launcher.PROJECTS[index % 4]
        name = f"extra{index}.pdf"
        payload = f"%PDF synthetic extra {index}".encode()
        (root / "sources" / project / name).write_bytes(payload)
        docs.append({"project_id": project, "manifest_name": name,
                     "expected_size_bytes": len(payload),
                     "original_sha256": hashlib.sha256(payload).hexdigest()})
    (root / "LOCAL_SOURCE_INVENTORY.json").write_text(json.dumps({
        "benchmark_id": "full_plan_takeoff_reconciliation_v2", "docs": docs}), encoding="utf-8")
    if damage == "missing":
        (root / "sources" / docs[0]["project_id"] / docs[0]["manifest_name"]).unlink()
    elif damage == "changed":
        path = root / "sources" / docs[1]["project_id"] / docs[1]["manifest_name"]
        data = bytearray(path.read_bytes())
        data[-1] ^= 1  # same size, different bytes
        path.write_bytes(bytes(data))
    return root


def test_verify_originals_accepts_exact_bytes_and_writes_a_report(tmp_path):
    kit = _kit(tmp_path / "kit")
    report = tmp_path / "report"
    assert launcher.verify_originals(kit, report) is True
    written = json.loads((report / "SOURCE_SHA_VERIFICATION.json").read_text(encoding="utf-8"))
    assert written["verified_document_count"] == 10 and written["score_granted"] is False


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_verify_originals_rejects_missing_or_same_size_modified_bytes(tmp_path, damage):
    kit = _kit(tmp_path / "kit", damage=damage)
    assert launcher.verify_originals(kit, tmp_path / "report") is False


def test_verify_originals_requires_exactly_ten_documents(tmp_path):
    kit = _kit(tmp_path / "kit")
    inventory = json.loads((kit / "LOCAL_SOURCE_INVENTORY.json").read_text(encoding="utf-8"))
    inventory["docs"] = inventory["docs"][:9]
    (kit / "LOCAL_SOURCE_INVENTORY.json").write_text(json.dumps(inventory), encoding="utf-8")
    with pytest.raises(ValueError, match="ten original"):
        launcher.verify_originals(kit, tmp_path / "report")


def test_verify_originals_accepts_inventory_with_utf8_bom(tmp_path):
    kit = _kit(tmp_path / "kit")
    path = kit / "LOCAL_SOURCE_INVENTORY.json"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert launcher.verify_originals(kit, tmp_path / "report") is True


def test_output_report_creates_nested_parent(tmp_path):
    target = tmp_path / "a" / "b" / "report.json"
    launcher.output_report(target, {"k": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"k": 1}


def test_run_logged_kills_a_process_that_exceeds_its_limit(tmp_path):
    rc, status, _ = launcher.run_logged(
        [sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, tmp_path / "x.log",
        timeout_s=1, poll_s=0.2)
    assert (rc, status) == (None, "TIMEOUT")


def test_run_logged_reports_exit_codes(tmp_path):
    assert launcher.run_logged([sys.executable, "-c", "pass"], tmp_path, tmp_path / "ok.log",
                               poll_s=0.2)[:2] == (0, "COMPLETED")
    rc, status, _ = launcher.run_logged([sys.executable, "-c", "raise SystemExit(3)"], tmp_path,
                                        tmp_path / "bad.log", poll_s=0.2)
    assert (rc, status) == (3, "PROCESS_FAILED")


def test_share_safe_status_removes_the_local_home_path():
    bs = chr(92)
    home = "C:" + bs + "Users" + bs + "someone"
    status = {"output_folder": home + bs + "Documents" + bs + "Run", "n": 1}
    safe = launcher.share_safe(status, home)
    assert "someone" not in json.dumps(safe) and safe["n"] == 1
    assert safe["output_folder"].startswith("<HOME>")


def test_sample_memory_sums_the_process_tree_and_never_raises():
    ws_kb, private_kb, _free = launcher.sample_memory_kb(os.getpid())
    assert ws_kb > 0 and private_kb > 0
    assert len(launcher.sample_memory_kb(999_999_999)) == 3  # unknown pid: measured as nothing, no exception


def test_memory_limit_stops_a_process_that_commits_too_much(tmp_path):
    code = ("b = bytearray(400 * 1024 * 1024); "
            "[b.__setitem__(i, 1) for i in range(0, len(b), 4096)]; "
            "import time; time.sleep(60)")
    rc, status, usage = launcher.run_logged(
        [sys.executable, "-c", code], tmp_path, tmp_path / "m.log",
        timeout_s=60, poll_s=0.5, max_private_mb=150)
    assert (rc, status) == (None, "MEMORY_LIMIT")
    assert usage["peak_private_kb"] > 150 * 1024


def test_system_memory_guard_stops_when_the_machine_has_no_headroom(tmp_path):
    rc, status, _ = launcher.run_logged(
        [sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, tmp_path / "g.log",
        timeout_s=60, poll_s=0.5, min_free_commit_mb=10 ** 9)
    assert (rc, status) == (None, "SYSTEM_MEMORY_GUARD")


def test_a_process_under_its_limits_still_completes_and_reports_peaks(tmp_path):
    rc, status, usage = launcher.run_logged(
        [sys.executable, "-c", "import time; time.sleep(1.5)"], tmp_path, tmp_path / "ok.log",
        timeout_s=60, poll_s=0.3, track_memory=True, max_private_mb=4096, min_free_commit_mb=1)
    assert (rc, status) == (0, "COMPLETED")
    assert usage["peak_private_kb"] > 0


def test_the_ocr_extras_command_installs_only_the_two_optional_packages_into_the_given_environment():
    from pathlib import Path

    command = launcher.ocr_install_command(Path("venv") / "python.exe")
    assert command[0].endswith("python.exe") and command[1:4] == ["-m", "pip", "install"]
    assert command[-2:] == ["rapidocr", "onnxruntime"] and "--disable-pip-version-check" in command
    assert not any(part.startswith("-r") or part == "requirements.txt" for part in command)


class _GitResult:
    def __init__(self, code: int, out: str = "", err: str = ""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def test_stale_checkout_is_not_reused_when_the_requested_ref_cannot_be_fetched(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    session = tmp_path / "session"
    session.mkdir()
    calls = []

    def fake_git(args, cwd):
        calls.append(list(args))
        return _GitResult(1, err="offline")

    monkeypatch.setattr(launcher, "git", fake_git)
    assert launcher.refresh_snapshot(repo, tmp_path, session, "main") is None
    assert calls == [["fetch", "--depth", "1", "origin", "main"]]
    written = json.loads((session / "SNAPSHOT_REFRESH.json").read_text(encoding="utf-8"))
    assert written["status"] == "FETCH_FAILED"
    assert written["repo_head_used"] is None
    assert written["preflight_started"] is False and written["production_started"] is False
    assert written["official_four_project_coverage_accuracy"] is None


def test_main_does_not_start_preflight_after_a_failed_snapshot_fetch(tmp_path, monkeypatch):
    kit = _kit(tmp_path / "kit")
    home = tmp_path / "home"
    repo = home / "Documents" / "PlanReader_Private_V2_Run" / "repo_readonly_snapshot"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(kit)
    monkeypatch.setattr(sys, "argv", ["four_job_windows_launcher.py"])
    monkeypatch.setattr(launcher.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(launcher.shutil, "which", lambda _name: "git")
    producer_calls = []

    def fake_git(args, cwd):
        return _GitResult(1, err="offline")

    def forbidden(*_args, **_kwargs):
        producer_calls.append("run")
        raise AssertionError("preflight or production started after a failed fetch")

    monkeypatch.setattr(launcher, "git", fake_git)
    monkeypatch.setattr(launcher, "run_logged", forbidden)
    assert launcher.main() == 4
    assert producer_calls == []


def test_pinned_commit_mismatch_does_not_return_a_different_head(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    session = tmp_path / "session"
    session.mkdir()
    requested = "a" * 40
    other = "b" * 40

    def fake_git(args, cwd):
        if args[0] == "fetch":
            return _GitResult(0)
        if args[0] == "checkout":
            return _GitResult(0)
        if args[:2] == ["rev-parse", "HEAD"]:
            return _GitResult(0, out=other + "\n")
        raise AssertionError(args)

    monkeypatch.setattr(launcher, "git", fake_git)
    assert launcher.refresh_snapshot(repo, tmp_path, session, requested) is None
    written = json.loads((session / "SNAPSHOT_REFRESH.json").read_text(encoding="utf-8"))
    assert written["status"] == "PINNED_COMMIT_MISMATCH"


def test_successful_refresh_returns_the_checked_out_head(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    session = tmp_path / "session"
    session.mkdir()
    head = "c" * 40
    calls = []

    def fake_git(args, cwd):
        calls.append(list(args))
        if args[0] == "fetch":
            return _GitResult(0)
        if args[0] == "checkout":
            return _GitResult(0)
        if args[:2] == ["rev-parse", "HEAD"]:
            return _GitResult(0, out=head + "\n")
        raise AssertionError(args)

    monkeypatch.setattr(launcher, "git", fake_git)
    assert launcher.refresh_snapshot(repo, tmp_path, session, "main") == head
    assert ["checkout", "--detach", "FETCH_HEAD"] in calls
    written = json.loads((session / "SNAPSHOT_REFRESH.json").read_text(encoding="utf-8"))
    assert written["status"] == "CHECKED_OUT" and written["repo_head_used"] == head


def test_handoff_bootstrap_keeps_an_apostrophe_in_a_windows_path_as_data():
    out = Path("C:/Users/O'Brien/Run")
    pdf = Path("C:/Users/O'Brien/plan's.pdf")
    code = launcher.handoff_bootstrap(out, pdf, launcher.PROJECTS[1], 10)
    compile(code, "<bootstrap>", "exec")
    captured = {}

    class _File:
        def write(self, _text):
            return 0

    def fake_open(path, mode="a", encoding="utf-8"):
        captured["opened"] = path
        return _File()

    import types
    faulthandler = types.ModuleType("faulthandler")
    faulthandler.dump_traceback_later = lambda *args, **kwargs: captured.setdefault("dump", True)
    runpy = types.ModuleType("runpy")

    def run_module(name, run_name, alter_sys):
        captured["argv"] = list(sys.argv)
        captured["module"] = name

    runpy.run_module = run_module
    previous = {name: sys.modules.get(name) for name in ("faulthandler", "runpy")}
    sys.modules["faulthandler"] = faulthandler
    sys.modules["runpy"] = runpy
    import builtins
    real_open = builtins.open
    builtins.open = fake_open
    try:
        exec(code, {"__name__": "__main__"})
    finally:
        builtins.open = real_open
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    assert captured["opened"] == str(out / "stack_dumps.txt")
    assert captured["argv"][captured["argv"].index("--pdf") + 1] == str(pdf)
    assert captured["argv"][captured["argv"].index("--output-dir") + 1] == str(out)
    assert captured["module"] == "tools.run_source_closed_project_handoff"


def test_timeout_status_keeps_the_stack_dump_tail_without_inventing_a_stage(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "stack_dumps.txt").write_text("frame one\nframe two\n", encoding="utf-8")
    assert launcher.timeout_stack_tail(out) == "frame one\nframe two"
    assert launcher.timeout_stack_tail(tmp_path / "missing") == "no stack dump was written"


def test_with_ocr_is_off_by_default_and_the_limits_have_safe_defaults():
    parser = launcher.build_parser()
    defaults = parser.parse_args([])
    assert defaults.with_ocr is False and defaults.max_private_gb == 10.0 and defaults.min_free_commit_gb == 3.0
    assert defaults.timeout_min == 180 and defaults.only is None and defaults.source_only is False
    assert parser.parse_args(["--with-ocr"]).with_ocr is True


def test_bounded_owner_source_scope_passes_explicit_family_and_floor_plan_page():
    code = launcher.handoff_bootstrap(
        Path("C:/Owner's Run"), Path("C:/Private/Original's Plan.pdf"),
        launcher.PROJECTS[2], 4, family_group="floor_area",
        source_plan_page_index=6,
    )
    compile(code, "<bounded-owner-bootstrap>", "exec")
    assert "'--family-group', 'floor_area'" in code
    assert "'--source-plan-page-index', 6" in code
    assert "'--project-id', 'au_qld_maryborough_service_station'" in code
    assert "Official" not in code and "coverage_accuracy" not in code

    unchanged = launcher.handoff_bootstrap(
        Path("C:/Private/Run"), Path("C:/Private/Plan.pdf"), launcher.PROJECTS[0], 4
    )
    assert "'--family-group', 'all'" in unchanged
    assert "'--source-plan-page-index'" not in unchanged


@pytest.mark.parametrize("family,page", [
    ("not-a-family", None), ("all", -1), ("floor_area", True),
    ("core", "7"), ("surfaces", -2),
])
def test_restrictive_owner_handoff_rejects_unsafe_or_untyped_source_override(family, page):
    with pytest.raises(ValueError):
        launcher.handoff_bootstrap(
            Path("private_run"), Path("original.pdf"),
            launcher.PROJECTS[0], 1, family_group=family,
            source_plan_page_index=page,
        )


def test_owner_partial_source_modes_are_explicit_and_default_remains_unmodified():
    parser = launcher.build_parser()
    default = parser.parse_args([])
    assert default.family_group == "all" and default.source_plan_page_index is None
    selected = parser.parse_args([
        "--only", "au_qld_maryborough_service_station",
        "--family-group", "floor_area",
        "--source-plan-page-index", "6",
    ])
    assert selected.only == [launcher.PROJECTS[2]]
    assert selected.family_group == "floor_area"
    assert selected.source_plan_page_index == 6
    with pytest.raises(SystemExit):
        parser.parse_args(["--family-group", "unverified"])


def test_original_role_command_reuses_installed_source_closed_producer_not_a_new_launcher():
    project = launcher.PROJECTS[1]
    command = launcher.source_role_handoff_command(
        Path("private-venv/python"), project,
        Path("private-sources") / project, Path("new-private-output"),
        family_group="all", timeout_min=60,
        max_private_gb=10.0, min_free_commit_gb=3.0,
    )
    assert command[:3] == [
        str(Path("private-venv/python")), "-m",
        "tools.gpt3_owner_all_source_role_handoff",
    ]
    assert command[command.index("--project-id") + 1] == project
    assert "--source-dir" in command and "--output-dir" in command
    assert "--timeout-min" in command and "--max-private-gb" in command
    assert "--min-free-commit-gb" in command
    assert "--pdf" not in command and "reference_takeoff" not in repr(command)


@pytest.mark.parametrize("family,timeout,private,free", [
    ("all", 0, 10.0, 3.0), ("UNKNOWN", 30, 10.0, 3.0),
    ("all", 30, -1.0, 3.0), ("all", 30, 10.0, -1.0),
    ("all", True, 10.0, 3.0),
])
def test_original_role_command_rejects_unsafe_policy(family, timeout, private, free):
    with pytest.raises(ValueError):
        launcher.source_role_handoff_command(
            Path("venv/python"), launcher.PROJECTS[0],
            Path("sources"), Path("out"), family_group=family,
            timeout_min=timeout, max_private_gb=private,
            min_free_commit_gb=free,
        )


def test_original_role_receipt_does_not_promote_missing_partial_or_duplicate_rows(tmp_path):
    project = launcher.PROJECTS[0]
    file = tmp_path / "SOURCE_ROLE_STATUS.json"
    assert launcher.source_role_handoff_status(
        file, project=project, expected_roles=2,
        process_status="COMPLETED", exit_code=0,
    )["first_failure"] == "source_role_receipt_missing"
    valid = {
        "project_id": project, "expected_source_document_roles": 2,
        "source_sha_verified": True,
        "status": "ALL_ROLES_SEALED_CUSTOMER_AND_V2_PENDING",
        "source_role_coverage_verified": True,
        "customer_bijection_verified": False,
        "benchmark_score_granted": False,
        "official_four_project_accuracy": None,
        "roles": [
            {"sealed": True, "process_status": "COMPLETED", "first_failure": None},
            {"sealed": True, "process_status": "COMPLETED", "first_failure": None},
        ],
    }
    file.write_text(json.dumps(valid), encoding="utf-8")
    result = launcher.source_role_handoff_status(
        file, project=project, expected_roles=2,
        process_status="COMPLETED", exit_code=0,
    )
    assert result == {
        "source_role_coverage_verified": True, "sealed_roles": 2,
        "expected_roles": 2, "first_failure": None,
    }
    for mutate in (
        {"source_role_coverage_verified": False},
        {"customer_bijection_verified": True},
        {"benchmark_score_granted": True},
        {"project_id": "other"},
        {"source_sha_verified": False},
        {"expected_source_document_roles": 1},
    ):
        file.write_text(json.dumps({**valid, **mutate}), encoding="utf-8")
        assert launcher.source_role_handoff_status(
            file, project=project, expected_roles=2,
            process_status="COMPLETED", exit_code=0,
        )["source_role_coverage_verified"] is False
    # A contradictory child result is not source authority merely because
    # a top-level report claims two successful role seals.
    inconsistent = {**valid, "roles": [
        {**valid["roles"][0], "process_status": "PROCESS_FAILED"},
        valid["roles"][1],
    ]}
    file.write_text(json.dumps(inconsistent), encoding="utf-8")
    assert launcher.source_role_handoff_status(
        file, project=project, expected_roles=2,
        process_status="COMPLETED", exit_code=0,
    )["source_role_coverage_verified"] is False

    file.write_text('{"project_id":"a","project_id":"b"}', encoding="utf-8")
    assert launcher.source_role_handoff_status(
        file, project=project, expected_roles=2,
        process_status="COMPLETED", exit_code=0,
    )["first_failure"] == "source_role_receipt_invalid"


def test_pinned_original_role_runtime_rejects_changed_code_checkout(monkeypatch):
    head = "a" * 40
    def good(args, _repo):
        if args[:2] == ["rev-parse", "HEAD"]:
            return _GitResult(0, head + "\n")
        return _GitResult(0, "")
    monkeypatch.setattr(launcher, "git", good)
    assert launcher.pinned_source_tree_unchanged(Path("repo"), head) is True
    status_calls = []
    def untracked_poison(args, repo):
        if args[0] == "status":
            status_calls.append(list(args))
            return _GitResult(0, "?? tools/untracked_producer_override.py\n")
        return _GitResult(0, head + "\n")
    monkeypatch.setattr(launcher, "git", untracked_poison)
    assert launcher.pinned_source_tree_unchanged(Path("repo"), head) is False
    assert status_calls == [["status", "--porcelain", "--untracked-files=all"]]
    monkeypatch.setattr(launcher, "git", lambda args, repo: (
        _GitResult(0, "tracked-original-code-changed\n")
        if args[0] == "status" else _GitResult(0, head + "\n")
    ))
    assert launcher.pinned_source_tree_unchanged(Path("repo"), head) is False
    assert launcher.pinned_source_tree_unchanged(Path("repo"), "main") is False


def test_all_source_roles_rejects_source_plan_page_selector(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "four_job_windows_launcher.py", "--all-source-roles",
        "--only", launcher.PROJECTS[0], "--source-plan-page-index", "2",
    ])
    with pytest.raises(SystemExit) as err:
        launcher.main()
    assert err.value.code == 2


@pytest.mark.parametrize("failed_project", [None, "au_qld_maryborough_service_station"])
def test_owner_four_job_opt_in_uses_existing_multi_role_source_producer(
    tmp_path, monkeypatch, failed_project,
):
    from types import SimpleNamespace
    kit = _kit(tmp_path / "private-kit")
    home = tmp_path / "home"
    runroot = home / "Documents" / "PlanReader_Private_V2_Run"
    repo = runroot / "repo_readonly_snapshot"
    inventory = json.loads((kit / "LOCAL_SOURCE_INVENTORY.json").read_text())
    for project in launcher.PROJECTS:
        doc_count = sum(row["project_id"] == project for row in inventory["docs"])
        manifest = (
            repo / "benchmarks" / "frozen_holdout" / "full_plan_v2"
            / "projects" / project / "source_manifest.json"
        )
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            "source_documents": [{"name": "original"}] * doc_count,
        }), encoding="utf-8")
    monkeypatch.chdir(kit)
    monkeypatch.setattr(launcher.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "git")
    monkeypatch.setattr(launcher, "refresh_snapshot", lambda *a: "a" * 40)
    monkeypatch.setattr(launcher, "pinned_source_tree_unchanged", lambda *a: True)
    def fake_venv(folder, *, with_pip):
        target = Path(folder) / (
            "Scripts/python.exe" if launcher.os.name == "nt" else "bin/python"
        )
        target.parent.mkdir(parents=True)
        target.write_text("synthetic interpreter")
    monkeypatch.setattr(launcher.venv, "create", fake_venv)
    def environment(args, **kwargs):
        return SimpleNamespace(stdout=(
            "3.13.0\n" if "-c" in args else "PyMuPDF==1.28.0\npytest==8.4.0\n"
        ))
    monkeypatch.setattr(launcher.subprocess, "run", environment)
    invoked = []
    def fake_logged(command, _cwd, logfile, **kwargs):
        usage = {
            "peak_working_set_kb": 0, "peak_private_kb": 0,
            "min_system_free_commit_kb": None,
        }
        if "tools.gpt3_owner_all_source_role_handoff" not in command:
            return 0, "COMPLETED", usage
        invoked.append(command)
        project = command[command.index("--project-id") + 1]
        output = Path(command[command.index("--output-dir") + 1])
        count = len(json.loads((
            repo / "benchmarks" / "frozen_holdout" / "full_plan_v2"
            / "projects" / project / "source_manifest.json"
        ).read_text())["source_documents"])
        okay = project != failed_project
        output.mkdir(parents=True)
        (output / "SOURCE_ROLE_STATUS.json").write_text(json.dumps({
            "project_id": project,
            "expected_source_document_roles": count,
            "source_sha_verified": True,
            "status": (
                "ALL_ROLES_SEALED_CUSTOMER_AND_V2_PENDING"
                if okay else "SOURCE_ROLES_INCOMPLETE"
            ),
            "source_role_coverage_verified": okay,
            "customer_bijection_verified": False,
            "benchmark_score_granted": False,
            "official_four_project_accuracy": None,
            "roles": [
                {
                    "sealed": okay or i < count - 1,
                    "process_status": "COMPLETED",
                    "first_failure": (
                        None if okay or i < count - 1
                        else "role_producer_no_sealable_result"
                    ),
                }
                for i in range(count)
            ],
        }), encoding="utf-8")
        return (0, "COMPLETED", usage) if okay else (2, "PROCESS_FAILED", usage)
    monkeypatch.setattr(launcher, "run_logged", fake_logged)
    monkeypatch.setattr(sys, "argv", [
        "four_job_windows_launcher.py", "--ref", "a" * 40,
        "--all-source-roles", "--timeout-min", "1",
    ])
    result_code = launcher.main()
    assert result_code == (0 if failed_project is None else 8)
    assert len(invoked) == len(launcher.PROJECTS)
    assert all("--pdf" not in cmd for cmd in invoked)
    assert [cmd[cmd.index("--project-id") + 1] for cmd in invoked] == list(launcher.PROJECTS)
    reports = list(runroot.glob("*/BENCHMARK_DIAGNOSTIC_STATUS.json"))
    assert len(reports) == 1
    status = json.loads(reports[0].read_text(encoding="utf-8"))
    assert status["repo_head"] == "a" * 40
    assert len(status["project_handoffs"]) == 4
    assert status["all_source_roles_requested"] is True
    assert status["private_runtime_environment_unchanged"] is True
    assert len(status["private_runtime_environment_sha256"]) == 64
    # Role seals are real source-role execution, NOT completed cross-family
    # quantity/customer source closure or frozen suite publication.
    assert status["source_scope_complete"] is False
    assert status["source_role_coverage_verified"] is (failed_project is None)
    assert status["full_suite_publication_status"] == "UNPUBLISHED"
    assert status["official_four_project_coverage_accuracy"] is None
    assert all(x["customer_bijection_verified"] is False for x in status["project_handoffs"])
    assert list(runroot.glob("*/PRIVATE_SOURCE_RUNTIME_PACKAGES.txt"))
