"""GPT3: physical opening cannot become two products by relabeling semantic key.

A separate, source-authenticated count can coexist with its genuine gross AREA.
Other trades/physical floors retain their existing layered semantic contracts.
"""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run,
    sealed_source_closed_run_from_dict,
)
from tests.test_source_closed_run_export import quantity, trace


def _q(identity: str, *, kind: str, family="opening_area",
       semantic_prefix=None, quantity_id="q-1", abstained=False):
    if semantic_prefix is None:
        semantic_prefix = f"{kind}_{'area' if family == 'opening_area' else 'count'}"
    return quantity(
        quantity_id=quantity_id,
        family=family,
        semantic_key=f"{semantic_prefix}:{identity}",
        value=None if abstained else 1.8,
        unit="m2" if family == "opening_area" else "ea",
        input_entity_ids=(identity,),
        evidence_ids=("ev-room-1",),
        status="abstained" if abstained else "corroborated",
        abstained=abstained,
        blocking_reasons=("physical_kind_unverified",) if abstained else (),
    )


def _seal(rows):
    return seal_source_closed_run(
        rows,
        project_id="project-a",
        traces_by_quantity_id={
            q.quantity_id: trace(canonical_entity_ids=q.input_entity_ids)
            for q in rows
        },
    )


@pytest.mark.parametrize("kind_pair", [
    ("door", "window"),
    ("window", "door"),
    ("window", "window"),
    ("door", "door"),
])
def test_same_source_opening_area_cannot_be_issued_twice_under_different_keys(kind_pair):
    first, second = kind_pair
    rows = [
        _q("physical-opening-1", kind=first, quantity_id="a1"),
        _q("physical-opening-1", kind=second, quantity_id="a2",
           semantic_prefix=f"{second}_area_other_source_receipt"),
    ]
    with pytest.raises(SourceClosedRunConflictError,
                       match="conflicting signed opening identity across semantic"):
        _seal(rows)


def test_opening_count_cannot_double_claim_same_physical_opening():
    rows = [
        _q("physical-opening-1", kind="door", family="opening_count", quantity_id="a1"),
        _q("physical-opening-1", kind="window", family="opening_count", quantity_id="a2"),
    ]
    with pytest.raises(SourceClosedRunConflictError, match="conflicting signed opening"):
        _seal(rows)


def test_opening_area_and_separate_complete_opening_count_can_coexist():
    rows = [
        _q("physical-opening-1", kind="door", family="opening_area", quantity_id="a1"),
        _q("physical-opening-1", kind="door", family="opening_count", quantity_id="a2"),
    ]
    sealed = _seal(rows)
    assert [q.family for q in sealed.quantities] == [
        "opening_area", "opening_count",
    ]
    assert sealed.quantities[0].object_identity_refs == ("physical-opening-1",)
    assert sealed.quantities[1].object_identity_refs == ("physical-opening-1",)


def test_separate_openings_with_distinct_proven_physical_ids_still_seal():
    rows = [
        _q("physical-opening-1", kind="door", quantity_id="a1"),
        _q("physical-opening-2", kind="window", quantity_id="a2"),
    ]
    sealed = _seal(rows)
    assert len(sealed.quantities) == 2
    assert sealed.fingerprint


def test_abstained_semantic_conflict_never_suppresses_a_real_issued_quantity():
    rows = [
        _q("physical-opening-1", kind="door", quantity_id="a1"),
        _q("physical-opening-1", kind="window", quantity_id="a2",
           abstained=True),
    ]
    sealed = _seal(rows)
    assert len(sealed.quantities) == 2
    assert sealed.quantities[0].abstained is False
    assert sealed.quantities[1].abstained is True


def test_unrelated_floor_layers_remain_unmodified_by_opening_only_rule():
    rows = [
        quantity(quantity_id="a1", family="floor_finish_area",
                 semantic_key="finish:vinyl", input_entity_ids=("floor-1",)),
        quantity(quantity_id="a2", family="floor_finish_area",
                 semantic_key="finish:carpet", input_entity_ids=("floor-1",)),
    ]
    assert len(_seal(rows).quantities) == 2


def test_original_lot16_eight_signed_run_stays_cryptographically_identical():
    path = Path(
        "docs/engineering/lot16_original_signed_eight_row_20261015/"
        "production/source_sealed_run.json"
    )
    archive = json.loads(path.read_text())
    sealed = sealed_source_closed_run_from_dict(archive)
    assert len(sealed.quantities) == 8
    assert sealed.fingerprint == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )
    # Reconstruct the run from its exact original sealed quantity objects;
    # physical opening distinctness and original signed body bytes are intact.
    ids = [q.object_identity_refs[0] for q in sealed.quantities]
    assert len(set(ids)) == 8
    assert all(q.family == "opening_area" for q in sealed.quantities)



def _commercial_openings(rows):
    from pb_quantity_takeoff_adapter import quantities_to_takeoff_output_rows
    from tests.test_quantity_takeoff_adapter import (
        quantity as commercial_quantity,
        source_trace, figured,
    )
    quantities = []
    for row in rows:
        quantities.append(commercial_quantity(
            quantity_id=row["quantity_id"],
            family=row["family"],
            semantic_key=row["semantic_key"],
            value=row["value"],
            unit=row["unit"],
            input_entity_ids=tuple(row["physical_ids"]),
        ))
    return quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id={
            q.quantity_id: source_trace(
                canonical_entity_ids=q.input_entity_ids,
            ) for q in quantities
        },
        authorities_by_quantity_id={
            q.quantity_id: figured() for q in quantities
        },
    )


def test_unsealed_commercial_projection_rejects_same_opening_two_area_semantics():
    source_rows = [
        {"quantity_id": "area-door", "family": "opening_area",
         "semantic_key": "door_area:actual-opening",
         "value": 1.8, "unit": "m2", "physical_ids": ["actual-opening"]},
        {"quantity_id": "area-window", "family": "opening_area",
         "semantic_key": "window_area:actual-opening",
         "value": 1.8, "unit": "m2", "physical_ids": ["actual-opening"]},
    ]
    from pb_quantity_takeoff_adapter import CommercialTakeoffConflictError
    with pytest.raises(CommercialTakeoffConflictError,
                       match="conflicting commercial physical opening"):
        _commercial_openings(source_rows)


def test_distinct_area_and_complete_count_can_project_same_physical_opening():
    source_rows = [
        {"quantity_id": "door-area", "family": "opening_area",
         "semantic_key": "door_area:actual-opening",
         "value": 1.8, "unit": "m2", "physical_ids": ["actual-opening"]},
        {"quantity_id": "door-count", "family": "opening_count",
         "semantic_key": "door_count:actual-opening",
         "value": 1, "unit": "ea", "physical_ids": ["actual-opening"]},
    ]
    rows = _commercial_openings(source_rows)
    assert [r["quantity_id"] for r in rows] == ["door-area", "door-count"]


def test_grouped_opening_count_overlap_is_not_hidden_by_new_semantic_key():
    source_rows = [
        {"quantity_id": "door-count-one", "family": "opening_count",
         "semantic_key": "door_count:source-owned-universe-A",
         "value": 2, "unit": "ea",
         "physical_ids": ["opening-1", "opening-2"]},
        {"quantity_id": "door-count-two", "family": "opening_count",
         "semantic_key": "door_count:source-owned-universe-B",
         "value": 2, "unit": "ea",
         "physical_ids": ["opening-2", "opening-3"]},
    ]
    from pb_quantity_takeoff_adapter import CommercialTakeoffConflictError
    with pytest.raises(CommercialTakeoffConflictError,
                       match="conflicting commercial physical opening"):
        _commercial_openings(source_rows)


def test_commercial_distinct_physical_openings_not_filtered_by_shared_area_family():
    source_rows = [
        {"quantity_id": "door-one", "family": "opening_area",
         "semantic_key": "door_area:one",
         "value": 1.8, "unit": "m2", "physical_ids": ["one"]},
        {"quantity_id": "door-two", "family": "opening_area",
         "semantic_key": "door_area:two",
         "value": 1.8, "unit": "m2", "physical_ids": ["two"]},
    ]
    assert len(_commercial_openings(source_rows)) == 2



@pytest.mark.parametrize("area_kind,count_kind", [
    ("door", "window"),
    ("window", "door"),
])
def test_original_seal_rejects_opposite_kinds_across_area_and_count(
    area_kind, count_kind,
):
    area = _q("physical-opening-1", kind=area_kind,
              family="opening_area", quantity_id="source-area")
    count = _q("physical-opening-1", kind=count_kind,
               family="opening_count", quantity_id="source-count")
    with pytest.raises(SourceClosedRunConflictError,
                       match="contradictory source-owned door/window kind"):
        _seal([area, count])


@pytest.mark.parametrize("area_kind,count_kind", [
    ("door", "window"),
    ("window", "door"),
])
def test_customer_projection_rejects_opposite_kinds_across_area_and_count(
    area_kind, count_kind,
):
    rows = [
        {"quantity_id": "area", "family": "opening_area",
         "semantic_key": f"{area_kind}_area:original-open",
         "value": 1.8, "unit": "m2",
         "physical_ids": ["original-open"]},
        {"quantity_id": "count", "family": "opening_count",
         "semantic_key": f"{count_kind}_count:original-open",
         "value": 1, "unit": "ea",
         "physical_ids": ["original-open"]},
    ]
    from pb_quantity_takeoff_adapter import CommercialTakeoffConflictError
    with pytest.raises(CommercialTakeoffConflictError,
                       match="contradictory source-owned door/window kind"):
        _commercial_openings(rows)


def test_multiple_proven_same_kind_area_and_count_remain_separate_families():
    rows = [
        {"quantity_id": "window-area", "family": "opening_area",
         "semantic_key": "window_area:original-open",
         "value": 1.8, "unit": "m2", "physical_ids": ["original-open"]},
        {"quantity_id": "window-count", "family": "opening_count",
         "semantic_key": "window_count:original-open",
         "value": 1, "unit": "ea", "physical_ids": ["original-open"]},
    ]
    assert len(_commercial_openings(rows)) == 2
