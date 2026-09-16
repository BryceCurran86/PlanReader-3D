"""Validator replay harness for frozen expected-RED test contracts.

This tool verifies git/content identity and test execution isolation.
It does NOT prove semantic completeness itself.

Design principles:
- Never silently mutate the caller's working tree
- Use isolated temporary git worktrees for replay
- Fail fast on preflight; collect on production run
- Separate expected-RED from behavioral regression
- Report in machine-readable JSON + human-readable Markdown
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence


__version__ = "0.1.0"

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================


class LaneType(str, Enum):
    """Validator lane identifier."""

    DIMENSIONS = "dimensions"
    COMPLETENESS = "completeness"
    HOST = "host"
    IDENTITY = "identity"


class FailureClassification(str, Enum):
    """Categorization of test/preflight failures."""

    CONTRACT_DRIFT = "contract_drift"
    PREFLIGHT_FAILURE = "preflight_failure"
    COLLECTION_FAILURE = "collection_failure"
    IMPORT_FAILURE = "import_failure"
    FIXTURE_FAILURE = "fixture_failure"
    EXPECTED_BEHAVIORAL_RED = "expected_behavioral_red"
    BEHAVIORAL_REGRESSION = "behavioral_regression"
    VALIDATOR_GREEN = "validator_green"


# ============================================================================
# LOGGING SETUP
# ============================================================================


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for harness."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger(__name__)


logger: Optional[logging.Logger] = None


def log(msg: str, level: int = logging.INFO) -> None:
    """Thread-safe logging."""
    if logger:
        logger.log(level, msg)


# ============================================================================
# AST SCANNERS — PURE UNIT TESTABLE
# ============================================================================


class EnumMemberScanner(ast.NodeVisitor):
    """Scan Python AST for EvidenceResolutionStatus references."""

    CANONICAL_MEMBERS = {
        "RAW",
        "CANDIDATE",
        "CORROBORATED",
        "CONFLICT",
        "ABSTAINED",
    }

    def __init__(self) -> None:
        self.invalid_references: list[tuple[int, str]] = []
        self.valid_references: list[tuple[int, str]] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check EvidenceResolutionStatus.MEMBER references."""
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "EvidenceResolutionStatus"
        ):
            member = node.attr
            if member not in self.CANONICAL_MEMBERS:
                self.invalid_references.append(
                    (node.lineno, f"EvidenceResolutionStatus.{member}")
                )
            else:
                self.valid_references.append(
                    (node.lineno, f"EvidenceResolutionStatus.{member}")
                )
        self.generic_visit(node)


class UnconditionalAssertionScanner(ast.NodeVisitor):
    """Detect unconditional raise AssertionError('not implemented') placeholders."""

    def __init__(self) -> None:
        self.unconditional_placeholders: list[tuple[int, str]] = []

    def visit_Raise(self, node: ast.Raise) -> None:
        """Flag raise AssertionError with literal 'not implemented' message."""
        if node.exc and isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "AssertionError":
                if (
                    node.exc.args
                    and isinstance(node.exc.args[0], ast.Constant)
                    and "not implemented" in str(node.exc.args[0].value).lower()
                ):
                    # Check if this is inside a pytest skip/xfail context
                    # For now, flag it conservatively
                    self.unconditional_placeholders.append(
                        (node.lineno, "unconditional raise AssertionError('not implemented')")
                    )
        self.generic_visit(node)


class ImportScanner(ast.NodeVisitor):
    """Scan for dynamic/conditional imports that should not block compilation."""

    def __init__(self) -> None:
        self.imports: list[tuple[int, str]] = []
        self.dynamic_imports: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Record regular imports."""
        for alias in node.names:
            self.imports.append((node.lineno, alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record from-imports."""
        module = node.module or "<relative>"
        for alias in node.names:
            self.imports.append((node.lineno, f"{module}.{alias.name}"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect __import__() or importlib patterns."""
        if isinstance(node.func, ast.Name):
            if node.func.id == "__import__":
                self.dynamic_imports.append((node.lineno, "__import__()"))
            elif node.func.id in ("importlib.import_module",):
                self.dynamic_imports.append((node.lineno, "importlib.import_module()"))
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == "import_module":
                self.dynamic_imports.append(
                    (node.lineno, "dynamic importlib.import_module()")
                )
        self.generic_visit(node)


def scan_python_file(path: Path) -> dict[str, Any]:
    """Parse Python file and extract scanner results."""
    result = {
        "path": str(path),
        "valid_enum_refs": [],
        "invalid_enum_refs": [],
        "unconditional_placeholders": [],
        "dynamic_imports": [],
        "static_imports": [],
        "error": None,
    }

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        enum_scanner = EnumMemberScanner()
        enum_scanner.visit(tree)
        result["valid_enum_refs"] = enum_scanner.valid_references
        result["invalid_enum_refs"] = enum_scanner.invalid_references

        assert_scanner = UnconditionalAssertionScanner()
        assert_scanner.visit(tree)
        result["unconditional_placeholders"] = assert_scanner.unconditional_placeholders

        import_scanner = ImportScanner()
        import_scanner.visit(tree)
        result["static_imports"] = import_scanner.imports
        result["dynamic_imports"] = import_scanner.dynamic_imports

    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


# ============================================================================
# CONTENT IDENTITY — PURE UNIT TESTABLE
# ============================================================================


def sha256_file(path: Path) -> str:
    """Compute SHA256 of file contents."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_string(content: str) -> str:
    """Compute SHA256 of string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ============================================================================
# GIT OPERATIONS
# ============================================================================


def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run git command with error handling."""
    cmd = ["git"] + list(args)
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=check,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        log(f"Git command timed out: {' '.join(cmd)}", logging.ERROR)
        raise
    except subprocess.CalledProcessError as e:
        log(
            f"Git command failed: {' '.join(cmd)}\n{e.stderr}",
            logging.ERROR,
        )
        raise


def get_commit_sha(ref: str, cwd: Path | None = None) -> str:
    """Get full commit SHA for a ref."""
    result = run_git("rev-parse", ref, cwd=cwd)
    return result.stdout.strip()


def get_changed_files(
    base_sha: str,
    head_sha: str,
    cwd: Path | None = None,
) -> list[str]:
    """Get list of files changed between two commits."""
    result = run_git(
        "diff",
        "--name-only",
        f"{base_sha}..{head_sha}",
        cwd=cwd,
    )
    return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]


def get_file_at_ref(
    file_path: str,
    ref: str,
    cwd: Path | None = None,
) -> str:
    """Get file contents at a specific git ref."""
    result = run_git(
        "show",
        f"{ref}:{file_path}",
        cwd=cwd,
    )
    return result.stdout


# ============================================================================
# WORKTREE MANAGEMENT
# ============================================================================


class IsolatedWorktree:
    """Context manager for isolated git worktree."""

    def __init__(
        self,
        repo_path: Path,
        target_sha: str,
        worktree_name: str = "harness-replay",
    ):
        self.repo_path = repo_path
        self.target_sha = target_sha
        self.worktree_name = worktree_name
        self.worktree_path: Optional[Path] = None

    def __enter__(self) -> Path:
        """Create isolated worktree."""
        log(f"Creating worktree for {self.target_sha[:8]}")
        temp_dir = Path(tempfile.gettempdir())
        self.worktree_path = temp_dir / f"pr-harness-{self.worktree_name}-{os.urandom(4).hex()}"

        run_git(
            "worktree",
            "add",
            str(self.worktree_path),
            self.target_sha,
            cwd=self.repo_path,
        )
        log(f"Worktree created at {self.worktree_path}")
        return self.worktree_path

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Clean up worktree."""
        if self.worktree_path and self.worktree_path.exists():
            log(f"Cleaning up worktree {self.worktree_path}")
            try:
                run_git(
                    "worktree",
                    "remove",
                    str(self.worktree_path),
                    cwd=self.repo_path,
                )
            except subprocess.CalledProcessError as e:
                log(
                    f"Warning: could not remove worktree cleanly: {e}",
                    logging.WARNING,
                )
                # Force remove if needed
                import shutil

                shutil.rmtree(self.worktree_path, ignore_errors=True)


# ============================================================================
# PREFLIGHT CHECKS
# ============================================================================


@dataclass
class PreflightResult:
    """Result of preflight checks."""

    passed: bool
    ruff_check: dict[str, Any] = field(default_factory=dict)
    compileall_check: dict[str, Any] = field(default_factory=dict)
    pytest_collection: dict[str, Any] = field(default_factory=dict)
    enum_validation: dict[str, Any] = field(default_factory=dict)
    unconditional_assertions: dict[str, Any] = field(default_factory=dict)
    blob_sha_check: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def run_ruff_check(
    worktree_path: Path,
    test_file_path: str,
) -> dict[str, Any]:
    """Run Ruff F821, F823, E9 on test file."""
    result = {
        "passed": False,
        "output": "",
        "error": None,
    }

    try:
        output = subprocess.run(
            [
                "ruff",
                "check",
                "--select",
                "F821,F823,E9",
                str(worktree_path / test_file_path),
            ],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        result["output"] = output.stdout + output.stderr
        result["passed"] = output.returncode == 0
    except FileNotFoundError:
        result["error"] = "Ruff not installed"
    except subprocess.TimeoutExpired:
        result["error"] = "Ruff check timed out"
    except Exception as e:
        result["error"] = str(e)

    return result


def run_compileall_check(worktree_path: Path, test_file_path: str) -> dict[str, Any]:
    """Compile Python test file."""
    result = {
        "passed": False,
        "output": "",
        "error": None,
    }

    try:
        import py_compile

        py_compile.compile(
            str(worktree_path / test_file_path),
            doraise=True,
        )
        result["passed"] = True
    except py_compile.PyCompileError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)

    return result


def scan_enum_validity(worktree_path: Path, test_file_path: str) -> dict[str, Any]:
    """AST scan for invalid enum references."""
    result = {
        "passed": False,
        "invalid_members": [],
        "error": None,
    }

    try:
        file_path = worktree_path / test_file_path
        if not file_path.exists():
            result["error"] = f"File not found: {test_file_path}"
            return result

        scan = scan_python_file(file_path)
        result["invalid_members"] = scan["invalid_enum_refs"]
        result["passed"] = len(scan["invalid_enum_refs"]) == 0

    except Exception as e:
        result["error"] = str(e)

    return result


def scan_unconditional_placeholders(
    worktree_path: Path,
    test_file_path: str,
) -> dict[str, Any]:
    """AST scan for unconditional raise AssertionError placeholders."""
    result = {
        "found": [],
        "error": None,
    }

    try:
        file_path = worktree_path / test_file_path
        if not file_path.exists():
            result["error"] = f"File not found: {test_file_path}"
            return result

        scan = scan_python_file(file_path)
        result["found"] = scan["unconditional_placeholders"]

    except Exception as e:
        result["error"] = str(e)

    return result


def verify_blob_sha(
    worktree_path: Path,
    test_file_path: str,
    expected_sha: str,
) -> dict[str, Any]:
    """Verify file blob SHA matches expected."""
    result = {
        "passed": False,
        "expected": expected_sha,
        "actual": None,
        "error": None,
    }

    try:
        file_path = worktree_path / test_file_path
        if not file_path.exists():
            result["error"] = f"File not found: {test_file_path}"
            return result

        actual = sha256_file(file_path)
        result["actual"] = actual
        result["passed"] = actual == expected_sha

    except Exception as e:
        result["error"] = str(e)

    return result


def run_pytest_collection(
    worktree_path: Path,
    test_file_path: str,
) -> dict[str, Any]:
    """Run pytest collection on test file."""
    result = {
        "passed": False,
        "count": 0,
        "output": "",
        "error": None,
    }

    try:
        output = subprocess.run(
            ["pytest", "--collect-only", "-q", str(worktree_path / test_file_path)],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        result["output"] = output.stdout + output.stderr
        result["passed"] = output.returncode == 0

        # Simple heuristic: count "test_" lines
        for line in output.stdout.split("\n"):
            if "test_" in line and "::" in line:
                result["count"] += 1

    except FileNotFoundError:
        result["error"] = "pytest not installed"
    except subprocess.TimeoutExpired:
        result["error"] = "pytest collection timed out"
    except Exception as e:
        result["error"] = str(e)

    return result


# ============================================================================
# PYTEST EXECUTION
# ============================================================================


@dataclass
class PytestResult:
    """Result of pytest execution."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    xfailed: int = 0
    xpassed: int = 0
    collection_errors: int = 0
    returncode: int = 1
    output: str = ""
    first_failure: Optional[str] = None
    error: Optional[str] = None


def run_pytest_normal(
    worktree_path: Path,
    test_file_path: str,
) -> PytestResult:
    """Run pytest normally (GREEN tests only)."""
    result = PytestResult()

    try:
        output = subprocess.run(
            ["pytest", "-v", "--tb=short", str(worktree_path / test_file_path)],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        result.output = output.stdout + output.stderr
        result.returncode = output.returncode

        # Parse output
        for line in result.output.split("\n"):
            if " PASSED" in line:
                result.passed += 1
            elif " FAILED" in line:
                result.failed += 1
                if result.first_failure is None:
                    result.first_failure = line.strip()
            elif " SKIPPED" in line:
                result.skipped += 1
            elif " XFAIL" in line:
                result.xfailed += 1
            elif " XPASS" in line:
                result.xpassed += 1

    except subprocess.TimeoutExpired:
        result.error = "pytest normal run timed out"
    except Exception as e:
        result.error = str(e)

    return result


def run_pytest_runxfail(
    worktree_path: Path,
    test_file_path: str,
) -> PytestResult:
    """Run pytest with --runxfail --maxfail=1 (expected-RED replay)."""
    result = PytestResult()

    try:
        output = subprocess.run(
            [
                "pytest",
                "--runxfail",
                "--maxfail=1",
                "-v",
                "--tb=short",
                str(worktree_path / test_file_path),
            ],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        result.output = output.stdout + output.stderr
        result.returncode = output.returncode

        # Parse output
        for line in result.output.split("\n"):
            if " PASSED" in line:
                result.passed += 1
            elif " FAILED" in line:
                result.failed += 1
                if result.first_failure is None:
                    result.first_failure = line.strip()
            elif " SKIPPED" in line:
                result.skipped += 1
            elif " XFAIL" in line:
                result.xfailed += 1
            elif " XPASS" in line:
                result.xpassed += 1

    except subprocess.TimeoutExpired:
        result.error = "pytest --runxfail run timed out"
    except Exception as e:
        result.error = str(e)

    return result


# ============================================================================
# REPORT STRUCTURES
# ============================================================================


@dataclass
class ValidatorReplayReport:
    """Complete validation replay report."""

    lane: str
    base_sha: str
    production_sha: str
    validator_ref: str
    validator_path: str
    expected_validator_blob_sha: Optional[str]
    actual_validator_blob_sha: Optional[str]
    sha_match: bool
    timestamp: str
    changed_files: list[str]
    production_file_count: int
    preflight: PreflightResult
    pytest_normal: PytestResult
    pytest_runxfail: PytestResult
    benchmark_touched: bool
    gold_touched: bool
    holdout_touched: bool
    verdict: str
    version: str = __version__

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "lane": self.lane,
            "base_sha": self.base_sha,
            "production_sha": self.production_sha,
            "validator_ref": self.validator_ref,
            "validator_path": self.validator_path,
            "expected_validator_blob_sha": self.expected_validator_blob_sha,
            "actual_validator_blob_sha": self.actual_validator_blob_sha,
            "sha_match": self.sha_match,
            "timestamp": self.timestamp,
            "changed_files": self.changed_files,
            "production_file_count": self.production_file_count,
            "preflight": {
                "passed": self.preflight.passed,
                "ruff_check": self.preflight.ruff_check,
                "compileall_check": self.preflight.compileall_check,
                "pytest_collection": self.preflight.pytest_collection,
                "enum_validation": self.preflight.enum_validation,
                "unconditional_assertions": self.preflight.unconditional_assertions,
                "blob_sha_check": self.preflight.blob_sha_check,
                "errors": self.preflight.errors,
            },
            "pytest_normal": asdict(self.pytest_normal),
            "pytest_runxfail": asdict(self.pytest_runxfail),
            "benchmark_touched": self.benchmark_touched,
            "gold_touched": self.gold_touched,
            "holdout_touched": self.holdout_touched,
            "verdict": self.verdict,
            "version": self.version,
        }

    def to_markdown(self) -> str:
        """Generate human-readable Markdown report."""
        lines = [
            "# Validator Replay Report",
            "",
            f"**Lane:** `{self.lane}`",
            f"**Timestamp:** {self.timestamp}",
            f"**Verdict:** `{self.verdict}`",
            "",
            "## Identity",
            "",
            f"- Base SHA: `{self.base_sha}`",
            f"- Production SHA: `{self.production_sha}`",
            f"- Validator Ref: `{self.validator_ref}`",
            f"- Validator Path: `{self.validator_path}`",
            "",
        ]

        if self.expected_validator_blob_sha:
            lines.extend([
                "## Blob SHA Verification",
                "",
                f"- Expected: `{self.expected_validator_blob_sha}`",
                f"- Actual: `{self.actual_validator_blob_sha}`",
                f"- Match: **{'✓ PASS' if self.sha_match else '✗ FAIL'}**",
                "",
            ])

        lines.extend([
            "## Changed Files",
            "",
            f"Total: {len(self.changed_files)} files",
            f"Production files: {self.production_file_count}",
            "",
        ])

        if self.changed_files:
            lines.append("```")
            for f in self.changed_files:
                lines.append(f)
            lines.append("```")
            lines.append("")

        lines.extend([
            "## Preflight Checks",
            "",
            f"**Status:** {'✓ PASS' if self.preflight.passed else '✗ FAIL'}",
            "",
        ])

        if self.preflight.errors:
            lines.append("**Errors:**")
            for err in self.preflight.errors:
                lines.append(f"- {err}")
            lines.append("")

        lines.extend([
            f"- Ruff (F821,F823,E9): {'✓' if self.preflight.ruff_check.get('passed') else '✗'}",
            f"- Compileall: {'✓' if self.preflight.compileall_check.get('passed') else '✗'}",
            f"- Pytest Collection: {'✓' if self.preflight.pytest_collection.get('passed') else '✗'}",
            f"- Enum Validation: {'✓' if self.preflight.enum_validation.get('passed') else '✗'}",
            "",
        ])

        lines.extend([
            "## Test Execution Results",
            "",
            "### Normal Run (GREEN tests only)",
            "",
            f"- Passed: {self.pytest_normal.passed}",
            f"- Failed: {self.pytest_normal.failed}",
            f"- Skipped: {self.pytest_normal.skipped}",
            f"- XFailed: {self.pytest_normal.xfailed}",
            f"- XPassed: {self.pytest_normal.xpassed}",
            "",
            "### Expected-RED Run (--runxfail --maxfail=1)",
            "",
            f"- Passed: {self.pytest_runxfail.passed}",
            f"- Failed: {self.pytest_runxfail.failed}",
            f"- Skipped: {self.pytest_runxfail.skipped}",
            f"- XFailed: {self.pytest_runxfail.xfailed}",
            f"- XPassed: {self.pytest_runxfail.xpassed}",
            "",
        ])

        lines.extend([
            "## Authority Constraints",
            "",
            f"- Benchmark Touched: {'❌' if self.benchmark_touched else '✓'}",
            f"- Gold Touched: {'❌' if self.gold_touched else '✓'}",
            f"- Holdout Touched: {'❌' if self.holdout_touched else '✓'}",
            "",
        ])

        return "\n".join(lines)


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================


@dataclass
class ReplayConfig:
    """Configuration for validator replay."""

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


def run_replay(config: ReplayConfig) -> ValidatorReplayReport:
    """Execute validator replay orchestration."""
    global logger
    logger = setup_logging(config.verbose)

    log(f"Starting validator replay for lane: {config.lane.value}")
    log(f"Production SHA: {config.production_sha}")
    log(f"Validator ref: {config.validator_ref}")

    # Step 1: Create isolated worktree at production SHA
    with IsolatedWorktree(
        config.repo_path,
        config.production_sha,
        f"validator-{config.lane.value}",
    ) as worktree_path:
        log(f"Worktree ready at {worktree_path}")

        # Step 2: Run preflight
        log("Running preflight checks...")
        preflight = PreflightResult()

        preflight.ruff_check = run_ruff_check(worktree_path, config.validator_path)
        if not preflight.ruff_check.get("passed"):
            preflight.errors.append(
                f"Ruff check failed: {preflight.ruff_check.get('error', preflight.ruff_check.get('output')[:100])}"
            )

        preflight.compileall_check = run_compileall_check(
            worktree_path,
            config.validator_path,
        )
        if not preflight.compileall_check.get("passed"):
            preflight.errors.append(
                f"Compileall failed: {preflight.compileall_check.get('error')}"
            )

        preflight.pytest_collection = run_pytest_collection(
            worktree_path,
            config.validator_path,
        )
        if not preflight.pytest_collection.get("passed"):
            preflight.errors.append(
                f"Pytest collection failed: {preflight.pytest_collection.get('error')}"
            )

        preflight.enum_validation = scan_enum_validity(
            worktree_path,
            config.validator_path,
        )
        if not preflight.enum_validation.get("passed"):
            preflight.errors.append(
                f"Enum validation failed: invalid members: {preflight.enum_validation.get('invalid_members')}"
            )

        preflight.unconditional_assertions = scan_unconditional_placeholders(
            worktree_path,
            config.validator_path,
        )
        if preflight.unconditional_assertions.get("found"):
            preflight.errors.append(
                f"Found unconditional placeholders: {len(preflight.unconditional_assertions.get('found', []))}"
            )

        if config.expected_validator_blob_sha:
            preflight.blob_sha_check = verify_blob_sha(
                worktree_path,
                config.validator_path,
                config.expected_validator_blob_sha,
            )
            if not preflight.blob_sha_check.get("passed"):
                preflight.errors.append(
                    f"Blob SHA mismatch: expected {config.expected_validator_blob_sha}, got {preflight.blob_sha_check.get('actual')}"
                )

        preflight.passed = len(preflight.errors) == 0

        log(f"Preflight result: {'PASS' if preflight.passed else 'FAIL'}")

        if config.preflight_only:
            # Return early with preflight-only report
            return ValidatorReplayReport(
                lane=config.lane.value,
                base_sha=config.base_sha,
                production_sha=config.production_sha,
                validator_ref=config.validator_ref,
                validator_path=config.validator_path,
                expected_validator_blob_sha=config.expected_validator_blob_sha,
                actual_validator_blob_sha=preflight.blob_sha_check.get("actual"),
                sha_match=preflight.blob_sha_check.get("passed", False),
                timestamp=datetime.utcnow().isoformat() + "Z",
                changed_files=[],
                production_file_count=0,
                preflight=preflight,
                pytest_normal=PytestResult(),
                pytest_runxfail=PytestResult(),
                benchmark_touched=False,
                gold_touched=False,
                holdout_touched=False,
                verdict="PREFLIGHT_ONLY",
            )

        # Step 3: Run pytest normal
        log("Running pytest (normal)...")
        pytest_normal = run_pytest_normal(worktree_path, config.validator_path)
        log(
            f"Pytest normal: {pytest_normal.passed} passed, {pytest_normal.failed} failed"
        )

        # Step 4: Run pytest --runxfail
        log("Running pytest (--runxfail)...")
        pytest_runxfail = run_pytest_runxfail(worktree_path, config.validator_path)
        log(
            f"Pytest --runxfail: {pytest_runxfail.passed} passed, {pytest_runxfail.failed} failed"
        )

    # Step 5: Determine changed files
    changed_files = get_changed_files(config.base_sha, config.production_sha, config.repo_path)
    production_file_count = sum(
        1 for f in changed_files
        if f.endswith(".py") and not f.startswith("tests/")
    )
    benchmark_touched = any("benchmark" in f.lower() for f in changed_files)
    gold_touched = any("gold" in f.lower() or "expected" in f.lower() for f in changed_files)
    holdout_touched = any("holdout" in f.lower() for f in changed_files)

    # Step 6: Determine verdict
    if not preflight.passed:
        verdict = "PREFLIGHT_FAILURE"
    elif pytest_runxfail.failed > 0 or pytest_runxfail.returncode != 0:
        verdict = "BEHAVIORAL_REGRESSION"
    elif pytest_normal.passed > 0 and pytest_runxfail.passed > 0:
        verdict = "VALIDATOR_GREEN"
    else:
        verdict = "UNKNOWN"

    report = ValidatorReplayReport(
        lane=config.lane.value,
        base_sha=config.base_sha,
        production_sha=config.production_sha,
        validator_ref=config.validator_ref,
        validator_path=config.validator_path,
        expected_validator_blob_sha=config.expected_validator_blob_sha,
        actual_validator_blob_sha=preflight.blob_sha_check.get("actual"),
        sha_match=preflight.blob_sha_check.get("passed", False),
        timestamp=datetime.utcnow().isoformat() + "Z",
        changed_files=changed_files,
        production_file_count=production_file_count,
        preflight=preflight,
        pytest_normal=pytest_normal,
        pytest_runxfail=pytest_runxfail,
        benchmark_touched=benchmark_touched,
        gold_touched=gold_touched,
        holdout_touched=holdout_touched,
        verdict=verdict,
    )

    # Step 7: Write reports
    if config.json_report:
        config.json_report.parent.mkdir(parents=True, exist_ok=True)
        config.json_report.write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8",
        )
        log(f"JSON report written to {config.json_report}")

    if config.markdown_report:
        config.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        config.markdown_report.write_text(
            report.to_markdown(),
            encoding="utf-8",
        )
        log(f"Markdown report written to {config.markdown_report}")

    return report


if __name__ == "__main__":
    print(f"Validator Replay Harness v{__version__}")
