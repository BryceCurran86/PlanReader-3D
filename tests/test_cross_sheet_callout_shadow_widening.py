"""Shadow callout widening never changes the production registration defaults."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from pb_cross_sheet_callout_evidence import (
    find_callout_near_geometry,
    find_callout_references,
    find_unique_bound_target_page,
    find_unique_page_sheet_code,
)
from pb_page_title_authority import PageTitle


@dataclass
class Page:
    words: list[tuple]
    number: int = 0

    def get_text(self, kind: str):
        assert kind == "words"
        return list(self.words)


def word(text: str, x: float, y: float, *, block: int = 0, line: int = 0, pos: int = 0):
    return (x, y, x + max(6, len(text) * 5), y + 10, text, block, line, pos)


def bound(page_no: int, code: str, source: str = "label-bound SHEET NO") -> PageTitle:
    return PageTitle(
        page_no=page_no, title="GENERAL ARRANGEMENT", confidence=96,
        source="label", region="title block", reason="field label",
        sheet_number=code, sheet_number_source=source, text_source="native",
        candidates=[],
    )


@pytest.mark.parametrize("text,expected", [
    ("1/A201", "A201"),
    ("5/A-302", "A-302"),
    ("5 / A-302", "A-302"),
    ("5/S-0.01", "S-0.01"),
])
def test_whole_token_widening_is_opt_in(text, expected):
    page = Page([word(text, 12, 20)])
    legacy = find_callout_references(page, page_num=1)
    extended = find_callout_references(page, page_num=1, shadow_extended=True)
    assert len(legacy) == (1 if text == "1/A201" else 0)
    assert len(extended) == 1
    assert (extended[0].mark, extended[0].referenced_sheet_code) == (
        text.split("/")[0].strip(), expected
    )


def test_adjacent_words_slash_form_is_shadow_only_and_source_is_unchanged():
    words = [word("5", 10, 40, pos=0), word("/", 20, 40, pos=1),
             word("A-302", 30, 40, pos=2)]
    page = Page(words)
    assert find_callout_references(page, page_num=2) == []
    expected = find_callout_references(page, page_num=2, shadow_extended=True)
    assert len(expected) == 1
    assert expected[0].mark == "5"
    assert expected[0].referenced_sheet_code == "A-302"
    assert expected[0].source_page == 2
    assert words == page.words
    assert find_callout_references(Page(list(reversed(words))), page_num=2, shadow_extended=True) == expected


def test_stacked_words_are_opt_in_but_distant_pairs_are_not():
    words = [word("5", 20, 5, line=0), word("A-302", 11, 17, line=1)]
    page = Page(words)
    assert find_callout_references(page, page_num=1) == []
    assert len(find_callout_references(page, page_num=1, shadow_extended=True)) == 1
    distant = Page([word("5", 20, 5), word("A-302", 400, 400, pos=1)])
    assert find_callout_references(distant, page_num=1, shadow_extended=True) == []


@pytest.mark.parametrize("tokens", [
    ["5", "see", "A-302"],
    ["5", "A-302", "unrelated"],
    ["5", "-", "A-302"],
    ["see", "detail", "on", "sheet", "S-203"],
])
def test_no_sentence_or_unprinted_separator_infers_callout(tokens):
    page = Page([word(text, n * 140.0, 10, pos=n) for n, text in enumerate(tokens)])
    assert find_callout_references(page, page_num=1, shadow_extended=True) == []


def test_multiple_near_callouts_still_abstain_in_shadow():
    page = Page([word("5/A-302", 10, 20, pos=0), word("6/A-302", 30, 40, line=1, pos=0)])
    assert find_callout_near_geometry(
        page, page_num=1, geometry_bbox=(10, 10, 100, 100),
        proximity_pt=120, shadow_extended=True,
    ) is None


def test_target_sheet_requires_title_reader_binding_not_stray_word():
    page = Page([word("A-302", 10, 10), word("S-0.01", 40, 20)])
    # Existing production token census is deliberately unchanged.
    assert find_unique_page_sheet_code(page) is None
    title = bound(1, "A-302")
    assert find_unique_page_sheet_code(page, bound_title=title) == "A-302"
    assert find_unique_page_sheet_code(page, bound_title=bound(2, "A-302")) is None
    assert find_unique_page_sheet_code(page, bound_title=bound(1, "A-302", "")) is None


def test_unique_title_bound_target_sheet_matching_and_conflicts():
    pages = [bound(1, "A201"), bound(2, "A-302"), bound(3, "S-0.01")]
    assert find_unique_bound_target_page(pages, "A-302") == 2
    assert find_unique_bound_target_page(pages, "s-0.01") == 3
    assert find_unique_bound_target_page(pages, "Z-404") is None
    assert find_unique_bound_target_page(pages + [bound(4, "A-302")], "A-302") is None
    assert find_unique_bound_target_page([bound(1, "A-302", "")], "A-302") is None
    assert find_unique_bound_target_page([bound(1, "A-302", "ambiguous: A-302, A-303")], "A-302") is None


def test_source_text_and_title_records_remain_unmodified():
    page = Page([word("5/A-302", 10, 10)])
    words_before = list(page.words)
    titles = [bound(1, "A-302"), bound(2, "S-0.01")]
    before = [title.meta() for title in titles]
    for _ in range(2):
        assert find_callout_references(page, page_num=1, shadow_extended=True)
        assert find_unique_bound_target_page(titles, "S-0.01") == 2
    assert words_before == page.words
    assert before == [title.meta() for title in titles]
