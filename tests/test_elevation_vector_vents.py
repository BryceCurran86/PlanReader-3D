"""Tests for the generic elevation vector vent symbol learner and extractor.

Validates the 10 requirements:
1. six labelled PV symbols + six identical unlabeled symbols on another elevation => 12 physical occurrences;
2. labels and geometry for the same instance do not double count;
3. `P.V denotes permanent vents` never counts;
4. unrelated rectangles/windows/grilles do not count as vents;
5. one or two labelled examples are insufficient to learn a risky generic symbol if ambiguity remains;
6. competing symbol signatures fail closed;
7. repeated elevation/reference/duplicate sheets do not multiply the count;
8. multiple legitimate facade/elevation regions aggregate correctly;
9. dotted `P.V` and plain `PV` labels behave consistently;
10. the generic solution does not rely on benchmark identifiers or expected totals.
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
    learn_vector_vent_signature,
)
from pb_raster_schedule_extractor import GenericScheduleTableExtractor, ScheduleRow


def _create_synthetic_elevation_sheet(
    tmp_path: Path,
    filename: str,
    elevation_titles: list[str],
    labeled_callouts_per_elevation: list[list[tuple[float, float, str]]],
    symbols_per_elevation: list[list[tuple[float, float, float, float]]],
    other_text: str = "",
    extra_drawings: list[tuple[float, float, float, float]] | None = None,
) -> fitz.Document:
    """Helper to build synthetic PDF sheets with vector drawings and text."""
    pdf_path = tmp_path / filename
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)

    # Insert general text
    if other_text:
        page.insert_text((50, 30), other_text, fontsize=9)

    # Insert elevation viewports
    y_step = 550.0 / max(len(elevation_titles), 1)
    for idx, title in enumerate(elevation_titles):
        top_y = 40.0 + idx * y_step
        page.insert_text((50, top_y), title, fontsize=12)
        page.insert_text((50, top_y + 15), "SCALE 1:100", fontsize=8)

        # Draw symbols for this elevation
        if idx < len(symbols_per_elevation):
            for rect_coords in symbols_per_elevation[idx]:
                x0, y0, x1, y1 = rect_coords
                page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=(0, 0, 0), fill=None, width=1.0)

        # Insert labeled callouts for this elevation
        if idx < len(labeled_callouts_per_elevation):
            for x, y, label_text in labeled_callouts_per_elevation[idx]:
                page.insert_text((x, y), label_text, fontsize=8)

    # Draw any extra drawings (e.g. windows, large frames, divider lines)
    if extra_drawings:
        for x0, y0, x1, y1 in extra_drawings:
            page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=(0, 0, 0), fill=None, width=1.0)

    doc.save(str(pdf_path))
    doc.close()
    return fitz.open(str(pdf_path))


def test_req1_six_labelled_plus_six_unlabeled_yields_twelve(tmp_path: Path):
    """Req 1: six labelled PV symbols + six identical unlabeled symbols on another elevation => 12 physical occurrences."""
    # Elevation 1 (top): 6 vents with PV callouts
    e1_symbols = [(100.0 + i * 80.0, 150.0, 120.0 + i * 80.0, 160.0) for i in range(6)]
    e1_labels = [(105.0 + i * 80.0, 175.0, "PV") for i in range(6)]

    # Elevation 2 (bottom): 6 identical unlabeled vent symbols (no PV text)
    e2_symbols = [(100.0 + i * 80.0, 400.0, 120.0 + i * 80.0, 410.0) for i in range(6)]
    e2_labels: list[tuple[float, float, str]] = []

    doc = _create_synthetic_elevation_sheet(
        tmp_path,
        "elev_12_vents.pdf",
        elevation_titles=["FRONT ELEVATION E-01", "REAR ELEVATION E-03"],
        labeled_callouts_per_elevation=[e1_labels, e2_labels],
        symbols_per_elevation=[e1_symbols, e2_symbols],
    )

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    assert res.quantity == 12.0
    assert res.labeled_callout_count == 6
    assert res.unlabeled_vector_count == 6
    assert res.is_vector_augmented is True


def test_req2_labels_and_geometry_do_not_double_count(tmp_path: Path):
    """Req 2: labels and geometry for the same instance do not double count."""
    # Only 6 vents on Elevation 1, each having both a symbol and a label.
    # Elevation 2 has NO vents. Total must be 6, NOT 12!
    e1_symbols = [(100.0 + i * 80.0, 150.0, 120.0 + i * 80.0, 160.0) for i in range(6)]
    e1_labels = [(105.0 + i * 80.0, 175.0, "PV") for i in range(6)]

    doc = _create_synthetic_elevation_sheet(
        tmp_path,
        "elev_6_vents_labelled.pdf",
        elevation_titles=["FRONT ELEVATION E-01", "REAR ELEVATION E-03"],
        labeled_callouts_per_elevation=[e1_labels, []],
        symbols_per_elevation=[e1_symbols, []],
    )

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    assert res.quantity == 6.0
    assert res.labeled_callout_count == 6
    assert res.unlabeled_vector_count == 0


def test_req3_legend_definition_never_counts(tmp_path: Path):
    """Req 3: P.V denotes permanent vents never counts."""
    # Sheet has 4 genuine PV callouts + the legend note
    labels = [(100.0 + i * 80.0, 150.0, "PV") for i in range(4)]
    symbols = [(95.0 + i * 80.0, 130.0, 115.0 + i * 80.0, 140.0) for i in range(4)]

    doc = _create_synthetic_elevation_sheet(
        tmp_path,
        "legend_note.pdf",
        elevation_titles=["NORTH ELEVATION"],
        labeled_callouts_per_elevation=[labels],
        symbols_per_elevation=[symbols],
        other_text="P.V denotes permanent vents.\nS.V.P denotes soil vent pipe.",
    )

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    assert res.quantity == 4.0
    assert res.labeled_callout_count == 4


def test_req4_unrelated_rectangles_do_not_count_as_vents(tmp_path: Path):
    """Req 4: unrelated rectangles/windows/grilles do not count as vents."""
    # 4 small vent symbols (20x10) with PV labels
    e1_symbols = [(100.0 + i * 80.0, 150.0, 120.0 + i * 80.0, 160.0) for i in range(4)]
    e1_labels = [(105.0 + i * 80.0, 175.0, "PV") for i in range(4)]

    # Large windows (100x120) and door frames on Elevation 2
    e2_large_rects = [
        (100.0, 350.0, 200.0, 470.0),
        (250.0, 350.0, 350.0, 470.0),
        (400.0, 350.0, 500.0, 470.0),
    ]

    doc = _create_synthetic_elevation_sheet(
        tmp_path,
        "unrelated_shapes.pdf",
        elevation_titles=["ELEVATION A", "ELEVATION B"],
        labeled_callouts_per_elevation=[e1_labels, []],
        symbols_per_elevation=[e1_symbols, e2_large_rects],
    )

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    assert res.quantity == 4.0
    assert res.unlabeled_vector_count == 0


def test_req5_insufficient_labelled_examples_fail_closed(tmp_path: Path):
    """Req 5: one or two labelled examples are insufficient to learn a risky generic symbol."""
    # Only 2 labelled PV instances
    labels = [(100.0, 150.0, "PV"), (200.0, 150.0, "PV")]
    symbols = [(95.0, 130.0, 115.0, 140.0), (195.0, 130.0, 215.0, 140.0)]
    # Unlabeled symbols on elevation 2
    unlabeled = [(100.0 + i * 80.0, 400.0, 120.0 + i * 80.0, 410.0) for i in range(6)]

    doc = _create_synthetic_elevation_sheet(
        tmp_path,
        "two_examples.pdf",
        elevation_titles=["ELEVATION 1", "ELEVATION 2"],
        labeled_callouts_per_elevation=[labels, []],
        symbols_per_elevation=[symbols, unlabeled],
    )

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    # Must fail closed: does not extrapolate the 6 unlabeled symbols because only 2 were labelled
    assert res.quantity == 2.0
    assert res.unlabeled_vector_count == 0
    assert res.is_vector_augmented is False


def test_req6_competing_symbol_signatures_fail_closed():
    """Req 6: competing symbol signatures fail closed."""
    # 2 callouts near a 15x8 rect, 2 callouts near a 35x25 rect
    c1 = CandidateVectorSymbol((100, 100, 115, 108), 15, 8, 15/8, 1, False, True, 1.0)
    c2 = CandidateVectorSymbol((200, 100, 215, 108), 15, 8, 15/8, 1, False, True, 1.0)
    c3 = CandidateVectorSymbol((300, 100, 335, 125), 35, 25, 35/25, 1, False, True, 1.0)
    c4 = CandidateVectorSymbol((400, 100, 435, 125), 35, 25, 35/25, 1, False, True, 1.0)

    callouts = [
        (100, 110, 115, 120, "PV"),
        (200, 110, 215, 120, "PV"),
        (300, 130, 315, 140, "PV"),
        (400, 130, 415, 140, "PV"),
    ]

    sig = learn_vector_vent_signature([c1, c2, c3, c4], callouts)
    # Neither cluster reaches min 3 instances, and competing clusters exist -> fail closed
    assert sig is None


def test_req7_repeated_duplicate_sheets_do_not_multiply(tmp_path: Path):
    """Req 7: repeated elevation/reference/duplicate sheets do not multiply the count."""
    extractor = GenericScheduleTableExtractor()

    # Create sheet 1
    symbols = [(100.0 + i * 80.0, 150.0, 120.0 + i * 80.0, 160.0) for i in range(5)]
    labels = [(105.0 + i * 80.0, 175.0, "PV") for i in range(5)]

    doc1 = _create_synthetic_elevation_sheet(
        tmp_path, "sheet_a.pdf",
        elevation_titles=["WEST ELEVATION"],
        labeled_callouts_per_elevation=[labels],
        symbols_per_elevation=[symbols],
    )
    # Create identical duplicate sheet 2
    doc2 = _create_synthetic_elevation_sheet(
        tmp_path, "sheet_a_copy.pdf",
        elevation_titles=["WEST ELEVATION"],
        labeled_callouts_per_elevation=[labels],
        symbols_per_elevation=[symbols],
    )

    rows1 = extractor._extract_callouts_from_page(doc1[0], page_num=1)
    rows2 = extractor._extract_callouts_from_page(doc2[0], page_num=2)

    # Set same sheet_number or let identical bbox match
    for r in rows1:
        r.sheet_number = "A-01"
    for r in rows2:
        r.sheet_number = "A-01"

    deduped = extractor.deduplicate_schedule_rows(list(rows1) + list(rows2))
    vent_rows = [r for r in deduped if r.tag == "brick_vents"]
    assert len(vent_rows) == 1
    assert vent_rows[0].quantity == 5.0


def test_req8_multiple_legitimate_facade_sheets_aggregate(tmp_path: Path):
    """Req 8: multiple legitimate facade/elevation regions aggregate correctly."""
    extractor = GenericScheduleTableExtractor()

    # Sheet 1: East Elevation with 4 vents
    s1_symbols = [(100.0 + i * 80.0, 150.0, 120.0 + i * 80.0, 160.0) for i in range(4)]
    s1_labels = [(105.0 + i * 80.0, 175.0, "PV") for i in range(4)]
    doc1 = _create_synthetic_elevation_sheet(
        tmp_path, "sheet_east.pdf",
        elevation_titles=["EAST ELEVATION"],
        labeled_callouts_per_elevation=[s1_labels],
        symbols_per_elevation=[s1_symbols],
    )

    # Sheet 2: West Elevation with 6 vents (different bbox and count)
    s2_symbols = [(120.0 + i * 60.0, 250.0, 140.0 + i * 60.0, 260.0) for i in range(6)]
    s2_labels = [(125.0 + i * 60.0, 275.0, "PV") for i in range(6)]
    doc2 = _create_synthetic_elevation_sheet(
        tmp_path, "sheet_west.pdf",
        elevation_titles=["WEST ELEVATION"],
        labeled_callouts_per_elevation=[s2_labels],
        symbols_per_elevation=[s2_symbols],
    )

    rows1 = extractor._extract_callouts_from_page(doc1[0], page_num=1)
    rows2 = extractor._extract_callouts_from_page(doc2[0], page_num=2)
    for r in rows1:
        r.sheet_number = "E-01"
    for r in rows2:
        r.sheet_number = "E-02"

    deduped = extractor.deduplicate_schedule_rows(list(rows1) + list(rows2))
    vent_rows = [r for r in deduped if r.tag == "brick_vents"]
    assert len(vent_rows) == 1
    # 4 + 6 = 10
    assert vent_rows[0].quantity == 10.0


def test_req9_dotted_pv_and_plain_pv_behave_consistently(tmp_path: Path):
    """Req 9: dotted P.V and plain PV labels behave consistently."""
    # Sheet with dotted "P.V"
    dotted_labels = [(105.0 + i * 80.0, 175.0, "P.V") for i in range(5)]
    symbols = [(100.0 + i * 80.0, 150.0, 120.0 + i * 80.0, 160.0) for i in range(5)]

    doc = _create_synthetic_elevation_sheet(
        tmp_path, "dotted_pv.pdf",
        elevation_titles=["SOUTH ELEVATION"],
        labeled_callouts_per_elevation=[dotted_labels],
        symbols_per_elevation=[symbols],
    )

    res = extract_elevation_vector_vents(doc[0], page_num=1)
    assert res is not None
    assert res.quantity == 5.0
    assert res.labeled_callout_count == 5


def test_req10_generic_solution_no_benchmark_identifiers():
    """Req 10: verify code does not contain hardcoded benchmark names or numbers."""
    from pathlib import Path
    source = Path("pb_elevation_vector_vent_extractor.py").read_text(encoding="utf-8")
    assert "murera" not in source.lower()
    assert "tenders_ke" not in source.lower()
    assert "219" not in source
    assert "1785347143869" not in source
