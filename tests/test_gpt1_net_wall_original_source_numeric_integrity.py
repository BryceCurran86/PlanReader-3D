"""Q03 gross/net wall diagnostics must abstain, not throw, on corrupted m²."""
from __future__ import annotations

from copy import copy

import pytest

from tests.test_wall_net_area_quantity import _build, _complete, _deduction, _gross


def replay(original, **updates):
    item = copy(original)
    for name, value in updates.items():
        object.__setattr__(item, name, value)
    return item


@pytest.mark.parametrize("bad", [True, False, "1.25", 10 ** 400, float("nan"), float("inf")])
def test_invalid_opening_deduction_never_subtracts_a_replayed_metric(bad):
    deduction = replay(_deduction("OP-1", 1.25), value=bad)
    result = _build(deductions=(deduction,), completion=_complete(("OP-1",)))
    assert result.abstained
    assert result.value is None
    assert "opening_deduction_value_invalid" in result.blocking_reasons
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


@pytest.mark.parametrize("bad", [True, False, "12.0", 10 ** 400, float("nan"), float("inf")])
def test_invalid_gross_wall_area_never_mints_positive_net_metric(bad):
    gross = replay(_gross(), value=bad)
    result = _build(
        gross=gross,
        deductions=(_deduction("OP-1", 1.25),),
        completion=_complete(("OP-1",)),
    )
    assert result.abstained
    assert result.value is None
    assert "gross_wall_area_value_invalid" in result.blocking_reasons
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_valid_source_gross_and_opening_deduction_remain_blocked_until_universe_complete():
    result = _build(
        gross=_gross(12.0),
        deductions=(_deduction("OP-1", 1.25),),
        completion=_complete(("OP-1",)),
    )
    assert result.abstained
    assert "gross_wall_area_value_invalid" not in result.blocking_reasons
    assert "opening_deduction_value_invalid" not in result.blocking_reasons
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons



@pytest.mark.parametrize("untrusted", [
    (True,), (123,), (" OP-1",), ("OP-1 ",),
])
def test_completion_source_member_ids_cannot_be_stringified_or_trimmed(untrusted):
    result = _build(
        deductions=(_deduction("OP-1", 1.25),),
        completion=_complete(untrusted),
    )
    assert result.abstained
    assert "opening_set_completion_ids_invalid" in result.blocking_reasons


@pytest.mark.parametrize("untrusted", [
    ("OP-1", True), (True, "WALL-1"),
    (" OP-1", "WALL-1"), ("OP-1 ", "WALL-1"),
])
def test_deduction_source_physical_identity_must_be_exact_typed_pair(untrusted):
    deduction = replay(_deduction("OP-1", 1.25), input_entity_ids=untrusted)
    result = _build(
        deductions=(deduction,),
        completion=_complete(("OP-1",)),
    )
    assert result.abstained
    assert "opening_deduction_identity_mismatch" in result.blocking_reasons



def test_blocked_net_wall_still_serializes_a_corrupt_nonfinite_dependency_receipt():
    from copy import copy
    gross = copy(_gross())
    object.__setattr__(gross, "value", float("nan"))
    deduction = copy(_deduction("OP-1", 1.25))
    object.__setattr__(deduction, "value", float("inf"))
    result = _build(
        gross=gross, deductions=(deduction,), completion=_complete(("OP-1",)),
    )
    assert result.abstained and result.value is None
    assert "gross_wall_area_value_invalid" in result.blocking_reasons
    assert "opening_deduction_value_invalid" in result.blocking_reasons
    assert len(result.metadata["deduction_dependency_fingerprints"]) == 1
    assert result.metadata["gross_dependency_fingerprint"]


def test_invalid_unhashable_evidence_receipt_never_crashes_blocked_net_wall():
    gross = replay(_gross(), evidence_ids=("ev-wall", ["unhashable-source"]))
    result = _build(gross=gross, completion=None)
    assert result.abstained
    assert result.value is None
    assert "ev-wall" in result.evidence_ids
    assert all(type(value) is str for value in result.evidence_ids)
