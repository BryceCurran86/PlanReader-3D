"""Room customer must source-audit all original receipts before empty selection.

No source geometry, new quantity, benchmark, or customer authority is minted.
"""
from dataclasses import replace

import pytest

from pb_live_room_area_customer_projection import project_live_room_area_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from test_live_floor_finish_area_source_closed_export import _claim
from tests.test_gpt1_room_area_customer_exact_semantic_owner import (
    _quantity as _source_room_quantity,
)


def _customer(inventory):
    claim = replace(_claim(), room_area_quantity_evidence=tuple(inventory))
    return project_live_room_area_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )


def _abstained():
    return replace(
        _source_room_quantity(), value=None, abstained=True,
        status="blocked", blocking_reasons=("original_room_unresolved",),
    )


def test_legitimate_all_abstained_original_room_customer_remains_empty():
    assert _customer((_abstained(),)) == ()


def test_duplicate_all_abstained_original_room_source_id_fails_customer():
    record = _abstained()
    with pytest.raises(SourceClosedRunConflictError, match="duplicate room-area quantity id"):
        _customer((record, record))


@pytest.mark.parametrize("invalid", ("foreign_family", "foreign_object", "padded_id", "blank_id"))
def test_all_abstained_invalid_original_room_receipt_cannot_be_hidden(invalid):
    record = _abstained()
    if invalid == "foreign_family":
        record = replace(record, family="ceiling_lining")
    elif invalid == "foreign_object":
        record = object()
    elif invalid == "padded_id":
        record = replace(record, quantity_id=" original-source-padded ")
    else:
        record = replace(record)
        object.__setattr__(record, "quantity_id", "")
    error = TypeError if invalid == "foreign_object" else SourceClosedRunConflictError
    with pytest.raises(error):
        _customer((record,))


def test_nonabstained_numeric_blocked_room_source_does_not_disappear():
    invalid = replace(
        _source_room_quantity(),
        blocking_reasons=("original_figured_area_conflict",),
    )
    with pytest.raises(SourceClosedRunConflictError, match="lacks admissible metric authority"):
        _customer((invalid,))


def test_preflight_source_error_does_not_mutate_original_room_inventory():
    record = _abstained()
    claim = replace(_claim(), room_area_quantity_evidence=(record, record))
    before = claim.room_area_quantity_evidence
    with pytest.raises(SourceClosedRunConflictError, match="duplicate room-area quantity id"):
        project_live_room_area_customer_rows(
            claim, workspace_id=1, project_id="project-1",
        )
    assert claim.room_area_quantity_evidence == before
