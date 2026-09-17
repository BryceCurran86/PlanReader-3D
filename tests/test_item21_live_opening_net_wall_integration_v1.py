"""Production regressions for the Item 21 live integration boundary."""
from __future__ import annotations

import inspect

import pytest

import pb_live_opening_net_wall_integration as live
from pb_migration_contracts import EvidenceResolutionStatus


def _selector() -> live.LiveOpeningNetWallSelector:
    return live.LiveOpeningNetWallSelector(
        document_id="doc-a",
        revision_id="rev-a",
        source_sha256="sha-a",
        snapshot_id="snap-a",
        decision_scope_id="scope-a",
        physical_wall_identity_id="physical-wall-a",
    )


def test_integrator_is_producer_owned_and_selector_only() -> None:
    with pytest.raises(ValueError):
        live.LiveOpeningNetWallIntegrator()
    assert tuple(inspect.signature(live.LiveOpeningNetWallIntegrator.resolve).parameters) == (
        "self",
        "selector",
    )


def test_selector_cannot_carry_raw_geometry_or_quantity_truth() -> None:
    params = set(inspect.signature(live.LiveOpeningNetWallSelector).parameters)
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
    assert not params.intersection(forbidden)


def test_current_head_resolves_unknown_net_as_abstained_not_zero() -> None:
    integrator = live.LiveOpeningNetWallIntegrator.fail_closed_current_head()
    result = integrator.resolve(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.abstained
    assert result.net_wall_record_id is None
    assert result.physical_wall_identity_id == "physical-wall-a"


def test_upstream_factory_fails_closed_until_exact_authorities_exist() -> None:
    with pytest.raises((RuntimeError, TypeError)):
        live.LiveOpeningNetWallIntegrator.from_authorities()


def test_source_has_no_known_legacy_shortcut_tokens() -> None:
    source = inspect.getsource(live)
    forbidden = (
        "calculate_provisional_wall_deductions",
        "provisional_net_area_m2",
        "primary_res",
        "nearest_wall",
        "first_wall",
        "default_height",
        "default_sill",
        "default_head",
    )
    for token in forbidden:
        assert token not in source
