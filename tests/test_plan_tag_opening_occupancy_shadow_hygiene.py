"""Structural guards: the occupancy census is reachable only from the callout shadow's opt-in adapter."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_plan_tag_opening_occupancy_shadow"
SOURCE = REPO / f"{MODULE}.py"
CALLOUT = REPO / "pb_source_plan_glazing_strip_callout_shadow.py"

# the live issuer, the host binder, the count producer, quantity publication, the wall adapter and the other
# sibling shadows. The schedule binder is allowed for ONE function-level private helper only (pinned below).
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_opening_host_binding_authority", "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_", "pb_strip_structural_assessment_shadow",
    "pb_strip_face_family_shadow", "pb_subfloor_ink_census_shadow", "pb_glazing_anatomy_inventory_shadow",
    "pb_native_text_residual_census_shadow", "pb_elevation_frame_locality_census_shadow", "pb_hosted_opening",
    "pb_bound_", "pb_canonical_quantity",
)
BINDER = "pb_schedule_opening_instance_binding_authority"
ALLOWED_IMPORTS = {
    "__future__", "math", "dataclasses", "typing", "pb_migration_contracts", "pb_physical_opening_authority",
    "pb_source_plan_glazing_strip_callout_shadow",
    # function-level, inside the producer adapter only
    BINDER, "pb_source_observation_authority",
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


def test_only_the_callout_shadows_opt_in_adapter_imports_the_census():
    scanned = _non_test_sources()
    assert len(scanned) > 500 and any(p.parent == REPO for p in scanned)
    for sample in (f"import {MODULE}", f"from {MODULE} import x", f"    import {MODULE} as census"):
        assert re.search(IMPORT_PATTERN, "x = 1\n" + sample + "\n", re.M), sample
    assert not re.search(IMPORT_PATTERN, f"# import {MODULE}\nimport {MODULE}_other\n", re.M)
    importers = [p.relative_to(REPO).as_posix() for p in scanned
                 if re.search(IMPORT_PATTERN, p.read_text(encoding="utf-8", errors="replace"), re.M)]
    assert importers == ["pb_source_plan_glazing_strip_callout_shadow.py"]


def test_that_import_is_function_level_inside_the_source_adapter_only():
    tree = ast.parse(CALLOUT.read_text(encoding="utf-8"))
    for top in tree.body:
        assert not (isinstance(top, ast.ImportFrom) and top.module == MODULE)
        assert not (isinstance(top, ast.Import) and any(a.name == MODULE for a in top.names))
    holders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if any(isinstance(sub, ast.ImportFrom) and sub.module == MODULE for sub in ast.walk(node)):
                holders.append(node.name)
    assert holders == ["audit_plan_callout_to_glazing_strip_from_source"]


def test_the_census_imports_no_issuer_host_count_wall_quantity_or_sibling_shadow_module():
    assert [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)] == []
    tree = ast.parse("def f():\n    from pb_opening_host_binding_authority import X\n    import pb_live_x\n")
    found = list(_imports_of(tree))
    assert len(found) == 2 and all(m.startswith(FORBIDDEN_IMPORT_PREFIXES) for m in found)


def test_the_census_imports_exactly_the_allow_listed_modules():
    assert set(_imports(SOURCE)) <= ALLOWED_IMPORTS


def test_the_schedule_binder_is_reached_only_for_its_aperture_helper_inside_the_adapter():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    binder_imports = [(node, [a.name for a in node.names]) for node in ast.walk(tree)
                      if isinstance(node, ast.ImportFrom) and node.module == BINDER]
    assert len(binder_imports) == 1 and binder_imports[0][1] == ["_opening_aperture"]
    assert not any(isinstance(top, (ast.Import, ast.ImportFrom)) and BINDER in ast.dump(top) for top in tree.body)
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("publish_scope", "ScheduleOpeningInstanceBinding", "resolve(", "_aperture_contains_bbox(",
                   "_blocked", "parse_schedule_rows"):
        assert needle not in text, needle


def test_importing_the_census_loads_no_consumer_module_and_not_even_the_binder():
    forbidden = FORBIDDEN_IMPORT_PREFIXES + (BINDER,)
    code = ("import sys; sys.path[:0] = [%r]; import pb_plan_tag_opening_occupancy_shadow; "
            "bad = [m for m in sys.modules if m.startswith(%r)]; print(sorted(bad))") % (str(REPO), forbidden)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr
    assert ast.literal_eval(completed.stdout.strip().splitlines()[-1]) == []


def test_the_census_never_builds_an_existence_record_and_calls_each_authority_entry_once():
    text = SOURCE.read_text(encoding="utf-8")
    assert "PhysicalOpeningExistenceRecord(" not in text and "PhysicalOpeningExistenceResult(" not in text
    assert text.count("prove_existence(") == 1 and text.count(".visible_candidate_structures(") == 1
    assert text.count("fork_native_source_shadow(") == 1 and text.count(".resolve_visible(") == 2
    for needle in ("physical_opening_authority()._", "_cache[", "_cache.clear", "capabilities", "publish_",
                   "text_integrity_authority", "OpeningElevationFrameArea", "from_source_visibility_producer",
                   "classify_disposition", "assess_visible_candidate_closure"):
        assert needle not in text, needle
    assert ".rect" not in text and "get_pixmap" not in text and "mediabox" not in text and "import fitz" not in text


def test_the_census_carries_no_benchmark_project_drawing_or_tag_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text) and not re.search(r"\.pdf\b", text)
    assert not re.search(r"""["'][A-Z]{1,3}0?\d{1,2}["']""", text)           # no tag literal, no letter test
    assert not re.search(r"page_id\s*==\s*\d", text) and "callout_mark_pattern" not in text
    assert "startswith(" not in text and "normalize_opening_tag" not in text   # the census never reads a tag's text


def test_the_census_has_no_distance_nearest_or_first_choice():
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called.add(node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", ""))
    # code, not prose: no distance, no extremum over candidates, no first-of-several choice
    assert not called & {"dist", "hypot", "min", "max", "next_nearest"}
    assert "[0]) <" not in text and "sorted(containing)[0]" not in text and "containing[0]" in text   # only the unique one
    # the unique-candidate branch is reached only after the several-candidate branch has returned
    assert text.index("len(containing) > 1") < text.index("containing[0]")
    # the only ordering is by candidate id, applied after every candidate has been tested against the anchor
    assert "containing.sort(key=lambda c: c.candidate_id)" in text


def test_the_census_adds_no_second_evidence_vocabulary_or_scale_or_quantity_schema():
    text = SOURCE.read_text(encoding="utf-8")
    assert "class EvidenceResolutionStatus" not in text and "class EvidenceAtom" not in text
    assert "def stable_contract_id" not in text
    assert "mm_per" not in text and "scale_granted=True" not in text and "solve_scale" not in text


def test_the_callout_module_remains_pure_it_still_imports_no_opening_authority():
    text = CALLOUT.read_text(encoding="utf-8")
    assert "visible_candidate_structures" not in text and "prove_existence" not in text
    assert MODULE in text and text.count(f"from {MODULE} import") == 1


def test_the_module_level_constants_are_immutable_tuples():
    import pb_plan_tag_opening_occupancy_shadow as M

    for name in ("STANDING_LIMITS", "_GRANT_FLAGS"):
        assert isinstance(getattr(M, name), tuple), name
    assert len(M.STANDING_LIMITS) == len(set(M.STANDING_LIMITS)) >= 2
