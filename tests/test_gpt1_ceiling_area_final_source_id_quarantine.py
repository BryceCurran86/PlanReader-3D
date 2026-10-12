"""Q07: final legacy ceiling-area seal refuses ambiguous original source identities.

The provisional canonical publisher intentionally accepts identical idempotent
source receipts; the signed commercial boundary does not. No source/metric/
finish authority, frozen benchmark or customer amount is modified here.
"""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_quantity_publication import (
    publish_live_ceiling_area_quantities,
)
from pb_live_ceiling_area_source_closed_export import (
    build_live_ceiling_area_source_traces,
    seal_live_ceiling_area_run,
)
from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import (
    _result,
    _shadow_quantity,
)


def _source_traces(result):
    return build_live_ceiling_area_source_traces(
        result, workspace_id=7, project_id="same-source-project"
    )


def _seal(result):
    return seal_live_ceiling_area_run(
        result, workspace_id=7, project_id="same-source-project"
    )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("kind", ["identical", "abstained"])
def test_final_legacy_ceiling_seal_rejects_duplicate_original_id_in_any_order(
    reverse, kind,
):
    original = _shadow_quantity()
    replay = (
        original
        if kind == "identical"
        else replace(
            original,
            status="blocked",
            value=None,
            abstained=True,
            blocking_reasons=("source-ceiling-conflict",),
        )
    )
    receipts = (replay, original) if reverse else (original, replay)
    result = replace(_result(), quantity_evidence=receipts)

    if kind == "identical":
        # Provisional reissuer still preserves its previous idempotent API.
        assert len(publish_live_ceiling_area_quantities(result)) == 1
    else:
        # Conflicting replay already fails closed before commercial projection.
        assert publish_live_ceiling_area_quantities(result) == ()

    with pytest.raises(SourceClosedRunConflictError, match="original ceiling source"):
        _source_traces(result)
    with pytest.raises(SourceClosedRunConflictError, match="original ceiling source"):
        _seal(result)
    if kind == "identical":
        with pytest.raises(SourceClosedRunConflictError, match="original ceiling source"):
            project_live_ceiling_area_customer_rows(
                result, workspace_id=7, project_id="same-source-project"
            )


@pytest.mark.parametrize("raw_id", [True, 42, " qty-foreign ", "  "])
def test_final_legacy_ceiling_seal_rejects_untyped_or_padded_original_id(raw_id):
    original = _shadow_quantity()
    unsupported = replace(
        original,
        quantity_id=raw_id,
        value=None,
        abstained=True,
        status="blocked",
        blocking_reasons=("unavailable-source",),
    )
    result = replace(_result(), quantity_evidence=(original, unsupported))
    assert len(publish_live_ceiling_area_quantities(result)) == 1
    with pytest.raises(SourceClosedRunConflictError, match="original ceiling source"):
        _source_traces(result)
    with pytest.raises(SourceClosedRunConflictError, match="original ceiling source"):
        _seal(result)


def test_independent_unavailable_source_does_not_poison_authentic_final_ceiling():
    original = _shadow_quantity()
    unrelated = replace(
        original,
        quantity_id="unrelated-source-ceiling-quantity",
        status="blocked",
        value=None,
        abstained=True,
        blocking_reasons=("no-original-ceiling-material-occurrence",),
    )
    result = replace(_result(), quantity_evidence=(original, unrelated))
    traces = _source_traces(result)
    run = _seal(result)
    customer_rows = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="same-source-project"
    )
    assert len(traces) == len(run.quantities) == len(customer_rows) == 1
    assert run.quantities[0].value == 13.270425
    assert run.quantities[0].lineage_ok is True
    assert customer_rows[0]["quantity_id"] == run.quantities[0].quantity_id
