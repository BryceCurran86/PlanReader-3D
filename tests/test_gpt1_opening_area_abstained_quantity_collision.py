"""Q04 exact quantity-ID conflict quarantine must precede ABSTAIN filtering."""
from dataclasses import replace

import pytest

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_opening_source_closed_export import _build_opening_area_source_traces
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_opening_area_quantity_publication import _opening


def _origin():
    opening = _opening()
    q = _opening_quantity(opening)
    assert q is not None
    return q, opening


def _traces(quantities, opening):
    return _build_opening_area_source_traces(
        quantities, (opening,), workspace_id=11, project_id="original-project"
    )


def test_positive_original_hosted_opening_2_172m2_still_seals_one_trace():
    qty, opening = _origin()
    trace = _traces((qty,), opening)[qty.quantity_id]
    assert trace.canonical_entity_ids == (opening.canonical_opening_id,)
    assert trace.source_sha256 == opening.source_sha256
    assert qty.value == 2.172


@pytest.mark.parametrize("order", ["firm_first", "abstain_first"])
def test_abstained_duplicate_same_source_quantity_blocks_firm_area(order):
    qty, opening = _origin()
    abstained = replace(
        qty, value=None, status="blocked", abstained=True,
        blocking_reasons=("unresolved_original_source",),
    )
    variants = (qty, abstained) if order == "firm_first" else (abstained, qty)
    with pytest.raises(SourceClosedRunConflictError, match="duplicate"):
        _traces(variants, opening)


@pytest.mark.parametrize("bad_id", [True, 5, None, "", " ", " opening-area-id "])
def test_invalid_unpublished_opening_id_also_fails_source_universe(bad_id):
    qty, opening = _origin()
    # QuantityEvidence construction rejects empty IDs and stringifies some
    # imported identity types. Reproduce the wire-replay corruption *after*
    # constructing a valid blocked quantity, before the final trace gate.
    from copy import copy
    blocked = replace(qty, abstained=True, value=None, status="blocked",
                      blocking_reasons=("original_source_unavailable",))
    bad = copy(blocked)
    object.__setattr__(bad, "quantity_id", bad_id)
    with pytest.raises(SourceClosedRunConflictError, match="invalid"):
        _traces((bad, qty), opening)


def test_distinct_abstained_quantity_does_not_poison_valid_original_opening():
    qty, opening = _origin()
    other = replace(qty, quantity_id="independent-blocked-quantity",
                    value=None, status="blocked", abstained=True,
                    blocking_reasons=("not_a_firm_measurement",))
    traces = _traces((qty, other), opening)
    assert tuple(traces) == (qty.quantity_id,)
