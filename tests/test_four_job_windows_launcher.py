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
