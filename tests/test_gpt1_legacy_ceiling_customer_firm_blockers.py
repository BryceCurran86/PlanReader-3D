"""Legacy ceiling customer must not hide contradictory original FIRM claims."""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import _result, _shadow_quantity


def _project(source_inventory):
    result = replace(_result(), quantity_evidence=tuple(source_inventory))
    return project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )


def _contradictory_firm():
    return replace(
        _shadow_quantity(),
        status="firm",
        blocking_reasons=("original_orthogonal_dimension_unresolved",),
    )


def test_numeric_firm_ceiling_with_blocker_must_not_look_like_empty_customer():
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project((_contradictory_firm(),))


@pytest.mark.parametrize("blocked_first", [True, False])
def test_mixed_provisional_and_contradictory_firm_preserves_completeness(blocked_first):
    valid = _shadow_quantity()
    broken = replace(
        _contradictory_firm(), quantity_id="other-source-blocked-firm",
    )
    inventory = (broken, valid) if blocked_first else (valid, broken)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project(inventory)


def test_ordinary_provisional_unresolved_source_stays_nonpublishing():
    original = _shadow_quantity()
    blocked = replace(
        original,
        blocking_reasons=("source_orthogonal_dimension_unresolved",),
    )
    assert blocked.status == "provisional"
    assert _project((blocked,)) == ()


def test_unrelated_provisional_unresolved_source_preserves_legitimate_customer():
    valid = _shadow_quantity()
    blocked = replace(
        valid,
        quantity_id="unrelated-provisional-original-ceiling",
        blocking_reasons=("source_original_area_unavailable",),
    )
    rows = _project((blocked, valid))
    assert len(rows) == 1
    assert rows[0]["quantity_family"] == "ceiling_lining"


def test_existing_authentic_legacy_ceiling_customer_preserved():
    rows = _project((_shadow_quantity(),))
    assert len(rows) == 1
    assert rows[0]["quantity_family"] == "ceiling_lining"


def test_legacy_ceiling_blocker_rejection_does_not_mutate_original_source():
    broken = _contradictory_firm()
    original = (broken, broken.metadata, broken.blocking_reasons)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project((broken,))
    assert (broken, broken.metadata, broken.blocking_reasons) == original
