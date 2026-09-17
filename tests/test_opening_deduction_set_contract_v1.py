"""Executable set-level attacks for future Opening Deduction Authority.

TEST ONLY. These tests lock fail-closed commercial-deduction set semantics without
substituting for Physical Opening Void or production deduction authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.opening_deduction_reference_support_v1 import (
    ReferenceDeductionCandidate,
    authorize_reference_deduction_set,
    reference_total_area_or_none,
)


def _candidate(opening_id: str, *, area: float = 1.89) -> ReferenceDeductionCandidate:
    return ReferenceDeductionCandidate(
        opening_identity_id=opening_id,
        physical_void_record_id=f"void-{opening_id}",
        wall_id="wall-a",
        face_scope_id="face-internal",
        assembly_scope_id="assembly-plaster",
        diagnostic_area_m2=area,
    )


def _authorize(*candidates: ReferenceDeductionCandidate, complete: bool = True):
    return authorize_reference_deduction_set(
        candidates,
        universe_complete=complete,
        wall_id="wall-a",
        face_scope_id="face-internal",
        assembly_scope_id="assembly-plaster",
    )


def test_incomplete_opening_universe_blocks_even_when_all_seen_openings_are_valid() -> None:
    assert _authorize(_candidate("opening-1"), complete=False) is None


def test_no_seen_openings_are_unknown_without_positive_completeness() -> None:
    assert _authorize(complete=False) is None
    assert reference_total_area_or_none(None) is None


def test_complete_empty_opening_universe_can_evidence_zero_without_unknown_conversion() -> None:
    authorized = _authorize(complete=True)
    assert authorized == ()
    assert reference_total_area_or_none(authorized) == pytest.approx(0.0)


def test_one_unresolved_relevant_opening_blocks_whole_authoritative_set() -> None:
    resolved = _candidate("opening-1")
    unresolved = replace(_candidate("opening-2"), resolved=False)
    assert _authorize(resolved, unresolved) is None


def test_exact_duplicate_observation_of_same_physical_opening_deduplicates_once() -> None:
    candidate = _candidate("opening-1")
    authorized = _authorize(candidate, candidate)
    assert authorized == (candidate,)
    assert reference_total_area_or_none(authorized) == pytest.approx(candidate.diagnostic_area_m2)


def test_same_physical_opening_with_conflicting_void_record_blocks_not_first_wins() -> None:
    first = _candidate("opening-1")
    conflicting = replace(first, physical_void_record_id="void-conflict")
    assert _authorize(first, conflicting) is None


def test_same_size_distinct_physical_openings_remain_distinct() -> None:
    first = _candidate("opening-1", area=1.89)
    second = _candidate("opening-2", area=1.89)
    authorized = _authorize(first, second)
    assert authorized is not None
    assert len(authorized) == 2
    assert {item.opening_identity_id for item in authorized} == {"opening-1", "opening-2"}


def test_wrong_wall_blocks_deduction_set() -> None:
    assert _authorize(replace(_candidate("opening-1"), wall_id="wall-b")) is None


def test_wrong_face_blocks_deduction_set() -> None:
    assert _authorize(replace(_candidate("opening-1"), face_scope_id="face-external")) is None


def test_wrong_assembly_blocks_deduction_set() -> None:
    assert _authorize(replace(_candidate("opening-1"), assembly_scope_id="assembly-paint")) is None


def test_unknown_authorized_set_never_becomes_numeric_zero() -> None:
    assert reference_total_area_or_none(None) is None
    assert reference_total_area_or_none(None) != 0.0
