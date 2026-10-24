"""A fallback preview does not invent a 3 m by 2.7 m mass."""
from pb_render_resilience_v143 import _mass_figure


def test_supplied_size_is_drawn_and_a_missing_height_is_not() -> None:
    drawn = _mass_figure([{"x": 0, "y": 0, "width": 4, "depth": 3, "height": 3.0, "label": "Living"}])
    assert len(drawn.data) == 1
    omitted = _mass_figure([{"x": 0, "y": 0, "width": 4, "depth": 3, "label": "Living"}])
    assert len(omitted.data) == 0
