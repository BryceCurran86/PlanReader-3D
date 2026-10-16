"""Adversarial, source-neutral scope guards for GPT MAX opening completeness.

These guards do not establish physical-opening semantic completeness, host
authority, an area, a count or a commercial seal.
"""
from __future__ import annotations

import pytest

from pb_opening_universe_completeness_source_adapter import (
    _validated_scope_page_ids,
)


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        ("1", TypeError),                         # 01 scalar page
        ("12", TypeError),                        # 02 ambiguous two-char scalar
        (b"1", TypeError),                        # 03 bytes page
        (None, TypeError),                        # 04 missing explicit scope
        (123, TypeError),                         # 05 numeric input
        ({"1"}, TypeError),                       # 06 unordered scope
        ({"1": True}, TypeError),                 # 07 mapping input
        ((), ValueError),                         # 08 zero-page claim
        ([], ValueError),                         # 09 zero-page mutable input
        ((1,), TypeError),                        # 10 numeric member
        ((None,), TypeError),                     # 11 null member
        ((b"1",), TypeError),                      # 12 bytes member
        ((True,), TypeError),                     # 13 boolean member
        (("1", 2), TypeError),                     # 14 mixed scope
        (("",), ValueError),                       # 15 blank page
        ((" ",), ValueError),                      # 16 whitespace-only page
        ((" 1",), ValueError),                     # 17 padded prefix
        (("1 ",), ValueError),                     # 18 padded suffix
        (("1", "1"), ValueError),                  # 19 duplicate one-page scope
        (("1", "2", "1"), ValueError),             # 20 duplicate multipage scope
    ],
)
def test_bad_opening_universe_page_scopes_fail_closed(raw, error):
    with pytest.raises(error):
        _validated_scope_page_ids(raw)


@pytest.mark.parametrize("pages", [("1",), ["1", "2"], ("01", "02", "03")])
def test_valid_opening_universe_page_scopes_keep_exact_identity(pages):
    assert _validated_scope_page_ids(pages) == tuple(pages)
