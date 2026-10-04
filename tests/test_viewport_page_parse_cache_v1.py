from __future__ import annotations

from types import SimpleNamespace

from pb_viewport_segmentation import (
    _axis_aligned_long_source_lines,
    _drawing_vector_primitive_count,
    _text_fragments,
    calibrate_viewport_layout,
    extract_vector_frames,
)


class _Page:
    def __init__(self) -> None:
        self.rect = SimpleNamespace(width=600.0, height=400.0)
        self.text_calls = {"words": 0, "dict": 0, "blocks": 0}
        self.drawing_calls = 0

    def get_text(self, mode: str):
        self.text_calls[mode] += 1
        if mode == "words":
            return [(10.0, 10.0, 40.0, 20.0, "PLAN", 0, 0, 0)]
        if mode == "dict":
            return {"blocks": []}
        if mode == "blocks":
            return []
        raise AssertionError(f"unexpected mode: {mode}")

    def get_drawings(self):
        self.drawing_calls += 1
        return []


def test_viewport_helpers_share_native_page_parses() -> None:
    page = _Page()
    calibration = calibrate_viewport_layout(page)

    assert _text_fragments(page) == []
    assert _text_fragments(page) == []
    assert extract_vector_frames(page, calibration) == []
    assert _axis_aligned_long_source_lines(page, calibration) == ((), ())
    assert (
        _drawing_vector_primitive_count(
            page,
            (0.0, 0.0, 300.0, 300.0),
            calibration,
        )
        == 0
    )

    assert page.text_calls == {"words": 1, "dict": 1, "blocks": 1}
    assert page.drawing_calls == 1
