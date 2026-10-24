"""Original raster host frames cannot borrow a different W4 source scope."""
import pytest

from test_raster_opening_whole_wall_frame import (
    GEOMETRY, _binding, _opening, _producer, _record, _scope,
)


@pytest.mark.parametrize("field,foreign", [
    ("document_id", "foreign-document"),
    ("revision_id", "foreign-revision"),
    ("source_sha256", "b" * 64),
    ("snapshot_id", "stale-snapshot"),
    ("page_id", "2"),
    ("decision_scope_id", "unrelated-wall-source-scope"),
])
def test_source_credible_wall_in_foreign_scope_cannot_frame_opening(field, foreign):
    wall = _record("wall:host")
    scope = _scope((wall,))
    setattr(scope, field, foreign)
    result = _producer(scope)._raster_whole_wall_frame(
        binding=_binding(), opening=_opening(), geometry=GEOMETRY,
    )
    assert result is None


def test_original_six_scope_keys_preserve_real_whole_wall_frame_positive():
    result = _producer(_scope((_record("wall:host"),)))._raster_whole_wall_frame(
        binding=_binding(), opening=_opening(), geometry=GEOMETRY,
    )
    assert result is not None
    assert result.whole_wall_length == 200.0
    assert (result.u0, result.u1) == (80.0, 120.0)
