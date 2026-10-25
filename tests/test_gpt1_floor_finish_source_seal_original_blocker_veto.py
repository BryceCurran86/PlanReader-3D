"""Fail-closed real floor-finish source sealing for contradictory original numeric evidence.

Source-neutral authority regression. No original PDF, new FIRM or benchmark data.
"""
from dataclasses import replace

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
    seal_live_floor_finish_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import _claim, _quantity


def _traces(claim):
    return build_live_floor_finish_area_source_traces(
        claim, workspace_id=1, project_id="source-owned-floor-finish"
    )


def _seal(claim):
    return seal_live_floor_finish_area_run(
        claim, workspace_id=1, project_id="source-owned-floor-finish"
    )


@pytest.mark.parametrize("mixed", (False, True))
@pytest.mark.parametrize("reverse", (False, True))
def test_original_numeric_blocker_is_rejected_before_direct_source_seal(mixed, reverse):
    valid = _quantity()
    blocked = replace(
        valid,
        quantity_id="original-blocked-finish-source",
        blocking_reasons=("unresolved_original_material_owner",),
    )
    originals = (valid, blocked) if mixed else (blocked,)
    if reverse:
        originals = tuple(reversed(originals))
    claim = replace(_claim(), floor_finish_quantity_evidence=originals)
    for consumer in (_traces, _seal):
        with pytest.raises(
            SourceClosedRunConflictError,
            match="numeric floor-finish source quantity retains unresolved blockers",
        ):
            consumer(claim)
    assert claim.floor_finish_quantity_evidence == originals
    assert blocked.blocking_reasons == ("unresolved_original_material_owner",)


@pytest.mark.parametrize("reverse", (False, True))
def test_independent_original_abstention_still_preserves_valid_seal(reverse):
    valid = _quantity()
    abstained = replace(
        valid,
        quantity_id="independent-original-unresolved-finish",
        value=None,
        abstained=True,
        status="provisional",
        blocking_reasons=("unresolved_other_material_owner",),
        metadata={
            **dict(valid.metadata),
            "finish_occurrence_record_id": "other-original-mark",
            "finish_occurrence_evidence_id": "other-original-observation",
        },
    )
    originals = (valid, abstained)
    if reverse:
        originals = tuple(reversed(originals))
    claim = replace(_claim(), floor_finish_quantity_evidence=originals)
    traces = _traces(claim)
    assert tuple(traces) == (valid.quantity_id,)
    sealed = _seal(claim)
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].quantity_id == valid.quantity_id
    assert claim.floor_finish_quantity_evidence == originals


def test_abstained_only_original_does_not_raise_false_numeric_conflict():
    original = _quantity()
    abstained = replace(
        original,
        value=None,
        abstained=True,
        status="provisional",
        blocking_reasons=("unresolved_original_material_owner",),
    )
    claim = replace(_claim(), floor_finish_quantity_evidence=(abstained,))
    assert _traces(claim) == {}
    assert claim.floor_finish_quantity_evidence == (abstained,)


def test_duplicate_original_ids_precede_numeric_blocker_veto():
    valid = _quantity()
    blocked = replace(
        valid, blocking_reasons=("unresolved_original_material_owner",),
    )
    claim = replace(_claim(), floor_finish_quantity_evidence=(blocked, valid))
    with pytest.raises(
        SourceClosedRunConflictError,
        match="duplicate original floor-finish quantity id",
    ):
        _traces(claim)
