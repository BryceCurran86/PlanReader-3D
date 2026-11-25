"""Companion verification suite for the 2040 mm standard external-door height fallback.

Validates Work Order Item 16 against MAX's #4711 policy and live publication path:
- 2040 mm fallback applies ONLY when no height is stated on an authenticated
  standard external door (never 2100 mm, never internal/window/garage/joinery).
- Explicit schedule or elevation heights (including explicit 2040 mm) always
  override the assumption and are never marked as assumed/provisional.
- Conflicting, unverified, or exception-noted heights block fallback cleanly.
- Mixed-opening batches preserve exact per-opening isolation and determinism.
"""
from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from pb_external_door_height_estimate_policy import (
    OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM,
    OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS,
    OWNER_EXTERNAL_DOOR_ASSUMPTION_REASON,
    OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL,
    resolve_external_door_height_estimate,
)
from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_EXTERNAL_DOOR_HEIGHT_ESTIMATE_AREA_QUANTITY_AUTHORITY,
    _opening_quantity,
)
from pb_live_opening_external_door_height_estimate_publication import (
    apply_live_external_door_height_estimates,
)
from pb_live_whole_wall_role_composition import (
    LiveWholeWallRoleComposition,
    LiveWholeWallRoleTrace,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification
from tests.test_live_opening_area_quantity_publication import _composition, _opening


def _policy(**kwargs):
    params = dict(
        opening_id="ext-door-companion-1",
        external_door_authenticated=True,
        external_door_identity_evidence_id="auth-ext-door-kind-1",
    )
    params.update(kwargs)
    return resolve_external_door_height_estimate(**params)


def _wall_roles(*pairs: tuple[str, WallRoleClassification]) -> LiveWholeWallRoleComposition:
    traces = tuple(
        LiveWholeWallRoleTrace(
            physical_wall_id=wall_id,
            page_id="2",
            decision_scope_id="scope-companion",
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("live_whole_wall_role_composition_resolved",),
            record_id=f"role-{wall_id}",
            role=role,
        )
        for wall_id, role in pairs
    )
    return LiveWholeWallRoleComposition(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_whole_wall_role_composition_resolved",),
        traces=traces,
        whole_wall_role_authority=None,
        role_selectors=MappingProxyType({}),
    )


def _width_only_door(
    *,
    opening_id: str = "opening-1",
    host_wall_id: str = "wall-ext-1",
    width_mm: float = 920.0,
    kind: str = "door",
    **changes,
):
    base = replace(
        _opening(
            canonical_id=opening_id,
            kind=kind,
            area_m2=None,
            area_basis=None,
            figured_area_record_id="figured-1",
        ),
        host_wall_id=host_wall_id,
        figured_single_axis_mm=width_mm,
    )
    return replace(base, **changes) if changes else base


def test_2040_fallback_applies_only_when_height_absent_and_never_2100() -> None:
    res = _policy()
    assert OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM == 2040
    assert res.height_mm == 2040.0
    assert res.height_mm != 2100.0
    assert res.basis == OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert res.reason_code == OWNER_EXTERNAL_DOOR_ASSUMPTION_REASON
    assert "2040" in OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL
    assert "2100" not in OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL
    assert res.assumption_used is True
    assert res.source_authenticated_height is False
    assert res.verify_on_site is True
    assert res.can_issue_labelled_provisional_customer is True
    assert res.can_issue_firm_quantity is False
    assert res.can_seal_source_closed_customer is False
    assert res.benchmark_score_granted is False


@pytest.mark.parametrize("explicit_height", [2040, 2100, 2200, 2340, 2400])
def test_explicit_schedule_height_always_overrides_2040_fallback(explicit_height: int) -> None:
    res = _policy(
        schedule_height_mm=explicit_height,
        schedule_height_evidence_id="sched-row-1",
        schedule_owned_to_opening=True,
    )
    assert res.height_mm == float(explicit_height)
    assert res.basis == "authenticated_door_schedule"
    assert res.source_authenticated_height is True
    assert res.assumption_used is False
    assert res.verify_on_site is False
    assert res.can_issue_labelled_provisional_customer is False
    assert res.can_issue_firm_quantity is False


@pytest.mark.parametrize("explicit_height", [2040, 2100, 2300])
def test_explicit_elevation_height_always_overrides_2040_fallback(explicit_height: int) -> None:
    res = _policy(
        elevation_height_mm=explicit_height,
        elevation_height_evidence_id="elev-witness-1",
        elevation_owned_to_opening=True,
    )
    assert res.height_mm == float(explicit_height)
    assert res.basis == "authenticated_door_elevation"
    assert res.source_authenticated_height is True
    assert res.assumption_used is False
    assert res.verify_on_site is False
    assert res.can_issue_labelled_provisional_customer is False


@pytest.mark.parametrize("sched_h,elev_h", [(2040, 2100), (2100, 2040), (2200, 2340)])
def test_conflicting_explicit_heights_block_2040_fallback(sched_h: int, elev_h: int) -> None:
    res = _policy(
        schedule_height_mm=sched_h,
        schedule_height_evidence_id="sched-1",
        schedule_owned_to_opening=True,
        elevation_height_mm=elev_h,
        elevation_height_evidence_id="elev-1",
        elevation_owned_to_opening=True,
    )
    assert res.height_mm is None
    assert res.reason_code == "schedule_elevation_height_conflict"
    assert res.assumption_used is False
    assert res.can_issue_labelled_provisional_customer is False


def test_agreeing_schedule_and_elevation_2040_is_authenticated_not_assumed() -> None:
    res = _policy(
        schedule_height_mm=2040,
        schedule_height_evidence_id="sched-2040",
        schedule_owned_to_opening=True,
        elevation_height_mm=2040,
        elevation_height_evidence_id="elev-2040",
        elevation_owned_to_opening=True,
    )
    assert res.height_mm == 2040.0
    assert res.source_authenticated_height is True
    assert res.assumption_used is False
    assert res.source_evidence_ids == ("sched-2040", "elev-2040")


@pytest.mark.parametrize(
    "exception_text",
    [
        "As per manufacturer",
        "Refer to the supplier",
        "To suit manufacturer frame",
        "Full-height external door",
        "FULL HEIGHT glazed leaf",
    ],
)
def test_live_width_only_door_with_height_exception_blocks_2040_fallback(
    exception_text: str,
) -> None:
    opening = _width_only_door(
        schedule_binding_record_id="sched-bind-1",
        schedule_row_description=exception_text,
    )
    comp = apply_live_external_door_height_estimates(
        composition=_composition(opening),
        whole_wall_role_composition=_wall_roles(("wall-ext-1", WallRoleClassification.EXTERNAL)),
    )
    assert comp.canonical_openings[0].area_m2 is None
    assert comp.canonical_openings[0].area_basis is None
    assert _opening_quantity(comp.canonical_openings[0]) is None


@pytest.mark.parametrize(
    "non_standard_desc",
    [
        "Garage sectional door",
        "Overhead roller shutter",
        "Panel lift door",
        "Custom joinery unit",
    ],
)
def test_live_non_standard_external_openings_never_get_2040_fallback(
    non_standard_desc: str,
) -> None:
    opening = _width_only_door(schedule_row_description=non_standard_desc)
    comp = apply_live_external_door_height_estimates(
        composition=_composition(opening),
        whole_wall_role_composition=_wall_roles(("wall-ext-1", WallRoleClassification.EXTERNAL)),
    )
    assert comp.canonical_openings[0].area_m2 is None
    assert _opening_quantity(comp.canonical_openings[0]) is None


def test_live_explicit_schedule_height_prevents_2040_fallback_stamp() -> None:
    opening = _width_only_door(
        schedule_binding_record_id="sched-bind-2200",
        schedule_declared_height_mm=2200.0,
    )
    comp = apply_live_external_door_height_estimates(
        composition=_composition(opening),
        whole_wall_role_composition=_wall_roles(("wall-ext-1", WallRoleClassification.EXTERNAL)),
    )
    out = comp.canonical_openings[0]
    assert out.area_m2 is None
    assert out.area_basis is None


def test_live_mixed_batch_isolates_2040_provisional_only_to_qualifying_door() -> None:
    qualifying = _width_only_door(opening_id="door-qual", host_wall_id="wall-ext-1", width_mm=820.0)
    explicit_h = _width_only_door(
        opening_id="door-explicit",
        host_wall_id="wall-ext-1",
        width_mm=920.0,
        schedule_binding_record_id="sched-1",
        schedule_declared_height_mm=2340.0,
    )
    internal = _width_only_door(opening_id="door-int", host_wall_id="wall-int-1", width_mm=820.0)
    window = _width_only_door(
        opening_id="win-ext", host_wall_id="wall-ext-1", width_mm=1200.0, kind="window",
    )
    already_figured = _opening(kind="door")

    roles = _wall_roles(
        ("wall-ext-1", WallRoleClassification.EXTERNAL),
        ("wall-int-1", WallRoleClassification.INTERNAL),
    )
    comp_in = _composition(qualifying, explicit_h, internal, window, already_figured)
    first = apply_live_external_door_height_estimates(
        composition=comp_in, whole_wall_role_composition=roles,
    )
    second = apply_live_external_door_height_estimates(
        composition=comp_in, whole_wall_role_composition=roles,
    )
    assert first == second

    by_id = {o.canonical_opening_id: o for o in first.canonical_openings}
    q_open = by_id["door-qual"]
    assert q_open.area_basis == OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert q_open.area_m2 == pytest.approx(820.0 * 2040.0 / 1_000_000.0)
    qty = _opening_quantity(q_open)
    assert qty is not None
    assert qty.authority == LIVE_OPENING_EXTERNAL_DOOR_HEIGHT_ESTIMATE_AREA_QUANTITY_AUTHORITY
    assert qty.metadata["assumed_height_mm"] == 2040
    assert qty.metadata["inclusion_status"] == "PROVISIONAL"
    assert qty.metadata["can_issue_firm_quantity"] is False
    assert qty.metadata["benchmark_score_granted"] is False

    assert by_id["door-explicit"].area_m2 is None
    assert by_id["door-int"].area_m2 is None
    assert by_id["win-ext"].area_m2 is None
    assert by_id[already_figured.canonical_opening_id] == already_figured
