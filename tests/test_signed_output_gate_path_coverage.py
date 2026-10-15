"""Signed-output replay gates must trigger on every module the replayed producer can import.

The Lot16 and Maryborough original-source workflows seal the production output and assert the signed quantities and customer rows.
A workflow-level ``paths`` filter that names only some modules lets a change to any other module on the same call path merge without
that replay ever running.  This test derives the import closure of each replay's producer entry points statically (AST, including
function-level imports) and requires every file in it to match at least one ``pull_request.paths`` pattern of the replay workflow.

It reads workflow text and Python sources only: no benchmark truth, no gold value and no source PDF is used.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# project -> (workflow file, producer entry points the workflow executes)
SIGNED_OUTPUT_REPLAYS = {
    "lot16": (
        ".github/workflows/score-gpt3-lot16-1215-opening-local.yml",
        (
            "tools/run_gpt3_lot16_original_sealed_score_input.py",
            "tools/diag_gptmax_source_authority_stages.py",
            "tools/run_source_closed_project_handoff.py",
        ),
    ),
    "maryborough": (
        ".github/workflows/test-gpt3-maryborough-original-floor-score-input.yml",
        (
            "tools/run_gpt3_maryborough_original_floor_score_input.py",
            "tools/run_source_closed_project_handoff.py",
        ),
    ),
}


def pull_request_paths(workflow_text: str) -> list[str] | None:
    """``on.pull_request.paths`` patterns, or ``None`` when the trigger is unfiltered / absent."""
    block = re.search(r"^on:\s*\n((?:[ \t]+.*\n|\n)*)", workflow_text, re.M)
    if not block:
        return None
    pr = re.search(r"^  pull_request:[ \t]*\n((?:    .*\n|\n)*)", block.group(1), re.M)
    if not pr:
        return None
    lines = pr.group(1).splitlines()
    for index, line in enumerate(lines):
        if re.fullmatch(r"    paths:[ \t]*", line):
            break
    else:
        return None  # no ``paths`` key at all: the trigger is unfiltered
    patterns: list[str] = []
    for line in lines[index + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # blank lines and comments may sit inside the list
        item = re.fullmatch(r"      -[ \t]*(.+?)[ \t]*(?:#.*)?", line)
        if item is None:
            break  # next key of ``pull_request`` or end of the trigger block
        patterns.append(item.group(1).strip().strip("'\""))
    if not patterns:
        raise ValueError("pull_request.paths is present but no pattern could be read")
    return patterns


def has_paths_ignore(workflow_text: str) -> bool:
    return re.search(r"^    paths-ignore:", workflow_text, re.M) is not None


def path_matches(pattern: str, path: str) -> bool:
    """GitHub filter glob: ``*`` stays inside one path segment, ``**`` crosses segments."""
    regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(regex, path) is not None


def _module_file(name: str, root: Path) -> Path | None:
    candidate = root.joinpath(*name.split(".")).with_suffix(".py")
    return candidate if candidate.is_file() else None


def _imported_modules(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            # ``from tools import x`` / ``from scripts import x`` import a submodule file
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def import_closure(entries: tuple[str, ...], root: Path) -> set[str]:
    """Repo-relative POSIX paths of every repo-local ``.py`` file reachable from ``entries`` by import."""
    seen: set[str] = set()
    pending = [root / entry for entry in entries]
    while pending:
        path = pending.pop()
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        for name in _imported_modules(path):
            target = _module_file(name, root)
            if target is not None:
                pending.append(target)
    return seen


def uncovered(closure: set[str], patterns: list[str] | None) -> list[str]:
    if patterns is None:
        return []
    return sorted(path for path in closure if not any(path_matches(p, path) for p in patterns))


# ---------------------------------------------------------------------------------------------------------------------------
# the real repository gates
# ---------------------------------------------------------------------------------------------------------------------------


def test_each_signed_output_replay_triggers_on_its_whole_import_closure():
    problems = {}
    for project, (workflow, entries) in SIGNED_OUTPUT_REPLAYS.items():
        text = (ROOT / workflow).read_text(encoding="utf-8")
        assert not has_paths_ignore(text), f"{workflow} must not use paths-ignore"
        patterns = pull_request_paths(text)
        closure = import_closure(entries, ROOT)
        # sanity: the closure really is the production chain, not an empty parse
        assert len(closure) > 100, (project, len(closure))
        assert "pb_source_visibility_authority.py" in closure
        # An unfiltered trigger (no ``paths`` key) runs on every change; a filtered one must cover the whole closure.
        missing = uncovered(closure, patterns)
        if patterns is not None:
            assert patterns, (project, "empty path filter")
        if missing:
            problems[project] = missing[:12] + ([f"... {len(missing) - 12} more"] if len(missing) > 12 else [])
    assert not problems, (
        "a change to these modules would merge without the signed-output replay running: " + repr(problems)
    )


def test_signed_output_replays_still_seal_and_verify_the_customer_rows():
    for project, (workflow, _entries) in SIGNED_OUTPUT_REPLAYS.items():
        text = (ROOT / workflow).read_text(encoding="utf-8")
        assert "source_sealed_run.json" in text, project
        assert "verified_customer_rows.json" in text, project
        assert "verify_sealed_customer_output" in text, project
        assert "pull_request:" in text, project


# ---------------------------------------------------------------------------------------------------------------------------
# synthetic controls for the checker itself (positive / negative / metamorphic)
# ---------------------------------------------------------------------------------------------------------------------------


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_closure_follows_module_level_and_function_level_imports(tmp_path):
    _write(tmp_path, "tools/entry.py", "import pb_a\nfrom tools import helper\n")
    _write(tmp_path, "pb_a.py", "def f():\n    import pb_lazy\n")
    _write(tmp_path, "pb_lazy.py", "from pb_deep import x\n")
    _write(tmp_path, "pb_deep.py", "x = 1\n")
    _write(tmp_path, "tools/helper.py", "")
    _write(tmp_path, "pb_unrelated.py", "")
    closure = import_closure(("tools/entry.py",), tmp_path)
    assert closure == {"tools/entry.py", "pb_a.py", "pb_lazy.py", "pb_deep.py", "tools/helper.py"}


def test_narrow_filter_is_detected_and_wildcard_filter_passes(tmp_path):
    closure = {"pb_a.py", "pb_b.py", "tools/run.py"}
    assert uncovered(closure, ["pb_a.py", "tools/run.py"]) == ["pb_b.py"]
    assert uncovered(closure, ["pb_*.py", "tools/run.py"]) == []
    assert uncovered(closure, None) == []  # an unfiltered trigger runs on every change
    # ``*`` does not cross directories: a top-level pattern must not cover a nested file
    assert uncovered({"tools/pb_x.py"}, ["pb_*.py"]) == ["tools/pb_x.py"]
    assert uncovered({"tools/pb_x.py"}, ["tools/*.py"]) == []


def test_workflow_paths_parser_reads_only_the_pull_request_filter():
    text = (
        "name: X\n\non:\n  push:\n    paths:\n      - 'push_only.py'\n  pull_request:\n    branches: [main]\n"
        "    paths:\n      - \"pb_*.py\"\n      - 'tools/run.py'\n  workflow_dispatch:\n\njobs:\n  a:\n    runs-on: x\n"
    )
    assert pull_request_paths(text) == ["pb_*.py", "tools/run.py"]
    # comments and blank lines inside the list must not hide the patterns (a comment once made the parser report "unfiltered")
    commented = (
        "on:\n  pull_request:\n    branches: [main]\n    paths:\n      # why\n\n      - \"pb_*.py\"  # trailing\n"
        "      # between\n      - 'tools/run.py'\n  workflow_dispatch:\n"
    )
    assert pull_request_paths(commented) == ["pb_*.py", "tools/run.py"]
    # the same list parsed with CRLF checked-out text
    assert pull_request_paths(commented.replace("\n", "\r\n").replace("\r\n", "\n")) == ["pb_*.py", "tools/run.py"]
    # a present-but-unreadable filter is an error, never a silent "unfiltered"
    import pytest
    with pytest.raises(ValueError):
        pull_request_paths("on:\n  pull_request:\n    paths:\n      # nothing\n  workflow_dispatch:\n")
    assert pull_request_paths("on:\n  pull_request:\n    branches: [main]\n") is None
    assert pull_request_paths("on:\n  push:\n    branches: [main]\n") is None
    assert has_paths_ignore("on:\n  pull_request:\n    paths-ignore:\n      - 'docs/**'\n")
