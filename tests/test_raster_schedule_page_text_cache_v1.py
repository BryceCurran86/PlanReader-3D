from __future__ import annotations

from pb_raster_schedule_extractor import GenericScheduleTableExtractor


class _Page:
    def __init__(self) -> None:
        self.calls = {"text": 0, "words": 0, "blocks": 0}

    def get_text(self, mode: str):
        self.calls[mode] += 1
        if mode == "text":
            return "WINDOW SCHEDULE"
        if mode in {"words", "blocks"}:
            return []
        raise AssertionError(f"unexpected mode: {mode}")


def test_schedule_subdetectors_share_page_text_and_word_parses() -> None:
    page = _Page()
    extractor = GenericScheduleTableExtractor()

    assert extractor._extract_card_style_schedules(page, 1) == []
    assert extractor._extract_row_aligned_opening_schedules(page, 1) == []
    assert extractor._extract_column_aligned_schedules(page, 1) == []

    assert page.calls["words"] == 1
    assert page.calls["text"] == 1
