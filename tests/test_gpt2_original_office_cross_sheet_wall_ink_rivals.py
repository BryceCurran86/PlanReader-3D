"""Keep every true and partial OFFICE wall source rival under original -78pt."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_cross_sheet_wall_ink_rivals import (
    audit_original_cross_sheet_wall_ink_rivals as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _synthetic():
    pdf = fitz.open()
    p1 = pdf.new_page()
    p1.draw_line((10, 10), (10, 80), color=(0,0,0), width=.48)
    p1.draw_line((10, 20), (10, 60), color=(0,0,0), width=.48)
    p1.draw_line((10, 10), (10, 80), color=(0,0,0), width=1)
    p2 = pdf.new_page()
    p2.draw_line((20, 80), (20, 10), color=(0,0,0), width=.48)
    raw = pdf.tobytes()
    pdf.close()
    return raw


def _run(raw, **extra):
    kwargs = {
        "expected_sha256": hashlib.sha256(raw).hexdigest(),
        "finish_page_1_based": 2, "floor_page_1_based": 1,
        "finish_source_path_item_ids": ("d0i0",),
        "floor_source_path_item_ids": ("d0i0", "d1i0", "d2i0"),
        "source_translation_pdf_pts": (-10.,0.),
    }
    kwargs.update(extra)
    return audit(raw, **kwargs)


def test_same_source_ink_both_windings_keeps_exact_partial_and_style_rivals():
    rows = _run(_synthetic())["all_original_candidate_pairs"]
    assert [r["original_source_comparison"] for r in rows] == [
        "exact_original_ink_equal",
        "partial_original_ink_interval_overlap",
        "original_ink_style_conflict",
    ]
    assert rows[0]["source_original_overlap_pdf_pts"] == pytest.approx(70.)
    assert rows[1]["source_original_overlap_pdf_pts"] == pytest.approx(40.)
    assert all(r["cross_page_physical_structural_wall_equivalence_granted"] is False
               for r in rows)


@pytest.mark.parametrize("kwargs", [
    {"source_translation_pdf_pts":(float("nan"),0.)},
    {"source_translation_pdf_pts":(-9.,0.)},
])
def test_bad_source_translation_does_not_elect_wall(kwargs):
    raw = _synthetic()
    if not all(isinstance(v, (int,float)) and v==v for v in kwargs["source_translation_pdf_pts"]):
        with pytest.raises(ValueError):
            _run(raw, **kwargs)
    else:
        rows = _run(raw, **kwargs)["all_original_candidate_pairs"]
        assert all(r["original_source_comparison"] ==
                   "no_original_source_line_overlap" for r in rows)


@pytest.mark.parametrize("bad", [
    {"expected_sha256":"0"*64},
    {"finish_source_path_item_ids":()},
    {"floor_source_path_item_ids":("d0i0","d0i0")},
    {"floor_source_path_item_ids":("foreign",)},
    {"maximum_candidate_pairs":2},
    {"maximum_native_paths":1},
])
def test_missing_or_unbounded_original_native_provenance_fails_closed(bad):
    with pytest.raises(ValueError):
        _run(_synthetic(), **bad)


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="private original unavailable")
def test_original_office_ink_pair_universe_preserves_full_tracks_and_split_parents():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = audit(
        raw, expected_sha256=SHA,
        finish_page_1_based=11, floor_page_1_based=7,
        finish_source_path_item_ids=("d2657i0","d3567i0","d2666i0"),
        floor_source_path_item_ids=(
            "d52239i0","d52248i0","d78352i0","d78358i0","d84230i0"),
        source_translation_pdf_pts=(-78.,0.),
    )
    rows = result["all_original_candidate_pairs"]
    exact = {(r["finish_original_path_item_id"],r["floor_original_path_item_id"])
             for r in rows if r["original_source_comparison"]=="exact_original_ink_equal"}
    partial = {(r["finish_original_path_item_id"],r["floor_original_path_item_id"])
               for r in rows if r["original_source_comparison"] ==
               "partial_original_ink_interval_overlap"}
    assert exact == {
        ("d2657i0","d52239i0"), ("d3567i0","d52239i0"),
        ("d2666i0","d52248i0"),
    }
    assert len(partial) == 6
    assert len(rows) == 15
    assert result["physical_structural_wall_or_finished_face_elected"] is False
    assert result["new_firm_quantities"] == 0
