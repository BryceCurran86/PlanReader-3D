"""Exact-head replay harness for frozen expected-RED validator contracts.

The harness overlays a validator branch's test-only changes onto an isolated
worktree at an exact production SHA, verifies the frozen Git blob identity,
runs fast contract preflight checks, and then executes baseline and --runxfail
pytest replays. It never mutates the caller's active worktree.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

__version__ = "0.2.0"


class LaneType(str, Enum):
    DIMENSIONS = "dimensions"
    COMPLETENESS = "completeness"
    HOST = "host"
    IDENTITY = "identity"


class FailureClassification(str, Enum):
    CONTRACT_DRIFT = "contract_drift"
    PREFLIGHT_FAILURE = "preflight_failure"
    COLLECTION_FAILURE = "collection_failure"
    IMPORT_FAILURE = "import_failure"
    FIXTURE_FAILURE = "fixture_failure"
    EXPECTED_BEHAVIORAL_RED = "expected_behavioral_red"
    BEHAVIORAL_REGRESSION = "behavioral_regression"
    VALIDATOR_GREEN = "validator_green"
    PREFLIGHT_ONLY = "preflight_only"


CANONICAL_EVIDENCE_STATUSES = {
    "RAW",
    "CANDIDATE",
    "CORROBORATED",
    "CONFLICT",
    "ABSTAINED",
}


def setup_logging(verbose: bool = False) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        force=True,
    )
    return logging.getLogger("validator-replay")


logger = logging.getLogger("validator-replay")


def _run(
    cmd: Sequence[str],
    *,
    cwd: Path,
    check: bool = False,
    timeout: int = 120,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        cwd=cwd,
        capture_output=True,
        text=text,
        check=check,
        timeout=timeout,
    )


def run_git(*args: str, cwd: Path, check: bool = True, text: bool = True):
    return _run(["git", *args], cwd=cwd, check=check, timeout=60, text=text)


def ensure_repo(repo_path: Path) -> Path:
    repo_path = repo_path.resolve()
    probe = run_git("rev-parse", "--show-toplevel", cwd=repo_path)
    return Path(probe.stdout.strip()).resolve()


def resolve_commit(repo_path: Path, ref: str, *, allow_fetch: bool = True) -> str:
    """Resolve a commit ref, fetching that exact branch from origin if needed."""
    for candidate in (ref, f"origin/{ref}"):
        result = run_git(
            "rev-parse",
            "--verify",
            f"{candidate}^{{commit}}",
            cwd=repo_path,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    if not allow_fetch:
        raise ValueError(f"git ref unavailable: {ref}")
    fetched = run_git("fetch", "--no-tags", "origin", ref, cwd=repo_path, check=False)
    if fetched.returncode != 0:
        raise ValueError(f"unable to fetch validator ref {ref}: {fetched.stderr.strip()}")
    result = run_git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=repo_path)
    return result.stdout.strip()


def git_blob_sha(repo_path: Path, ref: str, path: str) -> str:
    result = run_git("rev-parse", f"{ref}:{path}", cwd=repo_path, check=False)
    if result.returncode != 0:
        raise ValueError(f"path {path!r} does not exist at {ref}: {result.stderr.strip()}")
    return result.stdout.strip()


def worktree_blob_sha(worktree_path: Path, path: str) -> str:
    file_path = worktree_path / path
    if not file_path.exists():
        raise ValueError(f"validator path missing after overlay: {path}")
    result = run_git("hash-object", path, cwd=worktree_path)
    return result.stdout.strip()


def changed_files(repo_path: Path, base: str, head: str) -> list[str]:
    result = run_git("diff", "--name-only", f"{base}..{head}", cwd=repo_path)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _path_exists_at_ref(repo_path: Path, ref: str, path: str) -> bool:
    return (
        run_git("cat-file", "-e", f"{ref}:{path}", cwd=repo_path, check=False).returncode
        == 0
    )


def _read_blob(repo_path: Path, ref: str, path: str) -> bytes:
    result = run_git("show", f"{ref}:{path}", cwd=repo_path, text=False)
    return bytes(result.stdout)


def overlay_validator_changes(
    repo_path: Path,
    worktree_path: Path,
    *,
    base_sha: str,
    validator_commit: str,
) -> list[str]:
    """Overlay all validator-branch changes relative to its frozen base."""
    files = changed_files(repo_path, base_sha, validator_commit)
    for rel in files:
        target = worktree_path / rel
        if _path_exists_at_ref(repo_path, validator_commit, rel):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_read_blob(repo_path, validator_commit, rel))
        elif target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
    return files


class IsolatedWorktree:
    def __init__(self, repo_path: Path, target_sha: str, name: str = "replay") -> None:
        self.repo_path = ensure_repo(repo_path)
        self.target_sha = target_sha
        self.name = name
        self.path: Optional[Path] = None

    def __enter__(self) -> Path:
        root = Path(tempfile.gettempdir())
        self.path = root / f"planreader-{self.name}-{os.urandom(4).hex()}"
        run_git(
            "worktree",
            "add",
            "--detach",
            str(self.path),
            self.target_sha,
            cwd=self.repo_path,
        )
        return self.path

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.path is not None:
            run_git(
                "worktree",
                "remove",
                "--force",
                str(self.path),
                cwd=self.repo_path,
                check=False,
            )
            run_git("worktree", "prune", cwd=self.repo_path, check=False)
            if self.path.exists():
                shutil.rmtree(self.path, ignore_errors=True)


class ContractScanner(ast.NodeVisitor):
    def __init__(self) -> None:
        self.invalid_enum_refs: list[tuple[int, str]] = []
        self.placeholder_raises: list[tuple[int, str]] = []
        self._conditional_depth = 0
        self._function_depth = 0

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "EvidenceResolutionStatus":
            if node.attr not in CANONICAL_EVIDENCE_STATUSES:
                self.invalid_enum_refs.append((node.lineno, node.attr))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def _visit_conditional(self, node: ast.AST) -> None:
        self._conditional_depth += 1
        self.generic_visit(node)
        self._conditional_depth -= 1

    visit_If = _visit_conditional
    visit_For = _visit_conditional
    visit_AsyncFor = _visit_conditional
    visit_While = _visit_conditional
    visit_Try = _visit_conditional
    visit_With = _visit_conditional
    visit_AsyncWith = _visit_conditional
    visit_Match = _visit_conditional

    def visit_Raise(self, node: ast.Raise) -> None:
        if (
            self._function_depth
            and self._conditional_depth == 0
            and isinstance(node.exc, ast.Call)
        ):
            func = node.exc.func
            if isinstance(func, ast.Name) and func.id == "AssertionError":
                message = ""
                if node.exc.args and isinstance(node.exc.args[0], ast.Constant):
                    message = str(node.exc.args[0].value)
                self.placeholder_raises.append((node.lineno, message))
        self.generic_visit(node)


def scan_contract_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "invalid_enum_refs": [],
        "placeholder_raises": [],
        "syntax_error": None,
    }
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        result["syntax_error"] = str(exc)
        return result
    scanner = ContractScanner()
    scanner.visit(tree)
    result["invalid_enum_refs"] = scanner.invalid_enum_refs
    result["placeholder_raises"] = scanner.placeholder_raises
    return result


def _python_files(paths: Iterable[str]) -> list[str]:
    return [p for p in paths if p.endswith(".py")]


def _validator_production_files(paths: Iterable[str]) -> list[str]:
    return [
        p
        for p in paths
        if p.endswith(".py")
        and not p.startswith("tests/")
        and not p.startswith("tools/")
    ]


def _run_ruff(worktree: Path, files: Sequence[str]) -> dict[str, Any]:
    if not files:
        return {"passed": True, "returncode": 0, "output": "no python files"}
    result = _run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "F821,F823,E9",
            *files,
        ],
        cwd=worktree,
        timeout=60,
    )
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "output": result.stdout + result.stderr,
    }


def _run_compile(worktree: Path, files: Sequence[str]) -> dict[str, Any]:
    if not files:
        return {"passed": True, "returncode": 0, "output": "no python files"}
    result = _run(
        [sys.executable, "-m", "py_compile", *files],
        cwd=worktree,
        timeout=60,
    )
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "output": result.stdout + result.stderr,
    }


def _run_collection(worktree: Path, validator_path: str) -> dict[str, Any]:
    result = _run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", validator_path],
        cwd=worktree,
        timeout=120,
    )
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "output": result.stdout + result.stderr,
    }


@dataclass
class PytestResult:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    xfailed: int = 0
    xpassed: int = 0
    errors: int = 0
    returncode: int = 0
    output: str = ""
    first_failure: str = ""


def _extract_count(output: str, label: str) -> int:
    matches = re.findall(rf"(\d+)\s+{re.escape(label)}\b", output)
    return int(matches[-1]) if matches else 0


def _pytest(worktree: Path, validator_path: str, *, runxfail: bool) -> PytestResult:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short"]
    if runxfail:
        cmd.extend(["--runxfail", "--maxfail=1"])
    cmd.append(validator_path)
    result = _run(cmd, cwd=worktree, timeout=240)
    output = result.stdout + result.stderr
    failure_lines = [
        line
        for line in output.splitlines()
        if line.startswith("FAILED ") or line.startswith("ERROR ")
    ]
    return PytestResult(
        passed=_extract_count(output, "passed"),
        failed=_extract_count(output, "failed"),
        skipped=_extract_count(output, "skipped"),
        xfailed=_extract_count(output, "xfailed"),
        xpassed=_extract_count(output, "xpassed"),
        errors=_extract_count(output, "error") + _extract_count(output, "errors"),
        returncode=result.returncode,
        output=output,
        first_failure=failure_lines[0] if failure_lines else "",
    )


@dataclass
class PreflightResult:
    passed: bool = False
    seconds: float = 0.0
    ruff: dict[str, Any] = field(default_factory=dict)
    compile: dict[str, Any] = field(default_factory=dict)
    collection: dict[str, Any] = field(default_factory=dict)
    contract_scan: dict[str, Any] = field(default_factory=dict)
    blob_check: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class ReplayConfig:
    lane: LaneType
    repo_path: Path
    production_sha: str
    base_sha: str
    validator_ref: str
    validator_path: str
    expected_validator_blob_sha: Optional[str] = None
    preflight_only: bool = False
    json_report: Optional[Path] = None
    markdown_report: Optional[Path] = None
    verbose: bool = False


@dataclass
class ValidatorReplayReport:
    lane: str
    base_sha: str
    production_sha: str
    validator_ref: str
    validator_commit: str
    validator_path: str
    expected_validator_blob_sha: Optional[str]
    actual_validator_blob_sha: Optional[str]
    overlay_blob_sha: Optional[str]
    sha_match: bool
    timestamp: str
    validator_changed_files: list[str]
    validator_production_files: list[str]
    production_changed_files: list[str]
    preflight: PreflightResult
    pytest_normal: PytestResult
    pytest_runxfail: PytestResult
    benchmark_touched: bool
    gold_touched: bool
    holdout_touched: bool
    verdict: str
    version: str = __version__

    @property
    def production_file_count(self) -> int:
        """Back-compat: production files changed by the validator overlay."""
        return len(self.validator_production_files)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["production_file_count"] = self.production_file_count
        return payload

    def to_markdown(self) -> str:
        return "\n".join(
            [
                f"# Validator Replay — {self.lane}",
                "",
                f"- Verdict: **{self.verdict}**",
                f"- Production SHA: `{self.production_sha}`",
                f"- Validator commit: `{self.validator_commit}`",
                f"- Validator blob: `{self.actual_validator_blob_sha}`",
                f"- Frozen blob match: **{self.sha_match}**",
                f"- Validator production files changed: **{self.production_file_count}**",
                f"- Preflight: **{'PASS' if self.preflight.passed else 'FAIL'}** ({self.preflight.seconds:.3f}s)",
                f"- Baseline: {self.pytest_normal.passed} passed / {self.pytest_normal.failed} failed / {self.pytest_normal.xfailed} xfailed",
                f"- --runxfail: {self.pytest_runxfail.passed} passed / {self.pytest_runxfail.failed} failed",
                f"- Benchmark touched: {self.benchmark_touched}",
                f"- Gold touched: {self.gold_touched}",
                f"- Holdout touched: {self.holdout_touched}",
            ]
        ) + "\n"


def _classify_runxfail(result: PytestResult) -> str:
    if result.returncode == 0:
        return FailureClassification.VALIDATOR_GREEN.value
    lower = result.output.lower()
    if "modulenotfounderror" in lower or "importerror" in lower:
        return FailureClassification.IMPORT_FAILURE.value
    if "fixture" in lower and "not found" in lower:
        return FailureClassification.FIXTURE_FAILURE.value
    return FailureClassification.EXPECTED_BEHAVIORAL_RED.value


def _touch_flags(paths: Sequence[str]) -> tuple[bool, bool, bool]:
    low = [p.lower() for p in paths]
    benchmark = any("benchmark" in p for p in low)
    gold = any("gold" in p or "expected_" in p or "/expected" in p for p in low)
    holdout = any("holdout" in p for p in low)
    return benchmark, gold, holdout


def run_replay(config: ReplayConfig) -> ValidatorReplayReport:
    global logger
    logger = setup_logging(config.verbose)
    repo = ensure_repo(config.repo_path)
    production_sha = resolve_commit(repo, config.production_sha, allow_fetch=False)
    base_sha = resolve_commit(repo, config.base_sha, allow_fetch=False)
    validator_commit = resolve_commit(repo, config.validator_ref, allow_fetch=True)
    validator_files = changed_files(repo, base_sha, validator_commit)
    validator_prod = _validator_production_files(validator_files)
    production_files = changed_files(repo, base_sha, production_sha)
    benchmark_touched, gold_touched, holdout_touched = _touch_flags(validator_files)

    expected_blob = config.expected_validator_blob_sha
    actual_blob = git_blob_sha(repo, validator_commit, config.validator_path)

    preflight = PreflightResult()
    normal = PytestResult()
    runxfail = PytestResult()
    overlay_blob: Optional[str] = None

    with IsolatedWorktree(
        repo,
        production_sha,
        f"validator-{config.lane.value}",
    ) as worktree:
        overlay_validator_changes(
            repo,
            worktree,
            base_sha=base_sha,
            validator_commit=validator_commit,
        )
        overlay_blob = worktree_blob_sha(worktree, config.validator_path)

        started = time.perf_counter()
        py_files = _python_files(validator_files)
        preflight.ruff = _run_ruff(worktree, py_files)
        preflight.compile = _run_compile(worktree, py_files)
        preflight.collection = _run_collection(worktree, config.validator_path)

        scan_errors: list[dict[str, Any]] = []
        invalid_refs: list[tuple[str, int, str]] = []
        placeholders: list[tuple[str, int, str]] = []
        for rel in py_files:
            target = worktree / rel
            if not target.exists():
                continue
            scan = scan_contract_file(target)
            if scan["syntax_error"]:
                scan_errors.append({"path": rel, "error": scan["syntax_error"]})
            invalid_refs.extend(
                (rel, line, member) for line, member in scan["invalid_enum_refs"]
            )
            placeholders.extend(
                (rel, line, msg) for line, msg in scan["placeholder_raises"]
            )
        preflight.contract_scan = {
            "passed": not scan_errors and not invalid_refs and not placeholders,
            "syntax_errors": scan_errors,
            "invalid_enum_refs": invalid_refs,
            "placeholder_raises": placeholders,
        }
        blob_match = overlay_blob == actual_blob and (
            expected_blob is None or actual_blob == expected_blob
        )
        preflight.blob_check = {
            "passed": blob_match,
            "expected": expected_blob,
            "validator_ref_blob": actual_blob,
            "overlay_blob": overlay_blob,
        }

        if validator_prod:
            preflight.errors.append(
                f"validator changes production Python files: {validator_prod}"
            )
        if benchmark_touched or gold_touched or holdout_touched:
            preflight.errors.append("validator touches benchmark/gold/holdout paths")
        for name, result in (
            ("ruff", preflight.ruff),
            ("compile", preflight.compile),
            ("collection", preflight.collection),
            ("contract_scan", preflight.contract_scan),
            ("blob_check", preflight.blob_check),
        ):
            if not result.get("passed"):
                preflight.errors.append(f"{name} failed")
        preflight.seconds = time.perf_counter() - started
        preflight.passed = not preflight.errors

        if not config.preflight_only and preflight.passed:
            normal = _pytest(worktree, config.validator_path, runxfail=False)
            if normal.returncode == 0:
                runxfail = _pytest(worktree, config.validator_path, runxfail=True)

    if not preflight.passed:
        verdict = FailureClassification.PREFLIGHT_FAILURE.value
        if not preflight.blob_check.get("passed"):
            verdict = FailureClassification.CONTRACT_DRIFT.value
    elif config.preflight_only:
        verdict = FailureClassification.PREFLIGHT_ONLY.value
    elif normal.returncode != 0:
        verdict = FailureClassification.BEHAVIORAL_REGRESSION.value
    else:
        verdict = _classify_runxfail(runxfail)

    report = ValidatorReplayReport(
        lane=config.lane.value,
        base_sha=base_sha,
        production_sha=production_sha,
        validator_ref=config.validator_ref,
        validator_commit=validator_commit,
        validator_path=config.validator_path,
        expected_validator_blob_sha=expected_blob,
        actual_validator_blob_sha=actual_blob,
        overlay_blob_sha=overlay_blob,
        sha_match=bool(preflight.blob_check.get("passed")),
        timestamp=datetime.now(timezone.utc).isoformat(),
        validator_changed_files=validator_files,
        validator_production_files=validator_prod,
        production_changed_files=production_files,
        preflight=preflight,
        pytest_normal=normal,
        pytest_runxfail=runxfail,
        benchmark_touched=benchmark_touched,
        gold_touched=gold_touched,
        holdout_touched=holdout_touched,
        verdict=verdict,
    )
    if config.json_report:
        config.json_report.parent.mkdir(parents=True, exist_ok=True)
        config.json_report.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if config.markdown_report:
        config.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        config.markdown_report.write_text(report.to_markdown(), encoding="utf-8")
    return report
