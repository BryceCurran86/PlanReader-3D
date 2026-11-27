"""A07 tests: Unicode dimensions, rotated/split text, and schedule/tag normalization with ambiguity guards."""
from __future__ import annotations

import pytest

from pb_opening_schedule_v171 import (
    _parse_strict_schedule_dims_cell,
    parse_dimension,
    parse_single_dimension,
)
from pb_opening_tag_normalization import (
    find_explicit_opening_tags,
    normalize_opening_tag,
)


@pytest.mark.parametrize(
    ("raw", "expected_tag", "expected_trade"),
    [
        ("D\u201303", "D3", "doors"),
        ("W\u201407", "W7", "windows"),
        ("D\u221212", "D12", "doors"),
        ("W\u00a007", "W7", "windows"),
        ("DOOR\u200904", "D4", "doors"),
        ("\uff24\uff0d\uff10\uff15", "D5", "doors"),
        ("\uff37\uff10\uff19", "W9", "windows"),
        ("W\u200b02", "W2", "windows"),
    ],
)
def test_unicode_opening_tag_normalization(raw: str, expected_tag: str, expected_trade: str) -> None:
    norm = normalize_opening_tag(raw)
    assert norm is not None
    assert norm.tag == expected_tag
    assert norm.trade_type == expected_trade


@pytest.mark.parametrize(
    "ambiguous_or_non_tag",
    [
        "D\u201301 / D\u201302",
        "W\u201301 & W\u201302",
        "D8\u201303\u2013200",
        "820\u27152040",
        "",
        "\u00a0\u2009",
    ],
)
def test_unicode_opening_tag_ambiguity_and_negative_abstain(ambiguous_or_non_tag: str) -> None:
    assert normalize_opening_tag(ambiguous_or_non_tag) is None


def test_find_explicit_opening_tags_handles_unicode_dashes() -> None:
    found = find_explicit_opening_tags("D\u201301 and W\u221202")
    assert [(t.tag, t.trade_type) for t in found] == [("D1", "doors"), ("W2", "windows")]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("820\u2009\u2715\u20092040", (820, 2040)),
        ("820\u27162040", (820, 2040)),
        ("1,200 \u00d7 2,100", (1200, 2100)),
        ("\uff18\uff12\uff10\u00d7\uff12\uff10\uff14\uff10", (820, 2040)),
        ("820\u20442040", (820, 2040)),
        ("920\u00a0\u22c5\u00a02100", (920, 2100)),
    ],
)
def test_unicode_dimension_pair_normalization(raw: str, expected: tuple[int, int]) -> None:
    assert parse_dimension(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2,100 mm", 2100),
        ("1,800\u00a0mm", 1800),
        ("\uff12\uff10\uff14\uff10mm", 2040),
        ("2.1\u2009m", 2100),
    ],
)
def test_unicode_single_dimension_normalization(raw: str, expected: int) -> None:
    assert parse_single_dimension(raw) == expected


@pytest.mark.parametrize(
    "ambiguous",
    [
        "820\u27152040 / 920\u27152040",
        "1,200\u00d72,100 or 1,500\u00d72,100",
        "820mm 920mm 2040mm",
    ],
)
def test_unicode_dimension_pair_ambiguity_abstains(ambiguous: str) -> None:
    assert parse_dimension(ambiguous) == (None, None)


def test_unicode_single_dimension_ambiguity_abstains() -> None:
    assert parse_single_dimension("820\u00a0mm or 920\u00a0mm") is None


def test_strict_schedule_dims_cell_accepts_unicode_multiply_and_rejects_fire_rating() -> None:
    assert _parse_strict_schedule_dims_cell("820\u00a0\u2715\u00a02,040") == (820, 2040)
    assert _parse_strict_schedule_dims_cell("-/60/30") == (None, None)
