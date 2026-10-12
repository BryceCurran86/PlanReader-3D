"""Q02 ceiling lining FIRM identity cannot survive a blocked same-ID replay."""
from dataclasses import replace

import pytest

from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_lining_source_closed_export import _claim,_quantity


def test_original_authentic_rcp_lining_source_seals_positive_control():
    original=_quantity()
    claim=_claim(original)
    traces=build_live_ceiling_lining_source_traces(
        claim,workspace_id=7,project_id="authentic-ceiling-source",
    )
    assert len(traces)==1
    run=seal_live_ceiling_lining_run(
        claim,workspace_id=7,project_id="authentic-ceiling-source",
    )
    assert len(run.quantities)==1
    assert run.quantities[0].value==9.05352


@pytest.mark.parametrize("reverse",[False,True])
def test_blocked_replay_of_same_original_ceiling_id_quarantines_entire_seal(reverse):
    original=_quantity()
    blocked=replace(original,status="blocked",value=None,abstained=True,
        blocking_reasons=("original_finish_source_conflict",))
    quantities=(blocked,original) if reverse else (original,blocked)
    claim=replace(_claim(original),ceiling_lining_quantity_evidence=quantities)
    with pytest.raises(SourceClosedRunConflictError,match="duplicate or invalid"):
        build_live_ceiling_lining_source_traces(
            claim,workspace_id=7,project_id="authentic-ceiling-source",
        )
    with pytest.raises(SourceClosedRunConflictError,match="duplicate or invalid"):
        seal_live_ceiling_lining_run(
            claim,workspace_id=7,project_id="authentic-ceiling-source",
        )


@pytest.mark.parametrize("invalid",[True,42," ceiling-q ",""])
def test_original_ceiling_quantity_identity_never_string_coerced(invalid):
    original=_quantity()
    if invalid == "":
        # The dataclass itself must reject an empty identity before export.
        with pytest.raises(ValueError, match="quantity_id must be a non-empty string"):
            replace(original, quantity_id=invalid)
        return
    tampered=replace(original,quantity_id=invalid)
    claim=replace(_claim(original),ceiling_lining_quantity_evidence=(tampered,))
    with pytest.raises(SourceClosedRunConflictError,match="duplicate or invalid"):
        build_live_ceiling_lining_source_traces(
            claim,workspace_id=7,project_id="authentic-ceiling-source",
        )
