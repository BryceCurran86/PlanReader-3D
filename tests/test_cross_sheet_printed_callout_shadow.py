"""Adversarial negative tests for non-authoritative printed callout census."""
from __future__ import annotations

import random
import pytest

from pb_cross_sheet_printed_callout_shadow import (
    candidates_for_resolved_sheet_shadow,
    find_printed_callout_candidates_shadow,
)


class Page:
    def __init__(self, words):
        self.words = list(words)

    def get_text(self, kind):
        assert kind == "words"
        return self.words


def w(text, x, index, *, block=0, line=0, y=10):
    return (x, y, x + max(2, len(text) * 4), y + 10, text, block, line, index)


@pytest.mark.parametrize("literal,mark,sheet", [
    ("1/A201", "1", "A201"), ("12/A-201", "12", "A-201"),
    ("2/S-0.01", "2", "S-0.01"), ("99/AB123", "99", "AB123"),
])
def test_compact_printed_shapes(literal, mark, sheet):
    result = find_printed_callout_candidates_shadow(Page([w(literal, 10, 0)]), page_num=7)
    assert [(e.mark, e.referenced_sheet_code, e.source_page) for e in result] == [(mark, sheet, 7)]


@pytest.mark.parametrize("texts", [
    ("1", "/", "A-201"), ("1/", "A-201"), ("1", "/A-201"),
])
def test_contiguous_split_tokens(texts):
    offset = 10
    words = []
    for i, text in enumerate(texts):
        words.append(w(text, offset, i))
        offset = words[-1][2] + 0.5
    result = find_printed_callout_candidates_shadow(Page(words), page_num=11)
    assert [(e.mark, e.referenced_sheet_code) for e in result] == [("1", "A-201")]


@pytest.mark.parametrize("literal", [
    "A201", "1/250", "1:100", "FT3", "PWD", "2/", "/A-201", "2/A-201_extra",
    "SECTION/A-201", "12/A-201/3", "1/A-201.1.2", "1234/A201", "1/A-201,",
    "1/A-201/B202", "2/A_201", "2/A201.1234",
])
def test_not_a_printed_callout(literal):
    assert find_printed_callout_candidates_shadow(Page([w(literal, 10, 0)]), page_num=1) == []


@pytest.mark.parametrize("mutation", [
    lambda a, b: [a, (b[0], b[1], b[2], b[3], b[4], b[5], 1, b[7])],
    lambda a, b: [a, (b[0], b[1], b[2], b[3], b[4], 1, b[6], b[7])],
    lambda a, b: [a, (b[0], b[1], b[2], b[3], b[4], b[5], b[6], 2)],
    lambda a, b: [a, (200, b[1], 218, b[3], b[4], b[5], b[6], b[7])],
])
def test_split_cross_line_block_nonadjacent_or_far_ink_abstains(mutation):
    a, b = w("1/", 10, 0), w("A201", 23, 1)
    assert find_printed_callout_candidates_shadow(Page(mutation(a, b)), page_num=1) == []


def test_full_page_words_are_immutable():
    page = Page([w("1/A-201", 10, 0), w("2/S-0.01", 90, 1)])
    before = tuple(page.words)
    find_printed_callout_candidates_shadow(page, page_num=1)
    assert tuple(page.words) == before


def test_target_sheet_exact_spelling_not_hyphen_alias():
    page = Page([w("1/A201", 10, 0), w("2/A-201", 70, 1), w("3/S-0.01", 130, 2)])
    items = find_printed_callout_candidates_shadow(page, page_num=1)
    assert len(items) == 3
    assert [x.mark for x in candidates_for_resolved_sheet_shadow(items, sheet_number="A-201")] == ["2"]
    assert [x.mark for x in candidates_for_resolved_sheet_shadow(items, sheet_number="A201")] == ["1"]
    assert [x.mark for x in candidates_for_resolved_sheet_shadow(items, sheet_number="S-0.01")] == ["3"]


@pytest.mark.parametrize("target", ["", "ambiguous", "A-201 / A-202", "FLOOR PLAN", "A 201", "A-201 1:100"])
def test_unresolved_title_block_identity_never_matches(target):
    items = find_printed_callout_candidates_shadow(Page([w("1/A201", 10, 0)]), page_num=1)
    assert candidates_for_resolved_sheet_shadow(items, sheet_number=target) == []


def test_competing_targets_preserved_not_nearest_elected():
    page = Page([w("1/A201", 10, 0), w("1/A202", 60, 1), w("2/S-0.01", 120, 2)])
    items = find_printed_callout_candidates_shadow(page, page_num=11)
    assert len(items) == 3
    assert {e.referenced_sheet_code for e in items} == {"A201", "A202", "S-0.01"}


def test_input_order_independent():
    words = [w("1/A201", 10, 0), w("1/A202", 70, 1), w("2/S-0.01", 130, 2)]
    baseline = find_printed_callout_candidates_shadow(Page(words), page_num=7)
    for seed in range(10):
        candidate_words = words[:]
        random.Random(seed).shuffle(candidate_words)
        assert find_printed_callout_candidates_shadow(Page(candidate_words), page_num=7) == baseline


def test_nonfinite_geometry_excluded():
    page = Page([w("1/A201", float("nan"), 0), w("2/A-201", 60, 1)])
    assert [x.mark for x in find_printed_callout_candidates_shadow(page, page_num=1)] == ["2"]


def test_existing_production_parser_does_not_change():
    from pb_cross_sheet_callout_evidence import find_callout_references
    page = Page([w("1/A20", 10, 0), w("2/A-201", 60, 1)])
    assert [x.referenced_sheet_code for x in find_callout_references(page, page_num=1)] == ["A20"]
    assert [x.referenced_sheet_code for x in find_printed_callout_candidates_shadow(page, page_num=1)] == ["A20", "A-201"]
