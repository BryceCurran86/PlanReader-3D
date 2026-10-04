from __future__ import annotations

from pb_figured_dimension_evidence import (
    calibrate_dimension_layout,
    extract_native_dimension_observations,
    extract_vector_segments,
)


class _Page:
    def __init__(self) -> None:
        self.word_calls = 0
        self.drawing_calls = 0

    def get_text(self, mode: str):
        assert mode == "words"
        self.word_calls += 1
        return [(0.0, 0.0, 20.0, 8.0, "1200", 0, 0, 0)]

    def get_drawings(self):
        self.drawing_calls += 1
        return []


def test_dimension_consumers_share_raw_page_words_and_drawings() -> None:
    page = _Page()

    calibration = calibrate_dimension_layout(page)
    first = extract_native_dimension_observations(
        page,
        page_num=1,
        view_id="viewport-a",
        view_type="floor_plan",
    )
    second = extract_native_dimension_observations(
        page,
        page_num=1,
        view_id="viewport-b",
        view_type="floor_plan",
    )
    first_segments = extract_vector_segments(page, page_num=1, view_id="viewport-a")
    second_segments = extract_vector_segments(page, page_num=1, view_id="viewport-b")

    assert calibration.median_word_height_pt == 8.0
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].view_id == "viewport-a"
    assert second[0].view_id == "viewport-b"
    assert first_segments == []
    assert second_segments == []
    assert page.word_calls == 1
    assert page.drawing_calls == 1
