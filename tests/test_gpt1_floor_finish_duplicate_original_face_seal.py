"""Real floor-finish seal must not reissue one physical PDF face twice.

This is a negative-only original-face ownership gate. It neither measures
floor finishes nor authenticates the PDF bytes used by the source producer.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
    seal_live_floor_finish_area_run,
)
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import (
    _claim,
    _floor,
    _two_original_floor_finish_claims,
)


def _independent_floor_pair(*, ring=None, page="1", viewport="vp-1"):
    """Independent original face/area/finish receipts, not reused mark IDs."""
    claim = _two_original_floor_finish_claims(
        second_occurrence="occ-2",
        second_observation="ev-occ-2",
    )
    first_floor, second_floor = claim.canonical_floors
    first_quantity, second_quantity = claim.floor_finish_quantity_evidence
    second_floor = replace(
        second_floor,
        polygon_pdf_pts=(
            tuple(ring) if ring is not None else second_floor.polygon_pdf_pts
        ),
        metric_area_quantity_id="room-area-2",
        evidence_ids=("ev-room-2", "ev-area-2", "ev-occ-2", "ev-def-2"),
        page_id=page,
        viewport_id=viewport,
    )
    second_quantity = replace(
        second_quantity,
        evidence_ids=("ev-area-2", "ev-occ-2", "ev-def-2"),
        metadata={
            **dict(second_quantity.metadata),
            "page_no": page,
            "viewport_id": viewport,
            "finish_definition_record_id": "def-2",
        },
    )
    return replace(
        claim,
        canonical_floors=(first_floor, second_floor),
        floor_finish_quantity_evidence=(first_quantity, second_quantity),
    )


def _real_issuers():
    return (
        build_live_floor_finish_area_source_traces,
        seal_live_floor_finish_area_run,
        project_live_floor_finish_customer_rows,
    )


@pytest.mark.parametrize("variant", (
    "same", "rotated", "reversed", "closed", "one_split", "two_splits",
))
@pytest.mark.parametrize("reverse_order", (False, True))
def test_independent_finish_receipts_cannot_double_claim_same_original_face(
    variant, reverse_order,
):
    a, b, c, d = _floor().polygon_pdf_pts
    midpoint_ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    midpoint_bc = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
    original = (a, b, c, d)
    ring = {
        "same": original,
        "rotated": (c, d, a, b),
        "reversed": (d, c, b, a),
        "closed": original + (a,),
        "one_split": (a, midpoint_ab, b, c, d),
        "two_splits": (a, midpoint_ab, b, midpoint_bc, c, d),
    }[variant]
    claim = _independent_floor_pair(ring=ring)
    if reverse_order:
        claim = replace(
            claim,
            canonical_floors=tuple(reversed(claim.canonical_floors)),
            floor_finish_quantity_evidence=tuple(
                reversed(claim.floor_finish_quantity_evidence)
            ),
        )
    before_floors = claim.canonical_floors
    before_quantities = claim.floor_finish_quantity_evidence
    for issuer in _real_issuers():
        with pytest.raises(
            SourceClosedRunConflictError,
            match="same original physical floor face",
        ):
            issuer(claim, workspace_id=7, project_id="source-project")
    assert claim.canonical_floors == before_floors
    assert claim.floor_finish_quantity_evidence == before_quantities


@pytest.mark.parametrize("offset", (10.0, 20.0))
def test_distinct_and_adjacent_original_floor_faces_both_reach_customer(offset):
    original = _floor().polygon_pdf_pts
    other = tuple((x + offset, y) for x, y in original)
    claim = _independent_floor_pair(ring=other)
    traces = build_live_floor_finish_area_source_traces(
        claim, workspace_id=7, project_id="source-project",
    )
    signed = seal_live_floor_finish_area_run(
        claim, workspace_id=7, project_id="source-project",
    )
    rows = project_live_floor_finish_customer_rows(
        claim, workspace_id=7, project_id="source-project",
    )
    assert set(traces) == {"floor-finish-q1", "floor-finish-q2"}
    assert len(signed.quantities) == len(rows) == 2
    assert {row["quantity_id"] for row in rows} == set(traces)
    assert verify_sealed_customer_output(signed, rows).valid_quantity_count == 2


@pytest.mark.parametrize("different_scope", ("page", "viewport"))
def test_same_coordinates_in_independent_source_views_remain_publishable(
    different_scope,
):
    claim = _independent_floor_pair(
        page="2" if different_scope == "page" else "1",
        viewport="vp-2" if different_scope == "viewport" else "vp-1",
    )
    signed = seal_live_floor_finish_area_run(
        claim, workspace_id=7, project_id="source-project",
    )
    rows = project_live_floor_finish_customer_rows(
        claim, workspace_id=7, project_id="source-project",
    )
    assert len(signed.quantities) == len(rows) == 2


def test_existing_signed_and_customer_floor_finish_bodies_stay_identical():
    claim = _claim()
    first = seal_live_floor_finish_area_run(
        claim, workspace_id=7, project_id="source-project",
    )
    second = seal_live_floor_finish_area_run(
        claim, workspace_id=7, project_id="source-project",
    )
    rows1 = project_live_floor_finish_customer_rows(
        claim, workspace_id=7, project_id="source-project",
    )
    rows2 = project_live_floor_finish_customer_rows(
        claim, workspace_id=7, project_id="source-project",
    )
    assert first.to_json() == second.to_json()
    assert rows1 == rows2
    assert len(first.quantities) == len(rows1) == 1
    assert verify_sealed_customer_output(first, rows1).valid_quantity_count == 1
