"""Original room identity must survive the real FIRM floor-finish customer row.

Negative-only customer integrity checks: no source discovery, new area, or score.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_floor_finish_area_source_closed_export import _claim, _floor, _quantity


class _StringAlias(str):
    """A string-like imported receipt is not an original native source ID."""


@pytest.mark.parametrize(
    "source_room_id",
    (
        None,
        "",
        " room-1",
        "room-1 ",
        1,
        True,
        _StringAlias("room-1"),
    ),
)
def test_firm_floor_finish_customer_rejects_coerced_original_room_location(
    source_room_id,
):
    floor = replace(_floor(), room_entity_id=source_room_id)
    claim = _claim(floor)
    with pytest.raises(
        SourceClosedRunConflictError,
        match="customer location lacks exact original room identity",
    ):
        project_live_floor_finish_customer_rows(
            claim, workspace_id=1, project_id="project-1",
        )


def test_valid_original_room_location_preserves_real_customer_row_and_replay():
    claim = _claim()
    original = project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    replay = project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert original == replay
    assert len(original) == 1
    assert original[0]["quantity_id"] == _quantity().quantity_id
    assert original[0]["location"] == "room-1"
    assert original[0]["quantity"] == pytest.approx(8.64)


def test_rejected_original_room_identity_does_not_mutate_source_claim():
    floor = replace(_floor(), room_entity_id=" room-1 ")
    claim = _claim(floor)
    before_floor = floor.to_dict()
    before_quantity = claim.floor_finish_quantity_evidence[0].to_dict()
    with pytest.raises(SourceClosedRunConflictError):
        project_live_floor_finish_customer_rows(
            claim, workspace_id=1, project_id="project-1",
        )
    assert floor.to_dict() == before_floor
    assert claim.floor_finish_quantity_evidence[0].to_dict() == before_quantity


def test_abstained_original_floor_finish_still_has_no_customer_row():
    original = _quantity()
    blocked = replace(
        original,
        value=None,
        status=AuthorityStatus.BLOCKED.value,
        abstained=True,
        blocking_reasons=("source_room_owner_unresolved",),
    )
    claim = replace(
        _claim(replace(_floor(), room_entity_id=None)),
        floor_finish_quantity_evidence=(blocked,),
    )
    assert project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    ) == ()


@pytest.mark.parametrize(
    "source_floor_id",
    (
        " floor-1",
        "floor-1 ",
        1,
        True,
        _StringAlias("floor-1"),
    ),
)
def test_firm_customer_rejects_coerced_quantity_canonical_floor_id(source_floor_id):
    quantity = replace(_quantity(), input_entity_ids=(source_floor_id,))
    claim = replace(_claim(), floor_finish_quantity_evidence=(quantity,))
    with pytest.raises(
        SourceClosedRunConflictError,
        match="customer canonical floor input lacks exact source identity",
    ):
        project_live_floor_finish_customer_rows(
            claim, workspace_id=1, project_id="project-1",
        )


@pytest.mark.parametrize(
    "source_floor_id",
    (
        " floor-1",
        "floor-1 ",
        _StringAlias("floor-1"),
    ),
)
def test_firm_customer_rejects_coerced_original_canonical_floor_record(source_floor_id):
    claim = _claim(replace(_floor(), canonical_floor_id=source_floor_id))
    with pytest.raises(
        SourceClosedRunConflictError,
        match="customer canonical floor disagrees with original source identity",
    ):
        project_live_floor_finish_customer_rows(
            claim, workspace_id=1, project_id="project-1",
        )
