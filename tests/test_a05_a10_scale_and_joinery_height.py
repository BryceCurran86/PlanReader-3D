"""A05 & A10 tests: physical scale Unicode/thousands normalization & conflict veto, and joinery head-height note parsing."""
from __future__ import annotations

import pytest

from pb_document_joinery_head_height_authority import (
    _joinery_head_height_values,
    _parse_joinery_head_height_mm,
)
from pb_physical_scale_authority import (
    _TrustedWord,
    _physical_mm,
    _ratios,
)


@pytest.mark.parametrize(
    ("raw", "expected_mm"),
    [
        ("1,000mm", 1000.0),
        ("2,000 mm", 2000.0),
        ("5\u00a0m", 5000.0),
        ("2.5\u2009m", 2500.0),
        ("\uff15\uff4d", 5000.0),
        ("150 cm", 1500.0),
    ],
)
def test_a05_physical_mm_handles_unicode_spaces_fullwidth_and_thousands(
    raw: str, expected_mm: float
) -> None:
    assert _physical_mm(raw) == pytest.approx(expected_mm)


@pytest.mark.parametrize("bad", ["", "0 mm", "-100 mm", "1:100", "2,1 m"])
def test_a05_physical_mm_rejects_invalid_or_ambiguous_labels(bad: str) -> None:
    assert _physical_mm(bad) is None


def test_a05_ratios_detects_unicode_colons_thousands_and_conflicts() -> None:
    words = (
        _TrustedWord("t1", "1\u2236100", (0.0, 0.0, 20.0, 10.0)),
        _TrustedWord("t2", "1\uff1a1,000", (30.0, 0.0, 60.0, 10.0)),
        _TrustedWord("t3", "1\u00a0:\u00a050", (70.0, 0.0, 95.0, 10.0)),
    )
    assert _ratios(words) == (50.0, 100.0, 1000.0)


@pytest.mark.parametrize(
    ("note", "expected_mm"),
    [
        ("JOINERY HEIGHTS TO BE 2100 AFL U.N.O.", 2100.0),
        ("JOINERY HEIGHTS TO BE 2,100 MM AFL U.N.O.", 2100.0),
        ("JOINERY HEIGHT TO BE 2.1M AFL U.N.O.", 2100.0),
        ("JOINERY HEIGHTS TO BE 2.04 m AFL U.N.O.", 2040.0),
    ],
)
def test_a10_joinery_head_height_parses_mm_thousands_and_decimal_metres(
    note: str, expected_mm: float
) -> None:
    assert _parse_joinery_head_height_mm(note) == pytest.approx(expected_mm)


def test_a10_joinery_head_height_abstains_on_conflicting_heights() -> None:
    conflicting = (
        "JOINERY HEIGHTS TO BE 2,100 AFL U.N.O. "
        "AND JOINERY HEIGHTS TO BE 2.4M AFL U.N.O."
    )
    assert _joinery_head_height_values(conflicting) == (2100.0, 2400.0)
    assert _parse_joinery_head_height_mm(conflicting) is None


def test_a10_joinery_head_height_rejects_out_of_range_values() -> None:
    assert _parse_joinery_head_height_mm("JOINERY HEIGHTS TO BE 0.5M AFL U.N.O.") is None
    assert _parse_joinery_head_height_mm("JOINERY HEIGHTS TO BE 5.0M AFL U.N.O.") is None
