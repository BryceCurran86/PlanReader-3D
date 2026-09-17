"""Item 18 — Net-wall frozen replay preflight.

TEST-ONLY / REPLAY-PREPARATION / DO NOT MERGE.

This does not pretend Item 18 is complete before Item 17 production exists.
It pins the exact replay prerequisites while preserving the legacy scalar path
as non-authoritative.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

import pytest

import pb_wall_net_area_quantity as legacy_net


FOUNDATION_PR = 397
FOUNDATION_HEAD = "2a12103800f067fd707da241dfb26f57545339c1"
MODULE_NAME = "pb_net_wall_boolean_union_authority"
HAS_BOOLEAN_UNION_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_BOOLEAN_UNION_AUTHORITY,
    strict=True,
    reason="Item 17 net-wall Boolean-union production does not exist yet",
)


def test_item18_is_pinned_to_the_existing_boolean_union_validator_foundation() -> None:
    assert FOUNDATION_PR == 397
    assert FOUNDATION_HEAD == "2a12103800f067fd707da241dfb26f57545339c1"


def test_legacy_scalar_path_is_still_not_the_item17_authority() -> None:
    source = inspect.getsource(legacy_net.build_net_wall_area_quantity)
    assert "total_deduction += numeric" in source
    assert "unary_union" not in source
    assert "opening_universe_completeness_not_authenticated" in source
    assert not hasattr(legacy_net, "NetWallBooleanUnionAuthority")


@EXPECTED_RED
def test_item18_replay_target_must_expose_the_separate_boolean_union_authority() -> None:
    mod = importlib.import_module(MODULE_NAME)
    assert hasattr(mod, "NetWallBooleanUnionAuthority")
    assert hasattr(mod, "NetWallBooleanUnionProducer")
    assert hasattr(mod, "NetWallBooleanUnionSelector")


@EXPECTED_RED
def test_item18_replay_target_must_use_geometric_union_not_scalar_sum() -> None:
    mod = importlib.import_module(MODULE_NAME)
    union_source = inspect.getsource(mod.union_wall_local_void_polygons)
    subtract_source = inspect.getsource(mod.subtract_void_union_from_wall_polygon)
    assert "unary_union" in union_source
    assert ".difference(" in subtract_source
    assert "sum(" not in subtract_source


@EXPECTED_RED
def test_item18_replay_cannot_be_called_green_until_selector_only_authority_exists() -> None:
    mod = importlib.import_module(MODULE_NAME)
    assert tuple(inspect.signature(mod.NetWallBooleanUnionAuthority.resolve).parameters) == (
        "self",
        "selector",
    )
