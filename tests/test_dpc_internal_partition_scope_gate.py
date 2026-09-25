"""Regression tests for the DPC "all walls" scope gate.

pb_planreader_pdf_extractor only adds an evidenced internal partition's
length to damp_proof_course when the drawing's own DPC note explicitly
extends scope beyond the external perimeter (e.g. "... provided under all
walls on ground floor"). Proves both directions of that gate directly,
using a synthetic drawing with a real internal partition wall-like fill in
its vector geometry -- so these tests exercise the actual gate condition
(present vs absent "all walls" phrasing), not just the geometry detector.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

# A 10m x 8m envelope at 20 pt/m, with a 0.2m-thick internal partition
# spanning the full depth at the horizontal midpoint -- deliberately
# simple synthetic geometry, not derived from or matched to any benchmark
# drawing.
_SCALE_PT_PER_M = 20.0
_X0, _Y0 = 100.0, 100.0
_WIDTH_PT, _DEPTH_PT = 200.0, 160.0  # 10m x 8m at 20pt/m
_THICKNESS_PT = 4.0  # 0.2m


def _build_pdf(tmp_path: Path, name: str, dpc_note: str) -> Path:
    path = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)

    x1 = _X0 + _WIDTH_PT
    y1 = _Y0 + _DEPTH_PT
    mid_x = _X0 + _WIDTH_PT / 2.0

    # Four perimeter walls, drawn as thin solid black fills.
    page.draw_rect(fitz.Rect(_X0, _Y0, _X0 + _THICKNESS_PT, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - _THICKNESS_PT, _Y0, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, _Y0, x1, _Y0 + _THICKNESS_PT), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, y1 - _THICKNESS_PT, x1, y1), color=None, fill=(0, 0, 0))
    # One internal partition, spanning the full depth at the midpoint.
    page.draw_rect(
        fitz.Rect(mid_x - _THICKNESS_PT / 2.0, _Y0, mid_x + _THICKNESS_PT / 2.0, y1),
        color=None,
        fill=(0, 0, 0),
    )

    page.insert_text(
        (_X0, _Y0 - 20),
        "10,000 x 8,000",
        fontsize=10,
    )
    page.insert_text((_X0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((_X0, y1 + 40), dpc_note, fontsize=9)

    doc.save(path)
    doc.close()
    return path


def _preds(pdf: Path) -> dict:
    return {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(pdf)}


def test_all_walls_phrase_absent_does_not_add_internal_partition_to_dpc(tmp_path: Path) -> None:
    pdf = _build_pdf(
        tmp_path,
        "dpc_no_all_walls_scope.pdf",
        "DPC to be laid to external walls only, minimum 150mm above ground level.",
    )
    preds = _preds(pdf)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]
    # Naive external perimeter only: 2*(10+8) = 36m. If the internal
    # partition (8m) were wrongly added, this would read ~44m instead.
    assert dpc.quantity == 36.0
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_all_walls_phrase_present_adds_internal_partition_to_dpc(tmp_path: Path) -> None:
    pdf = _build_pdf(
        tmp_path,
        "dpc_all_walls_scope.pdf",
        "DPC denotes damp proof course to be of approved bituminous felt "
        "provided under all walls on ground floor.",
    )
    preds = _preds(pdf)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]
    # External perimeter (36m) + the evidenced internal partition (8m).
    assert dpc.quantity == 44.0
    assert (dpc.metadata or {}).get("internal_partition_length_m") == 8.0


def test_all_walls_phrase_variants_are_recognized(tmp_path: Path) -> None:
    for phrase in (
        "DPC to be laid to all walls on ground floor.",
        "DPC damp proof course beneath all walls.",
    ):
        pdf = _build_pdf(tmp_path, f"dpc_variant_{hash(phrase) & 0xffff}.pdf", phrase)
        preds = _preds(pdf)
        assert preds["damp_proof_course"].quantity == 44.0, phrase


def test_same_page_unrelated_all_walls_phrase_does_not_add_partition(tmp_path: Path) -> None:
    """Regression: a DPC note exists, and a separate, unrelated note on the
    same page happens to say "to all walls" (e.g. about plaster) -- the
    gate must require both signals in the SAME clause, not merely the same
    page, and must stay false here."""
    path = tmp_path / "dpc_unrelated_all_walls_phrase.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)

    x1 = _X0 + _WIDTH_PT
    y1 = _Y0 + _DEPTH_PT
    mid_x = _X0 + _WIDTH_PT / 2.0
    page.draw_rect(fitz.Rect(_X0, _Y0, _X0 + _THICKNESS_PT, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - _THICKNESS_PT, _Y0, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, _Y0, x1, _Y0 + _THICKNESS_PT), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, y1 - _THICKNESS_PT, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(
        fitz.Rect(mid_x - _THICKNESS_PT / 2.0, _Y0, mid_x + _THICKNESS_PT / 2.0, y1),
        color=None, fill=(0, 0, 0),
    )
    page.insert_text((_X0, _Y0 - 20), "10,000 x 8,000", fontsize=10)
    page.insert_text((_X0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    # DPC note with NO scope statement of its own.
    page.insert_text((_X0, y1 + 40), "DPC to be laid to external walls only.", fontsize=9)
    # A genuinely unrelated note, elsewhere on the same page, that happens
    # to contain the "all walls" phrase for a different trade entirely.
    page.insert_text((_X0, y1 + 60), "Plaster finish to be applied to all walls internally.", fontsize=9)
    doc.save(path)
    doc.close()

    preds = _preds(path)
    dpc = preds["damp_proof_course"]
    assert dpc.quantity == 36.0
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_newline_only_separated_unrelated_phrase_does_not_add_partition(tmp_path: Path) -> None:
    """Regression: two notes separated ONLY by a newline -- no terminal
    punctuation at all between them, so a period-only split cannot see any
    boundary here -- must still be recognized as two independent notes,
    not merged into one because they happen to share a text block."""
    path = tmp_path / "dpc_newline_only_unrelated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)

    x1 = _X0 + _WIDTH_PT
    y1 = _Y0 + _DEPTH_PT
    mid_x = _X0 + _WIDTH_PT / 2.0
    page.draw_rect(fitz.Rect(_X0, _Y0, _X0 + _THICKNESS_PT, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - _THICKNESS_PT, _Y0, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, _Y0, x1, _Y0 + _THICKNESS_PT), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(_X0, y1 - _THICKNESS_PT, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(
        fitz.Rect(mid_x - _THICKNESS_PT / 2.0, _Y0, mid_x + _THICKNESS_PT / 2.0, y1),
        color=None, fill=(0, 0, 0),
    )
    page.insert_text((_X0, _Y0 - 20), "10,000 x 8,000", fontsize=10)
    page.insert_text((_X0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    # One text block, two lines, NO period/semicolon anywhere -- only a
    # newline separates them, and the second line starts a genuinely new
    # sentence (capital "P"), not a wrapped continuation of the first.
    page.insert_text(
        (_X0, y1 + 40),
        "DPC to be laid to external walls only\nPlaster finish to all walls internally",
        fontsize=9,
    )
    doc.save(path)
    doc.close()

    preds = _preds(path)
    dpc = preds["damp_proof_course"]
    assert dpc.quantity == 36.0
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_semicolon_separated_unrelated_phrase_does_not_add_partition(tmp_path: Path) -> None:
    """Regression: DPC and an unrelated "all walls" phrase separated only
    by a semicolon on the same line must not be conflated."""
    pdf = _build_pdf(
        tmp_path,
        "dpc_semicolon_unrelated.pdf",
        "DPC to external walls only; plaster finish to all walls internally",
    )
    preds = _preds(pdf)
    dpc = preds["damp_proof_course"]
    assert dpc.quantity == 36.0
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_wrapped_dpc_note_across_a_hard_line_break_is_still_recognized() -> None:
    """Regression: a genuine DPC note commonly wraps across PDF text lines
    with no terminal punctuation at the wrap point (this is exactly how
    the real Lamu drawing's own note is extracted). Must still be
    recognized as one note, not severed into two meaningless fragments
    that individually lack one of the two required signals."""
    wrapped_note = (
        "3.    DPC denotes damp proof course to be of approved\n"
        "       bitumious felt provided under all walls on ground floor.\n"
        "4.    All walls less than 200mm thick to be reinforced."
    )
    assert GenericPlanReaderExtractor._has_dpc_all_walls_scope(wrapped_note)


def test_cross_page_all_walls_note_does_not_leak_to_different_page(tmp_path: Path) -> None:
    """Regression: page A states DPC scope extends to all walls, but page A
    itself carries no usable building/partition geometry. Page B has the
    real geometry and its own DPC mention, but that page's OWN note says
    nothing about "all walls". The page-A note must not leak into page B's
    DPC computation -- the scope check is page-local, not document-global.
    """
    path = tmp_path / "dpc_cross_page_leakage.pdf"
    doc = fitz.open()

    # Page A: DPC + "all walls" scope note, but no parseable envelope
    # dimensions and no wall-like fills -- contributes no geometry at all.
    page_a = doc.new_page(width=842, height=595)
    page_a.insert_text((100, 100), "GENERAL NOTES", fontsize=10)
    page_a.insert_text(
        (100, 130),
        "DPC denotes damp proof course provided under all walls on ground floor.",
        fontsize=9,
    )

    # Page B: the real building geometry, with its own DPC note that does
    # NOT extend scope to all walls.
    page_b = doc.new_page(width=842, height=595)
    x1 = _X0 + _WIDTH_PT
    y1 = _Y0 + _DEPTH_PT
    mid_x = _X0 + _WIDTH_PT / 2.0
    page_b.draw_rect(fitz.Rect(_X0, _Y0, _X0 + _THICKNESS_PT, y1), color=None, fill=(0, 0, 0))
    page_b.draw_rect(fitz.Rect(x1 - _THICKNESS_PT, _Y0, x1, y1), color=None, fill=(0, 0, 0))
    page_b.draw_rect(fitz.Rect(_X0, _Y0, x1, _Y0 + _THICKNESS_PT), color=None, fill=(0, 0, 0))
    page_b.draw_rect(fitz.Rect(_X0, y1 - _THICKNESS_PT, x1, y1), color=None, fill=(0, 0, 0))
    page_b.draw_rect(
        fitz.Rect(mid_x - _THICKNESS_PT / 2.0, _Y0, mid_x + _THICKNESS_PT / 2.0, y1),
        color=None, fill=(0, 0, 0),
    )
    page_b.insert_text((_X0, _Y0 - 20), "10,000 x 8,000", fontsize=10)
    page_b.insert_text((_X0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page_b.insert_text((_X0, y1 + 40), "DPC to be laid to external walls only.", fontsize=9)

    doc.save(path)
    doc.close()

    preds = _preds(path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]
    # Must be page B's own external perimeter only (36m) -- page A's "all
    # walls" note must not have leaked in to add the 8m partition.
    assert dpc.quantity == 36.0
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_compound_verandah_all_walls_dpc_includes_longitudinal_and_transverse_internal_walls(
    tmp_path: Path,
) -> None:
    """When a building envelope encompasses both primary space and an evidenced
    verandah, 'all walls' DPC scope accounts for both the internal longitudinal
    separating wall (length_m) and the transverse dividing wall (width_m)
    derived strictly from physically evidenced wall runs in vector geometry."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale   # 320 pt (16m)
    depth_pt = 8.2 * scale    # 164 pt (8.2m)
    thickness_pt = 4.0        # 0.2m
    main_room_depth_pt = 6.1 * scale  # 122 pt (6.1m)

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    y_classroom_bottom = y0 + main_room_depth_pt
    mid_x = x0 + width_pt / 2.0

    # Solid wall fills: rear wall, side walls up to classroom depth, internal transverse partition
    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y_classroom_bottom), color=None, fill=(0, 0, 0))
    # Longitudinal separating wall between classroom and verandah (physically drawn with openings):
    page.draw_rect(fitz.Rect(x0, y_classroom_bottom - thickness_pt, mid_x - 10.0, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(mid_x + 10.0, y_classroom_bottom - thickness_pt, x1, y_classroom_bottom), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "16,000 x 8,200", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((x0, y1 + 40), "VERANDAH", fontsize=9)
    page.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "compound_verandah_dpc.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # 48.4m envelope + 24.2m compound internal walls (16.0m + 8.2m) = 72.6m
    assert dpc.quantity == 72.6
    meta = dpc.metadata or {}
    assert meta.get("internal_partition_length_m") == 24.2
    assert meta.get("dpc_scope") == "external_perimeter_plus_compound_internal_walls"
    assert meta.get("transverse_runs_count") == 1
    assert meta.get("longitudinal_runs_count") == 1


def test_verandah_text_present_but_longitudinal_wall_absent_fails_closed(
    tmp_path: Path,
) -> None:
    """Negative test: 'VERANDAH' text and 'all walls' DPC note exist, but NO
    longitudinal separating wall is drawn in geometry. The extractor must fail
    closed -- it must NOT invent length_m or fire compound logic, but count only
    the physically evidenced transverse partition."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale   # 320 pt (16m)
    depth_pt = 8.2 * scale    # 164 pt (8.2m)
    thickness_pt = 4.0        # 0.2m
    main_room_depth_pt = 6.1 * scale  # 122 pt (6.1m)

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    y_classroom_bottom = y0 + main_room_depth_pt
    mid_x = x0 + width_pt / 2.0

    # Solid wall fills: rear wall, side walls up to classroom depth, internal transverse partition
    # NOTE: NO longitudinal wall is drawn along y_classroom_bottom!
    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y_classroom_bottom), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "16,000 x 8,200", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((x0, y1 + 40), "VERANDAH", fontsize=9)
    page.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "verandah_text_no_longitudinal_wall.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # Fails closed: only evidenced transverse partition (6.1m) added: 48.4m + 6.1m = 54.5m
    assert dpc.quantity == 54.5
    meta = dpc.metadata or {}
    assert meta.get("internal_partition_length_m") == 6.1
    assert meta.get("dpc_scope") == "external_perimeter_plus_evidenced_internal_partitions"
    assert meta.get("longitudinal_runs_count") == 0
    assert meta.get("transverse_runs_count") == 1


def test_verandah_text_present_but_no_internal_walls_at_all_fails_closed(
    tmp_path: Path,
) -> None:
    """Negative test: 'VERANDAH' text and 'all walls' DPC note exist, but NO
    internal walls whatsoever are drawn in geometry. The extractor must fail
    closed to external perimeter only."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale   # 320 pt (16m)
    depth_pt = 8.2 * scale    # 164 pt (8.2m)
    thickness_pt = 4.0        # 0.2m

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt

    # Only perimeter walls drawn -- zero internal walls
    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y1 - thickness_pt, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y1), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "16,000 x 8,200", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((x0, y1 + 40), "VERANDAH", fontsize=9)
    page.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "verandah_no_internal_walls_at_all.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # Fails closed to envelope perimeter only: 2*(16+8.2) = 48.4m
    assert dpc.quantity == 48.4
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_ordinary_building_without_verandah_does_not_fire_compound_logic(
    tmp_path: Path,
) -> None:
    """When no verandah is evidenced on the page, even a shorter partition
    falls back to simple partition length (does not invent longitudinal walls)."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale   # 320 pt (16m)
    depth_pt = 8.2 * scale    # 164 pt (8.2m)
    thickness_pt = 4.0        # 0.2m
    main_room_depth_pt = 6.1 * scale  # 122 pt (6.1m)

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    y_part_bottom = y0 + main_room_depth_pt
    mid_x = x0 + width_pt / 2.0

    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y_part_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y_part_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y_part_bottom), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "16,000 x 8,200", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    # NO verandah mention anywhere on page
    page.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "ordinary_no_verandah_dpc.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # Simple partition only: 48.4m envelope + 6.1m partition = 54.5m
    assert dpc.quantity == 54.5
    meta = dpc.metadata or {}
    assert meta.get("internal_partition_length_m") == 6.1
    assert meta.get("dpc_scope") == "external_perimeter_plus_evidenced_internal_partitions"


def test_ordinary_building_full_depth_partition_does_not_fire_compound_logic(
    tmp_path: Path,
) -> None:
    """When a partition spans the full building depth (deficit < 1.0m),
    compound logic does not fire even if 'verandah' text appears on the page."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale  # 320 pt (16m)
    depth_pt = 8.0 * scale   # 160 pt (8m)
    thickness_pt = 4.0       # 0.2m

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    mid_x = x0 + width_pt / 2.0

    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y1 - thickness_pt, x1, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y1), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y1), color=None, fill=(0, 0, 0))
    # Full depth partition (8m)
    page.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y1), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "16,000 x 8,000", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((x0, y1 + 40), "VERANDAH", fontsize=9)
    page.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "full_depth_verandah_dpc.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # Full depth partition: 2*(16+8) = 48.0m envelope + 8.0m partition = 56.0m
    assert dpc.quantity == 56.0
    meta = dpc.metadata or {}
    assert meta.get("internal_partition_length_m") == 8.0
    assert meta.get("dpc_scope") == "external_perimeter_plus_evidenced_internal_partitions"


def test_ambiguous_geometry_excessive_deficit_does_not_fire_compound_logic(
    tmp_path: Path,
) -> None:
    """When partition deficit exceeds plausible verandah depth (> 3.5m),
    compound logic abstains and falls back to simple partition length."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 20.0 * scale   # 400 pt (20m)
    depth_pt = 10.0 * scale   # 200 pt (10m)
    thickness_pt = 4.0        # 0.2m
    short_part_depth_pt = 4.0 * scale  # 80 pt (4m) -> deficit = 10m - 4m = 6m > 3.5m

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    y_part_bottom = y0 + short_part_depth_pt
    mid_x = x0 + width_pt / 2.0

    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y_part_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y_part_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y_part_bottom), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "20,000 x 10,000", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((x0, y1 + 40), "VERANDAH", fontsize=9)
    page.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "excessive_deficit_dpc.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # 2*(20+10) = 60.0m envelope + 4.0m partition = 64.0m
    assert dpc.quantity == 64.0
    meta = dpc.metadata or {}
    assert meta.get("internal_partition_length_m") == 4.0
    assert meta.get("dpc_scope") == "external_perimeter_plus_evidenced_internal_partitions"


def test_compound_geometry_with_all_walls_absent_stays_envelope_only(
    tmp_path: Path,
) -> None:
    """When compound verandah geometry is present, but the drawing's DPC note
    lacks 'all walls' scope, DPC stays scoped to external perimeter only."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale   # 320 pt (16m)
    depth_pt = 8.2 * scale    # 164 pt (8.2m)
    thickness_pt = 4.0        # 0.2m
    main_room_depth_pt = 6.1 * scale  # 122 pt (6.1m)

    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    y_classroom_bottom = y0 + main_room_depth_pt
    mid_x = x0 + width_pt / 2.0

    page.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y_classroom_bottom), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y_classroom_bottom), color=None, fill=(0, 0, 0))

    page.insert_text((x0, y0 - 20), "16,000 x 8,200", fontsize=10)
    page.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((x0, y1 + 40), "VERANDAH", fontsize=9)
    # DPC note with NO "all walls" phrasing
    page.insert_text((x0, y1 + 60), "DPC to be laid to external walls only.", fontsize=9)

    pdf_path = tmp_path / "compound_no_all_walls_dpc.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # External perimeter only: 2*(16+8.2) = 48.4m
    assert dpc.quantity == 48.4
    assert "internal_partition_length_m" not in (dpc.metadata or {})


def test_cross_page_verandah_mention_does_not_trigger_compound_logic_on_ordinary_page(
    tmp_path: Path,
) -> None:
    """Verandah mentioned on an unrelated page must not leak to an ordinary page
    and trigger compound verandah logic."""
    scale = 20.0
    x0, y0 = 100.0, 100.0
    width_pt = 16.0 * scale   # 320 pt (16m)
    depth_pt = 8.2 * scale    # 164 pt (8.2m)
    thickness_pt = 4.0        # 0.2m
    main_room_depth_pt = 6.1 * scale  # 122 pt (6.1m)

    doc = fitz.open()

    # Page 1: Administrative sheet mentioning VERANDAH, but no geometry
    page1 = doc.new_page(width=842, height=595)
    page1.insert_text((100, 100), "PROJECT SPECIFICATION: VERANDAH DETAILS", fontsize=10)

    # Page 2: Ordinary floor plan with partition, NO verandah text on this page
    page2 = doc.new_page(width=842, height=595)
    x1 = x0 + width_pt
    y1 = y0 + depth_pt
    y_part_bottom = y0 + main_room_depth_pt
    mid_x = x0 + width_pt / 2.0

    page2.draw_rect(fitz.Rect(x0, y0, x1, y0 + thickness_pt), color=None, fill=(0, 0, 0))
    page2.draw_rect(fitz.Rect(x0, y0, x0 + thickness_pt, y_part_bottom), color=None, fill=(0, 0, 0))
    page2.draw_rect(fitz.Rect(x1 - thickness_pt, y0, x1, y_part_bottom), color=None, fill=(0, 0, 0))
    page2.draw_rect(fitz.Rect(mid_x - thickness_pt / 2.0, y0, mid_x + thickness_pt / 2.0, y_part_bottom), color=None, fill=(0, 0, 0))

    page2.insert_text((x0, y0 - 20), "16,000 x 8,200", fontsize=10)
    page2.insert_text((x0, y1 + 20), "GROUND FLOOR PLAN", fontsize=10)
    page2.insert_text(
        (x0, y1 + 60),
        "DPC denotes damp proof course to be of approved bituminous felt provided under all walls on ground floor.",
        fontsize=9,
    )

    pdf_path = tmp_path / "cross_page_verandah_leakage.pdf"
    doc.save(pdf_path)
    doc.close()

    preds = _preds(pdf_path)
    assert "damp_proof_course" in preds
    dpc = preds["damp_proof_course"]

    # Must NOT fire compound logic because Page 2 has no verandah mention:
    # 48.4m envelope + 6.1m partition = 54.5m
    assert dpc.quantity == 54.5
    meta = dpc.metadata or {}
    assert meta.get("internal_partition_length_m") == 6.1
    assert meta.get("dpc_scope") == "external_perimeter_plus_evidenced_internal_partitions"


