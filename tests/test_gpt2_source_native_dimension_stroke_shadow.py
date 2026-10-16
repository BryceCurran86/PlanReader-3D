"""Strict native-stroke candidate census: no measure/owner/cross-sheet grant."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_source_native_dimension_stroke_shadow import (
    nominate_printed_native_dimension_strokes as nominate,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
ORIGINAL_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _word(text, *, box=(10., 20., 30., 30.)):
    return (*box, text, 1, 2, 3)


class FakePage:
    def __init__(self, strokes):
        self._strokes = strokes

    def get_drawings(self):
        return self._strokes


def _line(a, b, *, color=(0.,0.,0.), opacity=1., width=.48, kind="s"):
    return {
        "type":kind, "color":color,
        "stroke_opacity":opacity, "width":width,
        "items":[("l", SimpleNamespace(x=a[0],y=a[1]),
                       SimpleNamespace(x=b[0],y=b[1]))],
    }


def test_one_real_black_axis_source_segment_is_only_nomination():
    source = FakePage([_line((20.,0.),(20.,100.))])
    rows = nominate(source, _word("3570"))
    assert len(rows) == 1
    assert rows[0]["source_primitive_id"] == "d0i0"
    assert rows[0]["native_segment_length_pdf_pts"] == 100.
    assert rows[0]["word_candidate_not_authenticated_dimension"]
    assert not rows[0]["printed_dimension_witness_complete"]
    assert not rows[0]["source_physical_room_owner_proven"]


@pytest.mark.parametrize("bad", [
    ("0", (10.,20.,30.,30.)), ("92", (10.,20.,30.,30.)),
    ("FT2", (10.,20.,30.,30.)), ("3570mm", (10.,20.,30.,30.)),
    ("3570", (float("nan"),20.,30.,30.)),
    ("3570", (10.,20.,10.,30.)), ("3570", (10.,20.,30.,20.)),
])
def test_reject_bad_words_without_election(bad):
    assert nominate(FakePage([_line((20.,0.),(20.,100.))]),
                    _word(bad[0], box=bad[1])) == []


@pytest.mark.parametrize("stroke", [
    _line((20.,0.),(20.,100.), color=(1.,1.,1.)),
    _line((20.,0.),(20.,100.), color=(.5,.5,.5)),
    _line((20.,0.),(20.,100.), opacity=0.0),
    _line((20.,0.),(20.,100.), width=0.0),
    _line((20.,0.),(20.,100.), kind="f"),
    _line((20.,0.),(100.,80.)),
    _line((20.,0.),(20.,35.)),
])
def test_nonblack_hidden_fill_diagonal_or_too_short_not_a_dimension_candidate(stroke):
    assert nominate(FakePage([stroke]), _word("3570")) == []


def test_rival_black_line_candidates_are_all_retained_not_ranked_or_elected():
    a = _line((20.,0.),(20.,100.))
    b = _line((25.,0.),(25.,150.))
    rows = nominate(FakePage([a,b]),_word("3570"))
    assert len(rows) == 2
    assert [r["source_primitive_id"] for r in rows] == ["d0i0","d1i0"]
    assert all(not r["printed_dimension_witness_complete"] for r in rows)


def test_injected_native_word_is_not_modified():
    native = _word("3570")
    before = native
    nominate(FakePage([_line((20.,0.),(20.,100.))]), native)
    assert native == before


def test_original_page_a502_figured_3570_2200_native_lineage_recovered():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA
    with fitz.open(stream=raw,filetype="pdf") as pdf:
        assert len(pdf)==31
        page=pdf[25]
        original_words = page.get_text("words")
        dimension_cases = {
            "3570": ("d12615i0", 404.88, "native_y"),
            "2200": ("d12656i0", 249.36, "native_x"),
        }
        recovered = {}
        for raw_word in original_words:
            if raw_word[4] not in dimension_cases:
                continue
            rows = nominate(page, raw_word)
            for row in rows:
                recovered.setdefault(raw_word[4],[]).append(row)
        for literal, (primitive, expected_pts, axis) in dimension_cases.items():
            assert len(recovered[literal]) == 1
            row = recovered[literal][0]
            assert row["source_primitive_id"] == primitive
            assert row["line_axis"] == axis
            assert row["native_segment_length_pdf_pts"] == pytest.approx(expected_pts, abs=.01)
            assert row["word_candidate_not_authenticated_dimension"]
            assert not row["printed_dimension_witness_complete"]
            assert not row["source_physical_room_owner_proven"]
        # Candidate physical scale consistency is a diagnostic relation only.
        ratio_a = recovered["3570"][0]["native_segment_length_pdf_pts"]/3570
        ratio_b = recovered["2200"][0]["native_segment_length_pdf_pts"]/2200
        assert abs(ratio_a-ratio_b)/max(ratio_a,ratio_b) < .002
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA
