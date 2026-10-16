"""Source-close real original observation ownership; no synthetic FIRM promotions."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import (
    _claim,
    _floor,
    _quantity,
)


def _trace(claim):
    return build_live_floor_finish_area_source_traces(
        claim, workspace_id=1, project_id="project-1",
    )


def _two_independent_floors(*, share_original_observation: bool = False):
    floor1, quantity1 = _floor(), _quantity()
    floor2 = replace(
        floor1,
        canonical_floor_id="floor-2",
        physical_floor_surface_id="floor-2",
        room_entity_id="room-2",
        source_room_face_record_id="face-2",
        metric_area_quantity_id="room-area-2",
        evidence_ids=("ev-room-2", "ev-area-2", "ev-occ-2", "ev-def-2"),
    )
    second_evidence = (
        "ev-occ" if share_original_observation else "ev-occ-2"
    )
    if share_original_observation:
        floor2 = replace(
            floor2, evidence_ids=(*floor2.evidence_ids, second_evidence),
        )
    quantity2 = replace(
        quantity1,
        quantity_id="floor-finish-q2",
        semantic_key="floor_finish_area:floor-2:FT2:tile",
        input_entity_ids=("floor-2",),
        evidence_ids=("ev-area-2", second_evidence, "ev-def-2"),
        metadata={
            **dict(quantity1.metadata),
            "canonical_floor_id": "floor-2",
            "physical_floor_surface_id": "floor-2",
            "source_room_face_record_id": "face-2",
            "finish_code": "FT2",
            "finish_occurrence_record_id": "occ-2",
            "finish_definition_record_id": "def-2",
            "finish_occurrence_evidence_id": second_evidence,
        },
    )
    return replace(
        _claim(),
        canonical_floors=(floor1, floor2),
        floor_finish_quantity_evidence=(quantity1, quantity2),
    )


def test_one_real_floor_source_trace_still_seals_before_customer_hand_off():
    original = _claim()
    assert tuple(_trace(original)) == (original.floor_finish_quantity_evidence[0].quantity_id,)


def test_two_distinct_source_observations_keep_two_distinct_floor_quantities():
    original = _two_independent_floors()
    assert set(_trace(original)) == {"floor-finish-q1", "floor-finish-q2"}


@pytest.mark.parametrize("reverse", [False, True])
def test_one_original_mark_rekeyed_to_two_occurrence_ids_cannot_prove_two_floors(reverse):
    claim = _two_independent_floors(share_original_observation=True)
    if reverse:
        claim = replace(
            claim,
            floor_finish_quantity_evidence=tuple(reversed(claim.floor_finish_quantity_evidence)),
        )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="original observation has competing physical floors",
    ):
        _trace(claim)


@pytest.mark.parametrize("field", [
    "finish_occurrence_record_id",
    "finish_definition_record_id",
    "finish_occurrence_evidence_id",
    "support_snapshot_id",
    "support_page_id",
    "support_viewport_id",
])
@pytest.mark.parametrize("invalid", [True, 37, " missing", "missing ", ""])
def test_noncanonical_or_nonstr_source_issuer_ids_are_not_cast_to_valid_text(field, invalid):
    claim = _claim()
    original = claim.floor_finish_quantity_evidence[0]
    quantity = replace(original, metadata={**dict(original.metadata), field: invalid})
    altered = replace(claim, floor_finish_quantity_evidence=(quantity,))
    # Blank original IDs retain the established first failing source gate
    # (missing occurrence/definition, missing evidence, or missing support).
    # Typed/whitespace corruption is the newly enforced issuer contract.
    reason = (
        None if invalid == "" else "source issuer identity is malformed"
    )
    with pytest.raises(SourceClosedRunConflictError, match=reason):
        _trace(altered)


def test_unchanged_source_inventory_is_not_mutated_by_receipt_validation():
    claim = _claim()
    original = claim.floor_finish_quantity_evidence
    twice = (_trace(claim), _trace(claim))
    assert twice[0] == twice[1]
    assert claim.floor_finish_quantity_evidence == original
