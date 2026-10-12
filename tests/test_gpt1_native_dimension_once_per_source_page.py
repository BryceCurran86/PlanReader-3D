"""Q01 source-native dimension words are authenticated once per component run."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import pb_native_dimension_cap_evidence as native


def _source_axes(n):
    return {
        f"native-axis-{i}": (float(i*25), 0.0, float(i*25+12), 0.0)
        for i in range(n)
    }


def _source_words():
    return [
        {"id": "text-dimension-1", "text": "2500",
         "bbox": (2.0, 2.0, 9.0, 5.0), "axis": (1.0, 0.0)},
        {"id": "text-room-label", "text": "OFFICE",
         "bbox": (30.0, 2.0, 50.0, 5.0), "axis": (1.0, 0.0)},
        {"id": "text-dimension-2", "text": "600",
         "bbox": (52.0, 2.0, 59.0, 5.0), "axis": (0.0, 1.0)},
    ]


@pytest.mark.parametrize("axes", [1, 10, 55])
def test_each_original_source_word_classified_only_once(axes):
    segments = _source_axes(axes)
    words = _source_words()
    original_words = tuple(tuple(sorted(word.items())) for word in words)
    classifier = native.classify_dimension_token
    with patch.object(native, "classify_dimension_token", wraps=classifier) as check:
        result = native.compile_native_dimension_cap_components(
            segments=segments, words=words,
        )
    assert check.call_count == len(words)
    assert isinstance(result, tuple)
    assert tuple(tuple(sorted(word.items())) for word in words) == original_words


def test_no_original_axis_does_not_force_unneeded_text_authentication():
    words = [{"id": "bad-native", "text": "???", "axis": None, "bbox": None}]
    with patch.object(native, "classify_dimension_token", wraps=native.classify_dimension_token) as check:
        assert native.compile_native_dimension_cap_components(
            segments={}, words=words,
        ) == ()
    assert check.call_count == 0
