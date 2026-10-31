"""Structural guards: the correspondence is unreachable from production, free of benchmark inputs, and grants nothing."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow

REPO = Path(__file__).resolve().parent.parent
MODULE = "pb_callout_strip_whole_aperture_correspondence_shadow"
SOURCE = REPO / f"{MODULE}.py"

# the live issuer, binders, count producer, host resolver, quantity publication, the wall adapter and the nominator
FORBIDDEN_IMPORT_PREFIXES = (
    "pb_schedule_opening_instance_binding_authority", "pb_opening_host_binding_authority",
    "pb_live_opening_area_quantity_publication", "pb_generic_opening_count_authority",
    "pb_wall_room_topology_canonical_adapter", "pb_live_", "pb_semantic_opening_enumeration_authority",
    "pb_opening_universe_completeness", "pb_physical_wall_", "pb_source_plan_glazing_strip_callout_shadow",
    "pb_strip_structural_assessment_shadow", "pb_plan_tag_opening_occupancy_shadow",
)


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_nothing_in_production_imports_the_correspondence():
    importers = []
    for root in ("", "tools", "scripts"):
        for path in sorted((REPO / root).glob("*.py")):
            if path == SOURCE:
                continue
            if re.search(rf"^\s*(?:from|import)\s+{MODULE}\b", path.read_text(encoding="utf-8", errors="replace"), re.M):
                importers.append(path.relative_to(REPO).as_posix())
    assert importers == []


def test_the_correspondence_imports_no_issuer_binder_count_host_wall_or_nominator_module():
    bad = [m for m in _imports(SOURCE) if m.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    assert bad == []


def test_the_only_authority_modules_it_reaches_are_the_aperture_authority_and_the_source_producers():
    reached = {m for m in _imports(SOURCE) if m.startswith("pb_")}
    assert reached == {
        "pb_migration_contracts", "pb_structural_whole_opening_aperture_authority", "pb_source_observation_authority",
        "pb_source_visibility_authority", "pb_vector_geometry_v130"}


def test_importing_the_correspondence_loads_no_consumer_module():
    code = ("import sys; sys.path[:0] = [%r]; import %s; "
            "bad = sorted(m for m in sys.modules if m.startswith(('pb_live_', 'pb_schedule_opening', 'pb_opening_host_binding',"
            " 'pb_generic_opening_count', 'pb_wall_room_topology_canonical_adapter',"
            " 'pb_source_plan_glazing_strip_callout_shadow'))); "
            "print(bad); sys.exit(1 if bad else 0)") % (str(REPO), MODULE)
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_correspondence_carries_no_benchmark_project_or_drawing_constants():
    text = SOURCE.read_text(encoding="utf-8")
    for needle in ("frozen_holdout", "reference_takeoff", "benchmarks", "Maryborough", "documents/sources", "expected_"):
        assert needle not in text, needle
    assert not re.search(r"\b[0-9a-f]{64}\b", text)                      # no source SHA
    assert not re.search(r"""["'][WD]0?\d{1,2}["']""", text)             # no tag literal
    assert ".pdf" not in text


def test_it_never_edits_the_authorities_it_reads():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in {"setattr", "delattr", "exec", "eval"}:
            raise AssertionError(f"{node.func.id} is not allowed in a read-only shadow")
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    # only the shadow's own instance state may be assigned; never an imported module or an authority
                    assert target.value.id == "self" or (
                        target.value.id not in imported and target.value.id not in {"authority", "producer"}
                    ), ast.dump(target)


def test_no_grant_flag_is_ever_true_by_default_and_the_set_is_complete():
    receipt_fields = {f.name: f for f in fields(shadow.WholeApertureCorrespondenceShadow)}
    assert set(shadow._GRANT_FLAGS) <= set(receipt_fields)
    assert all(receipt_fields[name].default is False for name in shadow._GRANT_FLAGS)
    assert receipt_fields["shadow_only"].default is True
    forbidden_names = {"mm_per_pt", "scale", "area", "width_mm", "quantity", "count"}
    assert not any(name in forbidden_names for name in receipt_fields)


def test_the_correspondence_publishes_no_absolute_scale_or_size_anywhere():
    text = SOURCE.read_text(encoding="utf-8")
    assert "mm_per_pt" not in text and "page.rect" not in text and "get_pixmap" not in text
    assert "scale_granted=True" not in text


def test_the_standing_limits_are_typed_strings_and_name_what_is_not_established():
    limits = shadow.STANDING_LIMITS
    assert len(set(limits)) == len(limits) and all(type(x) is str and x for x in limits)
    joined = " ".join(limits)
    for topic in ("identity", "link", "whole_versus_nested", "jamb_threshold", "kind_host"):
        assert topic in joined, topic
