"""The real floor-finish seal requires an exact original physical room-face ID.

A valid material occurrence and documented m² cannot replace the producer's
room-face source receipt. This is a negative source-lineage gate, not a new
measurement, room/finish inference, or original-PDF verification.
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
    _quantity,
)


@pytest.mark.parametrize("floor_face,receipt_face", (
    ("", ""),
    (" ", " "),
    (None, None),
    (True, True),
    (7, 7),
    (" face-1", "face-1"),
    ("face-1", " face-1"),
    ("face-1 ", "face-1 "),
))
def test_matching_missing_or_coerced_room_face_never_seals_a_finish(
    floor_face, receipt_face,
):
    floor = replace(_floor(), source_room_face_record_id=floor_face)
    original = _quantity()
    quantity = replace(
        original,
        metadata={
            **dict(original.metadata),
            "source_room_face_record_id": receipt_face,
        },
    )
    claim = replace(
        _claim(floor),
        floor_finish_quantity_evidence=(quantity,),
    )
    before = claim.floor_finish_quantity_evidence
    for issuer in (
        build_live_floor_finish_area_source_traces,
        seal_live_floor_finish_area_run,
        project_live_floor_finish_customer_rows,
    ):
        with pytest.raises(
            SourceClosedRunConflictError, match="source room face mismatch"
        ):
            issuer(claim, workspace_id=7, project_id="source-project")
    assert claim.floor_finish_quantity_evidence == before
    assert claim.canonical_floors == (floor,)


def test_producer_shaped_exact_room_face_keeps_signed_and_customer_output():
    claim = _claim()
    original_source = claim.floor_finish_quantity_evidence
    first = seal_live_floor_finish_area_run(
        claim, workspace_id=7, project_id="source-project",
    )
    second = seal_live_floor_finish_area_run(
        claim, workspace_id=7, project_id="source-project",
    )
    rows = project_live_floor_finish_customer_rows(
        claim, workspace_id=7, project_id="source-project",
    )
    assert len(first.quantities) == len(rows) == 1
    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint
    assert first.quantities[0].value == 8.64
    assert rows[0]["finish_system"] == "FT1 (tile)"
    assert verify_sealed_customer_output(first, rows).verified_quantity_ids == (
        original_source[0].quantity_id,
    )
    assert claim.floor_finish_quantity_evidence == original_source
    assert claim.canonical_floors == (_floor(),)
