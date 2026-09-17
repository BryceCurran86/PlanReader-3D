"""Item 22 — live integration replay + benchmark-integrity audit.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

This validator is intentionally independent of Item 21 production.  It freezes
what must remain true when the live integration is finally activated.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

import pytest

import pb_benchmark_accuracy_engine as benchmark_engine
import pb_wall_net_area_quantity as legacy_net


MODULE_NAME = "pb_live_opening_net_wall_integration"
HAS_LIVE_INTEGRATION = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_LIVE_INTEGRATION,
    strict=True,
    reason="Item 21 live integration is not present on this independent baseline",
)

_FORBIDDEN_BENCHMARK_TOKENS = (
    "pb_benchmark_accuracy_engine",
    "expected_boq",
    "benchmark_results",
    "tolerance",
    "ground_truth",
    "holdout",
)


def test_current_main_legacy_net_path_is_still_fail_closed_not_union_authority() -> None:
    source = inspect.getsource(legacy_net.build_net_wall_area_quantity)
    assert "opening_universe_completeness_not_authenticated" in source
    assert "unary_union" not in source


def test_benchmark_scorer_still_exposes_quantity_none_guard_path() -> None:
    source = inspect.getsource(benchmark_engine)
    assert "quantity" in source
    assert "missed_in_extraction" in source.lower()


@EXPECTED_RED
def test_live_integration_is_benchmark_and_gold_isolated() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod).lower()
    for token in _FORBIDDEN_BENCHMARK_TOKENS:
        assert token.lower() not in source


@EXPECTED_RED
def test_live_selector_is_lineage_and_identity_only() -> None:
    mod = importlib.import_module(MODULE_NAME)
    params = set(inspect.signature(mod.LiveOpeningNetWallSelector).parameters)
    assert "physical_wall_identity_id" in params
    forbidden = {
        "expected",
        "gold",
        "tolerance",
        "net_area",
        "opening_area",
        "opening_count",
        "opening_set_complete",
        "bound_wall_id",
        "host_wall_id",
        "confidence",
    }
    assert not params.intersection(forbidden)


@EXPECTED_RED
def test_live_result_preserves_blocked_unknown_state() -> None:
    mod = importlib.import_module(MODULE_NAME)
    integrator = mod.LiveOpeningNetWallIntegrator.fail_closed_current_head()
    selector = mod.LiveOpeningNetWallSelector(
        document_id="doc-a",
        revision_id="rev-a",
        source_sha256="sha-a",
        snapshot_id="snap-a",
        decision_scope_id="scope-a",
        physical_wall_identity_id="wall-a",
    )
    result = integrator.resolve(selector)
    assert result.abstained
    assert result.net_wall_record_id is None


@EXPECTED_RED
def test_live_integration_does_not_import_legacy_provisional_routing() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod)
    forbidden = (
        "pb_opening_deduction_pipeline",
        "calculate_provisional_wall_deductions",
        "provisional_net_area_m2",
        "primary_res",
    )
    for token in forbidden:
        assert token not in source
