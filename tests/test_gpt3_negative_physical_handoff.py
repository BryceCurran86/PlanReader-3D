"""Fail closed on corrupted negative physical quantities before source sealing.

These tests exercise the final handoff gate, not the already strict
QuantityEvidence constructor. No benchmark truth or source files are used.
"""
from dataclasses import replace

import pytest

from test_source_closed_project_handoff import _quantity
from tools import run_source_closed_project_handoff as handoff


@pytest.mark.parametrize(("family", "negative"), [
    ("floor_area", -2.5),
    ("floor_finish_area", -0.001),
    ("opening_area", -0.001),
    ("opening_count", -1),
    ("ceiling_area", -3.0),
])
def test_corrupted_negative_physical_quantity_cannot_reach_seal(family, negative):
    # The constructor rejects negative values; simulate a tampered/faulty
    # producer receipt that bypassed its original validation.
    quantity = _quantity("negative-source", family)
    object.__setattr__(quantity, "value", negative)
    assert handoff._non_abstained((quantity,)) == ()


@pytest.mark.parametrize("value", [0.0, -0.0, 1.0])
def test_nonnegative_firm_source_quantity_preserves_authority(value):
    quantity = replace(_quantity("source-area", "floor_area"), value=value)
    assert handoff._non_abstained((quantity,)) == (quantity,)


def test_abstention_remains_absent_instead_of_becoming_zero():
    quantity = replace(
        _quantity("unmeasured-area", "floor_area"),
        value=None,
        abstained=True,
        blocking_reasons=("source_not_proven",),
    )
    assert handoff._non_abstained((quantity,)) == ()
