"""Q04 source count trace requires original workspace identity before filtering."""
import pytest

from pb_live_opening_count_source_closed_export import build_live_opening_count_source_traces
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_floor_finish_area_source_closed_export import _claim


def _build(workspace):
    # Unavailable opening count is not a zero or a default count=1.
    return build_live_opening_count_source_traces(
        _claim(), workspace_id=workspace, project_id="source-project"
    )


def test_real_positive_workspace_preserves_unsupported_opening_count_as_empty():
    assert _build(17) == {}


@pytest.mark.parametrize("bad", [True, False, 17.0, 17.3, "17", "017", " 17", None, 0, -17])
def test_count_trace_rejects_lossy_source_workspace_even_without_openings(bad):
    with pytest.raises(SourceClosedRunConflictError, match="workspace_id"):
        _build(bad)
