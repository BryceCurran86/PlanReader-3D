"""Structural guards: the shadow is unreachable from production, free of benchmark inputs, and census-only."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from plan_callout_strip_fixture import Sheet, add_window

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_source_plan_glazing_strip_callout_shadow"
OWN_FILES = {
    "pb_source_plan_glazing_strip_callout_shadow.py",
    "tools/diag_plan_callout_strip_census.py",
}


def _python_files(*roots: str):
    for root in roots:
        for path in sorted((REPO / root).rglob("*.py")) if root else sorted(REPO.glob("*.py")):
            yield path


def test_nothing_in_production_imports_the_shadow():
    importers = []
    for path in list(_python_files("")) + list(_python_files("tools")) + list(_python_files("scripts")):
        relative = path.relative_to(REPO).as_posix()
        if relative in OWN_FILES:
            continue
        if re.search(rf"^\s*(?:from|import)\s+{MODULE}\b", path.read_text(encoding="utf-8", errors="replace"), re.M):
            importers.append(relative)
    assert importers == []


@pytest.mark.parametrize("relative", sorted(OWN_FILES))
def test_the_shadow_and_its_tool_carry_no_benchmark_project_or_drawing_constants(relative):
    text = (REPO / relative).read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, (relative, needle)
    assert not re.search(r"\b[0-9a-f]{64}\b", text), relative                  # no source SHA
    assert not re.search(r"""["'][WD]0?\d{1,2}["']""", text), relative          # no tag literal
    assert not re.search(r"\.pdf\b", text.replace("private drawing", ""), re.I) or relative.endswith("census.py")


def test_the_shadow_never_reads_the_page_rectangle_or_claims_scale():
    text = Path(shadow.__file__).read_text(encoding="utf-8")
    assert "page.rect" not in text and "get_pixmap" not in text
    assert "mm_per_pt" not in text and "scale_granted=True" not in text
    receipt_fields = {f for f in shadow.PlanCalloutStripShadow.__dataclass_fields__}
    assert not any("mm_per" in f or f == "scale" for f in receipt_fields)


def test_the_receipt_publishes_no_absolute_scale_anywhere():
    sheet = Sheet(size=(1400.0, 900.0))
    add_window(sheet, 0, "W1", panels=3, length=204.0)
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    from plan_callout_strip_fixture import MM_PER_PT, run
    result = run(sheet)
    published = json.dumps([[n, v] for c in result.correspondences for n, v in c.numbers])
    for c in result.correspondences:
        for _, value in c.numbers:
            assert abs(value - MM_PER_PT) > 1e-3
    assert "mm" not in published


def test_the_census_tool_imports_and_exposes_only_its_cli():
    completed = subprocess.run(
        [sys.executable, "-I", "-c", "import sys; sys.path[:0] = [%r]; import tools.diag_plan_callout_strip_census as t; "
         "print(sorted(n for n in dir(t) if not n.startswith('_')))" % str(REPO)],
        capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert "census" in completed.stdout and "main" in completed.stdout
