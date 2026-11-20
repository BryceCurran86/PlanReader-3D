"""Source-independent ceiling customer exclusion guards on both live paths."""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows, _customer_quantity,
)
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import (
    _result as legacy_result, _shadow_quantity,
)
from test_live_ceiling_lining_source_closed_export import _claim, _quantity


def _project(source, variant):
    if variant == "canonical":
        claim = replace(_claim(source), ceiling_lining_quantity_evidence=(source,))
        return project_live_ceiling_customer_rows(
            claim, workspace_id=3, project_id="arbitrary-building",
        )
    original = replace(legacy_result(), quantity_evidence=(source,))
    return project_live_ceiling_area_customer_rows(
        original, workspace_id=3, project_id="arbitrary-building",
    )


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
@pytest.mark.parametrize("scope", ["EXCLUSION", "EXCLUDED", "ABSTAIN", "REVIEW", "", 12, True])
def test_excluded_or_unresolved_original_ceiling_cannot_be_included(variant, scope):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "inclusion_status": scope,
    })
    with pytest.raises(
        SourceClosedRunConflictError,
        match="customer_source_inclusion_scope_unresolved",
    ):
        _project(source, variant)


@pytest.mark.parametrize("variant", ["canonical", "legacy"])
def test_source_inclusion_still_produces_authorised_ceiling_customer(variant):
    source = _quantity() if variant == "canonical" else _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "inclusion_status": "INCLUSION",
    })
    rows = _project(source, variant)
    assert len(rows) == 1
    assert rows[0]["quantity_family"] == "ceiling_lining"
    if variant == "canonical":
        assert rows[0]["quantity_id"] == source.quantity_id


def test_direct_legacy_adapter_cannot_overwrite_exclusion():
    source = _shadow_quantity()
    source = replace(source, metadata={
        **dict(source.metadata), "inclusion_status": "EXCLUSION",
    })
    with pytest.raises(SourceClosedRunConflictError):
        _customer_quantity(
            source, room_entity_id="arbitrary-room", finish_descriptor="acoustic",
        )
