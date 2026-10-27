"""Structural guards: the census is unreachable from production, reaches no consumer, and mirrors the producer's floors."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pb_subfloor_ink_census_shadow as C

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_subfloor_ink_census_shadow"
SOURCE = REPO / f"{MODULE}.py"

# the live issuer, binders, count producer, host resolver, quantity publication and the wall adapter
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
    "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_",
)
# everything the module may import, at module scope or lazily inside the adapter
ALLOWED_IMPORTS = {
    "__future__", "hashlib", "math", "re", "collections", "dataclasses", "typing", "fitz",
    "pb_migration_contracts", "pb_physical_opening_authority", "pb_wall_room_topology_typed_negative_evidence",
    "pb_source_observation_authority", "pb_source_visibility_authority", "pb_vector_geometry_v130",
    "pb_viewport_segmentation",
}
# the only names taken from the physical-opening module: three reason codes, never its authority or its records
ALLOWED_PHYSICAL_OPENING_NAMES = {
    "OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED", "SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE",
    "VISIBLE_SOURCE_AUTHORITY_REQUIRED",
}


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_nothing_in_production_imports_the_census():
    importers = []
    for root in ("", "tools", "scripts"):
        for path in sorted((REPO / root).glob("*.py")):
            if path == SOURCE:
                continue
            if re.search(rf"^\s*(?:from|import)\s+{MODULE}\b", path.read_text(encoding="utf-8", errors="replace"), re.M):
                importers.append(path.relative_to(REPO).as_posix())
    assert importers == []


def test_the_census_imports_no_issuer_binder_count_host_or_wall_module():
    bad = [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    assert bad == []


def test_the_census_imports_only_an_allowlist_and_takes_three_codes_from_the_physical_opening_module():
    seen = {m.split(".")[0] for m in _imports(SOURCE)}
    assert seen <= ALLOWED_IMPORTS, sorted(seen - ALLOWED_IMPORTS)
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    taken = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
             and node.module == "pb_physical_opening_authority" for alias in node.names}
    assert taken == ALLOWED_PHYSICAL_OPENING_NAMES
    assert not any(isinstance(node, ast.Import) and any(a.name == "pb_physical_opening_authority" for a in node.names)
                   for node in ast.walk(tree))


# the producer's own extraction and its own clip proof; nothing else is taken from the extraction module
ALLOWED_VECTOR_NAMES = {"extract_native_page", "_clip_scissor_by_seqno", "_resolve_clip_proof_fields"}


def test_only_the_producers_extraction_and_clip_proof_are_taken_from_the_vector_geometry_module():
    import pb_vector_geometry_v130 as producer_extraction

    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    taken = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
             and node.module == "pb_vector_geometry_v130" for alias in node.names}
    assert taken == ALLOWED_VECTOR_NAMES
    assert all(callable(getattr(producer_extraction, name)) for name in taken)       # fails if the producer renames them


def test_the_census_does_not_import_the_strip_finder_it_mirrors():
    """The finder's rule is restated here and compared with the finder in the tests; the module itself stays independent."""
    assert not [m for m in _imports(SOURCE) if "glazing_strip" in m or "strip_structural" in m]


def test_importing_the_census_loads_no_consumer_module():
    code = ("import sys; sys.path[:0] = [%r]; import pb_subfloor_ink_census_shadow; "
            "bad = [m for m in sys.modules if m.startswith(%r)]; print(sorted(bad))") % (str(REPO), FORBIDDEN_IMPORT_PREFIXES)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr
    # pb_physical_opening_authority legitimately pulls the wall candidate stack; the consumers below must stay unloaded
    loaded = eval(completed.stdout.strip().splitlines()[-1])
    consumers = [m for m in loaded if m.startswith(FORBIDDEN_IMPORT_PREFIXES[:5])]
    assert consumers == []


def test_the_census_never_builds_an_existence_record_or_edits_any_cache():
    text = SOURCE.read_text(encoding="utf-8")
    assert "PhysicalOpeningExistenceRecord(" not in text and "PhysicalOpeningExistenceResult(" not in text
    assert "_cache[" not in text and "_cache.clear" not in text and "_cache =" not in text
    assert "capabilities" not in text and "publish_" not in text
    assert "physical_opening_authority()" not in text and "fork_native_source_shadow" not in text
    assert ".rect" not in text and "get_pixmap" not in text


def test_the_census_reads_no_page_rotation_or_rotated_frame():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in (".rotation", "set_rotation", "derotation", "rotation_matrix", "mediabox", "cropbox"):
        assert needle not in text, needle


def test_the_census_carries_no_benchmark_project_drawing_or_tag_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text)
    assert not re.search(r"""["'][WD]0?\d{1,2}["']""", text)
    assert not re.search(r"\.pdf\b", text)


def test_the_module_defines_no_second_status_or_quantity_vocabulary():
    names = {f.name for f in C.SubFloorInkCensus.__dataclass_fields__.values()}
    assert not ({"area_m2", "length_m", "aperture_bbox_pt", "host_candidate_id", "existence_record", "structural_pattern",
                 "candidate_wall_ids_considered", "quantity", "count"} & names)
    text = SOURCE.read_text(encoding="utf-8")
    assert not re.search(r"class\s+\w*Status\b", text)
    # the only status the module ever resolves from the producer is read, never issued
    assert "EvidenceResolutionStatus.CORROBORATED" in text and text.count("EvidenceResolutionStatus.CORROBORATED") == 1


# --- the producer's floors, mirrored: a change of either fails here -----------------------------------------


def _hypot_floor(module_name: str, function_name: str) -> list[float]:
    """Every constant a `math.hypot(...)` result is compared with, with `<`, inside one function of the producer."""
    tree = ast.parse((REPO / f"{module_name}.py").read_text(encoding="utf-8"))
    out: list[float] = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == function_name:
            for node in ast.walk(fn):
                if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Call)
                        and isinstance(node.left.func, ast.Attribute) and node.left.func.attr == "hypot"
                        and len(node.ops) == 1 and isinstance(node.ops[0], ast.Lt)
                        and isinstance(node.comparators[0], ast.Constant)):
                    out.append(float(node.comparators[0].value))
    return out


def test_the_mirrored_extractor_line_floor_is_the_producers_literal():
    assert _hypot_floor("pb_vector_geometry_v130", "extract_native_page") == [C.PRODUCER_LINE_ITEM_FLOOR_PT]


def test_the_mirrored_visibility_floor_is_the_producers_literal():
    assert _hypot_floor("pb_source_visibility_authority", "_segment_geometry") == [C.PRODUCER_VISIBLE_SEGMENT_FLOOR_PT]


def test_the_two_floors_are_documented_with_the_modules_that_own_them():
    text = SOURCE.read_text(encoding="utf-8")
    assert "pb_vector_geometry_v130.extract_native_page" in text
    assert "pb_source_visibility_authority._segment_geometry" in text
