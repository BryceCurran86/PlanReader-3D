"""Synthetic GPT3 diagnostics for cross-semantic exact-physical-source review.

This is a shadow reader, NOT new V1 deduplication or publication authority.
Actual full-plan V2 expected values are never loaded into these tests.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    seal_source_closed_run,
    sealed_source_closed_run_from_dict,
)
from test_source_closed_run_export import quantity, trace
from tools.diag_gpt3_cross_semantic_physical_claims import (
    audit_cross_semantic_physical_claims,
)


def _pair(name, family, semantic, ids, *, value=2.0, abstained=False,
          status="firm", sha="a" * 64, document="doc-a", revision="rev-a"):
    ev = (f"source-observation-{name}",)
    parents = tuple(ids)
    q = quantity(
        quantity_id=name,
        family=family,
        semantic_key=semantic,
        input_entity_ids=parents,
        evidence_ids=ev,
        value=None if abstained else value,
        status="abstained" if abstained else status,
        abstained=abstained,
        blocking_reasons=("source_not_yet_proven",) if abstained else (),
        metadata={
            "project_id": "project-a",
            "document_id": document,
            "source_sha256": sha,
            "revision_id": revision,
        },
    )
    t = trace(
        project_id="project-a", document_id=document,
        source_sha256=sha, revision_id=revision, current_revision_id=revision,
        evidence_ids=ev, canonical_entity_ids=parents,
    )
    return q, t


def _run(*entries):
    quantities = [row for row, _ in entries]
    receipts = {row.quantity_id: t for row, t in entries}
    return seal_source_closed_run(
        quantities, project_id="project-a", traces_by_quantity_id=receipts
    )


def test_same_source_opening_alternative_door_window_semantics_rejected_by_new_issuer():
    # Diagnostic readers cannot mint impossible source-signed history.
    with pytest.raises(SourceClosedRunConflictError, match="conflicting signed opening identity"):
        _run(
            _pair("one", "opening_area", "door_area", ("physical-opening-a",), value=3.0),
            _pair("two", "opening_area", "window_area", ("physical-opening-a",), value=4.0),
        )

def test_same_room_different_family_floor_and_ceiling_remains_independent():
    run = _run(
        _pair("floor", "floor_area", "room.floor", ("room-one",)),
        _pair("ceiling", "ceiling_area", "room.ceiling", ("room-one",)),
    )
    assert audit_cross_semantic_physical_claims(run)["review_group_count"] == 0
    assert len(run.quantities) == 2


def test_distinct_physical_openings_never_coalesce_by_equal_value_or_name():
    run = _run(
        _pair("one", "opening_area", "door_area", ("physical-a",), value=3.0),
        _pair("two", "opening_area", "window_area", ("physical-b",), value=3.0),
    )
    assert audit_cross_semantic_physical_claims(run)["review_group_count"] == 0


def test_distinct_finish_subsystems_on_one_exact_room_are_flagged_not_deleted():
    run = _run(
        _pair("paint", "floor_finish_area", "floor.paint", ("room-one",)),
        _pair("tile", "floor_finish_area", "floor.tile", ("room-one",)),
    )
    got = audit_cross_semantic_physical_claims(run)
    assert got["review_group_count"] == 1
    assert len(run.quantities) == 2
    assert got["cross_semantic_overlap_groups"][0]["semantic_keys"] == [
        "floor.paint", "floor.tile",
    ]
    assert got["duplicate_claim_removed"] is False


def test_partially_overlapping_opening_parent_sets_rejected_before_shadow():
    with pytest.raises(SourceClosedRunConflictError, match="conflicting signed opening identity"):
        _run(
            _pair("part-a", "opening_area", "door_area", ("a", "shared")),
            _pair("part-b", "opening_area", "window_area", ("b", "shared")),
        )

def test_separate_document_envelopes_cannot_double_sign_one_physical_opening():
    # A cross-document source claim is not license to publish a duplicate.
    with pytest.raises(SourceClosedRunConflictError, match="conflicting signed opening identity"):
        _run(
            _pair("old", "opening_area", "door_area", ("p-one",)),
            _pair("new", "opening_area", "window_area", ("p-one",),
                  sha="b" * 64, document="doc-b", revision="rev-b"),
        )

def test_abstained_opening_alternative_is_excluded_from_source_claims():
    run = _run(
        _pair("firm", "opening_area", "door_area", ("p-one",)),
        _pair("abstained", "opening_area", "window_area", ("p-one",),
              abstained=True),
    )
    audit = audit_cross_semantic_physical_claims(run)
    assert audit["considered_firm_or_corroborated_rows"] == 1
    assert audit["excluded_unfirm_or_abstained_quantity_ids"] == ["abstained"]
    assert audit["review_group_count"] == 0


def test_unfirm_but_nonabstained_review_row_cannot_double_sign_physical_opening():
    with pytest.raises(SourceClosedRunConflictError, match="conflicting signed opening identity"):
        _run(
            _pair("firm", "opening_area", "door_area", ("p-one",)),
            _pair("review", "opening_area", "skylight_area", ("p-one",),
                  status="review_required"),
        )

def test_diagnostic_is_deterministic_input_order_invariant_and_no_mutation():
    # Determinism is assessed on source-valid distinct physical claims, not
    # by minting an invalid duplicate-signature receipt for a shadow reader.
    entries = [
        _pair("two", "opening_area", "window_area", ("p-three",)),
        _pair("three", "opening_area", "door_area", ("p-two",)),
        _pair("one", "opening_area", "door_area", ("p-one",)),
    ]
    first = _run(*entries)
    before = deepcopy(first.to_dict())
    expected = audit_cross_semantic_physical_claims(first)
    assert audit_cross_semantic_physical_claims(_run(*reversed(entries))) == expected
    assert first.to_dict() == before
    assert expected["review_group_count"] == 0


def test_independent_door_area_and_complete_count_are_distinct_source_families():
    run = _run(
        _pair("area", "opening_area", "door_area:opening-one", ("opening-one",), value=2.0),
        _pair("count", "opening_count", "door_count:opening-one", ("opening-one",), value=1.0),
    )
    assert len(run.quantities) == 2
    assert audit_cross_semantic_physical_claims(run)["review_group_count"] == 0

def test_existing_same_semantic_double_count_is_still_rejected_by_v1_sealer():
    with pytest.raises(SourceClosedRunConflictError, match="sealed physical claim"):
        _run(
            _pair("one", "opening_area", "door_area", ("p-one",)),
            _pair("two", "opening_area", "door_area", ("p-one",)),
        )


def test_invalid_run_inputs_and_tampered_original_fingerprints_fail_closed():
    with pytest.raises(TypeError, match="SealedSourceClosedRun"):
        audit_cross_semantic_physical_claims({})
    run = _run(_pair("one", "opening_area", "door_area", ("p-one",)))
    damaged = deepcopy(run.to_dict())
    damaged["quantities"][0]["value"] += 1
    with pytest.raises(SourceClosedRunConflictError):
        sealed_source_closed_run_from_dict(damaged)


def test_original_signed_lot16_eight_rows_have_no_cross_semantic_claim():
    root = Path(__file__).resolve().parents[1]
    archived = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production/source_sealed_run.json"
    run = sealed_source_closed_run_from_dict(json.loads(archived.read_text(encoding="utf-8")))
    audit = audit_cross_semantic_physical_claims(run)
    assert audit["project_id"] == "au_qld_lot16_power"
    assert audit["source_run_fingerprint"] == run.fingerprint
    assert audit["review_group_count"] == 0
    assert audit["benchmark_score_granted"] is False
