"""Final floor-area seals cannot hide duplicate original room metric source IDs."""
from dataclasses import replace

import pytest

from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
    seal_live_floor_area_run,
)
from pb_live_floor_area_customer_projection import project_live_floor_area_customer_rows
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with_canonical_room,
    _source_area,
)


def _claim(*source_receipts):
    return _claim_with_canonical_room(*source_receipts)


def _traces(claim):
    return build_live_floor_area_source_traces(
        claim, workspace_id=1, project_id="source-owned-floor"
    )


@pytest.mark.parametrize("reverse", (False, True))
def test_canonical_floor_publisher_can_abstain_but_final_seal_rejects_reused_source_id(reverse):
    firm = _source_area()
    provisional = replace(
        firm, value=None, abstained=True, status="provisional",
        blocking_reasons=("source_area_unresolved",),
    )
    entries = (provisional, firm) if reverse else (firm, provisional)
    claim = _claim(*entries)
    # Intentionally preserve the producer's existing replay tolerance.
    assert len(publish_live_floor_area_quantities(claim)) == 1
    with pytest.raises(SourceClosedRunConflictError, match="duplicate original room-area source ID"):
        _traces(claim)
    with pytest.raises(SourceClosedRunConflictError, match="duplicate original room-area source ID"):
        seal_live_floor_area_run(claim, workspace_id=1, project_id="source-owned-floor")
    with pytest.raises(SourceClosedRunConflictError, match="duplicate original room-area source ID"):
        project_live_floor_area_customer_rows(
            claim, workspace_id=1, project_id="source-owned-floor"
        )


def test_unrelated_abstention_remains_unavailable_and_firm_floor_is_unchanged():
    firm = _source_area()
    abstain = replace(
        firm, quantity_id="source-room-area-not-published",
        value=None, abstained=True, status="provisional",
        blocking_reasons=("source_metric_unavailable",),
    )
    claim = _claim(abstain, firm)
    traces = _traces(claim)
    assert len(traces) == 1
    sealed = seal_live_floor_area_run(
        claim, workspace_id=1, project_id="source-owned-floor"
    )
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].lineage_ok is True
    assert sealed.quantities[0].value == 8.64


def test_duplicate_two_unresolved_original_room_area_receipts_are_conflicted():
    source = _source_area()
    unresolved = replace(
        source, value=None, abstained=True, status="provisional",
        blocking_reasons=("source_unavailable",),
    )
    with pytest.raises(SourceClosedRunConflictError, match="duplicate original room-area source ID"):
        _traces(_claim(unresolved, unresolved))


@pytest.mark.parametrize("bad", ("", " room-area-1", "room-area-1 ", True))
def test_invalid_original_source_id_cannot_be_hidden_by_abstention(bad):
    firm = _source_area()
    rejected = replace(
        firm, value=None, abstained=True, status="provisional",
        blocking_reasons=("source_unavailable",),
    )
    object.__setattr__(rejected, "quantity_id", bad)
    with pytest.raises(SourceClosedRunConflictError, match="invalid original room-area source ID"):
        _traces(_claim(firm, rejected))


def test_unmodified_firm_source_still_seals_as_one_physical_floor():
    claim = _claim(_source_area())
    traces = _traces(claim)
    assert len(traces) == 1
    sealed = seal_live_floor_area_run(
        claim, workspace_id=1, project_id="source-owned-floor"
    )
    assert len(sealed.quantities) == 1
    assert sealed.quantities[0].value == 8.64



def test_floor_customer_empty_selection_cannot_hide_two_abstained_source_receipts():
    source = _source_area()
    absent = replace(
        source, value=None, abstained=True, status="provisional",
        blocking_reasons=("source_metric_unavailable",),
    )
    claim = _claim(absent, absent)
    assert publish_live_floor_area_quantities(claim) == ()
    with pytest.raises(SourceClosedRunConflictError, match="duplicate or invalid original room-area source ID"):
        project_live_floor_area_customer_rows(
            claim, workspace_id=1, project_id="source-owned-floor"
        )
    legitimate = _claim(absent)
    assert project_live_floor_area_customer_rows(
        legitimate, workspace_id=1, project_id="source-owned-floor"
    ) == ()


@pytest.mark.parametrize("invalid", ("foreign_family", "untyped_object", "padded_id"))
def test_floor_customer_empty_selection_cannot_hide_foreign_source_inventory(invalid):
    absent = replace(
        _source_area(), value=None, abstained=True, status="provisional",
        blocking_reasons=("original_room_unresolved",),
    )
    if invalid == "foreign_family":
        raw = replace(absent, family="ceiling_lining")
    elif invalid == "untyped_object":
        raw = object()
    else:
        raw = replace(absent)
        object.__setattr__(raw, "quantity_id", " original-room-area ")
    claim = _claim(raw)
    error = TypeError if invalid == "untyped_object" else SourceClosedRunConflictError
    with pytest.raises(error):
        project_live_floor_area_customer_rows(
            claim, workspace_id=1, project_id="source-owned-floor"
        )
