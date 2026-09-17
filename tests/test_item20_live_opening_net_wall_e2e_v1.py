"""Item 20 — live opening -> net-wall end-to-end validator foundation.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

This freezes the integration boundary before Items 11-19 are all available.
The live path must consume sealed upstream authorities in sequence; it must not
reconstruct host binding, voids, deductions, net area, or wall identity from
legacy caller metadata or provisional arithmetic.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

import pytest

import pb_wall_net_area_quantity as legacy_net


MODULE_NAME = "pb_live_opening_net_wall_integration"
HAS_LIVE_INTEGRATION = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_LIVE_INTEGRATION,
    strict=True,
    reason="Item 20 live authority integration is intentionally not implemented yet",
)


_REQUIRED_AUTHORITY_MODULES = (
    "pb_physical_opening_void_authority",
    "pb_opening_deduction_authority",
    "pb_net_wall_boolean_union_authority",
    "pb_exact_wall_quantity_propagation",
)

_FORBIDDEN_LEGACY_SHORTCUTS = (
    "calculate_provisional_wall_deductions",
    "provisional_net_area_m2",
    "primary_res",
    "nearest_wall",
    "first_wall",
    "default_height",
    "default_sill",
    "default_head",
)


def test_current_main_still_fails_closed_before_live_boolean_union_integration() -> None:
    source = inspect.getsource(legacy_net.build_net_wall_area_quantity)
    assert "opening_universe_completeness_not_authenticated" in source
    assert "unary_union" not in source


@EXPECTED_RED
def test_future_live_integration_exports_one_sealed_orchestrator_boundary() -> None:
    mod = importlib.import_module(MODULE_NAME)
    required = {
        "LiveOpeningNetWallIntegrator",
        "LiveOpeningNetWallSelector",
        "LiveOpeningNetWallResult",
    }
    assert required <= set(dir(mod))
    assert tuple(inspect.signature(mod.LiveOpeningNetWallIntegrator.resolve).parameters) == (
        "self",
        "selector",
    )


@EXPECTED_RED
def test_future_live_integration_consumes_every_authority_layer_not_legacy_arithmetic() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod)
    lowered = source.lower()
    for module_name in _REQUIRED_AUTHORITY_MODULES:
        assert module_name in source
    for shortcut in _FORBIDDEN_LEGACY_SHORTCUTS:
        assert shortcut.lower() not in lowered


@EXPECTED_RED
def test_future_live_selector_cannot_carry_raw_opening_or_net_wall_truth() -> None:
    mod = importlib.import_module(MODULE_NAME)
    params = tuple(inspect.signature(mod.LiveOpeningNetWallSelector).parameters)
    forbidden = {
        "opening_area",
        "opening_areas",
        "width",
        "height",
        "sill",
        "head",
        "host_wall_id",
        "bound_wall_id",
        "net_area",
        "deduction_area",
        "opening_set_complete",
        "claimed_complete",
        "nearest",
        "first",
        "confidence",
    }
    assert not (set(params) & forbidden)


@EXPECTED_RED
def test_future_live_integration_keeps_blocked_net_unknown_not_zero() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod.LiveOpeningNetWallResult).lower()
    assert "net" in source
    assert "optional" in source or "none" in source or "abstain" in source


@EXPECTED_RED
def test_future_live_integration_preserves_exact_wall_identity_into_propagation() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod).lower()
    assert "physical_wall" in source
    assert "pb_exact_wall_quantity_propagation" in source
    assert "primary_res" not in source
