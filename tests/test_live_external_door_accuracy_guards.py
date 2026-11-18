"""Original PlanReader external-door provisional accuracy: independent synthetic cases.

None of these tests promote a source-closed/FIRM measurement or change frozen120.
"""
from dataclasses import replace

import pytest

from pb_live_opening_external_door_height_estimate_publication import (
    apply_live_external_door_height_estimates,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_role_authority import WallRoleClassification
from tests.test_live_opening_external_door_height_estimate_publication import (
    _bare_external_door, _roles,
)
from tests.test_live_opening_area_quantity_publication import _composition


def estimated(opening=None, roles=None):
    return apply_live_external_door_height_estimates(
        composition=_composition(opening or _bare_external_door()),
        whole_wall_role_composition=roles or _roles("wall-1"),
    ).canonical_openings[0]


def test_revision_mismatch_cannot_borrow_an_external_wall_role():
    assert estimated(roles=replace(_roles("wall-1"), revision_id="other")).area_m2 is None


def test_stale_opening_revision_cannot_get_fallback():
    assert estimated(opening=_bare_external_door(revision_id="stale")).area_m2 is None


def test_other_page_external_wall_role_cannot_authenticate_door():
    roles = _roles("wall-1")
    roles = replace(roles, traces=(replace(roles.traces[0], page_id="A999"),))
    assert estimated(roles=roles).area_m2 is None


def test_repeated_external_role_trace_is_ambiguous():
    roles = _roles("wall-1")
    roles = replace(roles, traces=(roles.traces[0], roles.traces[0]))
    assert estimated(roles=roles).area_m2 is None


def test_conflicting_internal_wall_role_vetoes_external_claim():
    roles = _roles("wall-1")
    roles = replace(roles, traces=(
        roles.traces[0],
        replace(roles.traces[0], role=WallRoleClassification.INTERNAL,
                record_id="internal-evidence"),
    ))
    assert estimated(roles=roles).area_m2 is None


def test_abstained_role_for_same_wall_vetoes_positive_sibling():
    roles = _roles("wall-1")
    roles = replace(roles, traces=(
        roles.traces[0],
        replace(roles.traces[0], status=EvidenceResolutionStatus.ABSTAINED,
                record_id=None),
    ))
    assert estimated(roles=roles).area_m2 is None


def test_one_role_receipt_cannot_authenticate_two_walls():
    roles = _roles("wall-1", "wall-2")
    roles = replace(roles, traces=(
        roles.traces[0],
        replace(roles.traces[1], record_id=roles.traces[0].record_id),
    ))
    assert estimated(roles=roles).area_m2 is None


def test_internal_host_conflicts_with_external_frame():
    opening = _bare_external_door(
        host_wall_id="internal-wall", wall_local_frame_id="external-frame",
    )
    external = _roles("external-frame")
    internal = _roles("internal-wall", role=WallRoleClassification.INTERNAL)
    roles = replace(external, traces=external.traces + internal.traces)
    assert estimated(opening=opening, roles=roles).area_m2 is None


def test_conflicting_schedule_width_blocks_provisional_area():
    assert estimated(opening=_bare_external_door(
        schedule_declared_width_mm=920,
    )).area_m2 is None


def test_matching_schedule_width_still_requires_missing_height():
    opening = estimated(opening=_bare_external_door(
        schedule_declared_width_mm=870,
    ))
    assert opening.area_m2 == pytest.approx(1.827)


@pytest.mark.parametrize("height", [10**1000, float("inf"), -1])
def test_invalid_schedule_heights_fail_closed_without_exception(height):
    opening = _bare_external_door(
        schedule_declared_height_mm=height,
        schedule_binding_record_id="source-schedule-height",
    )
    assert estimated(opening=opening).area_m2 is None


def test_oversized_figured_width_does_not_crash_or_publish():
    assert estimated(opening=_bare_external_door(
        figured_single_axis_mm=10**1000,
    )).area_m2 is None


@pytest.mark.parametrize("field", ["owner_approved_width_mm", "owner_approved_height_mm"])
def test_preexisting_owner_axis_vetoes_unapproved_default(field):
    assert estimated(opening=_bare_external_door(**{field: 1900.0})).area_m2 is None


def test_prepopulated_external_role_receipt_is_not_overwritten():
    assert estimated(opening=_bare_external_door(
        external_wall_role_record_id="unverified-previous-role",
    )).area_m2 is None


def test_unbound_host_identifiers_do_not_gain_provisional_area():
    assert estimated(opening=_bare_external_door(
        host_binding_record_id=None, host_frame_record_id=None,
    )).area_m2 is None


def test_complete_geometry_with_missing_height_is_contradictory():
    assert estimated(opening=_bare_external_door(
        geometry_complete=True,
    )).area_m2 is None


def test_duplicate_canonical_door_ids_are_not_double_counted():
    opening = _bare_external_door()
    result = apply_live_external_door_height_estimates(
        composition=_composition(opening, opening),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert all(item.area_m2 is None for item in result.canonical_openings)


def test_duplicate_physical_door_ids_are_not_double_counted():
    a = _bare_external_door()
    b = replace(a, canonical_opening_id="second-id")
    result = apply_live_external_door_height_estimates(
        composition=_composition(a, b),
        whole_wall_role_composition=_roles("wall-1"),
    )
    assert all(item.area_m2 is None for item in result.canonical_openings)


def test_valid_external_door_remains_provisional_not_measured():
    opening = estimated()
    assert opening.area_m2 == pytest.approx(1.827)
    assert opening.height_m is None
    assert opening.area_basis == "assumed_external_door_height_2100_mm_owner_policy"
