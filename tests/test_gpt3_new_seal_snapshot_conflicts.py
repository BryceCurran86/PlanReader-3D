"""Original producer snapshot conflicts must not be silently sealed in new V1 runs."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run,
    sealed_source_closed_run_from_dict,
)
from tests.test_source_closed_run_export import quantity, trace, SHA_A, SHA_B


def _two_quantities(first="source_snapshot_A", second="source_snapshot_B",
                    *, two_documents=False):
    q1 = quantity(
        quantity_id="room-source-1",
        semantic_key="room-A",
        input_entity_ids=("physical-room-A",),
        metadata={
            "project_id": "project-a", "document_id": "doc-a",
            "source_sha256": SHA_A, "revision_id": "rev-a",
            "snapshot_id": first,
        } if first is not None else {
            "project_id": "project-a", "document_id": "doc-a",
            "source_sha256": SHA_A, "revision_id": "rev-a",
        },
    )
    second_meta = {
        "project_id": "project-a",
        "document_id": "doc-b" if two_documents else "doc-a",
        "source_sha256": SHA_B if two_documents else SHA_A,
        "revision_id": "rev-b" if two_documents else "rev-a",
    }
    if second is not None:
        second_meta["snapshot_id"] = second
    q2 = quantity(
        quantity_id="room-source-2", semantic_key="room-B",
        input_entity_ids=("physical-room-B",),
        metadata=second_meta,
    )
    t1 = trace(canonical_entity_ids=("physical-room-A",))
    t2 = trace(
        document_id=second_meta["document_id"],
        source_sha256=second_meta["source_sha256"],
        revision_id=second_meta["revision_id"],
        current_revision_id=second_meta["revision_id"],
        canonical_entity_ids=("physical-room-B",),
    )
    return (q1, q2), {q1.quantity_id: t1, q2.quantity_id: t2}


def _seal(quantities, traces):
    return seal_source_closed_run(
        quantities, project_id="project-a", traces_by_quantity_id=traces,
    )


def test_new_run_rejects_two_explicit_conflicting_original_snapshots():
    quantities, traces = _two_quantities()
    with pytest.raises(SourceClosedRunConflictError,
                       match="conflicting explicit source snapshot"):
        _seal(quantities, traces)


def test_conflict_fails_regardless_of_producer_quantity_order():
    quantities, traces = _two_quantities()
    for supplied in (quantities, tuple(reversed(quantities))):
        with pytest.raises(SourceClosedRunConflictError,
                           match="conflicting explicit source snapshot"):
            _seal(supplied, traces)


def test_distinct_physical_quantities_from_one_snapshot_still_seal():
    quantities, traces = _two_quantities(second="source_snapshot_A")
    sealed = _seal(quantities, traces)
    assert len(sealed.quantities) == 2
    assert sealed.fingerprint
    assert sealed_source_closed_run_from_dict(sealed.to_dict()) == sealed


def test_distinct_source_documents_have_independent_original_snapshots():
    quantities, traces = _two_quantities(two_documents=True)
    sealed = _seal(quantities, traces)
    assert len(sealed.quantities) == 2
    assert len(sealed.source_sha256s) == 2


def test_missing_legacy_snapshot_not_synthesized_or_copied():
    quantities, traces = _two_quantities(first=None, second="source_snapshot_B")
    sealed = _seal(quantities, traces)
    assert len(sealed.quantities) == 2
    assert "snapshot_id" not in sealed.to_dict()["quantities"][0]


@pytest.mark.parametrize("bad", [None, "", " source_snapshot_A ", True, 7, [], {}])
def test_invalid_explicit_source_snapshot_receipt_is_rejected(bad):
    quantities, traces = _two_quantities(first="source_snapshot_A",
                                        second="source_snapshot_A")
    first = quantities[0]
    meta = dict(first.metadata)
    meta["snapshot_id"] = bad
    from dataclasses import replace
    quantities = (replace(first, metadata=meta), quantities[1])
    with pytest.raises(SourceClosedRunConflictError,
                       match="explicit original producer snapshot_id"):
        _seal(quantities, traces)


def test_original_lot16_eight_v1_seal_still_valid_after_new_issue_gate():
    archive = json.loads(Path(
        "docs/engineering/lot16_original_signed_eight_row_20261015/"
        "production/source_sealed_run.json"
    ).read_text())
    loaded = sealed_source_closed_run_from_dict(archive)
    assert len(loaded.quantities) == 8
    assert loaded.fingerprint == (
        "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
    )



def test_new_issuer_and_trace_source_snapshot_must_agree():
    quantities, traces = _two_quantities(
        first="source_snapshot_A", second="source_snapshot_A"
    )
    traces["room-source-1"] = trace(
        canonical_entity_ids=("physical-room-A",),
        metadata={"snapshot_id": "source_snapshot_FOREIGN"},
    )
    with pytest.raises(SourceClosedRunConflictError,
                       match="quantity/trace snapshot receipts conflict"):
        _seal(quantities, traces)


def test_trace_only_original_snapshot_still_prevents_mixed_issuer_snapshots():
    quantities, traces = _two_quantities(
        first=None, second="source_snapshot_B"
    )
    traces["room-source-1"] = trace(
        canonical_entity_ids=("physical-room-A",),
        metadata={"snapshot_id": "source_snapshot_A"},
    )
    with pytest.raises(SourceClosedRunConflictError,
                       match="conflicting explicit source snapshot"):
        _seal(quantities, traces)


def test_matching_quantity_and_trace_snapshot_retains_unchanged_v1_wire():
    quantities, traces = _two_quantities(
        first="source_snapshot_A", second="source_snapshot_A"
    )
    traces["room-source-1"] = trace(
        canonical_entity_ids=("physical-room-A",),
        metadata={"snapshot_id": "source_snapshot_A"},
    )
    sealed = _seal(quantities, traces)
    assert len(sealed.quantities) == 2
    assert "snapshot_id" not in sealed.quantities[0].to_dict()
    assert sealed_source_closed_run_from_dict(sealed.to_dict()).fingerprint == sealed.fingerprint


@pytest.mark.parametrize("bad",[None,True,0, " source_snapshot_A ", [], {}])
def test_bad_trace_only_snapshot_cannot_be_implicitly_granted(bad):
    quantities, traces = _two_quantities(first=None, second=None)
    traces["room-source-1"] = trace(
        canonical_entity_ids=("physical-room-A",),
        metadata={"snapshot_id": bad},
    )
    with pytest.raises(SourceClosedRunConflictError,
                       match="explicit original producer snapshot_id"):
        _seal(quantities, traces)
