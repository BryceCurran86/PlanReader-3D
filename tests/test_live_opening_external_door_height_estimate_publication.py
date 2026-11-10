"""Owner 2100 mm external-door estimate becomes a labelled provisional customer quantity."""
from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType, SimpleNamespace

import pytest

from pb_external_door_height_estimate_policy import (
    OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM,
    OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS,
    OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL,
)
from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_EXTERNAL_DOOR_HEIGHT_ESTIMATE_AREA_QUANTITY_AUTHORITY,
    _opening_quantity,
    publish_live_opening_area_quantities,
)
from pb_live_opening_customer_projection import (
    _eligible_area_quantities,
    project_live_opening_customer_rows,
)
from pb_live_opening_external_door_height_estimate_publication import (
    apply_live_external_door_height_estimates,
)
from pb_live_physical_opening_void_composition import _figured_single_axis_mm
from pb_live_opening_source_closed_export import seal_live_opening_area_run
from pb_live_whole_wall_role_composition import (
    LiveWholeWallRoleComposition,
    LiveWholeWallRoleTrace,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification
from tests.test_live_floor_finish_area_source_closed_export import _claim
from tests.test_live_opening_area_quantity_publication import _composition, _opening


def _roles(*wall_ids: str, role=WallRoleClassification.EXTERNAL):
    traces = tuple(
        LiveWholeWallRoleTrace(
            physical_wall_id=wall_id,
            page_id="3",
            decision_scope_id="scope-1",
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("live_whole_wall_role_composition_resolved",),
            record_id=f"role-{wall_id}",
            role=role,
        )
        for wall_id in wall_ids
    )
    return LiveWholeWallRoleComposition(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_whole_wall_role_composition_resolved",),
        traces=traces,
        whole_wall_role_authority=None,
        role_selectors=MappingProxyType({}),
    )


def _bare_external_door(**changes) -> object:
    opening = replace(
        _opening(
            kind="door",
            area_m2=None,
            area_basis=None,
            figured_area_record_id="figured-1",
        ),
        figured_single_axis_mm=870.0,
    )
    return replace(opening, **changes) if changes else opening


def test_authenticated_external_door_with_one_printed_width_gets_labelled_customer_area():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door()),
        whole_wall_role_composition=_roles("wall-1"),
    )
    opening = composition.canonical_openings[0]
    assert opening.area_basis == OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert opening.area_m2 == pytest.approx(870.0 * 2100.0 / 1_000_000.0)
    assert opening.width_m is None
    assert opening.height_m is None
    assert opening.external_wall_role_record_id == "role-wall-1"
    assert "role-wall-1" in opening.evidence_ids

    quantity = _opening_quantity(opening)
    assert quantity is not None
    assert quantity.status == "corroborated"
    assert quantity.abstained is False
    assert quantity.value == pytest.approx(1.827)
    assert quantity.authority == (
        LIVE_OPENING_EXTERNAL_DOOR_HEIGHT_ESTIMATE_AREA_QUANTITY_AUTHORITY
    )
    assert quantity.metadata["commercial_projection_allowed"] is True
    assert quantity.metadata["owner_external_door_height_assumption"] is True
    assert quantity.metadata["can_issue_firm_quantity"] is False
    assert quantity.metadata["benchmark_score_granted"] is False
    assert quantity.metadata["inclusion_status"] == "PROVISIONAL"
    assert OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL in quantity.metadata["element"]
    assert OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL in quantity.metadata["location"]
    assert quantity.metadata["assumed_height_mm"] == OWNER_EXTERNAL_DOOR_ASSUMED_HEIGHT_MM
    assert "firm" not in quantity.status

    claim = replace(
        _claim(),
        canonical_openings=(opening,),
        opening_quantity_evidence=(quantity,),
    )
    assert _eligible_area_quantities(claim) == (quantity,)

    sealed = seal_live_opening_area_run(
        composition, workspace_id=7, project_id="source-project",
    )
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].lineage_ok is True

    rows = project_live_opening_customer_rows(
        claim, workspace_id=7, project_id="source-project",
    )
    assert len(rows) == 1
    assert rows[0]["quantity"] == pytest.approx(1.827)
    assert OWNER_EXTERNAL_DOOR_HEIGHT_ESTIMATE_LABEL in rows[0]["element"]
    assert rows[0]["inclusion_status"] == "PROVISIONAL"
    assert rows[0]["quantity_status"] == "To review"


def test_internal_host_cannot_receive_the_2100_assumption():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door()),
        whole_wall_role_composition=_roles(
            "wall-1", role=WallRoleClassification.INTERNAL,
        ),
    )
    opening = composition.canonical_openings[0]
    assert opening.area_m2 is None
    assert _opening_quantity(opening) is None


def test_window_cannot_receive_the_2100_assumption():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door(opening_kind="window")),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_garage_panel_description_cannot_receive_the_2100_assumption():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(
            _bare_external_door(schedule_row_description="Garage roller door")
        ),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_unauthenticated_host_cannot_receive_the_2100_assumption():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door(host_wall_id="other-wall")),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_framed_whole_wall_identity_authenticates_external_role_when_host_id_is_opening_scoped():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(
            _bare_external_door(
                host_wall_id="opening_host_binding_group_abc",
                wall_local_frame_id="whole-wall-frame-1",
            )
        ),
        whole_wall_role_composition=_roles("whole-wall-frame-1"),
    )
    opening = composition.canonical_openings[0]
    assert opening.area_basis == OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert opening.external_wall_role_record_id == "role-whole-wall-frame-1"


def test_conflicting_host_and_frame_external_roles_abstain():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(
            _bare_external_door(
                host_wall_id="wall-1",
                wall_local_frame_id="wall-2",
            )
        ),
        whole_wall_role_composition=_roles("wall-1", "wall-2"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_unverified_schedule_height_blocks_the_2100_fallback():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(
            _bare_external_door(schedule_declared_height_mm=2400)
        ),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_existing_figured_area_is_not_replaced():
    original = _opening(kind="door")
    composition = apply_live_external_door_height_estimates(
        composition=_composition(original),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0] == original


def test_missing_printed_width_cannot_invent_an_area():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door(figured_single_axis_mm=None)),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_conflicting_metric_width_and_printed_figure_abstains():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door(width_m=1.2)),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert composition.canonical_openings[0].area_m2 is None


def test_estimate_quantity_rejects_tampered_area():
    composition = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door()),
        whole_wall_role_composition=_roles("wall-1"),
    )
    opening = composition.canonical_openings[0]
    assert _opening_quantity(opening) is not None
    assert _opening_quantity(replace(opening, area_m2=9.99)) is None
    assert _opening_quantity(replace(opening, opening_kind="window")) is None
    assert _opening_quantity(
        replace(opening, external_wall_role_record_id=None)
    ) is None


def test_one_figure_label_is_retained_and_two_figure_product_is_not():
    assert _figured_single_axis_mm(
        SimpleNamespace(dimension_values_mm=(870.0,))
    ) == 870.0
    assert _figured_single_axis_mm(
        SimpleNamespace(dimension_values_mm=(870.0, 2100.0))
    ) is None
    assert _figured_single_axis_mm(None) is None
    assert _figured_single_axis_mm(SimpleNamespace(dimension_values_mm=())) is None


def test_estimate_is_deterministic_under_replay():
    first = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door()),
        whole_wall_role_composition=_roles("wall-1"),
    )
    second = apply_live_external_door_height_estimates(
        composition=_composition(_bare_external_door()),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert first.canonical_openings == second.canonical_openings
    assert publish_live_opening_area_quantities(first) == (
        publish_live_opening_area_quantities(second)
    )
