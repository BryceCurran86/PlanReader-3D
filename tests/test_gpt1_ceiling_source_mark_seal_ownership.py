"""Original RCP mark source receipts survive ceiling-to-customer publication."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_lining_source_closed_export import (
    _claim,
    _room,
    _quantity,
    _canonical_ceiling,
)


def _traces(claim):
    return build_live_ceiling_lining_source_traces(
        claim, workspace_id=1, project_id="project-1"
    )


def _two_source_owned_ceiling_quantities(
    *, same_original_mark=False, same_occurrence=False,
):
    first = _quantity()
    second_mark = "occ-evidence" if same_original_mark else "second-source-mark"
    second = replace(
        first,
        quantity_id="qty-ceiling-2",
        semantic_key="ceiling_lining:ceiling-2:GRID:ceiling_grid",
        value=7.0,
        input_entity_ids=("ceiling-2",),
        evidence_ids=(
            "room-evidence-2", "room-label-evidence-2",
            "area-evidence-2", second_mark, "def-evidence",
        ),
        metadata={
            **dict(first.metadata),
            "canonical_ceiling_id": "ceiling-2",
            "physical_ceiling_surface_id": "ceiling-2",
            "canonical_room_id": "canonical-room-2",
            "physical_room_id": "physical-room-2",
            "source_room_face_record_id": "face-2",
            "source_room_index_id": "room-index-2",
            "upstream_room_area_quantity_id": "room-area-qty-2",
            "room_area_quantity_id": "room-area-qty-2",
            "figured_dimension_ids": ["second-dim-h", "second-dim-v"],
            "finish_occurrence_record_id": (
                "occ-grid" if same_occurrence else "second-occurrence"
            ),
            "finish_occurrence_evidence_id": second_mark,
        },
    )
    second_ceiling = replace(
        _canonical_ceiling(second, area=7.0),
        canonical_ceiling_id="ceiling-2",
        room_entity_id="canonical-room-2",
        ceiling_quantity_id="qty-ceiling-2",
        room_area_quantity_id="room-area-qty-2",
        source_room_index_id="room-index-2",
        figured_dimension_ids=("second-dim-h", "second-dim-v"),
        evidence_ids=tuple(second.evidence_ids),
        polygon_pdf_pts=((120., 20.), (180., 20.), (180., 100.), (120., 100.)),
    )
    second_room = replace(
        _room(),
        canonical_room_id="canonical-room-2",
        physical_room_id="physical-room-2",
        source_room_face_record_id="face-2",
        decision_scope_id="scope-2",
        room_label="SECOND ROOM",
        evidence_ids=("room-evidence-2",),
        room_label_binding_record_id="label-binding-2",
        room_label_evidence_ids=("room-label-evidence-2",),
    )
    base = _claim(first)
    return replace(
        base,
        canonical_rooms=(*base.canonical_rooms, second_room),
        canonical_ceilings=(*base.canonical_ceilings, second_ceiling),
        ceiling_lining_quantity_evidence=(first, second),
    )


def test_unmodified_original_ceilings_still_source_seal_and_project():
    quantity = _quantity()
    claim = _claim(quantity)
    assert set(_traces(claim)) == {"qty-ceiling-1"}
    sealed = seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1"
    )
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].quantity_id == quantity.quantity_id
    assert sealed.quantities[0].value == 9.05352


def test_two_independent_source_owned_rcp_marks_can_seal_two_ceilings():
    claim = _two_source_owned_ceiling_quantities()
    traces = _traces(claim)
    assert set(traces) == {"qty-ceiling-1", "qty-ceiling-2"}


@pytest.mark.parametrize("reverse", [False, True])
def test_rekeyed_original_source_mark_cannot_mint_two_ceiling_quantities(reverse):
    claim = _two_source_owned_ceiling_quantities(same_original_mark=True)
    if reverse:
        claim = replace(
            claim, ceiling_lining_quantity_evidence=tuple(
                reversed(claim.ceiling_lining_quantity_evidence)
            ),
        )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="original RCP material mark has competing ceilings",
    ):
        _traces(claim)


@pytest.mark.parametrize("key", [
    "finish_occurrence_record_id",
    "finish_occurrence_evidence_id",
    "finish_definition_record_id",
    "finish_code",
    "semantic_finish",
])
@pytest.mark.parametrize("bad", [None, True, 12, "", " padded", "padded "])
def test_material_issuer_ids_cannot_be_coerced_or_trimmed(key, bad):
    q = _quantity()
    changed = replace(q, metadata={**q.metadata, key: bad})
    with pytest.raises(SourceClosedRunConflictError):
        _traces(_claim(changed))


def test_missing_original_mark_witness_on_quantity_blocks_customer_seal():
    original = _quantity()
    stripped = replace(
        original,
        evidence_ids=tuple(x for x in original.evidence_ids if x != "occ-evidence"),
    )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="material occurrence source receipt mismatch",
    ):
        _traces(_claim(stripped))


def test_missing_original_mark_witness_on_canonical_ceiling_blocks_seal():
    original = _quantity()
    ceiling = replace(
        _canonical_ceiling(original),
        evidence_ids=("room-evidence", "room-label-evidence",
                      "area-evidence", "def-evidence"),
    )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="canonical ceiling trace does not cover quantity evidence",
    ):
        _traces(_claim(original, canonical_ceiling=ceiling))


def test_source_receipt_verification_is_idempotent_and_does_not_mutate_evidence():
    claim = _claim(_quantity())
    original = claim.ceiling_lining_quantity_evidence
    first = _traces(claim)
    assert first == _traces(claim)
    assert claim.ceiling_lining_quantity_evidence == original


@pytest.mark.parametrize("reverse", [False, True])
def test_producer_occurrence_id_reused_for_different_marks_cannot_seal(reverse):
    claim = _two_source_owned_ceiling_quantities(same_occurrence=True)
    if reverse:
        claim = replace(
            claim,
            ceiling_lining_quantity_evidence=tuple(
                reversed(claim.ceiling_lining_quantity_evidence)
            ),
        )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="original RCP material mark has competing ceilings",
    ):
        _traces(claim)


