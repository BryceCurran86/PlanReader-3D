"""Structural guards: the face-family shadow is unreachable from production and reaches no consumer."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_strip_face_family_shadow"
SOURCE = (REPO / f"{MODULE}.py")

# the live issuer, binders, count producer, host resolver, quantity publication, the wall adapter and the sibling shadows
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
    "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_", "pb_strip_", "pb_source_plan_glazing_strip",
)
# every module the shadow may import, at any nesting depth
ALLOWED_IMPORTS = {
    "__future__", "bisect", "hashlib", "math", "re", "dataclasses", "typing", "fitz",
    "pb_migration_contracts", "pb_physical_opening_authority", "pb_wall_room_topology_typed_negative_evidence",
    "pb_source_visibility_authority", "pb_source_observation_authority", "pb_vector_geometry_v130",
    "pb_viewport_segmentation", "pb_pdf_text_integrity_authority",
}

# a tiny synthetic audit in a clean interpreter, run through the adapter, listing what ended up loaded
_AUDIT_PROBE = "\n".join([
    "import sys; sys.path[:0] = [{repo!r}]",
    "import fitz, {module} as F",
    "from pb_source_visibility_authority import SourceVisibilityProducer",
    "doc = fitz.open(); page = doc.new_page(width=400, height=400)",
    "page.draw_line(fitz.Point(50, 100), fitz.Point(150, 100), color=(0, 0, 0), width=0.5)",
    "source = SourceVisibilityProducer(producer_method='hygiene', producer_version='1')",
    "pub = source.ingest_native_pdf_bytes(document_id='d', source_bytes=doc.tobytes(), source_locator='memory://d')",
    "got = F.StripFaceFamilyShadow(source, enabled=True).audit(revision_id=pub.revision.revision_id, page_id=1,",
    "    nominated_observation_ids=list(pub.visible_observation_ids), coordinate_quantum_pt=0.24)",
    "print(sorted(m for m in sys.modules if m.startswith({prefixes!r})))",
])


# the pure core on a mixed page (a through line, a thicker rival at the same offset, a broken pair, a short line)
_REPLAY_PROBE = "\n".join([
    "import sys; sys.path[:0] = [{repo!r}]",
    "import {module} as F",
    "own = F.FaceFamilyOwnership('d', 'r', 's', 'a' * 64, '7')",
    "vp = F.ViewportRef('v', (0.0, 0.0, 3000.0, 3000.0))",
    "def st(i, x0, y0, x1, y1, w=0.48):",
    "    return F.SourceStroke(i, (x0, y0, x1, y1), w, (0.0, 0.0, 0.0), True, True, 'line', True, later_area_paint_clear=True)",
    "page = [st('n1', 100, 300, 304, 300), st('n2', 100, 305.52, 304, 305.52), st('n3', 100, 300, 100, 305.52),",
    "        st('n4', 304, 300, 304, 305.52), st('a', 20, 296, 400, 296), st('b', 190, 296.05, 200, 296.05, 0.96),",
    "        st('c', 20, 310.52, 250, 310.52), st('d', 20, 290, 180, 290), st('e', 220, 290, 400, 290),",
    "        st('f', 50, 296.10, 60, 296.10), st('g', 20, 285, 400, 285), st('h', 20, 285, 400, 285)]",
    "got = F.audit_strip_face_family(ownership=own, viewport=vp, nominated_ids=['n4', 'n3', 'n2', 'n1'],",
    "    page_strokes=page, coordinate_quantum_pt=0.24)",
    "print(got.status.value, got.reason_codes, got.record_id, [g.group_id for g in got.groups],",
    "      [g.member_observation_ids for g in got.groups], got.continuous_group_ids, got.conflicted_group_ids)",
])


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_nothing_in_production_imports_the_face_family_shadow():
    importers = []
    for root in ("", "tools", "scripts"):
        for path in sorted((REPO / root).glob("*.py")):
            if path == SOURCE:
                continue
            if re.search(rf"^\s*(?:from|import)\s+{MODULE}\b", path.read_text(encoding="utf-8", errors="replace"), re.M):
                importers.append(path.relative_to(REPO).as_posix())
    assert importers == []


def test_the_shadow_imports_no_issuer_binder_count_host_wall_or_sibling_strip_module():
    bad = [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    assert bad == []


def test_the_shadow_imports_only_the_allow_listed_modules_at_every_nesting_depth():
    assert sorted({m for m in _imports(SOURCE)} - ALLOWED_IMPORTS) == []


def test_importing_the_shadow_loads_no_consumer_module():
    """Every forbidden prefix, with the shadow itself the only match allowed."""
    code = ("import sys; sys.path[:0] = [%r]; import %s; "
            "bad = [m for m in sys.modules if m.startswith(%r)]; print(sorted(bad))") % (
        str(REPO), MODULE, FORBIDDEN_IMPORT_PREFIXES)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr
    loaded = ast.literal_eval(completed.stdout.strip().splitlines()[-1])
    assert [m for m in loaded if m != MODULE] == []


def test_a_full_adapter_audit_of_a_synthetic_page_loads_no_consumer_module_either():
    """The adapter's own lazy imports (producer, observation authority, vector geometry, viewport segmentation)."""
    code = _AUDIT_PROBE.format(repo=str(REPO), module=MODULE, prefixes=FORBIDDEN_IMPORT_PREFIXES)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=600)
    assert completed.returncode == 0, completed.stderr
    loaded = ast.literal_eval(completed.stdout.strip().splitlines()[-1])
    assert [m for m in loaded if m != MODULE] == []


def test_the_verdict_and_every_id_are_identical_across_python_hash_seeds():
    """Dict / set ordering must never reach a result: the same page replays to the same ids in any interpreter."""
    code = _REPLAY_PROBE.format(repo=str(REPO), module=MODULE)
    outputs = []
    for seed in ("0", "1", "4242"):
        completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=300,
                                   env={"PYTHONHASHSEED": seed, "SYSTEMROOT": "C:/Windows", "PATH": ""})
        assert completed.returncode == 0, completed.stderr
        outputs.append(completed.stdout.strip().splitlines()[-1])
    assert len(set(outputs)) == 1, outputs
    assert outputs[0].startswith("conflict") or outputs[0].startswith("candidate") or outputs[0].startswith("abstained")


def test_the_shadow_never_builds_an_existence_record_and_never_calls_the_opening_authority_or_edits_state():
    text = SOURCE.read_text(encoding="utf-8")
    assert "PhysicalOpeningExistenceRecord(" not in text and "PhysicalOpeningExistenceResult(" not in text
    for needle in ("prove_existence", "visible_candidate_structures", "physical_opening_authority(",
                   "fork_native_source_shadow", ".text_integrity_authority(", "_physical_opening_authority_cache"):
        assert needle not in text, needle
    neutral_geometry = {"_exact_fill_path_coverage", "_fill_text_char_bbox_coverage_upper_bound",
                        "_later_paint_spatial_candidates"}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom) and node.module == "pb_pdf_text_integrity_authority":
            assert {alias.name for alias in node.names} == neutral_geometry
    assert "_cache[" not in text and "_cache.clear" not in text and "_cache =" not in text
    assert "capabilities" not in text and "publish_" not in text
    assert ".rect" not in text and "get_pixmap" not in text and "mediabox" not in text


def test_the_shadow_carries_no_benchmark_project_drawing_or_tag_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text)
    assert not re.search(r"""["'][WD]0?\d{1,2}["']""", text)
    assert not re.search(r"\.pdf\b", text)
    # no floating-point literal other than the repository's own black-ink convention, the quarter-quantum snap, the
    # midrange divisor and the PDF's own "fully opaque" value
    literals = {n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Constant) and type(n.value) is float}
    assert literals <= {0.0, 0.1, 0.25, 1.0, 2.0}, literals
    # and no integer literal that could be a fitted threshold: only the structural ones (the 4 geometry coordinates
    # and their indices, the 3 colour channels, the 6 decimal places of the paint key, the work bound, 0 and 1)
    integers = {n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Constant) and type(n.value) is int}
    assert integers <= {0, 1, 2, 3, 4, 5_000, 6}, integers


def test_the_gate_the_grants_and_the_work_bound_are_declared_in_the_source():
    text = SOURCE.read_text(encoding="utf-8")
    assert "enabled: bool = False" in text and "type(enabled) is not bool" in text
    assert "_MAX_GROUPS = 5_000" in text and "if self.shadow_only is not True" in text
    assert text.count("shadow_only: bool = True") == 1
    for flag in ("takeoff_eligible", "deduction_authority", "existence_record_issued"):
        assert f"{flag}: bool = False" in text
