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


def test_same_source_opening_alternative_door_window_semantics_is_review_only():
    run = _run(
        _pair("one", "opening_area", "door_area", ("physical-opening-a",), value=3.0),
        _pair("two", "opening_area", "window_area", ("physical-opening-a",), value=4.0),
    )
    audit = audit_cross_semantic_physical_claims(run)
    assert audit["review_group_count"] == 1
    flag = audit["cross_semantic_overlap_groups"][0]
    assert flag["family"] == "opening_area"
    assert flag["quantity_ids"] == ["one", "two"]
    assert flag["semantic_keys"] == ["door_area", "window_area"]
    assert flag["source_envelope_count"] == 1
    assert flag["first_gate"] == "SOURCE_OWNED_SEMANTIC_CLAIM_EQUIVALENCE_UNPROVEN"
    assert flag["commercial_decision"] == "ABSTAIN_REVIEW_ONLY"
    assert "physical-opening-a" not in json.dumps(audit)
    assert audit["source_issuer_equivalence_authenticated"] is False
    assert audit["duplicate_claim_removed"] is False
    assert audit["customer_output_approval_granted"] is False
    assert audit["benchmark_score_granted"] is False


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


def test_partially_overlapping_physical_parent_sets_are_found_without_guessing():
    run = _run(
        _pair("part-a", "opening_area", "door_area", ("a", "shared")),
        _pair("part-b", "opening_area", "window_area", ("b", "shared")),
    )
    got = audit_cross_semantic_physical_claims(run)
    assert got["review_group_count"] == 1
    assert got["cross_semantic_overlap_groups"][0]["quantity_ids"] == [
        "part-a", "part-b",
    ]


def test_separate_document_source_envelopes_are_review_not_auto_identity():
    run = _run(
        _pair("old", "opening_area", "door_area", ("p-one",)),
        _pair("new", "opening_area", "window_area", ("p-one",),
              sha="b" * 64, document="doc-b", revision="rev-b"),
    )
    group = audit_cross_semantic_physical_claims(run)["cross_semantic_overlap_groups"][0]
    assert group["source_envelope_count"] == 2
    assert group["cross_source_envelope_review"] is True
    assert group["commercial_decision"] == "ABSTAIN_REVIEW_ONLY"


def test_abstention_or_unfirm_row_does_not_create_a_false_firm_overlap():
    run = _run(
        _pair("firm", "opening_area", "door_area", ("p-one",)),
        _pair("abstained", "opening_area", "window_area", ("p-one",),
              abstained=True),
        _pair("review", "opening_area", "skylight_area", ("p-one",),
              status="review_required"),
    )
    audit = audit_cross_semantic_physical_claims(run)
    assert audit["considered_firm_or_corroborated_rows"] == 1
    assert audit["excluded_unfirm_or_abstained_quantity_ids"] == [
        "abstained", "review",
    ]
    assert audit["review_group_count"] == 0


def test_diagnostic_is_deterministic_input_order_invariant_and_no_mutation():
    entries = [
        _pair("two", "opening_area", "window_area", ("p-one",)),
        _pair("three", "opening_area", "door_area", ("p-two",)),
        _pair("one", "opening_area", "door_area", ("p-one",)),
    ]
    first = _run(*entries)
    before = deepcopy(first.to_dict())
    expected = audit_cross_semantic_physical_claims(first)
    assert audit_cross_semantic_physical_claims(_run(*reversed(entries))) == expected
    assert first.to_dict() == before
    assert expected["review_group_count"] == 1


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
