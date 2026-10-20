"""GPT3 release veto: a geometric floor_area cannot claim one physical floor twice."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run,
    sealed_source_closed_run_from_dict,
)
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffConflictError, quantities_to_takeoff_output_rows,
)
from tests.test_source_closed_run_export import (
    quantity as sealed_quantity, trace as sealed_trace,
)
from tests.test_quantity_takeoff_adapter import (
    quantity as commercial_quantity, source_trace, figured,
)


def _source_rows(
    first_members=("floor-original-1",),
    second_members=("floor-original-1",),
    *,
    second_family="floor_area",
    first_family="floor_area",
):
    return [
        sealed_quantity(
            quantity_id="floor-a", family=first_family,
            semantic_key="floor_area:source-view-A",
            input_entity_ids=first_members, value=9.05352,
        ),
        sealed_quantity(
            quantity_id="floor-b", family=second_family,
            semantic_key="floor_area:other-source-name-B",
            input_entity_ids=second_members, value=9.05352,
        ),
    ]


def _seal(quantities):
    return seal_source_closed_run(
        quantities, project_id="project-a",
        traces_by_quantity_id={
            q.quantity_id: sealed_trace(
                canonical_entity_ids=q.input_entity_ids,
            )
            for q in quantities
        },
    )


def _customer(quantities):
    return quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id={
            q.quantity_id: source_trace(
                canonical_entity_ids=q.input_entity_ids,
            )
            for q in quantities
        },
        authorities_by_quantity_id={
            q.quantity_id: figured()
            for q in quantities
        },
    )


def _commercial_rows(
    first_members=("floor-original-1",),
    second_members=("floor-original-1",),
    *,
    second_family="floor_area",
):
    return [
        commercial_quantity(
            quantity_id="floor-a", family="floor_area",
            semantic_key="floor_area:original-view-A",
            input_entity_ids=first_members, value=9.05352,
            unit="m2",
        ),
        commercial_quantity(
            quantity_id="floor-b", family=second_family,
            semantic_key="floor_area:other-view-B",
            input_entity_ids=second_members, value=9.05352,
            unit="m2",
        ),
    ]


@pytest.mark.parametrize("members_a,members_b", [
    (("floor-original-1",), ("floor-original-1",)),
    (("floor-original-1", "floor-original-2"),
     ("floor-original-2", "floor-original-3")),
])
def test_floor_area_cannot_be_signed_twice_with_different_semantic_names(
    members_a, members_b,
):
    with pytest.raises(SourceClosedRunConflictError,
                       match="same original physical floor area signed twice"):
        _seal(_source_rows(members_a, members_b))


@pytest.mark.parametrize("members_a,members_b", [
    (("floor-original-1",), ("floor-original-1",)),
    (("floor-original-1", "floor-original-2"),
     ("floor-original-2", "floor-original-3")),
])
def test_floor_area_cannot_be_commercially_projected_twice_under_other_keys(
    members_a, members_b,
):
    with pytest.raises(CommercialTakeoffConflictError,
                       match="same original physical floor area commercially"):
        _customer(_commercial_rows(members_a, members_b))


def test_two_distinct_source_physical_floors_remain_independently_measured():
    quantities = _source_rows(
        ("floor-original-1",), ("floor-original-2",)
    )
    assert len(_seal(quantities).quantities) == 2
    assert len(_customer(_commercial_rows(
        ("floor-original-1",), ("floor-original-2"),
    ))) == 2


def test_distinct_floor_finish_layers_not_confused_with_geometric_floor_area():
    quantities = _source_rows(
        ("floor-original-1",), ("floor-original-1",),
        second_family="floor_finish_area",
    )
    assert len(_seal(quantities).quantities) == 2
    assert len(_customer(_commercial_rows(
        second_family="floor_finish_area",
    ))) == 2


def test_two_source_finish_layers_retain_independent_material_semantic_claims():
    quantities = _source_rows(
        ("floor-original-1",), ("floor-original-1",),
        first_family="floor_finish_area",
        second_family="floor_finish_area",
    )
    assert len(_seal(quantities).quantities) == 2


def test_abstained_secondary_geometric_floor_does_not_block_firm_floor():
    from dataclasses import replace

    first, second = _source_rows()
    second = replace(
        second, abstained=True, value=None, status="abstained",
        blocking_reasons=("floor_closure_unproven",),
    )
    result = _seal([first, second])
    assert len(result.quantities) == 2
    assert [q.abstained for q in result.quantities] == [False, True]


def test_original_eight_lot16_source_signed_fingerprint_is_unchanged():
    archived = json.loads((
        Path("docs/engineering/lot16_original_signed_eight_row_20261015")
        / "production/source_sealed_run.json"
    ).read_text(encoding="utf-8"))
    parsed = sealed_source_closed_run_from_dict(archived)
    assert len(parsed.quantities) == 8
    assert parsed.fingerprint == archived["fingerprint"]
    assert parsed.fingerprint == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )
