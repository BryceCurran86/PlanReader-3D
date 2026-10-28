"""Independent original ROOM_AREA claims cannot re-use one physical PDF ring.

The synthetic PDF-backed production fixture proves real input/issuer wiring,
but does NOT provide a private original source or a new measured quantity.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from shapely.geometry import Polygon

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_room_area_source_closed_export import (
    _firm_room_area_quantities,
    build_live_room_area_source_traces,
    seal_live_room_area_run,
)
from pb_live_room_area_customer_projection import project_live_room_area_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_room_area_source_closed_export import (
    live_claim,
    _second_original_figured_room,
    _firm_quantity,
    _resolved_floor,
)


def _competing_room_claim(live_claim, *, variant="same", reverse=False):
    claim = _second_original_figured_room(live_claim, same_root=True)
    # A real original drawing may have two independently authenticated
    # figured dimension pairs. Their distinct receipts alone cannot prove
    # different physical room faces.
    original = _firm_quantity(live_claim)
    second = next(q for q in claim.room_area_quantity_evidence
                  if q.quantity_id == "independent-figured-room-area")
    second = replace(
        second,
        evidence_ids=tuple((*second.evidence_ids, "independent-axes-receipt")),
        metadata={
            **dict(second.metadata),
            "figured_dimension_ids": (
                "independent-original-horizontal",
                "independent-original-vertical",
            ),
        },
    )
    first_floor = _resolved_floor(live_claim)
    ring = tuple(first_floor.polygon_pdf_pts)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 4:
        raise AssertionError("expected original fixture four-corner physical floor")
    a, b, c, d, *rest = ring
    if rest:
        # Use the source's own ring for the unchanged case.
        if variant not in ("same", "rotated", "reversed", "closed"):
            raise AssertionError("unexpected source ring shape")
    mid_ab = ((a[0]+b[0])/2, (a[1]+b[1])/2)
    alternate = {
        "same": ring,
        "rotated": ring[2:] + ring[:2],
        "reversed": tuple(reversed(ring)),
        "closed": ring + (ring[0],),
        "collinear": (a, mid_ab, *ring[1:]),
        "adjacent": tuple((x + 10.0, y) for x, y in ring),
    }[variant]
    floor2 = next(f for f in claim.canonical_floors
                  if f.metric_area_quantity_id == second.quantity_id)
    room2 = next(room for room in claim.canonical_rooms
                 if room.canonical_room_id == floor2.room_entity_id)
    floor2 = replace(
        floor2,
        polygon_pdf_pts=tuple(alternate),
        evidence_ids=tuple((*floor2.evidence_ids, "independent-axes-receipt")),
    )
    room2 = replace(room2, polygon_pdf_pts=tuple(alternate))
    source_rows = tuple(second if q.quantity_id == second.quantity_id else q
                        for q in claim.room_area_quantity_evidence)
    floors = tuple(floor2 if f.canonical_floor_id == floor2.canonical_floor_id else f
                   for f in claim.canonical_floors)
    rooms = tuple(room2 if q.canonical_room_id == room2.canonical_room_id else q
                  for q in claim.canonical_rooms)
    if reverse:
        source_rows = tuple(reversed(source_rows))
        floors = tuple(reversed(floors))
        rooms = tuple(reversed(rooms))
    return replace(
        claim,
        room_area_quantity_evidence=source_rows,
        canonical_floors=floors,
        canonical_rooms=rooms,
    )


def _trace(claim):
    return build_live_room_area_source_traces(
        claim, workspace_id=7, project_id="source-room-geometry",
    )


def _seal(claim):
    return seal_live_room_area_run(
        claim, workspace_id=7, project_id="source-room-geometry",
    )


def _customer(claim):
    return project_live_room_area_customer_rows(
        claim, workspace_id=7, project_id="source-room-geometry",
    )


@pytest.mark.parametrize("variant", ("same", "rotated", "reversed", "closed", "collinear"))
@pytest.mark.parametrize("reverse", (False, True))
def test_independently_figured_original_room_claim_cannot_sell_same_pdf_face(
    live_claim, variant, reverse,
):
    claim = _competing_room_claim(live_claim, variant=variant, reverse=reverse)
    firm = _firm_room_area_quantities(claim)
    assert len(firm) == 2
    original_source = claim.room_area_quantity_evidence
    original_floors = claim.canonical_floors
    for consumer in (_trace, _seal, _customer):
        with pytest.raises(
            SourceClosedRunConflictError,
            match="same physical PDF room face",
        ):
            consumer(claim)
    assert claim.room_area_quantity_evidence == original_source
    assert claim.canonical_floors == original_floors


def test_independent_source_rooms_with_different_pdf_faces_retain_signed_customer(
    live_claim,
):
    claim = _competing_room_claim(live_claim, variant="adjacent")
    traces = _trace(claim)
    signed = _seal(claim)
    customer = _customer(claim)
    assert len(traces) == len(signed.quantities) == len(customer) == 2
    assert verify_sealed_customer_output(signed, customer).valid_quantity_count == 2


def test_independent_source_document_with_reused_coordinate_ring_remains_distinct(
    live_claim,
):
    # Existing main's actual synthetic PDF-derived fixture deliberately uses
    # another source SHA/revision/document for its second physical room.
    claim = _second_original_figured_room(live_claim, same_root=False)
    assert len(_trace(claim)) == 2
    assert len(_seal(claim).quantities) == 2


def test_one_original_room_area_sealed_output_is_unchanged(live_claim):
    first, replay = _seal(live_claim), _seal(live_claim)
    rows = _customer(live_claim)
    assert first.to_json() == replay.to_json()
    assert len(first.quantities) == len(rows) == 1
    assert verify_sealed_customer_output(first, rows).valid_quantity_count == 1
