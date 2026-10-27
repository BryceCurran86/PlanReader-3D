"""A contradicted original numeric ceiling must not bypass customer veto at seal.

These tests exercise the real ceiling source trace, direct source-closed seal,
and customer projection. They confer no new geometry or material authority.
"""
from dataclasses import replace

import pytest

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


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_numeric_firm_ceiling_with_unresolved_original_blocker_cannot_seal(consumer):
    original = _quantity()
    conflicted = replace(
        original,
        blocking_reasons=("original_rcp_material_conflict",),
    )
    claim = _claim(conflicted)
    before = (claim.ceiling_lining_quantity_evidence, claim.canonical_ceilings)
    with pytest.raises(SourceClosedRunConflictError, match="unresolved blockers"):
        consumer(claim, workspace_id=1, project_id="project-1")
    assert (claim.ceiling_lining_quantity_evidence, claim.canonical_ceilings) == before


@pytest.mark.parametrize("reverse", (False, True))
def test_unrelated_numeric_blocker_cannot_hide_behind_clean_ceiling(reverse):
    clean = _quantity()
    conflicted = replace(
        clean,
        quantity_id="contradicted-ceiling-source",
        blocking_reasons=("unresolved_original_ceiling",),
        metadata={
            **dict(clean.metadata),
            "finish_occurrence_record_id": "other-occurrence",
            "finish_occurrence_evidence_id": "other-ink",
        },
    )
    originals = (conflicted, clean) if reverse else (clean, conflicted)
    claim = replace(_claim(clean), ceiling_lining_quantity_evidence=originals)
    for consumer in CONSUMERS:
        with pytest.raises(SourceClosedRunConflictError, match="unresolved blockers"):
            consumer(claim, workspace_id=1, project_id="project-1")


def test_duplicate_original_ceiling_identity_precedes_numeric_blocker():
    original = replace(
        _quantity(),
        blocking_reasons=("unresolved_original_ceiling",),
    )
    claim = replace(
        _claim(original),
        ceiling_lining_quantity_evidence=(original, original),
    )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="duplicate or invalid original ceiling-lining quantity id",
    ):
        build_live_ceiling_lining_source_traces(
            claim, workspace_id=1, project_id="project-1"
        )


def test_clean_firm_and_unrelated_true_abstention_preserve_seal_and_customer():
    clean = _quantity()
    blocked = replace(
        clean,
        quantity_id="unrelated-unmeasurable-ceiling",
        value=None,
        abstained=True,
        blocking_reasons=("unmeasured_original_zone",),
        metadata={
            **dict(clean.metadata),
            "finish_occurrence_record_id": "unrelated-occurrence",
            "finish_occurrence_evidence_id": "unrelated-ink",
        },
    )
    claim = replace(
        _claim(clean),
        ceiling_lining_quantity_evidence=(blocked, clean),
    )
    before = (claim.ceiling_lining_quantity_evidence, claim.canonical_ceilings)
    traces = build_live_ceiling_lining_source_traces(
        claim, workspace_id=1, project_id="project-1"
    )
    sealed = seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1"
    )
    rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1"
    )
    assert tuple(traces) == ("qty-ceiling-1",)
    assert len(sealed.quantities) == len(rows) == 1
    assert sealed.quantities[0].quantity_id == rows[0]["quantity_id"]
    assert sealed.quantities[0].value == rows[0]["quantity"] == 9.05352
    assert (claim.ceiling_lining_quantity_evidence, claim.canonical_ceilings) == before
