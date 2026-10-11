"""Q07: no unverified opening source value reaches customer draft quantities."""
from __future__ import annotations

from copy import copy
from dataclasses import replace

import pytest

from pb_live_opening_customer_projection import (
    _eligible_area_quantities, _eligible_count_quantities,
)
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening
from tests.test_live_floor_finish_area_source_closed_export import _claim


def _source_opening_area():
    source = _opening_quantity(_opening())
    assert source is not None
    return source


def _source_opening_count():
    return replace(
        _source_opening_area(),
        family="opening_count",
        quantity_id="source-count-1",
        value=1.0,
        unit="ea",
        status="firm",
        metadata={"schedule_corroborated": True, "opening_mark": "W1"},
    )


def _replay(source, **changes):
    changed = copy(source)
    for key, value in changes.items():
        object.__setattr__(changed, key, value)
    return changed


@pytest.mark.parametrize("bad", [True, False, "2.172", 10 ** 400,
                                  float("nan"), float("inf"), -1.0])
def test_untyped_or_nonpositive_source_area_cannot_reach_customer(bad):
    quantity = _replay(_source_opening_area(), value=bad)
    claim = replace(_claim(), opening_quantity_evidence=(quantity,))
    assert _eligible_area_quantities(claim) == ()


def test_customer_area_requires_exact_producer_corrob_status_and_square_metres():
    source = _source_opening_area()
    assert _eligible_area_quantities(
        replace(_claim(), opening_quantity_evidence=(source,))
    ) == (source,)
    for bad in (replace(source, status="provisional"),
                replace(source, unit="ea")):
        assert _eligible_area_quantities(
            replace(_claim(), opening_quantity_evidence=(bad,))
        ) == ()


@pytest.mark.parametrize("bad", [True, False, "1", 10 ** 400, 1.5,
                                  float("nan"), float("inf"), -1])
def test_untyped_or_fractional_source_count_cannot_reach_customer(bad):
    count = _replay(_source_opening_count(), value=bad)
    claim = replace(_claim(), opening_count_quantity_evidence=(count,))
    assert _eligible_count_quantities(claim) == ()


def test_count_customer_requires_source_schedule_corrob_and_firm_each():
    source = _source_opening_count()
    assert _eligible_count_quantities(
        replace(_claim(), opening_count_quantity_evidence=(source,))
    ) == (source,)
    for bad in (
        replace(source, status="provisional"),
        replace(source, unit="m2"),
        replace(source, metadata={"schedule_corroborated": False, "opening_mark": "W1"}),
    ):
        assert _eligible_count_quantities(
            replace(_claim(), opening_count_quantity_evidence=(bad,))
        ) == ()
