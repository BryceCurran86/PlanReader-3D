"""Direct legacy ceiling-area source seal must audit contradictory original FIRM.

The customer projection already vetoes blocked original numeric FIRM. The
independent direct source-trace/seal entrypoint must not publish an empty or
partial signed inventory when the original producer retained that conflict.
These are source-neutral boundary tests, not new ceiling measurements.
"""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_source_closed_export import (
    build_live_ceiling_area_source_traces,
    seal_live_ceiling_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import _result, _shadow_quantity


def _traces(originals):
    return build_live_ceiling_area_source_traces(
        replace(_result(), quantity_evidence=tuple(originals)),
        workspace_id=7, project_id="source-project",
    )


def _seal(originals):
    return seal_live_ceiling_area_run(
        replace(_result(), quantity_evidence=tuple(originals)),
        workspace_id=7, project_id="source-project",
    )


def _blocked_firm():
    return replace(
        _shadow_quantity(), status="firm",
        blocking_reasons=("original_orthogonal_dimension_unresolved",),
    )


@pytest.mark.parametrize("entrypoint", [_traces, _seal])
def test_direct_source_seal_rejects_only_blocked_numeric_firm(entrypoint):
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        entrypoint((_blocked_firm(),))


@pytest.mark.parametrize("entrypoint", [_traces, _seal])
@pytest.mark.parametrize("reverse", [False, True])
def test_direct_source_seal_rejects_blocked_firm_in_mixed_inventory(entrypoint, reverse):
    valid = _shadow_quantity()
    broken = replace(_blocked_firm(), quantity_id="unrelated-blocked-original")
    originals = (broken, valid) if reverse else (valid, broken)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        entrypoint(originals)


@pytest.mark.parametrize("entrypoint", [_traces, _seal])
@pytest.mark.parametrize("reverse", [False, True])
def test_direct_source_seal_preserves_valid_ceiling_with_unrelated_abstention(entrypoint, reverse):
    valid = _shadow_quantity()
    abstained = replace(
        valid, quantity_id="unrelated-abstained-original",
        status="blocked", value=None, abstained=True,
        blocking_reasons=("original_ceiling_source_unavailable",),
    )
    originals = (abstained, valid) if reverse else (valid, abstained)
    published = entrypoint(originals)
    if entrypoint is _traces:
        assert len(published) == 1
    else:
        assert len(published.quantities) == 1
        assert published.quantities[0].value == 13.270425
        assert published.quantities[0].lineage_ok is True


@pytest.mark.parametrize("entrypoint", [_traces, _seal])
@pytest.mark.parametrize("reverse", [False, True])
def test_original_duplicate_id_precedes_numeric_firm_blocker(entrypoint, reverse):
    blocked = _blocked_firm()
    replay = _shadow_quantity()
    originals = (blocked, replay) if reverse else (replay, blocked)
    with pytest.raises(SourceClosedRunConflictError, match="duplicate or invalid original ceiling source quantity id"):
        entrypoint(originals)


@pytest.mark.parametrize("entrypoint", [_traces, _seal])
def test_direct_source_blocker_veto_does_not_mutate_originals(entrypoint):
    blocked = _blocked_firm()
    before = (blocked, blocked.metadata, blocked.blocking_reasons)
    with pytest.raises(SourceClosedRunConflictError, match="retains unresolved blockers"):
        entrypoint((blocked,))
    assert (blocked, blocked.metadata, blocked.blocking_reasons) == before


def test_direct_source_seal_preserves_existing_authentic_ceiling_quantity():
    run = _seal((_shadow_quantity(),))
    assert len(run.quantities) == 1
    assert run.quantities[0].value == 13.270425
    assert run.quantities[0].lineage_ok is True
