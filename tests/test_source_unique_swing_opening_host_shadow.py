"""Unique source swing hinge hosts one unhosted opening; it does not mint one."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from types import MappingProxyType

import fitz
import pytest

from pb_external_door_height_estimate_policy import OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_opening_external_door_height_estimate_publication import (
    apply_live_external_door_height_estimates,
)
from pb_live_whole_wall_role_composition import (
    LiveWholeWallRoleComposition,
    LiveWholeWallRoleTrace,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_quarter_swing_opening_kind_shadow import apply_source_quarter_swing_opening_kinds
from pb_source_unique_swing_opening_host_shadow import (
    apply_source_one_room_envelope_external_roles,
    apply_source_sliding_leaf_opening_hosts,
    apply_source_unique_swing_opening_hosts,
)
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import robe_room, stacker_room
from pb_wall_role_authority import WallRoleClassification
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import room as _walled_room
from tests.test_live_opening_area_quantity_publication import _composition, _opening
from tests.test_source_quarter_swing_opening_kind_shadow import (
    CLOSED_TIP,
    HINGE,
    _hosted,
    _quarter_swing_drawings,
    _stroke,
)


def _unhosted(*, geom, kind=None, opening_id="opening-1"):
    return replace(
        _hosted(geom=geom, kind=kind, opening_id=opening_id),
        host_wall_id=None,
        host_binding_record_id=None,
        host_frame_record_id=None,
    )


def _empty_roles():
    return LiveWholeWallRoleComposition(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("live_whole_wall_role_composition_unavailable",),
        traces=(),
        whole_wall_role_authority=None,
        role_selectors=MappingProxyType({}),
    )


def test_unique_unhosted_opening_at_the_hinge_gets_a_host() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0))
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    updated = composition.canonical_openings[0]
    assert updated.host_wall_id
    assert updated.host_wall_id.startswith("opening_host_binding_group_")
    assert updated.host_binding_record_id.startswith("opening_host_binding_v3_")
    assert updated.canonical_opening_id == opening.canonical_opening_id
    assert any(
        item.startswith("source_unique_swing_opening_host_")
        for item in updated.evidence_ids
    )


def test_two_unhosted_openings_at_the_same_hinge_abstain() -> None:
    first = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="opening-a")
    second = _unhosted(geom=(50.0, 49.2, 50.0, 52.5), opening_id="opening-b")
    composition = apply_source_unique_swing_opening_hosts(
        _composition(first, second),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert composition.canonical_openings[0].host_wall_id is None
    assert composition.canonical_openings[1].host_wall_id is None


def test_already_hosted_opening_at_the_hinge_blocks_a_second_host() -> None:
    hosted = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="opening-hosted")
    extra = _unhosted(geom=(48.8, 50.0, 51.0, 50.0), opening_id="opening-extra")
    composition = apply_source_unique_swing_opening_hosts(
        _composition(hosted, extra),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    by_id = {item.canonical_opening_id: item for item in composition.canonical_openings}
    assert by_id["opening-hosted"].host_wall_id == hosted.host_wall_id
    assert by_id["opening-extra"].host_wall_id is None


def test_closed_tip_opening_is_not_hosted_from_the_hinge() -> None:
    opening = _unhosted(geom=(49.2, 25.0, 52.5, 25.0))
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert composition.canonical_openings[0].host_wall_id is None
    assert CLOSED_TIP[1] == 25.0
    assert HINGE[1] == 50.0


def test_window_stays_unhosted_even_at_the_hinge() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="window")
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert composition.canonical_openings[0].host_wall_id is None
    assert composition.canonical_openings[0].opening_kind == "window"


def test_unique_diagonal_leaf_hosts_the_opening_at_its_hinge() -> None:
    hinge = (20.0, 20.0)
    tip = (20.0 + 24.66, 20.0 + 24.66)
    opening = _unhosted(geom=(20.0, 20.0, 20.0, 17.5))
    drawings = [_stroke("l", hinge, tip, layer="Enclosure_WallInternal")]
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].host_wall_id


def test_window_interruption_without_a_leaf_stays_unhosted() -> None:
    opening = _unhosted(geom=(100.0, 100.0, 102.5, 100.0))
    drawings = [_stroke("l", (90.0, 100.0), (110.0, 100.0))]
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].host_wall_id is None


def test_corroborated_internal_host_is_not_stamped_external() -> None:
    drawings = _walled_room()
    opening = replace(
        _unhosted(geom=(97.2, 40.0, 100.5, 40.0), kind="door"),
        host_wall_id="opening_host_binding_group_synthetic",
        host_binding_record_id="opening_host_binding_v3_synthetic",
    )
    internal = LiveWholeWallRoleComposition(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_whole_wall_role_composition_resolved",),
        traces=(
            LiveWholeWallRoleTrace(
                physical_wall_id=opening.host_wall_id,
                page_id="3",
                decision_scope_id="live-page-3",
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("existing_internal",),
                record_id="internal-role-1",
                role=WallRoleClassification.INTERNAL,
            ),
        ),
        whole_wall_role_authority=None,
        role_selectors=MappingProxyType({}),
    )
    roles = apply_source_one_room_envelope_external_roles(
        internal,
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert all(trace.role is not WallRoleClassification.EXTERNAL for trace in roles.traces)
    estimated = apply_live_external_door_height_estimates(
        composition=_composition(replace(opening, figured_single_axis_mm=870.0)),
        whole_wall_role_composition=roles,
    )
    assert estimated.canonical_openings[0].area_basis != OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert estimated.canonical_openings[0].area_m2 is None


def test_zero_opacity_swing_does_not_host_an_opening() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0))
    drawings = [{**row, "stroke_opacity": 0.0} for row in _quarter_swing_drawings()]
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].host_wall_id is None


def test_generated_swing_host_binding_is_not_a_quantity_receipt() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    hosted = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    updated = hosted.canonical_openings[0]
    assert updated.host_wall_id
    assert updated.host_binding_record_id
    assert updated.host_binding_record_id not in updated.evidence_ids
    billed = replace(
        updated,
        opening_kind="door",
        area_m2=1.827,
        area_basis="figured_opening_label",
        figured_area_record_id="figured-1",
    )
    assert _opening_quantity(billed) is None


def test_one_room_envelope_wall_gets_an_external_role() -> None:
    drawings = _walled_room()
    # Right-wall swing hinge from the synthetic room helper: (98, 40).
    opening = replace(
        _unhosted(geom=(97.2, 40.0, 100.5, 40.0), kind="door"),
        host_wall_id="opening_host_binding_group_synthetic",
        host_binding_record_id="opening_host_binding_v3_synthetic",
    )
    roles = apply_source_one_room_envelope_external_roles(
        _empty_roles(),
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert roles.traces
    assert roles.traces[0].physical_wall_id == opening.host_wall_id
    assert roles.traces[0].role is WallRoleClassification.EXTERNAL
    assert roles.traces[0].status is EvidenceResolutionStatus.CORROBORATED


def _two_rooms_shared_partition():
    from tests.test_layered_wall_doorway_room_ring_shadow_v1 import strip, swing

    rows = []
    rows += strip(0, 0, 200, 2)
    rows += strip(0, 98, 200, 100)
    rows += strip(0, 2, 2, 98)
    rows += strip(198, 2, 200, 98)
    rows += strip(98, 2, 100, 40)
    rows += strip(98, 64, 100, 98)
    rows += swing((98, 40), (74, 40), (98, 64))
    return rows


def test_internal_wall_between_two_rooms_is_not_external() -> None:
    opening = replace(
        _unhosted(geom=(97.2, 40.0, 100.5, 40.0), kind="door"),
        host_wall_id="opening_host_binding_group_party",
        host_binding_record_id="opening_host_binding_v3_party",
    )
    roles = apply_source_one_room_envelope_external_roles(
        _empty_roles(),
        _composition(opening),
        drawings_by_page_id={"3": _two_rooms_shared_partition()},
    )
    assert all(
        trace.physical_wall_id != opening.host_wall_id
        for trace in roles.traces
    )


def test_envelope_external_door_with_printed_width_gets_the_2100_estimate() -> None:
    drawings = _walled_room()
    opening = replace(
        _unhosted(geom=(97.2, 40.0, 100.5, 40.0)),
        figured_single_axis_mm=870.0,
    )
    hosted = apply_source_unique_swing_opening_hosts(
        _composition(opening), drawings_by_page_id={"3": drawings},
    )
    kinded = apply_source_quarter_swing_opening_kinds(
        hosted, drawings_by_page_id={"3": drawings},
    )
    roles = apply_source_one_room_envelope_external_roles(
        _empty_roles(), kinded, drawings_by_page_id={"3": drawings},
    )
    estimated = apply_live_external_door_height_estimates(
        composition=kinded, whole_wall_role_composition=roles,
    )
    updated = estimated.canonical_openings[0]
    assert updated.host_wall_id
    assert updated.opening_kind == "door"
    assert updated.area_basis == OWNER_EXTERNAL_DOOR_ASSUMPTION_BASIS
    assert updated.area_m2 == pytest.approx(870.0 * 2100.0 / 1_000_000.0)
    assert updated.height_m is None


def test_swing_without_a_closed_room_is_not_external() -> None:
    opening = replace(
        _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door"),
        host_wall_id="opening_host_binding_group_no-ring",
        host_binding_record_id="opening_host_binding_v3_no-ring",
    )
    roles = apply_source_one_room_envelope_external_roles(
        _empty_roles(),
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert roles.traces == ()


def test_original_unhosted_opening_at_a_detected_swing_hinge_gets_a_host() -> None:
    from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs

    original = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("private 3Laurel original not provisioned")
    with fitz.open(original) as doc:
        drawings = tuple(doc[2].get_drawings())
    arcs, _rejected = _swing_arcs(drawings)
    assert arcs
    hinge = tuple(arcs[0]["centre"])
    opening = _unhosted(geom=(hinge[0] - 0.8, hinge[1], hinge[0] + 2.5, hinge[1]))
    composition = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].host_wall_id


def test_unique_door_in_a_sliding_leaf_closure_gets_a_host() -> None:
    opening = _unhosted(geom=(44.4, 28.0, 44.4, 30.0), kind="door")
    composition = apply_source_sliding_leaf_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": robe_room()},
    )
    updated = composition.canonical_openings[0]
    assert updated.host_wall_id
    assert any(
        item.startswith("source_sliding_leaf_opening_host_")
        for item in updated.evidence_ids
    )


def test_two_doors_in_the_same_sliding_closure_abstain() -> None:
    first = _unhosted(geom=(44.4, 28.0, 44.4, 30.0), kind="door", opening_id="opening-a")
    second = _unhosted(geom=(94.0, 28.0, 94.0, 30.0), kind="door", opening_id="opening-b")
    composition = apply_source_sliding_leaf_opening_hosts(
        _composition(first, second),
        drawings_by_page_id={"3": robe_room()},
    )
    assert composition.canonical_openings[0].host_wall_id is None
    assert composition.canonical_openings[1].host_wall_id is None


def test_unkinded_tick_beside_a_unique_sliding_door_does_not_block_it() -> None:
    door = _unhosted(geom=(44.4, 28.0, 44.4, 30.0), kind="door", opening_id="opening-door")
    tick = _unhosted(geom=(45.0, 28.0, 46.2, 28.0), opening_id="opening-tick")
    composition = apply_source_sliding_leaf_opening_hosts(
        _composition(door, tick),
        drawings_by_page_id={"3": robe_room()},
    )
    by_id = {item.canonical_opening_id: item for item in composition.canonical_openings}
    assert by_id["opening-door"].host_wall_id
    assert by_id["opening-tick"].host_wall_id is None


def test_unique_door_in_a_stacker_leaf_closure_gets_a_host() -> None:
    opening = _unhosted(geom=(44.4, 28.0, 44.4, 30.0), kind="door")
    composition = apply_source_sliding_leaf_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": stacker_room()},
        stacker_leaf_frame_closure=True,
    )
    updated = composition.canonical_openings[0]
    assert updated.host_wall_id
    assert any(
        item.startswith("source_stacker_leaf_opening_host_")
        for item in updated.evidence_ids
    )


def test_stacker_host_stays_off_unless_its_own_control_is_set() -> None:
    opening = _unhosted(geom=(44.4, 28.0, 44.4, 30.0), kind="door")
    composition = apply_source_sliding_leaf_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": stacker_room()},
    )
    assert composition.canonical_openings[0].host_wall_id is None
