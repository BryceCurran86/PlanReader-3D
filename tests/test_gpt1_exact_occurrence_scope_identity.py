"""A source occurrence may be repeated, never reinterpreted, across complete scopes.

These are source-neutral consumer tests. They do not grant the original FT3
material, cross-sheet physical-floor identity, metric authority, or a score.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_cross_view_floor_finish_authority import _occurrences_on_page
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SourceMaterialOccurrenceRecord,
    SourceMaterialOccurrenceScopeResult,
)


def _record(
    record_id: str = "original-occurrence-1",
    evidence_id: str = "source-observation-1",
    *,
    page_id: str = "11",
    bbox: tuple[float, float, float, float] = (50.0, 50.0, 65.0, 65.0),
    code: str = "FT3",
) -> SourceMaterialOccurrenceRecord:
    return SourceMaterialOccurrenceRecord(
        record_id=record_id,
        document_id="source-document",
        revision_id="source-revision",
        source_sha256="a" * 64,
        snapshot_id="source-snapshot",
        page_id=page_id,
        viewport_id="physical-plan-viewport",
        code=code,
        semantic_finish="tile",
        definition_record_id="source-definition",
        bbox_pdf_pts=bbox,
        raw_text=code,
        source_evidence_id=evidence_id,
        source_text_observation_ids=(evidence_id,),
    )


def _scope(
    *records: SourceMaterialOccurrenceRecord,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    complete: bool = True,
) -> SourceMaterialOccurrenceScopeResult:
    return SourceMaterialOccurrenceScopeResult(
        status=status,
        reason_codes=(),
        scope_complete=complete,
        records=tuple(records),
    )


def test_one_original_occurrence_repeated_in_two_complete_scopes_is_one():
    original = _record()
    first = _scope(original)
    second = _scope(replace(original))
    assert _occurrences_on_page((first, second), page_id="11") == (original,)
    assert _occurrences_on_page((second, first), page_id="11") == (original,)


def test_same_occurrence_repeated_inside_one_scope_does_not_double_count():
    original = _record()
    assert _occurrences_on_page((_scope(original, original),), page_id="11") == (
        original,
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"bbox_pdf_pts": (51.0, 50.0, 65.0, 65.0)},
        {"code": "FT2"},
        {"definition_record_id": "other-definition"},
        {"snapshot_id": "other-source-snapshot"},
        {"source_evidence_id": "other-observation"},
        {"source_text_observation_ids": ("other-observation",)},
        {"source_sha256": "b" * 64},
        {"viewport_id": "other-viewport"},
    ],
)
def test_conflicting_reuse_of_one_issuer_id_quarantines_all(changed):
    original = _record()
    changed_record = replace(original, **changed)
    assert _occurrences_on_page(
        (_scope(original), _scope(changed_record)), page_id="11"
    ) == ()
    assert _occurrences_on_page(
        (_scope(changed_record), _scope(original)), page_id="11"
    ) == ()


def test_two_distinct_occurrence_ids_reusing_one_original_evidence_id_conflict():
    first = _record("record-one", "shared-physical-source")
    second = _record("record-two", "shared-physical-source")
    assert _occurrences_on_page((_scope(first), _scope(second)), page_id="11") == ()
    assert _occurrences_on_page((_scope(second), _scope(first)), page_id="11") == ()


def test_unrelated_legitimate_source_observations_remain_separate():
    first = _record("one", "first", bbox=(50.0, 50.0, 60.0, 60.0))
    second = _record("two", "second", bbox=(70.0, 70.0, 80.0, 80.0))
    expected = (first, second)
    assert _occurrences_on_page((_scope(second), _scope(first)), page_id="11") == expected
    assert _occurrences_on_page((_scope(first, second, first),), page_id="11") == expected


def test_disputed_source_id_withholds_itself_but_not_an_independent_occurrence():
    disputed = _record()
    changed = replace(disputed, code="FT2")
    independent = _record("independent", "second-source", bbox=(80, 80, 90, 90))
    assert _occurrences_on_page(
        (_scope(disputed, independent), _scope(changed)), page_id="11"
    ) == (independent,)


@pytest.mark.parametrize(
    "status,complete",
    [
        (EvidenceResolutionStatus.CORROBORATED, False),
        (EvidenceResolutionStatus.CANDIDATE, True),
        (EvidenceResolutionStatus.ABSTAINED, True),
        (EvidenceResolutionStatus.CONFLICT, True),
    ],
)
def test_incomplete_or_untrusted_scope_never_supplies_a_positive(status, complete):
    assert _occurrences_on_page(
        (_scope(_record(), status=status, complete=complete),), page_id="11"
    ) == ()


def test_page_specific_selection_does_not_borrow_other_sheet_mark():
    on_plan = _record(page_id="11")
    on_schedule = _record("schedule", "schedule-evidence", page_id="12")
    assert _occurrences_on_page(
        (_scope(on_schedule, on_plan),), page_id="11"
    ) == (on_plan,)


@pytest.mark.parametrize("bad", ["", " issuer-id", "issuer-id "])
def test_noncanonical_source_occurrence_identity_is_withheld(bad):
    assert _occurrences_on_page(
        (_scope(_record(record_id=bad)),), page_id="11"
    ) == ()


@pytest.mark.parametrize("bad", ["", " ev", "ev "])
def test_noncanonical_source_evidence_identity_is_withheld(bad):
    assert _occurrences_on_page(
        (_scope(_record(evidence_id=bad)),), page_id="11"
    ) == ()


def test_malformed_source_record_is_not_counted_as_authenticated_occurrence():
    assert _occurrences_on_page(
        (_scope(_record(), None),), page_id="11"
    ) == (_record(),)
