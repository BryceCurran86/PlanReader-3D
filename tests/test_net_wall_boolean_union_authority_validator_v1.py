"""Net-wall Boolean Union authority validator foundation v1.

DRAFT / TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / DO NOT MERGE.

The current legacy net-wall readiness path is scalar and deliberately fail-closed.
Future authoritative net wall geometry must subtract the geometric union of
wall-local physical void polygons, not a scalar sum of opening areas.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

import pytest

import pb_wall_net_area_quantity as legacy_net


MODULE_NAME = "pb_net_wall_boolean_union_authority"
HAS_BOOLEAN_UNION_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_BOOLEAN_UNION_AUTHORITY,
    strict=True,
    reason="net-wall Boolean-union authority is not implemented on the foundation base",
)


def _future_module():
    assert HAS_BOOLEAN_UNION_AUTHORITY, (
        "future production must add a separate net-wall Boolean-union authority; "
        "do not relabel legacy scalar readiness as geometric authority"
    )
    return importlib.import_module(MODULE_NAME)


def test_legacy_scalar_net_wall_path_remains_non_union_and_fail_closed() -> None:
    source = inspect.getsource(legacy_net.build_net_wall_area_quantity)
    assert "total_deduction += numeric" in source
    assert "unary_union" not in source
    assert "opening_universe_completeness_not_authenticated" in source
    assert not hasattr(legacy_net, "NetWallBooleanUnionAuthority")


@EXPECTED_RED
def test_future_public_resolver_is_selector_only_and_cannot_accept_raw_geometry() -> None:
    mod = _future_module()
    selector_cls = mod.NetWallBooleanUnionSelector
    authority_cls = mod.NetWallBooleanUnionAuthority
    producer_cls = mod.NetWallBooleanUnionProducer

    selector_fields = tuple(inspect.signature(selector_cls).parameters)
    assert selector_fields
    assert any("wall" in name for name in selector_fields)

    forbidden_selector_tokens = (
        "polygon",
        "coord",
        "voids",
        "void_areas",
        "opening_ids",
        "deduction",
        "complete",
        "count",
        "nearest",
        "radius",
        "confidence",
        "deductible",
        "net_area",
    )
    for field in selector_fields:
        lowered = field.lower()
        assert not any(token in lowered for token in forbidden_selector_tokens), field

    resolve_params = tuple(inspect.signature(authority_cls.resolve).parameters)
    assert resolve_params == ("self", "selector")

    factory = getattr(producer_cls, "from_authorities")
    factory_params = tuple(inspect.signature(factory).parameters)
    forbidden_factory_names = {
        "gross_polygon",
        "void_polygons",
        "void_areas",
        "opening_ids",
        "deductible",
        "claimed_complete",
        "candidate_wall_ids",
        "nearest_wall_id",
    }
    assert not forbidden_factory_names.intersection(factory_params)


@EXPECTED_RED
def test_geometry_helper_unions_overlaps_instead_of_scalar_summing() -> None:
    mod = _future_module()
    from shapely.geometry import box

    union = mod.union_wall_local_void_polygons
    left = box(0.0, 0.0, 2.0, 2.0)
    right = box(1.0, 0.0, 3.0, 2.0)

    merged = union((left, right))
    assert merged.area == pytest.approx(6.0)
    assert merged.area != pytest.approx(left.area + right.area)


@EXPECTED_RED
def test_geometry_helper_handles_duplicate_disjoint_and_same_size_distinct_voids() -> None:
    mod = _future_module()
    from shapely.geometry import box

    union = mod.union_wall_local_void_polygons
    first = box(0.0, 0.0, 2.0, 2.0)
    duplicate = box(0.0, 0.0, 2.0, 2.0)
    second_same_size = box(4.0, 0.0, 6.0, 2.0)

    assert union((first, duplicate)).area == pytest.approx(4.0)
    assert union((first, second_same_size)).area == pytest.approx(8.0)


@EXPECTED_RED
def test_wall_local_boolean_subtraction_is_translation_rotation_and_reversal_invariant() -> None:
    mod = _future_module()
    from shapely import affinity
    from shapely.geometry import box

    subtract = mod.subtract_void_union_from_wall_polygon
    gross = box(0.0, 0.0, 10.0, 3.0)
    voids = (
        box(2.0, 0.0, 4.0, 2.0),
        box(3.0, 1.0, 5.0, 3.0),
    )
    baseline = subtract(gross, voids)
    assert baseline.area == pytest.approx(23.0)

    moved_gross = affinity.translate(gross, xoff=100.0, yoff=-35.0)
    moved_voids = tuple(affinity.translate(v, xoff=100.0, yoff=-35.0) for v in voids)
    assert subtract(moved_gross, moved_voids).area == pytest.approx(baseline.area)

    rotated_gross = affinity.rotate(gross, 37.0, origin=(0.0, 0.0))
    rotated_voids = tuple(affinity.rotate(v, 37.0, origin=(0.0, 0.0)) for v in voids)
    assert subtract(rotated_gross, rotated_voids).area == pytest.approx(baseline.area)

    reversed_gross = affinity.scale(gross, xfact=-1.0, yfact=1.0, origin=(5.0, 0.0))
    reversed_voids = tuple(
        affinity.scale(v, xfact=-1.0, yfact=1.0, origin=(5.0, 0.0)) for v in voids
    )
    assert subtract(reversed_gross, reversed_voids).area == pytest.approx(baseline.area)


@EXPECTED_RED
def test_geometry_implementation_uses_shapely_unary_union_at_geometry_layer() -> None:
    mod = _future_module()
    union_source = inspect.getsource(mod.union_wall_local_void_polygons)
    subtract_source = inspect.getsource(mod.subtract_void_union_from_wall_polygon)

    assert "unary_union" in union_source
    assert ".difference(" in subtract_source
    assert "sum(" not in subtract_source