"""Commercial floor-finish IDs are unique before abstained-source filtering."""
from dataclasses import replace

import pytest

from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
    seal_live_floor_finish_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import _claim, _quantity


def _with_sources(*quantities):
    return replace(_claim(), floor_finish_quantity_evidence=quantities)


def _traces(*quantities):
    return build_live_floor_finish_area_source_traces(
        _with_sources(*quantities), workspace_id=1, project_id="original"
    )


@pytest.mark.parametrize("reverse", (False, True))
def test_original_source_id_collision_across_firm_and_abstain_fails_seal(reverse):
    firm = _quantity()
    abstain = replace(
        firm, abstained=True, value=None, status="provisional",
        blocking_reasons=("finish_source_occurrence_unresolved",),
    )
    pair = (abstain, firm) if reverse else (firm, abstain)
    with pytest.raises(
        SourceClosedRunConflictError, match="duplicate original floor-finish quantity id"
    ):
        _traces(*pair)
    with pytest.raises(
        SourceClosedRunConflictError, match="duplicate original floor-finish quantity id"
    ):
        seal_live_floor_finish_area_run(
            _with_sources(*pair), workspace_id=1, project_id="original"
        )


def test_two_blocked_original_source_records_cannot_reuse_one_quantity_id():
    firm = _quantity()
    blocked = replace(
        firm, value=None, status="provisional", abstained=True,
        blocking_reasons=("no_authenticated_material",),
    )
    with pytest.raises(
        SourceClosedRunConflictError, match="duplicate original floor-finish quantity id"
    ):
        _traces(blocked, blocked)


def test_distinct_blocked_source_is_unavailable_not_poisoning_true_firm_finish():
    firm = _quantity()
    blocked = replace(
        firm, quantity_id="other-source-unavailable",
        value=None, abstained=True, status="provisional",
        blocking_reasons=("unresolved_finish_occurrence",),
    )
    traces = _traces(blocked, firm)
    assert tuple(traces) == (firm.quantity_id,)
    run = seal_live_floor_finish_area_run(
        _with_sources(blocked, firm), workspace_id=1, project_id="original"
    )
    assert len(run.quantities) == 1
    assert run.quantities[0].quantity_id == firm.quantity_id


@pytest.mark.parametrize("bad", ("", " floor-finish-q1", "floor-finish-q1 ", True))
def test_malformed_original_source_id_must_fail_even_if_abstained(bad):
    firm = _quantity()
    blocked = replace(
        firm, value=None, abstained=True, status="provisional",
        blocking_reasons=("unproven",),
    )
    # Original typed constructor already rejects an empty source ID.
    # Test a deserialised or externally replayed receipt at the exporter.
    object.__setattr__(blocked, "quantity_id", bad)
    with pytest.raises(
        SourceClosedRunConflictError, match="invalid original floor-finish quantity id"
    ):
        _traces(firm, blocked)


def test_one_original_firm_finish_still_seals_with_unchanged_source_trace():
    firm = _quantity()
    traced = _traces(firm)
    assert tuple(traced) == (firm.quantity_id,)
    run = seal_live_floor_finish_area_run(
        _with_sources(firm), workspace_id=1, project_id="original"
    )
    assert len(run.quantities) == 1
    assert run.quantities[0].value == 8.64
    assert run.quantities[0].lineage_ok is True
