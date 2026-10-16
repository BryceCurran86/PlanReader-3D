"""Synthetic original-F07 scope negatives. No claimed numeric authority."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diag_gptmax_original_viewport_mark_ownership import (
    STATUS, _fits, census_pages,
)


def view(view_id, bbox, *, status="resolved", kind="elevation",
         source="vector_frame", valid=True):
    return NS(view_id=view_id, bounding_box=bbox, status=status,
              view_type=kind, label="ELEVATION",
              boundary_source=source, valid=valid)


def word(t, n, x, y, *, line=0, block=0):
    return (x, y, x + 6.0, y + 4.0, t, block, line, n)


class Page:
    def __init__(self, words):
        self.words = words

    def get_text(self, how):
        assert how == "words"
        return list(self.words)


def report(views, words, *, title=()):
    return census_pages(
        [Page(words)], page_indices=[0], phrase="2127 STACKER",
        datum_tokens=["2100", "2590"],
        segment=lambda _page, *, page_number: list(views),
        is_f07_record=lambda v: v.valid, resolved_titles=title,
    )


def firstmark(result):
    return result["pages"][0]["mark_occurrences"][0]


def test_one_resolved_f07_frame_is_still_not_a_height():
    words = [word("2127", 0, 14, 25), word("STACKER", 1, 24, 25),
             word("2100", 0, 28, 40, line=1)]
    result = report([view("v1", (0, 0, 100, 100))], words)
    assert result["status"] == STATUS
    assert firstmark(result)["resolved_f07_vector_frame_view_id"] == "v1"
    assert result["pages"][0]["datum_token_occurrences"]["2100"][0][
        "resolved_f07_vector_frame_view_id"
    ] == "v1"
    assert firstmark(result)["dimension_anchor_bound_to_opening"] is False
    for field in ("specific_opening_dimension_binding_proven",
                  "cross_sheet_physical_identity_proven", "opening_count_proven",
                  "firm_quantity_granted"):
        assert result[field] is False


@pytest.mark.parametrize("views", [
    [view("v1", (0, 0, 26, 100))],
    [view("v1", (0, 0, 100, 100), status="derived", source="title_partition")],
    [view("v1", (0, 0, 100, 100), status="unsupported", source="none")],
    [view("v1", (0, 0, 100, 100), valid=False)],
    [view("v1", (0, 0, 100, 100)), view("v2", (0, 0, 100, 100))],
    [view("v1", (0, 0, 100, 100)),
     view("v2", (0, 0, 100, 100), status="derived", source="title_partition")],
])
def test_clipped_derived_untrusted_or_competing_frames_abstain(views):
    result = report(views, [word("2127", 0, 14, 25),
                            word("STACKER", 1, 24, 25)])
    assert firstmark(result)["resolved_f07_vector_frame_view_id"] is None


def test_different_datum_view_does_not_supply_height():
    words = [word("2127", 0, 14, 25), word("STACKER", 1, 24, 25),
             word("2100", 0, 28, 130, line=1)]
    result = report(
        [view("upper", (0, 0, 100, 100)),
         view("lower", (0, 110, 100, 160))], words,
    )
    assert firstmark(result)["resolved_f07_vector_frame_view_id"] == "upper"
    assert result["pages"][0]["datum_token_occurrences"]["2100"][0][
        "resolved_f07_vector_frame_view_id"
    ] == "lower"
    assert result["specific_opening_dimension_binding_proven"] is False


def test_competing_occurrences_never_resolve_by_first():
    words = [word("2127", 0, 14, 25), word("STACKER", 1, 24, 25),
             word("2127", 0, 14, 125, line=1),
             word("STACKER", 1, 24, 125, line=1)]
    result = report(
        [view("upper", (0, 0, 100, 100)),
         view("lower", (0, 110, 100, 160))], words,
    )
    assert [mark["resolved_f07_vector_frame_view_id"] for mark in
            result["pages"][0]["mark_occurrences"]] == ["upper", "lower"]


def test_unrelated_frame_cannot_claim_mark():
    result = report(
        [view("other", (200, 200, 400, 400))],
        [word("2127", 0, 14, 25), word("STACKER", 1, 24, 25)],
    )
    assert firstmark(result)["resolved_f07_vector_frame_view_id"] is None


def test_source_order_and_view_order_do_not_pick_a_winner():
    words = [word("STACKER", 1, 24, 25), word("2127", 0, 14, 25),
             word("2100", 0, 28, 130, line=1)]
    views = [view("upper", (0, 0, 100, 100)),
             view("lower", (0, 110, 100, 160))]
    a = report(views, words)
    b = report(list(reversed(views)), list(reversed(words)))
    assert firstmark(a)["resolved_f07_vector_frame_view_id"] == firstmark(b)[
        "resolved_f07_vector_frame_view_id"]
    assert a["pages"][0]["datum_token_occurrences"] == b["pages"][0][
        "datum_token_occurrences"]


@pytest.mark.parametrize("page_indices", [[], [0, 0], [-1], [1]])
def test_bad_pages_fail_closed(page_indices):
    with pytest.raises(ValueError):
        census_pages(
            [Page([])], page_indices=page_indices, phrase="2127 STACKER",
            datum_tokens=[],
            segment=lambda _p, *, page_number: [],
            is_f07_record=lambda _: False,
        )


def test_duplicate_producer_view_id_is_rejected():
    with pytest.raises(ValueError, match="non-unique"):
        report([view("x", (0, 0, 100, 100)),
                view("x", (0, 0, 100, 100))], [])


def test_complete_bbox_required():
    assert _fits([1, 1, 2, 2], [0, 0, 3, 3])
    assert not _fits([1, 1, 4, 2], [0, 0, 3, 3])
    assert not _fits([1, 1, 2, 2], None)


def test_title_metadata_does_not_create_physical_source():
    title = [NS(title="ELEVATIONS", sheet_number="A-500", source="label")]
    result = report(
        [], [word("2127", 0, 14, 25), word("STACKER", 1, 24, 25)],
        title=title,
    )
    assert result["pages"][0]["source_title_block_sheet_code"] == "A-500"
    assert firstmark(result)["resolved_f07_vector_frame_view_id"] is None
