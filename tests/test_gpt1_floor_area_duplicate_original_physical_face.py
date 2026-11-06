"""A single original physical whole-room floor face cannot be sold twice.

Exercise the genuine already-FIRM issuer, final source trace, sealed run and
customer projection. Synthetic data never establish an owner PDF measurement.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_floor_area_customer_projection import project_live_floor_area_customer_rows
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
    seal_live_floor_area_run,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with, _source_area,
)
from tests.test_live_floor_finish_area_source_closed_export import _floor


def _two_source_floors(*, second_ring=None, second_page="1", second_viewport="vp-1",
                       reverse=False):
    first = _source_area()
    first = replace(first, metadata={
        **dict(first.metadata),
        "figured_dimension_ids": ("a-horizontal", "a-vertical"),
    })
    second = replace(
        first,
        quantity_id="room-area-2",
        semantic_key="room_area:source-room-2",
        input_entity_ids=("source-room-2",),
        evidence_ids=("ev-room-2", "ev-area-2"),
        metadata={
            **dict(first.metadata),
            "page_no": second_page,
            "viewport_id": second_viewport,
            "figured_dimension_ids": ("b-horizontal", "b-vertical"),
        },
    )
    first_floor = _floor()
    second_floor = replace(
        first_floor,
        canonical_floor_id="floor-2",
        physical_floor_surface_id="floor-2",
        room_entity_id="room-2",
        source_room_face_record_id="face-2",
        metric_area_quantity_id=second.quantity_id,
        evidence_ids=("ev-room-2", "ev-area-2"),
        polygon_pdf_pts=tuple(second_ring) if second_ring is not None
            else first_floor.polygon_pdf_pts,
        page_id=second_page,
        viewport_id=second_viewport,
    )
    quantities = (first, second)
    floors = (first_floor, second_floor)
    if reverse:
        quantities = tuple(reversed(quantities))
        floors = tuple(reversed(floors))
    claim = _claim_with(*quantities)
    return replace(claim, canonical_floors=floors)


def _consumers():
    return (
        lambda c: build_live_floor_area_source_traces(
            c, workspace_id=7, project_id="source-owned-floor"),
        lambda c: seal_live_floor_area_run(
            c, workspace_id=7, project_id="source-owned-floor"),
        lambda c: project_live_floor_area_customer_rows(
            c, workspace_id=7, project_id="source-owned-floor"),
    )


@pytest.mark.parametrize("variant", (
    "same", "rotated", "reversed", "closed", "one_split", "two_splits",
))
@pytest.mark.parametrize("reverse_order", (False, True))
def test_independent_firm_floor_ids_cannot_double_claim_same_original_face(
    variant, reverse_order,
):
    a, b, c, d = _floor().polygon_pdf_pts
    midpoint_ab = ((a[0]+b[0])/2, (a[1]+b[1])/2)
    midpoint_bc = ((b[0]+c[0])/2, (b[1]+c[1])/2)
    ring = {
        "same": (a, b, c, d),
        "rotated": (c, d, a, b),
        "reversed": (d, c, b, a),
        "closed": (a, b, c, d, a),
        "one_split": (a, midpoint_ab, b, c, d),
        "two_splits": (a, midpoint_ab, b, midpoint_bc, c, d),
    }[variant]
    claim = _two_source_floors(second_ring=ring, reverse=reverse_order)
    assert len(publish_live_floor_area_quantities(claim)) == 2
    before = (claim.canonical_floors, claim.room_area_quantity_evidence)
    for consumer in _consumers():
        with pytest.raises(SourceClosedRunConflictError,
                           match="same original physical floor face"):
            consumer(claim)
    assert (claim.canonical_floors, claim.room_area_quantity_evidence) == before


@pytest.mark.parametrize("offset", (10.0, 20.0))
def test_adjacent_or_distinct_original_floor_faces_keep_own_signed_customer_rows(offset):
    original = _floor().polygon_pdf_pts
    adjacent = tuple((x+offset, y) for x, y in original)
    claim = _two_source_floors(second_ring=adjacent)
    quantities = publish_live_floor_area_quantities(claim)
    traces = _consumers()[0](claim)
    sealed = _consumers()[1](claim)
    customer = _consumers()[2](claim)
    assert len(quantities) == len(traces) == len(sealed.quantities) == len(customer) == 2
    assert {q.quantity_id for q in quantities} == set(traces)
    assert {row["quantity_id"] for row in customer} == set(traces)
    assert verify_sealed_customer_output(sealed, customer).valid_quantity_count == 2


@pytest.mark.parametrize("different", ("page", "viewport"))
def test_same_coordinates_on_different_original_source_views_are_not_aliases(
    different,
):
    claim = _two_source_floors(
        second_page="2" if different == "page" else "1",
        second_viewport="vp-2" if different == "viewport" else "vp-1",
    )
    assert len(publish_live_floor_area_quantities(claim)) == 2
    assert len(_consumers()[0](claim)) == 2
    assert len(_consumers()[1](claim).quantities) == 2


def test_existing_one_original_firm_floor_remains_byte_identical():
    one = _source_area()
    one = replace(one, metadata={
        **dict(one.metadata),
        "figured_dimension_ids": ("a-horizontal", "a-vertical"),
    })
    claim = _claim_with(one)
    first = _consumers()[1](claim)
    second = _consumers()[1](claim)
    rows1 = _consumers()[2](claim)
    rows2 = _consumers()[2](claim)
    assert first.to_json() == second.to_json()
    assert rows1 == rows2
    assert len(first.quantities) == len(rows1) == 1
    assert verify_sealed_customer_output(first, rows1).valid_quantity_count == 1
