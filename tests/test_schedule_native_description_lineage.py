"""Complete source line retention never supplies table or row ownership."""
import pytest

from pb_schedule_opening_instance_binding_authority import _source_owned_description


def _words():
    return {
        "a": ("IPF3", "1", 7, 0, 0),
        "b": ("SOLID", "1", 7, 0, 1),
        "c": ("CORE", "1", 7, 0, 2),
    }


def test_complete_owned_native_line_retains_exact_words_without_mutation():
    words = _words()
    before = dict(words)
    assert _source_owned_description("IPF3", ("c", "a", "b"), words) == "IPF3 SOLID CORE"
    assert words == before


@pytest.mark.parametrize("failure", ["foreign_word", "missing_middle", "duplicate_number", "middle_prefix", "competing_start", "different_page", "different_line", "missing_lineage"])
def test_incomplete_or_competing_native_line_does_not_publish_truncated_description(failure):
    words = _words()
    ids = tuple(words)
    prefix = "IPF3"
    if failure == "foreign_word":
        ids = ("a", "b")
    elif failure == "missing_middle":
        del words["b"]
    elif failure == "duplicate_number":
        words["b"] = ("SOLID", "1", 7, 0, 0)
    elif failure == "middle_prefix":
        prefix = "SOLID"
    elif failure == "competing_start":
        words["d"] = ("IPF3", "1", 8, 0, 0)
        ids += ("d",)
    elif failure == "different_page":
        words["b"] = ("SOLID", "2", 7, 0, 1)
    elif failure == "different_line":
        words["b"] = ("SOLID", "1", 7, 1, 1)
    elif failure == "missing_lineage":
        words = {}
    assert _source_owned_description(prefix, ids, words) == ""
