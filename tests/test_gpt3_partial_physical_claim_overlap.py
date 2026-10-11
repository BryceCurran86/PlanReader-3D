"""Partial physical overlap cannot produce two sealed quantities."""
import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run,
    combine_source_closed_runs,
)
from test_source_closed_run_export import quantity, trace


def run(name, ids, *, family="room_area", semantic_key="room.area", abstained=False):
    q=quantity(
        quantity_id=name,
        family=family,
        semantic_key=semantic_key,
        input_entity_ids=tuple(ids),
        evidence_ids=(f"evidence-{name}",),
        value=None if abstained else 13.0,
        status="abstained" if abstained else "firm",
        abstained=abstained,
        blocking_reasons=("source_unavailable",) if abstained else (),
    )
    t=trace(
        canonical_entity_ids=tuple(ids),
        evidence_ids=(f"evidence-{name}",),
    )
    return seal_source_closed_run(
        [q],project_id="project-a",traces_by_quantity_id={name:t}
    )


@pytest.mark.parametrize("a,b",[
    (("room-a","shared"),("shared","room-b")),
    (("room-a",),("room-a","room-b")),
    (("room-a","room-b"),("room-a",)),
])
def test_two_signed_runs_cannot_combine_overlapping_physical_claims(a,b):
    first=run("q-one",a)
    second=run("q-two",b)
    with pytest.raises(SourceClosedRunConflictError,match="conflicting sealed physical claim"):
        combine_source_closed_runs([first,second])


def test_same_sealing_call_rejects_partially_overlapping_source_parents():
    a=quantity(
        quantity_id="q-a",semantic_key="room.area",
        input_entity_ids=("floor-a","floor-shared"),evidence_ids=("ev-a",),
    )
    b=quantity(
        quantity_id="q-b",semantic_key="room.area",
        input_entity_ids=("floor-b","floor-shared"),evidence_ids=("ev-b",),
    )
    with pytest.raises(SourceClosedRunConflictError,match="overlapping source identity"):
        seal_source_closed_run(
            [a,b],project_id="project-a",
            traces_by_quantity_id={
                "q-a":trace(canonical_entity_ids=a.input_entity_ids,evidence_ids=a.evidence_ids),
                "q-b":trace(canonical_entity_ids=b.input_entity_ids,evidence_ids=b.evidence_ids),
            },
        )


def test_disjoint_sources_with_same_semantic_key_preserve_independent_quantities():
    first=run("q-one",("floor-a","floor-b"))
    second=run("q-two",("floor-c","floor-d"))
    merged=combine_source_closed_runs([first,second])
    assert [q.quantity_id for q in merged.quantities]==["q-one","q-two"]


def test_distinct_quantity_families_can_legitimately_share_one_physical_object():
    first=run("q-floor",("room-a",),family="floor_area")
    second=run("q-ceiling",("room-a",),family="ceiling_area")
    merged=combine_source_closed_runs([first,second])
    assert len(merged.quantities)==2


def test_source_abstention_does_not_create_a_false_commercial_duplicate():
    first=run("q-firm",("room-a",))
    blocked=run("q-abstained",("room-a",),abstained=True)
    combined=combine_source_closed_runs([first,blocked])
    assert len(combined.quantities)==2
    assert sum(not x.abstained for x in combined.quantities)==1


def test_exact_set_same_value_is_still_detected_as_duplicate():
    first=run("q-one",("room-a","room-b"))
    second=run("q-two",("room-b","room-a"))
    with pytest.raises(SourceClosedRunConflictError,match="duplicate sealed physical claim"):
        combine_source_closed_runs([first,second])


def test_same_source_geometry_with_different_semantic_keys_is_independent_claim():
    first=run("q-area",("room-a",),semantic_key="floor.area")
    second=run("q-finish",("room-a",),semantic_key="floor.finish")
    combined=combine_source_closed_runs([first,second])
    assert len(combined.quantities)==2
