"""Original ceiling source inventory must remain complete at customer boundary.

Only negative source-integrity invariants. No new ceiling authority or m².
"""
from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_ceiling_lining_source_closed_export import _claim, _quantity


def _project(inventory):
    source = _quantity()
    claim = replace(
        _claim(source), ceiling_lining_quantity_evidence=tuple(inventory),
    )
    return project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )


def _abstained(quantity):
    return replace(
        quantity, status=AuthorityStatus.BLOCKED.value,
        abstained=True, value=None,
        blocking_reasons=("original_source_unresolved",),
    )


def test_original_ceiling_valid_firm_still_projects_one_customer():
    valid = _quantity()
    rows = _project((valid,))
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == valid.quantity_id


def test_legitimate_original_abstained_only_inventory_returns_empty():
    assert _project((_abstained(_quantity()),)) == ()


@pytest.mark.parametrize("invalid", ("wrong_family", "foreign_type", "blank_id", "padded_id"))
def test_invalid_original_ceiling_inventory_cannot_be_silently_filtered(invalid):
    original = _abstained(_quantity())
    if invalid == "wrong_family":
        source = replace(original, family="floor_finish_area")
    elif invalid == "foreign_type":
        source = object()
    elif invalid == "padded_id":
        source = replace(original, quantity_id=" padded-original-id ")
    else:
        source = replace(original)
        object.__setattr__(source, "quantity_id", "")
    error = TypeError if invalid == "foreign_type" else SourceClosedRunConflictError
    with pytest.raises(error):
        _project((source,))


def test_duplicate_abstained_ceiling_source_id_never_becomes_empty_customer():
    source = _abstained(_quantity())
    with pytest.raises(SourceClosedRunConflictError, match="duplicate or invalid"):
        _project((source, source))


@pytest.mark.parametrize("blocked_first", (True, False))
def test_numeric_ceiling_with_blockers_never_vanishes_from_mixed_customer(
    blocked_first,
):
    valid = _quantity()
    broken = replace(
        valid, quantity_id="numeric-ceiling-with-blockers",
        blocking_reasons=("room_ceiling_owner_unresolved",),
    )
    inventory = (broken, valid) if blocked_first else (valid, broken)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project(inventory)


def test_numeric_blocked_only_ceiling_does_not_return_empty_customer():
    broken = replace(
        _quantity(), blocking_reasons=("original_rcp_finish_unresolved",),
    )
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project((broken,))


def test_separate_abstained_ceiling_does_not_hide_valid_source_customer():
    valid = _quantity()
    other = _abstained(
        replace(
            valid, quantity_id="independent-abstained-ceiling",
            metadata={
                **dict(valid.metadata),
                "finish_occurrence_record_id": "independent-mark",
                "finish_occurrence_evidence_id": "independent-observation",
            },
        )
    )
    rows = _project((other, valid))
    assert len(rows) == 1
    assert rows[0]["quantity_id"] == valid.quantity_id


def test_ceiling_customer_veto_does_not_mutate_source_inventory():
    broken = replace(
        _quantity(), blocking_reasons=("original_source_unresolved",),
    )
    original = (broken, dict(broken.metadata), tuple(broken.blocking_reasons))
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        _project((broken,))
    assert (broken, dict(broken.metadata), tuple(broken.blocking_reasons)) == original
