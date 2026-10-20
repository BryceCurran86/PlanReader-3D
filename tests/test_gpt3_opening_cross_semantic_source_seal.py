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
