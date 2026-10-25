"""Original numeric FIRM room-area blockers cannot vanish at the floor seal/customer boundary.

Source-neutral contract regression; no original PDF, quantity promotion or frozen truth.
"""
from dataclasses import replace

import pytest

from pb_live_floor_area_customer_projection import project_live_floor_area_customer_rows
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
    seal_live_floor_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_gpt1_floor_seal_raw_room_area_source_ids import _claim
from tests.test_live_floor_area_quantity_publication_integrity import _source_area


def _source_traces(claim):
    return build_live_floor_area_source_traces(
        claim, workspace_id=1, project_id="source-owned-floor"
    )


def _customer(claim):
    return project_live_floor_area_customer_rows(
        claim, workspace_id=1, project_id="source-owned-floor"
    )


def _seal(claim):
    return seal_live_floor_area_run(
        claim, workspace_id=1, project_id="source-owned-floor"
    )


@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_original_numeric_firm_with_blockers_cannot_disappear_from_seal_or_customer(
    mixed, reverse,
):
    source = _source_area()
    blocked = replace(
        source,
        quantity_id="blocked-independent-source-area",
        blocking_reasons=("unresolved_original_room_boundary",),
    )
    sources = (source, blocked) if mixed else (blocked,)
    if reverse:
        sources = tuple(reversed(sources))
    claim = _claim(*sources)
    # The original producer legitimately refuses blocked FIRM input. It
    # must remain a conflict, not be silently hidden, at the final boundary.
    published = publish_live_floor_area_quantities(claim)
    assert len(published) == (1 if mixed else 0)
    for consumer in (_source_traces, _seal, _customer):
        with pytest.raises(
            SourceClosedRunConflictError,
            match="original numeric firm room-area source retains unresolved blockers",
        ):
            consumer(claim)
    assert claim.room_area_quantity_evidence == sources
    assert blocked.blocking_reasons == ("unresolved_original_room_boundary",)


@pytest.mark.parametrize("reverse", [False, True])
def test_provisional_abstention_remains_nonpublishing_without_poisoning_valid_floor(reverse):
    source = _source_area()
    provisional = replace(
        source,
        quantity_id="independent-unresolved-original-area",
        value=None,
        abstained=True,
        status="provisional",
        blocking_reasons=("unresolved_original_room_boundary",),
    )
    sources = (source, provisional)
    if reverse:
        sources = tuple(reversed(sources))
    claim = _claim(*sources)
    assert len(publish_live_floor_area_quantities(claim)) == 1
    traces = _source_traces(claim)
    assert len(traces) == 1
    sealed = _seal(claim)
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].value == source.value
    rows = _customer(claim)
    assert len(rows) == 1
    assert claim.room_area_quantity_evidence == sources


def test_all_provisional_original_room_areas_still_abstain_without_false_conflict():
    source = _source_area()
    provisional = replace(
        source,
        value=None,
        abstained=True,
        status="provisional",
        blocking_reasons=("unresolved_original_room_boundary",),
    )
    claim = _claim(provisional)
    assert publish_live_floor_area_quantities(claim) == ()
    assert _source_traces(claim) == {}
    assert _customer(claim) == ()
    assert claim.room_area_quantity_evidence == (provisional,)
