"""Structural guards: the inventory is unreachable from production and reaches no consumer."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_glazing_anatomy_inventory_shadow"
SOURCE = REPO / f"{MODULE}.py"

# the live issuer, binders, count producer, host resolver, quantity publication, the wall adapter, and the
# sibling shadows (this inventory reads the producer itself and imports no other shadow)
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
    "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_", "pb_source_plan_glazing_strip_callout_shadow",
    "pb_strip_structural_assessment_shadow", "pb_hosted_opening", "pb_bound_", "pb_canonical_quantity",
)
ALLOWED_IMPORTS = {
    "__future__", "hashlib", "math", "re", "bisect", "collections", "dataclasses", "typing",
    "pb_migration_contracts", "pb_physical_opening_authority", "pb_wall_room_topology_typed_negative_evidence",
    # function-level, inside the producer adapter only
    "fitz", "pb_source_visibility_authority", "pb_source_observation_authority", "pb_vector_geometry_v130",
    "pb_viewport_segmentation",
}
IMPORT_PATTERN = rf"^\s*(?:from|import)\s+{MODULE}\b"
_SKIPPED_DIRS = {".git", ".claude", "node_modules", "__pycache__"}


def _imports_of(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def _imports(path: Path):
    yield from _imports_of(ast.parse(path.read_text(encoding="utf-8")))


def _non_test_sources():
    out = []
    for path in sorted(REPO.rglob("*.py")):
        parts = path.relative_to(REPO).parts
        if path == SOURCE or parts[0] == "tests" or any(part in _SKIPPED_DIRS for part in parts):
            continue
        out.append(path)
    return out


def test_nothing_in_production_imports_the_inventory():
    scanned = _non_test_sources()
    # the scan is only meaningful if it really covers the production tree and its pattern really matches an import
    assert len(scanned) > 500
    assert any(p.parent == REPO for p in scanned) and any(p.parent.name == "tools" for p in scanned)
    for sample in (f"import {MODULE}", f"from {MODULE} import x", f"    import {MODULE} as inventory"):
        assert re.search(IMPORT_PATTERN, "x = 1\n" + sample + "\n", re.M), sample
    assert not re.search(IMPORT_PATTERN, f"# import {MODULE}\nimport {MODULE}_other\n", re.M)
    importers = [p.relative_to(REPO).as_posix() for p in scanned
                 if re.search(IMPORT_PATTERN, p.read_text(encoding="utf-8", errors="replace"), re.M)]
    assert importers == []                                  # only this inventory's own tests import it
    assert len(list((REPO / "tests").glob("test_glazing_anatomy_inventory_shadow_*.py"))) == 3


def test_the_inventory_imports_no_issuer_binder_count_host_wall_quantity_or_sibling_shadow_module():
    assert [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)] == []
    # positive control: the AST walk sees function-level imports and the prefixes flag a forbidden one
    tree = ast.parse("def f():\n    from pb_schedule_opening_instance_binding_authority import X\n    import pb_live_x\n")
    found = list(_imports_of(tree))
    assert len(found) == 2 and all(m.startswith(FORBIDDEN_IMPORT_PREFIXES) for m in found)


def test_the_inventory_imports_exactly_the_allow_listed_modules():
    assert set(_imports(SOURCE)) <= ALLOWED_IMPORTS


def test_importing_the_inventory_loads_no_consumer_module():
    code = ("import sys; sys.path[:0] = [%r]; import pb_glazing_anatomy_inventory_shadow; "
            "bad = [m for m in sys.modules if m.startswith(%r)]; print(sorted(bad))") % (str(REPO), FORBIDDEN_IMPORT_PREFIXES)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr
    loaded = eval(completed.stdout.strip().splitlines()[-1])
    # the vocabulary constants come from pb_physical_opening_authority; it must pull in no issuer, binder, count,
    # host, live, wall or sibling-shadow module, checked against the COMPLETE forbidden set
    assert loaded == []


def test_the_inventory_never_builds_an_existence_record_or_calls_the_opening_authority():
    text = SOURCE.read_text(encoding="utf-8")
    assert "PhysicalOpeningExistenceRecord(" not in text and "PhysicalOpeningExistenceResult(" not in text
    for needle in ("physical_opening_authority(", "prove_existence", "visible_candidate_structures",
                   "fork_native_source_shadow", "_cache[", "_cache.clear", "_cache =", "capabilities", "publish_",
                   "text_integrity_authority", "OpeningElevationFrameArea", "from_source_visibility_producer"):
        assert needle not in text, needle
    assert ".rect" not in text and "get_pixmap" not in text and "mediabox" not in text
    # the one authority call the adapter makes is the producer's own visible-observation resolution
    assert text.count(".resolve_visible(") == 1 and text.count("source.authority()") == 1


def test_the_inventory_carries_no_benchmark_project_drawing_or_tag_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text)
    assert not re.search(r"""["'][A-Z]{1,3}0?\d{1,2}["']""", text)
    assert not re.search(r"\.pdf\b", text)
    # no page number, plan name, tag pattern or stroke-width literal is wired into the module
    assert not re.search(r"page_id\s*==\s*\d", text) and "callout_mark_pattern" not in text and "panel_token" not in text
    assert not re.search(r"\b(?:0\.48|0\.96|1\.2)\b", text)


def test_the_inventory_adds_no_second_evidence_vocabulary_or_scale_or_quantity_schema():
    text = SOURCE.read_text(encoding="utf-8")
    assert "class EvidenceResolutionStatus" not in text and "class EvidenceAtom" not in text
    assert "def stable_contract_id" not in text
    assert "mm_per" not in text and "scale_granted=True" not in text and "solve_scale" not in text
    assert "EvidenceResolutionStatus.CONFLICT" not in text      # verdicts are CANDIDATE / ABSTAINED only


def test_the_module_level_gate_constants_are_immutable_tuples():
    import pb_glazing_anatomy_inventory_shadow as A

    for name in ("GATE_NAMES", "STANDING_LIMITS", "NEAR_MISS_GATES", "_GRANT_FLAGS", "_STATUSES"):
        assert isinstance(getattr(A, name), tuple), name
    assert len(set(A.GATE_NAMES)) == 8 and all(n.startswith(f"g{i + 1}_") for i, n in enumerate(A.GATE_NAMES))
    assert len(A.STANDING_LIMITS) == len(set(A.STANDING_LIMITS)) >= 5
