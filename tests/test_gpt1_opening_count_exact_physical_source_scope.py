"""Q04 original counted opening must preserve page and viewport source ownership."""
from dataclasses import replace

import pytest

from pb_live_opening_count_source_closed_export import build_live_opening_count_source_traces
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_opening_count_quantity_publication import (
    _floor_plan_with_schedule_quantity,
)


def _verified(tmp_path):
    file=tmp_path/"original-counted.pdf"
    file.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim=collect_live_physical_net_wall_claim(file,pages=(0,))
    assert len(claim.canonical_openings)==1
    assert len(claim.opening_count_quantity_evidence)==1
    return claim


def test_original_source_one_explicit_schedule_window_remains_sealable(tmp_path):
    claim=_verified(tmp_path)
    traces=build_live_opening_count_source_traces(
        claim,workspace_id=13,project_id="project-13",
    )
    assert len(traces)==1
    receipt=next(iter(traces.values()))
    assert receipt.canonical_entity_ids==(claim.canonical_openings[0].canonical_opening_id,)
    assert receipt.source_sha256==claim.canonical_openings[0].source_sha256


@pytest.mark.parametrize("field,value", [
    ("page_id",True),("page_id",1),("page_id"," 1"),
    ("page_id",""),("page_id",None),
    ("viewport_id",True),("viewport_id",1),("viewport_id"," vp-1"),
    ("viewport_id",""),("viewport_id",None),
])
def test_replayed_count_member_must_keep_original_source_scope(tmp_path,field,value):
    claim=_verified(tmp_path)
    opening=replace(claim.canonical_openings[0],**{field:value})
    forged=replace(claim,canonical_openings=(opening,))
    with pytest.raises(SourceClosedRunConflictError,match="original page/viewport"):
        build_live_opening_count_source_traces(
            forged,workspace_id=13,project_id="project-13",
        )
