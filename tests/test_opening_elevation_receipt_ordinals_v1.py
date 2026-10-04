"""Receipts may leave paint/line ordinals unresolved (``None``).

PdfTextIntegrityReceipt declares ``sequence_number``/``block_no`` as
``Optional[int] = None``.  The elevation-frame producer used to coerce them
with ``int(getattr(receipt, name, -1))``, which raises ``TypeError`` for a
present-but-``None`` value.  The live net-wall chain catches that exception and
abstains, so one such word silently removed every live wall/opening/room claim
for the document.

Contract pinned here:
* an unresolved ``sequence_number`` is only a tie-break after ``word_no`` and
  may sort first (-1);
* an unresolved line identity (``block_no``/``line_no``) or in-line order
  (``word_no``) makes the word unusable.  It must NOT collapse onto a shared
  sentinel, because words sharing (block, line) are assembled into one title
  line and unrelated words would then be merged.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_opening_elevation_frame_area_authority import (
    OpeningElevationFrameAreaProducer,
    _page_family_and_title_ids,
)

_word_from_receipt = OpeningElevationFrameAreaProducer._word_from_receipt


def _receipt(**overrides):
    values = dict(
        geometry=(10.0, 20.0, 40.0, 32.0),
        block_no=1,
        line_no=2,
        word_no=3,
        sequence_number=7,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_resolved_ordinals_are_preserved_exactly() -> None:
    word = _word_from_receipt("obs-1", _receipt(), "WINDOW")
    assert word is not None
    assert (word.block_no, word.line_no, word.word_no, word.sequence_number) == (1, 2, 3, 7)


def test_unresolved_sequence_number_does_not_raise_and_sorts_first() -> None:
    word = _word_from_receipt("obs-1", _receipt(sequence_number=None), "WINDOW")
    assert word is not None
    assert word.sequence_number == -1
    assert (word.block_no, word.line_no, word.word_no) == (1, 2, 3)


@pytest.mark.parametrize("field", ["block_no", "line_no", "word_no"])
def test_unresolved_line_identity_makes_the_word_unusable(field: str) -> None:
    assert _word_from_receipt("obs-1", _receipt(**{field: None}), "WINDOW") is None


def test_missing_ordinal_attributes_are_treated_as_unresolved() -> None:
    bare = SimpleNamespace(geometry=(10.0, 20.0, 40.0, 32.0))
    assert _word_from_receipt("obs-1", bare, "WINDOW") is None


def test_unresolved_words_never_merge_into_one_pseudo_line() -> None:
    """Two unrelated words with unresolved lines must not fabricate a title."""
    elevation = _word_from_receipt(
        "obs-elevation", _receipt(block_no=None, line_no=None, geometry=(0.0, 0.0, 80.0, 10.0)), "ELEVATION"
    )
    window = _word_from_receipt(
        "obs-window", _receipt(block_no=None, line_no=None, geometry=(500.0, 900.0, 540.0, 910.0)), "WINDOW"
    )
    assert elevation is None and window is None
    family, title_ids = _page_family_and_title_ids(
        [word for word in (elevation, window) if word is not None]
    )
    assert family is None and title_ids == ()


def test_resolved_same_line_words_still_form_a_title() -> None:
    """Control: the same two words on a genuinely shared line do form a title."""
    words = [
        _word_from_receipt("obs-w", _receipt(word_no=0, sequence_number=1, geometry=(0.0, 0.0, 40.0, 10.0)), "WINDOW"),
        _word_from_receipt("obs-e", _receipt(word_no=1, sequence_number=None, geometry=(45.0, 0.0, 120.0, 10.0)), "ELEVATION"),
    ]
    assert all(word is not None for word in words)
    family, title_ids = _page_family_and_title_ids(words)
    assert family == "window"
    assert set(title_ids) == {"obs-w", "obs-e"}
