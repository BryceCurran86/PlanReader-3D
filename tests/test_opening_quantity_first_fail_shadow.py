"""Shadow proofs for opening-area first-fail classification. No live wiring."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

from pb_opening_label_dimension_authority import parse_opening_label_dimensions
from pb_opening_quantity_first_fail_shadow import (
    classify_opening_quantity_first_fail,
    classify_opening_quantity_first_fail_from_producer,
)


def _classify(**kwargs):
    return classify_opening_quantity_first_fail(**kwargs)


def _laundry_kwargs():
    parsed = parse_opening_label_dimensions("870 CS")
    assert parsed is not None
    assert parsed.dimension_values_mm == (870.0,)
    assert parsed.area_m2 is None
    return dict(
        host_wall_id_present=True,
        host_binding_present=True,
        host_frame_present=True,
        area_m2=None,
        label_status="corroborated",
        label_dimension_values_mm=parsed.dimension_values_mm,
        label_area_m2=parsed.area_m2,
        exact_frozen_location_join=True,
        quantity_family="opening_area",
    )


def test_single_870_cs_owns_one_axis_and_no_area() -> None:
    parsed = parse_opening_label_dimensions("870 CS")
    assert parsed is not None
    assert parsed.dimension_values_mm == (870.0,)
    assert parsed.area_m2 is None


def test_hosted_laundry_single_870_fails_at_second_axis() -> None:
    result = _classify(**_laundry_kwargs())
    assert result["first_failing_authority"] == "figured_label_second_axis_unavailable"
    assert result["unique_host_identity_present"] is True
    assert result["would_publish_live_opening_area"] is False
    assert result["invented_second_axis_mm"] is None
    assert result["diagnostic_only"] is True


def test_hosted_bedroom_870_without_frame_still_fails_at_second_axis() -> None:
    kwargs = _laundry_kwargs()
    kwargs["host_frame_present"] = False
    result = _classify(**kwargs)
    assert result["first_failing_authority"] == "figured_label_second_axis_unavailable"
    assert result["unique_host_identity_present"] is True
    assert result["invented_second_axis_mm"] is None


def test_missing_host_fails_before_the_single_870_label() -> None:
    result = _classify(
        host_wall_id_present=False,
        host_binding_present=False,
        host_frame_present=False,
        area_m2=None,
        label_status="corroborated",
        label_dimension_values_mm=(870.0,),
        label_area_m2=None,
    )
    assert result["first_failing_authority"] == "unique_host_identity_unavailable"
    assert result["unique_host_identity_present"] is False


def test_hosted_opening_without_label_text_fails_at_text_unavailable() -> None:
    result = _classify(
        host_wall_id_present=True,
        host_binding_present=True,
        host_frame_present=True,
        area_m2=None,
        label_status="abstained",
        label_dimension_values_mm=None,
        label_area_m2=None,
    )
    assert result["first_failing_authority"] == "opening_label_dimension_text_unavailable"
    assert result["unique_host_identity_present"] is True


def test_hosted_opening_with_conflicting_label_fails_ambiguous() -> None:
    result = _classify(
        host_wall_id_present=True,
        host_binding_present=True,
        host_frame_present=False,
        area_m2=None,
        label_status="conflict",
        label_dimension_values_mm=None,
        label_area_m2=None,
    )
    assert result["first_failing_authority"] == "opening_label_dimension_ambiguous"


def test_two_axis_figured_label_with_host_is_already_published() -> None:
    parsed = parse_opening_label_dimensions("2,100 - 4,800 Panel Lift Door")
    assert parsed is not None
    assert parsed.dimension_values_mm == (2100.0, 4800.0)
    assert parsed.area_m2 == 10.08
    result = _classify(
        host_wall_id_present=True,
        host_binding_present=True,
        host_frame_present=False,
        area_m2=parsed.area_m2,
        label_status="corroborated",
        label_dimension_values_mm=parsed.dimension_values_mm,
        label_area_m2=parsed.area_m2,
    )
    assert result["first_failing_authority"] == "none_area_already_published"
    assert result["would_publish_live_opening_area"] is True


def test_unequal_frozen_box_is_not_joined_by_nearest() -> None:
    result = _classify(
        host_wall_id_present=True,
        host_binding_present=True,
        host_frame_present=True,
        area_m2=None,
        label_status="corroborated",
        label_dimension_values_mm=(870.0,),
        label_area_m2=None,
        exact_frozen_location_join=False,
    )
    assert result["first_failing_authority"] == "exact_source_location_join_unavailable"
    assert result["invented_second_axis_mm"] is None


def test_denominator_without_frozen_box_fails_closed() -> None:
    result = _classify(
        host_wall_id_present=False,
        host_binding_present=False,
        host_frame_present=False,
        area_m2=None,
        label_status="",
        label_dimension_values_mm=None,
        label_area_m2=None,
        exact_frozen_location_join=None,
    )
    assert result["first_failing_authority"] == "frozen_source_location_unavailable"


def test_ceiling_family_cannot_publish_opening_area() -> None:
    result = _classify(
        host_wall_id_present=False,
        host_binding_present=False,
        host_frame_present=False,
        area_m2=None,
        label_status="",
        label_dimension_values_mm=None,
        label_area_m2=None,
        quantity_family="ceiling_area",
    )
    assert result["first_failing_authority"] == "family_not_opening_area_quantity"
    assert result["would_publish_live_opening_area"] is False


def test_producer_adapter_reads_canonical_and_label_maps() -> None:
    result = classify_opening_quantity_first_fail_from_producer(
        {
            "host_wall_id": "wall-a",
            "host_binding_record_id": "host-a",
            "host_frame_record_id": "frame-a",
            "area_m2": None,
        },
        {
            "status": "corroborated",
            "evidence": {
                "dimension_values_mm": [870.0],
                "area_m2": None,
            },
        },
    )
    assert result["first_failing_authority"] == "figured_label_second_axis_unavailable"


def test_typical_door_height_is_never_invented() -> None:
    result = _classify(**_laundry_kwargs())
    assert result["invented_second_axis_mm"] is None
    assert 2100.0 not in (_laundry_kwargs()["label_dimension_values_mm"] or ())


def test_classification_does_not_mutate_caller_dimensions() -> None:
    dims = [870.0]
    before = deepcopy(dims)
    _classify(
        host_wall_id_present=True,
        host_binding_present=True,
        host_frame_present=True,
        area_m2=None,
        label_status="corroborated",
        label_dimension_values_mm=dims,
        label_area_m2=None,
    )
    assert dims == before


def test_replay_is_deterministic() -> None:
    kwargs = _laundry_kwargs()
    assert _classify(**kwargs) == _classify(**kwargs)


class TestNoQuantityOrLiveWiring:
    def test_no_production_module_imports_first_fail_shadow(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skip = {"tests", "benchmarks", "scripts", "tools", "node_modules"}
        offenders = []
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root)
            if rel.parts[0] in skip or any(part.startswith(".") for part in rel.parts):
                continue
            if path.name.startswith("tmp_"):
                continue
            if path.name == "pb_opening_quantity_first_fail_shadow.py":
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
                name == "pb_opening_quantity_first_fail_shadow"
                or name.startswith("pb_opening_quantity_first_fail_shadow.")
                for name in imported
            ):
                offenders.append(path.name)
        assert offenders == []

    def test_shadow_does_not_construct_quantity_evidence(self) -> None:
        import pb_opening_quantity_first_fail_shadow as mod

        source = open(mod.__file__, encoding="utf-8").read()
        assert "import QuantityEvidence" not in source
        assert "QuantityEvidence(" not in source
        assert not hasattr(mod, "QuantityEvidence")

    def test_not_imported_by_live_extractor(self) -> None:
        source = open("pb_planreader_pdf_extractor.py", encoding="utf-8").read()
        assert "pb_opening_quantity_first_fail_shadow" not in source
        assert "pb_annotation_cycle_shadow" not in source
        assert "pb_source_join_readiness_shadow" not in source
