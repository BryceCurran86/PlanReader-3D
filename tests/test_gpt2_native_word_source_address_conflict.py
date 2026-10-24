"""Native PDF word identity conflicts must stop source-to-floor mark census."""
import pytest
import fitz

import tools.gpt2_native_material_mark_census as census
from tests.test_gpt2_native_ft2_ft3_original_mark_census import _synthetic, _census


class _Page:
    def __init__(self, words):
        self.words = words

    def get_text(self, kind, sort=False):
        assert kind == "words" and sort is False
        return self.words


class _Doc:
    page_count = 1

    def __init__(self, words):
        self.words = words

    def load_page(self, index):
        assert index == 0
        return _Page(self.words)

    def close(self):
        pass


def _source_words():
    data = _synthetic()
    with fitz.open(stream=data, filetype="pdf") as pdf:
        words = list(pdf[0].get_text("words", sort=False))
    return data, words


def test_conflicting_native_source_word_identity_rejected_before_partition(monkeypatch):
    data, words = _source_words()
    assert len(words) >= 2
    # Duplicate one native source token: even different ink cannot re-key
    # the same source-owned (page, block, line, word) receipt.
    duplicated = list(words[0])
    duplicated[4] = "FT3"
    monkeypatch.setattr(census.fitz, "open", lambda **kw: _Doc([*words, duplicated]))
    with pytest.raises(ValueError, match="duplicate_original_source_word_address"):
        _census(data)


@pytest.mark.parametrize("bad_index", [-1, True, 0.25, None])
def test_malformed_original_word_address_never_mints_mark_identity(monkeypatch, bad_index):
    data, words = _source_words()
    damaged = list(words[0])
    damaged[5] = bad_index
    monkeypatch.setattr(census.fitz, "open", lambda **kw: _Doc([damaged, *words[1:]]))
    with pytest.raises(ValueError, match="malformed_original_source_word_address"):
        _census(data)


def test_valid_native_words_and_plan_schedule_partition_unchanged():
    result = _census(_synthetic())
    assert len(result["within_supplied_plan_view"]) == 1
    assert len(result["outside_supplied_plan_view"]) == 1
    assert result["source_word_partition_complete"] is True
    assert result["new_firm_floor_finish_quantities"] == 0
