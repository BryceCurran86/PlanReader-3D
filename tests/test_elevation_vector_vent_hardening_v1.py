"""Regressions for three gaps found reviewing PR #535 (Phase F.8/F.24 vents):

1. The legacy page-loop extractor this module replaced matched both the
   "PV"/"P.V" abbreviation AND the spelled-out "Permanent Vent"/"Brick Vent"
   phrases (``\\bPV\\b|\\bPermanent Vent\\b|\\bBrick Vent\\b``). The
   replacement only matched the abbreviation, silently dropping any drawing
   set that spells vents out in full.
2. The spelled-out phrase form must still respect the "<abbrev/phrase>
   denotes <meaning>" legend exclusion, exactly like the abbreviation form
   does.
3. ``detect_unlabeled_vent_symbols`` had a fallback that treated any
   signature-matching symbol "not in the page margin" as a valid unlabeled
   vent whenever viewport segmentation returned nothing (empty list or a
   caught exception) -- i.e. it stopped requiring genuine elevation-viewport
   containment exactly when segmentation was least reliable. A matching
   symbol placed outside any real elevation viewport must never be counted.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_elevation_vector_vent_extractor import (
    CandidateVectorSymbol,
    VectorVentSymbolSignature,
    detect_unlabeled_vent_symbols,
    extract_elevation_vector_vents,
    extract_verified_pv_callouts,
)


def _save(doc: fitz.Document, path: Path) -> fitz.Document:
    doc.save(str(path))
    doc.close()
    return fitz.open(str(path))


def test_spelled_out_permanent_vent_phrase_is_detected_without_any_pv_abbreviation(
    tmp_path: Path,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((50, 40), "SOUTH ELEVATION", fontsize=12)
    page.insert_text((50, 55), "SCALE 1:100", fontsize=8)
    for i in range(3):
        x = 100.0 + i * 80.0
        page.draw_rect(fitz.Rect(x, 150.0, x + 20.0, 160.0), color=(0, 0, 0), fill=None, width=1.0)
        page.insert_text((x + 2, 178.0), "Permanent Vent", fontsize=8)
    doc = _save(doc, tmp_path / "phrase_only.pdf")

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    assert res.labeled_callout_count == 3
    assert res.quantity >= 3.0


def test_brick_vent_phrase_is_also_detected(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((50, 40), "NORTH ELEVATION", fontsize=12)
    for i in range(2):
        x = 100.0 + i * 80.0
        page.insert_text((x, 178.0), "Brick Vent", fontsize=8)
    doc = _save(doc, tmp_path / "brick_vent.pdf")

    callouts = extract_verified_pv_callouts(doc[0])
    assert len(callouts) == 2
    assert all(text.lower() == "brick vent" for *_bbox, text in callouts)


def test_spelled_out_phrase_legend_definition_is_excluded(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((50, 40), "SOUTH ELEVATION", fontsize=12)
    # A legend line using the full phrase, not the abbreviation.
    page.insert_text((50, 500), "Permanent Vent denotes a wall ventilation opening", fontsize=8)
    doc = _save(doc, tmp_path / "phrase_legend.pdf")

    callouts = extract_verified_pv_callouts(doc[0])
    assert callouts == []


def test_pv_and_phrase_forms_are_not_double_counted_on_the_same_page(tmp_path: Path) -> None:
    """A document that happens to use both spellings for distinct instances
    still counts each callout exactly once, never overlapping matches."""
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_text((50, 40), "WEST ELEVATION", fontsize=12)
    page.insert_text((100, 150), "PV", fontsize=8)
    page.insert_text((250, 150), "Permanent Vent", fontsize=8)
    doc = _save(doc, tmp_path / "mixed_forms.pdf")

    callouts = extract_verified_pv_callouts(doc[0])
    assert len(callouts) == 2


def test_unlabeled_match_outside_any_elevation_viewport_is_never_counted() -> None:
    """No page-wide fallback: when elevation_viewports is empty (segmentation
    found nothing, or failed and was caught upstream), a signature-matching
    symbol must not be treated as a valid unlabeled vent merely because it
    sits away from the page margin."""
    signature = VectorVentSymbolSignature(
        width_pt=20.0, height_pt=10.0, aspect_ratio=2.0,
        path_item_count=1, has_fill=False, has_stroke=True, stroke_width=1.0,
    )
    # A same-sized rectangle far from any labeled callout, with no
    # segmented elevation viewport provided at all.
    stray = CandidateVectorSymbol(
        bbox=(400.0, 400.0, 420.0, 410.0), width_pt=20.0, height_pt=10.0,
        aspect_ratio=2.0, path_item_count=1, has_fill=False, has_stroke=True,
        stroke_width=1.0,
    )
    matched = detect_unlabeled_vent_symbols(
        candidates=[stray],
        signature=signature,
        labeled_callouts=[(100.0, 150.0, 110.0, 160.0, "PV")],
        elevation_viewports=[],
        page_rect=fitz.Rect(0, 0, 800, 600),
    )
    assert matched == []
