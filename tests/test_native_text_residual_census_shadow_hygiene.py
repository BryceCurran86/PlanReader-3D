"""Structural guards: the census is unreachable from production, reaches no consumer, and keeps no word text."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_native_text_residual_census_shadow"
SOURCE = REPO / f"{MODULE}.py"

# the live issuer, binders, count producer, host resolver, quantity publication and the wall adapter
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
    "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_",
)
# everything the census may import, at module level or lazily
ALLOWED_IMPORTS = {
    "__future__", "hashlib", "math", "collections", "dataclasses", "typing", "fitz",
    "pb_migration_contracts", "pb_pdf_text_integrity_authority", "pb_physical_opening_authority",
    "pb_wall_room_topology_typed_negative_evidence", "pb_source_visibility_authority",
    "pb_opening_tag_normalization", "pb_source_observation_authority",
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
    # the only importers are this census's own tests (they live under tests/, which is not scanned here)
    assert importers == []


def test_the_census_imports_no_issuer_binder_count_host_or_wall_module():
    bad = [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    assert bad == []


def test_the_census_imports_only_an_allowlisted_set_of_modules():
    unexpected = sorted({m.split(".")[0] for m in _imports(SOURCE)} - ALLOWED_IMPORTS)
    assert unexpected == []


def test_importing_the_census_loads_no_consumer_module():
    code = ("import sys; sys.path[:0] = [%r]; import %s; "
            "bad = [m for m in sys.modules if m.startswith(%r)]; print(sorted(bad))") % (
        str(REPO), MODULE, FORBIDDEN_IMPORT_PREFIXES)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=600)
    assert completed.returncode == 0, completed.stderr
    # not the issuer, the binders, the count producer, the host resolver, the wall stack or the canonical adapter
    assert eval(completed.stdout.strip().splitlines()[-1]) == []


def test_running_a_census_loads_no_module_the_producer_itself_did_not_already_load():
    code = "\n".join([
        "import sys; sys.path[:0] = [%r]",
        "import fitz",
        "from pb_source_visibility_authority import SourceVisibilityProducer",
        "import %s as C",
        "doc = fitz.open(); page = doc.new_page(width=300, height=200)",
        "page.insert_text((20, 100), 'Hello', fontsize=10, fontname='helv')",
        "source = SourceVisibilityProducer(producer_method='hygiene', producer_version='1')",
        "published = source.ingest_native_pdf_bytes(document_id='hygiene-doc', source_bytes=doc.tobytes(),",
        "                                           source_locator='memory://hygiene.pdf')",
        "before = set(sys.modules)",
        "got = C.NativeTextResidualCensusShadow(source, enabled=True).census(",
        "    revision_id=published.revision.revision_id, page_ids=(1,))",
        "assert got.status.value == 'candidate' and got.pages[0].total_count == 1",
        "new = sorted(m for m in set(sys.modules) - before)",
        "print(new)",
    ]) % (str(REPO), MODULE)
    completed = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=900)
    assert completed.returncode == 0, completed.stderr
    new = eval(completed.stdout.strip().splitlines()[-1])
    assert [m for m in new if m.startswith(FORBIDDEN_IMPORT_PREFIXES)] == []
    assert [m for m in new if m.startswith("pb_")] in ([], ["pb_opening_tag_normalization"])


def test_the_census_never_builds_an_existence_record_or_edits_any_authoritys_state():
    text = SOURCE.read_text(encoding="utf-8")
    assert "PhysicalOpeningExistenceRecord(" not in text and "PhysicalOpeningExistenceResult(" not in text
    assert "_cache[" not in text and "_cache.clear" not in text and "_cache =" not in text
    assert "capabilities" not in text and "publish_" not in text
    assert ".rect" not in text and "get_pixmap" not in text
    # no opening authority, no fork, no OCR or raster path: a census only reads text receipts and font tables
    for needle in ("physical_opening_authority(", "fork_native_source_shadow", "ocr", "render_native_page", "prove_existence"):
        assert needle not in text.replace("pb_physical_opening_authority", ""), needle


def test_the_only_producer_internals_the_census_reads_are_the_revision_check_and_the_source_bytes():
    text = SOURCE.read_text(encoding="utf-8")
    assert sorted(set(re.findall(r"source\._producer\.(\w+)", text))) == ["_store", "current_revision_id"]
    assert sorted(set(re.findall(r"_store\.(\w+)", text))) == ["source_bytes_by_revision"]
    assert re.findall(r"source_bytes_by_revision(\S*)", text) == [".get(revision_id)"]
    # reads only: nothing assigns to, deletes from or mutates a producer attribute
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "source":
                        raise AssertionError("the census assigns to the producer")
        assert not isinstance(node, ast.Delete)


def test_word_text_is_only_ever_measured_or_syntax_checked_never_stored_or_compared():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("raw_text", "trusted_text"):
            parent = parents[node]
            # `type(...)` only checks that the receipt's text is a str; it reveals and stores nothing
            ok = (isinstance(parent, ast.Call) and node in parent.args
                  and isinstance(parent.func, ast.Name) and parent.func.id in ("len", "type", "normalize_opening_tag"))
            uses.append((node.attr, ok))
    assert uses and all(ok for _, ok in uses), uses
    # the only calls that read the text are the length, the type check and the generic tag normaliser, once each
    readers = sorted(parents[n].func.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "raw_text")
    assert readers == ["len", "normalize_opening_tag", "type"], readers
    assert not any(attr == "trusted_text" for attr, _ in uses)
    # no record field is named for text
    fields_named = [n.target.id for n in ast.walk(tree) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
    assert not [f for f in fields_named if "text" in f.lower() and f not in ("text_length", "text_identity_granted",
                                                                          "trusted_text_granted", "text_trust_changed",
                                                                          "text_ids_without_receipt")]


def test_every_grant_flag_default_is_false_in_the_source():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for flag in ("takeoff_eligible", "deduction_authority", "existence_record_issued", "trusted_text_granted",
                 "text_identity_granted", "text_trust_changed"):
        found = [n for n in ast.walk(tree) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                 and n.target.id == flag]
        assert len(found) == 2, flag                                  # the page census and the roll-up
        assert all(isinstance(n.value, ast.Constant) and n.value.value is False for n in found), flag


def test_the_census_carries_no_benchmark_project_drawing_or_tag_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "Lot16", "3Laurel", "Ghazi",
                   "documents/sources", "expected_", "benchmark_", "gold"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text)
    assert not re.search(r"""["'][WD]0?\d{1,2}["']""", text)
    assert not re.search(r"\.pdf\b", text)
    # no hard-coded page number, revision, document or font name decides anything
    tree = ast.parse(text)
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for font in ("Arial", "Helvetica", "Verdana", "ISOCPEUR", "Calibri", "Courier", "Times"):
        assert not any(font in s for s in strings), font


def test_the_work_bounds_are_the_only_numeric_thresholds():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    constants = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
                 if isinstance(t, ast.Name) and isinstance(n.value, (ast.Constant, ast.UnaryOp))
                 and isinstance(getattr(n.value, "value", None), (int, float))}
    # exactly these module-level numbers: nothing else is a threshold
    assert constants == {"DEFAULT_MAX_UNTRUSTED_RECORDS", "_MAX_WORDS_PER_PAGE", "_MAX_PAGES_PER_CALL", "_GRID_CELL_PT",
                         "_MAX_CELLS_PER_SPAN", "_DIRECTION_NOISE"}
    # and no other float literal hides inside a function (only the exact half of a centre and the zero vector)
    floats = sorted({n.value for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) for n in ast.walk(f)
                     if isinstance(n, ast.Constant) and type(n.value) is float})
    assert floats == [0.0, 0.5], floats
    # integer literals inside functions are structural indexes and the six character PDF subset tag only
    ints = sorted({n.value for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) for n in ast.walk(f)
                   if isinstance(n, ast.Constant) and type(n.value) is int})
    assert ints == [0, 1, 2, 3, 4, 6, 7], ints


def test_the_gate_and_the_page_request_are_the_only_caller_inputs_of_the_adapter():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    shadow = next(c for c in ast.walk(tree) if isinstance(c, ast.ClassDef) and c.name == "NativeTextResidualCensusShadow")
    args = {n.name: [a.arg for a in n.args.args + n.args.kwonlyargs] for n in shadow.body
            if isinstance(n, ast.FunctionDef) and n.name in ("census", "__init__")}
    assert args == {"__init__": ["self", "source", "enabled", "max_untrusted_records"],
                    "census": ["self", "revision_id", "page_ids"]}
