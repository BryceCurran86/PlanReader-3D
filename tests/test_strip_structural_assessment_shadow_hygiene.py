"""Structural guards: the assessment is unreachable from production and reaches no consumer."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_strip_structural_assessment_shadow"
SOURCE = (REPO / f"{MODULE}.py")

# the live issuer, binders, count producer, host resolver, quantity publication and the wall adapter
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
    "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_",
)


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_only_the_diagnostic_cli_imports_the_assessment():
    importers = []
    for root in ("", "tools", "scripts"):
        for path in sorted((REPO / root).glob("*.py")):
            if path == SOURCE:
                continue
            if re.search(rf"^\s*(?:from|import)\s+{MODULE}\b", path.read_text(encoding="utf-8", errors="replace"), re.M):
                importers.append(path.relative_to(REPO).as_posix())
    assert importers == ["tools/diag_plan_callout_strip_census.py"]
    # The exception is exactly this diagnostic function, never a live issuer.
    diagnostic = ast.parse((REPO / importers[0]).read_text(encoding="utf-8"))
    for top in diagnostic.body:
        assert not (isinstance(top, ast.ImportFrom) and top.module == MODULE)
        assert not (isinstance(top, ast.Import) and any(a.name == MODULE for a in top.names))
    functions = [node.name for node in ast.walk(diagnostic) if isinstance(node, ast.FunctionDef)
                 and MODULE in set(_imports_from_tree(node))]
    assert functions == ["census"]


def _imports_from_tree(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_the_assessment_imports_no_issuer_binder_count_host_or_wall_module():
    bad = [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    assert bad == []


def test_importing_the_assessment_loads_no_consumer_module():
    code = ("import sys; sys.path[:0] = [%r]; import pb_strip_structural_assessment_shadow; "
            "bad = [m for m in sys.modules if m.startswith(%r)]; print(sorted(bad))") % (str(REPO), FORBIDDEN_IMPORT_PREFIXES)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr
    # pb_physical_opening_authority legitimately pulls the wall candidate stack; the consumers below must stay unloaded
    loaded = eval(completed.stdout.strip().splitlines()[-1])
    consumers = [m for m in loaded if m.startswith(FORBIDDEN_IMPORT_PREFIXES[:5])]
    assert consumers == []


def test_the_assessment_never_builds_an_existence_record_or_edits_the_authoritys_state():
    text = SOURCE.read_text(encoding="utf-8")
    assert "PhysicalOpeningExistenceRecord(" not in text and "PhysicalOpeningExistenceResult(" not in text
    assert "_cache[" not in text and "_cache.clear" not in text and "_cache =" not in text
    assert "capabilities" not in text and "publish_" not in text
    assert ".rect" not in text and "get_pixmap" not in text


def test_the_assessment_carries_no_benchmark_project_drawing_or_tag_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text)
    assert not re.search(r"""["'][WD]0?\d{1,2}["']""", text)
    assert not re.search(r"\.pdf\b", text)
