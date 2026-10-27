"""GPT1 RCP semantic-source IDs must survive exact through actual customer seal.

These tests are negative source-integrity proofs only. They do not grant
physical room/ceiling geometry, RCP finish or measured m2 authority.
"""
from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_lining_source_closed_export import _claim, _quantity


CONSUMERS = (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
    project_live_ceiling_customer_rows,
)
SUPPORT_FIELDS = (
    "support_snapshot_id", "support_page_id", "support_viewport_id",
)


@pytest.mark.parametrize("field", SUPPORT_FIELDS)
@pytest.mark.parametrize("forged", (
    None, True, 7, " ", " padded-source ", ["support"],
))
def test_replayed_ceiling_cannot_launder_rcp_support_receipt(field, forged):
    original = _quantity()
    changed = replace(original, metadata={**original.metadata, field: forged})
    claim = _claim(changed)
    original_metadata = dict(changed.metadata)
    for consumer in CONSUMERS:
        with pytest.raises(
            SourceClosedRunConflictError,
            match="exact semantic support lineage",
        ):
            consumer(claim, workspace_id=1, project_id="project-1")
        assert dict(changed.metadata) == original_metadata
    assert claim.ceiling_lining_quantity_evidence == (changed,)


def test_exact_rcp_support_receipts_preserve_signed_customer_body():
    source = _quantity()
    claim = _claim(source)
    first = seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1",
    )
    first_rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(first.quantities) == len(first_rows) == 1
    assert verify_sealed_customer_output(first, first_rows).valid_quantity_count == 1
    for field in SUPPORT_FIELDS:
        assert first_rows[0]["quantity_id"] == source.quantity_id
        assert isinstance(source.metadata[field], str)
        assert source.metadata[field] == source.metadata[field].strip()
    assert first_rows == project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert first == seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1",
    )


def test_immutable_valid_rcp_support_metadata_keeps_exact_customer_rows():
    source = _quantity()
    immutable = replace(source, metadata=MappingProxyType(dict(source.metadata)))
    baseline = project_live_ceiling_customer_rows(
        _claim(source), workspace_id=1, project_id="project-1",
    )
    assert project_live_ceiling_customer_rows(
        _claim(immutable), workspace_id=1, project_id="project-1",
    ) == baseline
