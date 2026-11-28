"""Regression for native CAD paths containing both distinct jamb strokes."""
import pytest

from test_layered_wall_end_jamb_caps_v1 import (
    _build, _near_closed, _strict, thin,
)


@pytest.mark.parametrize("builder", [_build, _strict])
@pytest.mark.parametrize("tf", [lambda x, y: (x, y), lambda x, y: (y, x)])
def test_two_jambs_batched_in_one_native_path(builder, tf):
    rows = thin(tf)
    separate = builder(rows)
    assert _near_closed(separate, tf)
    rows[-2]["items"] += rows[-1]["items"]
    rows.pop()
    assert _near_closed(builder(rows), tf)


@pytest.mark.parametrize("builder", [_build, _strict])
def test_duplicate_single_jamb_does_not_close(builder):
    rows = thin()
    rows[-2]["items"] *= 2
    rows.pop()
    assert not _near_closed(builder(rows))
