"""Q04 source-owned one physical opening cannot seal two count rows."""
from dataclasses import replace

import pytest

from pb_live_opening_count_source_closed_export import (
    build_live_opening_count_source_traces, seal_live_opening_count_run,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_opening_count_quantity_publication import _floor_plan_with_schedule_quantity


def _one_source(tmp_path):
    file=tmp_path/"authentic-scheduled-opening.pdf"
    file.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    result=collect_live_physical_net_wall_claim(file,pages=(0,))
    assert len(result.canonical_openings)==1
    assert len(result.opening_count_quantity_evidence)==1
    return result


def test_one_explicit_original_schedule_count_still_signs_one_physical_member(tmp_path):
    source=_one_source(tmp_path)
    traces=build_live_opening_count_source_traces(
        source,workspace_id=19,project_id="source-count-19",
    )
    assert len(traces)==1
    sealed=seal_live_opening_count_run(
        source,workspace_id=19,project_id="source-count-19",
    )
    assert len(sealed.quantities)==1
    assert sealed.quantities[0].value==1.0


@pytest.mark.parametrize("reverse_order",[False,True])
def test_same_original_member_never_signs_two_distinct_commercial_count_rows(tmp_path,reverse_order):
    source=_one_source(tmp_path)
    original=source.opening_count_quantity_evidence[0]
    duplicate=replace(original,quantity_id="alternative-source-owned-quantity-identity")
    rows=(duplicate,original) if reverse_order else (original,duplicate)
    disputed=replace(source,opening_count_quantity_evidence=rows)
    with pytest.raises(SourceClosedRunConflictError,match="counted across multiple"):
        build_live_opening_count_source_traces(
            disputed,workspace_id=19,project_id="source-count-19",
        )
    with pytest.raises(SourceClosedRunConflictError,match="counted across multiple"):
        seal_live_opening_count_run(
            disputed,workspace_id=19,project_id="source-count-19",
        )
