"""Real customer projection must never silently omit numeric source blockers.

These are source-neutral negative invariants, not new source/metric authority.
"""
from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_floor_finish_area_source_closed_export import _claim, _quantity


def _project(quantities):
    claim = replace(_claim(), floor_finish_quantity_evidence=tuple(quantities))
    return project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1"
    )


def _blocked_positive():
    original = _quantity()
    # QuantityEvidence explicitly permits this stale/contradictory producer
    # shape: FIRM numeric, not ABSTAINED, but with a retained blocking reason.
    return replace(
        original, blocking_reasons=("original_finish_owner_unresolved",)
    )


def test_numeric_firm_with_blocker_must_not_disappear_as_empty_customer():
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project((_blocked_positive(),))


@pytest.mark.parametrize("blocked_first", [True, False])
def test_mixed_positive_and_blocked_inventory_cannot_silently_omit_member(
    blocked_first,
):
    valid = _quantity()
    blocked = replace(_blocked_positive(), quantity_id="blocked-source-member")
    members = (blocked, valid) if blocked_first else (valid, blocked)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project(members)


def test_abstained_unrelated_original_remains_legitimate_customer_exclusion():
    valid = _quantity()
    blocked = replace(
        valid,
        quantity_id="abstained-other-original",
        value=None,
        status=AuthorityStatus.BLOCKED.value,
        abstained=True,
        blocking_reasons=("original_finish_owner_unresolved",),
        metadata={
            **dict(valid.metadata),
            "finish_occurrence_record_id": "occ-other",
            "finish_occurrence_evidence_id": "ev-other",
        },
    )
    rows = _project((blocked, valid))
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == valid.quantity_id


def test_valid_original_positive_customer_row_unchanged():
    rows = _project((_quantity(),))
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == "floor-finish-q1"


def test_customer_veto_does_not_mutate_original_source_inventory():
    original = _blocked_positive()
    claim = replace(_claim(), floor_finish_quantity_evidence=(original,))
    before = (claim.floor_finish_quantity_evidence, original.metadata)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        project_live_floor_finish_customer_rows(
            claim, workspace_id=1, project_id="project-1"
        )
    assert (claim.floor_finish_quantity_evidence, original.metadata) == before
