"""A FIRM-looking wall dimension that still lists blocking reasons must not become a FIRM gross area.

``QuantityEvidence`` forbids an *abstained* quantity without blocking reasons but allows a value-bearing one to carry them, so
imported or replayed evidence can be contradictory.  The gross builder must treat that as unknown/conflicting and abstain
(AGENTS.md: unknown, conflicting, stale or ambiguous evidence must abstain).  Found by the strict-xfail matrix in #2821.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_wall_gross_area_quantity import quantity_evidence_fingerprint

from tests.test_wall_gross_area_quantity import _gross, _height, _length


@pytest.mark.parametrize("which", ("length", "height"))
@pytest.mark.parametrize("reasons", (("original_source_conflict",), ("a", "b"), ("measurement_input_abstained",)))
def test_firm_dimension_with_blocking_reasons_abstains(which, reasons):
    parent = _length() if which == "length" else _height()
    contradictory = replace(parent, blocking_reasons=reasons)
    assert contradictory.abstained is False and contradictory.value is not None  # the contradictory state is constructible
    result = _gross(**{which: contradictory})
    assert result.abstained is True
    assert result.value is None
    assert result.status == AuthorityStatus.BLOCKED.value
    assert f"wall_{which}_source_blocked" in result.blocking_reasons


def test_both_dimensions_contradictory_report_both():
    result = _gross(
        length=replace(_length(), blocking_reasons=("x",)),
        height=replace(_height(), blocking_reasons=("y",)),
    )
    assert result.abstained
    assert {"wall_length_source_blocked", "wall_height_source_blocked"} <= set(result.blocking_reasons)


def test_clean_firm_dimensions_still_publish_the_same_firm_area():
    first, second = _gross(), _gross()
    assert first.to_dict() == second.to_dict()
    assert first.abstained is False and first.status == AuthorityStatus.FIRM.value and first.value == 12.0
    assert "wall_length_source_blocked" not in first.blocking_reasons
    assert "wall_height_source_blocked" not in first.blocking_reasons
    assert quantity_evidence_fingerprint(first) == quantity_evidence_fingerprint(second)


def test_an_abstained_dimension_keeps_exactly_its_previous_reasons():
    height = _height(value=None, status=AuthorityStatus.BLOCKED.value, abstained=True, blockers=("no_height",))
    result = _gross(height=height)
    assert result.abstained
    assert "wall_height_abstained" in result.blocking_reasons and "wall_height_not_firm" in result.blocking_reasons
    assert "wall_height_source_blocked" not in result.blocking_reasons  # an abstained parent is already refused for being abstained
