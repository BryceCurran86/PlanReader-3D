"""Shadow proofs for exact-project join readiness. No live wiring."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

from pb_source_join_readiness_shadow import classify_produced_item_join_readiness


def _classify(**kwargs):
    return classify_produced_item_join_readiness(**kwargs)


def test_empty_identity_map_cannot_match_a_scored_family() -> None:
    result = _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:a",),
        denominator_families=("opening_area",),
        identity_bindings=(),
    )
    assert result["join_status"] == "empty_identity_map_pins_zero_matches"
    assert result["would_increment_matched_within_tolerance"] is False
    assert result["would_increment_unsupported_extra"] is True
    assert result["diagnostic_only"] is True
    assert result["quantity_or_metric_area_published"] is False


def test_floor_extra_cannot_match_a_door_denominator() -> None:
    result = _classify(
        produced_family="floor_area",
        produced_object_refs=("floor:a",),
        denominator_families=("door", "window"),
        identity_bindings=({
            "production_family": "door",
            "production_object_identity_refs": ("door:a",),
        },),
    )
    assert result["join_status"] == "family_mismatch_increments_extras_not_matches"
    assert result["would_increment_matched_within_tolerance"] is False
    assert result["would_increment_unsupported_extra"] is True


def test_reviewed_binding_leaves_the_match_to_the_evaluator() -> None:
    result = _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:a",),
        denominator_families=("opening_area",),
        identity_bindings=({
            "production_family": "opening_area",
            "production_object_identity_refs": ("opening:a",),
        },),
    )
    assert result["join_status"] == "reviewed_binding_present_evaluator_owns_match"
    assert result["would_increment_matched_within_tolerance"] is True
    assert result["would_increment_unsupported_extra"] is False


def test_scored_family_without_its_own_binding_stays_an_extra() -> None:
    result = _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:b",),
        denominator_families=("opening_area",),
        identity_bindings=({
            "production_family": "opening_area",
            "production_object_identity_refs": ("opening:a",),
        },),
    )
    assert result["join_status"] == "unmapped_extra_awaits_reviewed_binding"
    assert result["would_increment_matched_within_tolerance"] is False


def test_two_bindings_do_not_resolve_a_tie_by_first_or_smallest() -> None:
    first = _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:a", "opening:b"),
        denominator_families=("opening_area",),
        identity_bindings=(
            {"production_family": "opening_area", "production_object_identity_refs": ("opening:a",)},
            {"production_family": "opening_area", "production_object_identity_refs": ("opening:b",)},
        ),
    )
    reversed_bindings = _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:b", "opening:a"),
        denominator_families=("opening_area",),
        identity_bindings=(
            {"production_family": "opening_area", "production_object_identity_refs": ("opening:b",)},
            {"production_family": "opening_area", "production_object_identity_refs": ("opening:a",)},
        ),
    )
    assert first["join_status"] == reversed_bindings["join_status"]
    assert first["would_increment_matched_within_tolerance"] is True


def test_unusable_inputs_fail_closed() -> None:
    assert _classify(
        produced_family="",
        produced_object_refs=("opening:a",),
        denominator_families=("opening_area",),
        identity_bindings=(),
    )["join_status"] == "inputs_unusable"
    assert _classify(
        produced_family="opening_area",
        produced_object_refs=(),
        denominator_families=("opening_area",),
        identity_bindings=(),
    )["join_status"] == "inputs_unusable"
    assert _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:a",),
        denominator_families=(),
        identity_bindings=(),
    )["join_status"] == "inputs_unusable"


def test_malformed_binding_does_not_count_as_a_reviewed_map() -> None:
    result = _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:a",),
        denominator_families=("opening_area",),
        identity_bindings=("not-a-map", {"production_family": "opening_area"}),
    )
    assert result["join_status"] == "empty_identity_map_pins_zero_matches"


def test_classification_does_not_mutate_caller_bindings() -> None:
    bindings = [{
        "production_family": "opening_area",
        "production_object_identity_refs": ["opening:a"],
    }]
    before = deepcopy(bindings)
    _classify(
        produced_family="opening_area",
        produced_object_refs=("opening:a",),
        denominator_families=("opening_area",),
        identity_bindings=bindings,
    )
    assert bindings == before


def test_replay_is_deterministic() -> None:
    kwargs = dict(
        produced_family="floor_area",
        produced_object_refs=("floor:a",),
        denominator_families=("door",),
        identity_bindings=(),
    )
    assert _classify(**kwargs) == _classify(**kwargs)


class TestNoQuantityOrLiveWiring:
    def test_no_production_module_imports_join_readiness_shadow(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skip = {"tests", "benchmarks", "scripts", "tools", "node_modules"}
        offenders = []
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root)
            if rel.parts[0] in skip or any(part.startswith(".") for part in rel.parts):
                continue
            if path.name.startswith("tmp_"):
                continue
            if path.name == "pb_source_join_readiness_shadow.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    imported.append(node.value)
            if any(
                name == "pb_source_join_readiness_shadow"
                or name.startswith("pb_source_join_readiness_shadow.")
                for name in imported
            ):
                offenders.append(path.name)
        assert offenders == []

    def test_shadow_does_not_construct_quantity_evidence(self) -> None:
        import pb_source_join_readiness_shadow as mod

        source = open(mod.__file__, encoding="utf-8").read()
        assert "import QuantityEvidence" not in source
        assert "QuantityEvidence(" not in source
        assert not hasattr(mod, "QuantityEvidence")

    def test_not_imported_by_live_extractor(self) -> None:
        source = open("pb_planreader_pdf_extractor.py", encoding="utf-8").read()
        assert "pb_source_join_readiness_shadow" not in source
        assert "pb_annotation_cycle_shadow" not in source
        assert "pb_opening_quantity_first_fail_shadow" not in source
