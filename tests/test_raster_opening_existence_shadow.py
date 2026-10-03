"""Raster physical-opening existence (pb_raster_opening_existence_shadow): shadow only.

Synthetic fixtures only: no source PDF, project name, benchmark identity or expected
quantity is read here. Every drawing is built in points (paper units) and rasterised at
a chosen dpi, so the same drawing can be re-rendered at another resolution, translated,
rotated, mirrored, tiled or padded and must keep proving the same openings.

Real-source evidence (Lot16 raster floor plan, scanned pages of other projects) lives in
scripts/raster_opening_existence_shadow_diff.py and docs/raster_opening_existence_shadow_report.md.
"""
from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2
import fitz
import numpy as np
import pytest

import pb_raster_opening_existence_shadow as rs
from pb_migration_contracts import EvidenceResolutionStatus

ROOT = Path(__file__).resolve().parent.parent
CORROBORATED = EvidenceResolutionStatus.CORROBORATED
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CONFLICT = EvidenceResolutionStatus.CONFLICT

DPI = 288  # four pixels per point: every point coordinate below lands on a pixel edge
WALL = 3.4  # wall poche thickness in points
SHA = "ab" * 32


# ---------------------------------------------------------------------------
# Synthetic raster plan builders (paper units)
# ---------------------------------------------------------------------------


def _px(value_pt: float, dpi: int = DPI) -> int:
    return int(round(value_pt * dpi / 72.0))


class Sheet:
    """A white raster canvas drawn in points."""

    def __init__(self, width_pt: float = 300, height_pt: float = 120, dpi: int = DPI) -> None:
        self.dpi = dpi
        self.gray = np.full((_px(height_pt, dpi), _px(width_pt, dpi)), 255, np.uint8)

    def rect(self, x0: float, y0: float, x1: float, y1: float, value: int = 0) -> None:
        self.gray[_px(y0, self.dpi) : _px(y1, self.dpi), _px(x0, self.dpi) : _px(x1, self.dpi)] = value

    def hline(self, x0: float, x1: float, y: float, weight: float = 0.5, value: int = 0) -> None:
        thick = max(1, _px(weight, self.dpi))
        row = _px(y, self.dpi) - thick // 2
        self.gray[row : row + thick, _px(x0, self.dpi) : _px(x1, self.dpi)] = value

    def vline(self, y0: float, y1: float, x: float, weight: float = 0.5, value: int = 0) -> None:
        thick = max(1, _px(weight, self.dpi))
        col = _px(x, self.dpi) - thick // 2
        self.gray[_px(y0, self.dpi) : _px(y1, self.dpi), col : col + thick] = value

    def arc(self, cx: float, cy: float, radius: float, start: int, end: int, weight: float = 0.5) -> None:
        thick = max(1, _px(weight, self.dpi))
        centre = (_px(cx, self.dpi), _px(cy, self.dpi))
        axes = (_px(radius, self.dpi), _px(radius, self.dpi))
        cv2.ellipse(self.gray, centre, axes, 0, start, end, 0, thick, cv2.LINE_8)


def window_wall(
    sheet: Sheet,
    g0: float = 120,
    g1: float = 180,
    *,
    yc: float = 60,
    x0: float = 20,
    x1: float = 280,
    thickness: float = WALL,
    inset: float = 0.5,
    weight: float = 0.5,
) -> tuple[float, float]:
    """Poche wall with a gap [g0, g1] crossed by two frame lines inside the wall faces."""
    top, bot = yc - thickness / 2, yc + thickness / 2
    sheet.rect(x0, top, g0, bot)
    sheet.rect(g1, top, x1, bot)
    sheet.hline(g0, g1, top + inset + weight / 2, weight)
    sheet.hline(g0, g1, bot - inset - weight / 2, weight)
    return top, bot


def door_wall(
    sheet: Sheet,
    g0: float = 120,
    g1: float = 144,
    *,
    yc: float = 60,
    hinge: str = "low",
    swing: str = "up",
    weight: float = 0.5,
) -> tuple[float, float]:
    """Poche wall with a bare gap [g0, g1], a leaf line and a quarter-circle swing arc."""
    top, bot = yc - WALL / 2, yc + WALL / 2
    sheet.rect(20, top, g0, bot)
    sheet.rect(g1, top, 280, bot)
    radius = g1 - g0
    if swing == "up":
        if hinge == "low":
            sheet.vline(top - radius, top, g0 + weight / 2, weight)
            sheet.arc(g0, top, radius, 270, 360, weight)
        else:
            sheet.vline(top - radius, top, g1 - weight / 2, weight)
            sheet.arc(g1, top, radius, 180, 270, weight)
    elif hinge == "low":
        sheet.vline(bot, bot + radius, g0 + weight / 2, weight)
        sheet.arc(g0, bot, radius, 0, 90, weight)
    else:
        sheet.vline(bot, bot + radius, g1 - weight / 2, weight)
        sheet.arc(g1, bot, radius, 90, 180, weight)
    return top, bot


def bare_gap(sheet: Sheet, g0: float = 120, g1: float = 180, *, yc: float = 60) -> tuple[float, float]:
    top, bot = yc - WALL / 2, yc + WALL / 2
    sheet.rect(20, top, g0, bot)
    sheet.rect(g1, top, 280, bot)
    return top, bot


def lineage_for(gray: np.ndarray, dpi: int = DPI, *, layer_id: str = "L" * 32) -> rs.RasterLayerLineage:
    return rs.RasterLayerLineage(
        source_sha256=SHA,
        page_number=1,
        render_dpi=dpi,
        pixel_height=int(gray.shape[0]),
        pixel_width=int(gray.shape[1]),
        placements=(),
        render_spec=rs.RASTER_OPENING_RENDER_SPEC,
        algorithm_version=rs.RASTER_OPENING_ALGORITHM_VERSION,
        layer_id=layer_id,
    )


def analyse(gray: np.ndarray, dpi: int = DPI) -> rs.RasterOpeningExistenceResult:
    return rs.analyse_raster_layer(gray, dpi=dpi, lineage=lineage_for(gray, dpi))


def decision_reasons(result: rs.RasterOpeningExistenceResult) -> list[tuple[str, ...]]:
    return [d.reason_codes for d in result.decisions]


def boxes(result: rs.RasterOpeningExistenceResult) -> list[tuple[str, tuple[int, int, int, int], tuple[str, ...]]]:
    return [
        (r.axis, r.gap_box_px, tuple(sorted(e.kind for e in r.symbol_evidence)))
        for r in result.records
    ]


# ---------------------------------------------------------------------------
# Synthetic PDF builders (raster placements, vector overlays)
# ---------------------------------------------------------------------------


def png_bytes(gray: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", gray)
    assert ok
    return buffer.tobytes()


def new_pdf(
    placements: list[tuple[np.ndarray, tuple[float, float]]],
    *,
    page_size: tuple[float, float] = (400, 260),
    dpi: int = DPI,
    rotation: int = 0,
    overlay=None,
) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=page_size[0], height=page_size[1])
    for gray, (x, y) in placements:
        width = gray.shape[1] * 72.0 / dpi
        height = gray.shape[0] * 72.0 / dpi
        page.insert_image(fitz.Rect(x, y, x + width, y + height), stream=png_bytes(gray), keep_proportion=False)
    if overlay is not None:
        overlay(page)
    if rotation:
        page.set_rotation(rotation)
    reopened = fitz.open(stream=doc.tobytes(), filetype="pdf")
    doc.close()
    return reopened


def propose(doc: fitz.Document, page_index: int = 0, sha: str = SHA) -> rs.RasterOpeningExistenceResult:
    return rs.propose_raster_opening_existence(doc, page_index, source_sha256=sha)


# ---------------------------------------------------------------------------
# Positives
# ---------------------------------------------------------------------------


def test_window_with_inset_frame_lines_is_proven():
    sheet = Sheet()
    window_wall(sheet)
    result = analyse(sheet.gray)
    assert result.status is CORROBORATED
    assert result.reason_codes == (rs.RASTER_OPENING_EXISTENCE_PROVEN,)
    (record,) = result.records
    assert record.axis == "horizontal"
    assert record.status is CORROBORATED
    assert record.proposition == rs.RASTER_PHYSICAL_OPENING_EXISTS
    assert [e.kind for e in record.symbol_evidence] == [rs.EVIDENCE_FRAME_LINES]
    assert record.gap_length_pt == pytest.approx(60.0, abs=0.5)
    assert record.band_thickness_pt == pytest.approx(WALL, abs=0.3)
    # the gap is bounded by the two continuing wall bands, in page pixels
    assert record.flank_a.box_px[2] + 1 == record.gap_box_px[0]
    assert record.gap_box_px[2] + 1 == record.flank_b.box_px[0]
    assert record.gap_box_pt[0] == pytest.approx(120.0, abs=0.5)
    assert record.gap_box_pt[2] == pytest.approx(180.0, abs=0.5)


def test_records_and_results_are_shadow_only_and_never_authoritative():
    sheet = Sheet()
    window_wall(sheet)
    result = analyse(sheet.gray)
    payload = result.to_dict()
    assert result.shadow_only is True and result.authoritative is False
    assert result.canonical_publication is False
    assert payload["shadow_only"] is True and payload["authoritative"] is False
    assert payload["canonical_publication"] is False
    for record in result.records:
        assert record.shadow_only is True and record.authoritative is False
        assert record.to_dict()["authoritative"] is False
    json.dumps(payload)  # JSON-serialisable evidence only


@pytest.mark.parametrize("hinge", ["low", "high"])
@pytest.mark.parametrize("swing", ["up", "down"])
def test_door_leaf_and_swing_arc_proves_an_opening(hinge, swing):
    sheet = Sheet()
    door_wall(sheet, hinge=hinge, swing=swing)
    result = analyse(sheet.gray)
    assert result.status is CORROBORATED
    (record,) = result.records
    (evidence,) = record.symbol_evidence
    assert evidence.kind == rs.EVIDENCE_DOOR_SWING
    assert evidence.detail["hinge_end"] == hinge
    assert evidence.detail["swing_side"] == ("low_rows" if swing == "up" else "high_rows")
    assert record.gap_length_pt == pytest.approx(24.0, abs=0.5)


def test_vertical_walls_are_proven_through_the_same_rule():
    sheet = Sheet()
    window_wall(sheet)
    vertical = np.ascontiguousarray(np.rot90(sheet.gray))
    result = analyse(vertical)
    (record,) = result.records
    assert record.axis == "vertical"
    assert record.gap_length_pt == pytest.approx(60.0, abs=0.5)
    assert [e.kind for e in record.symbol_evidence] == [rs.EVIDENCE_FRAME_LINES]


def test_two_windows_in_one_wall_are_two_distinct_records_with_distinct_ids():
    sheet = Sheet()
    top, bot = 60 - WALL / 2, 60 + WALL / 2
    sheet.rect(20, top, 60, bot)
    sheet.rect(110, top, 160, bot)
    sheet.rect(190, top, 280, bot)
    for g0, g1 in ((60, 110), (160, 190)):
        sheet.hline(g0, g1, top + 0.75, 0.5)
        sheet.hline(g0, g1, bot - 0.75, 0.5)
    result = analyse(sheet.gray)
    assert len(result.records) == 2
    assert len({r.record_id for r in result.records}) == 2
    assert [r.gap_length_pt for r in result.records] == pytest.approx([50.0, 30.0], abs=0.5)


# ---------------------------------------------------------------------------
# Look-alike negatives and fail-closed behaviour
# ---------------------------------------------------------------------------


def test_bare_wall_break_without_opening_evidence_abstains_and_is_retained():
    sheet = Sheet()
    bare_gap(sheet)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert result.status is ABSTAINED
    assert result.reason_codes == (rs.RASTER_NO_OPENING_CANDIDATES,)
    (decision,) = result.decisions  # the candidate is retained, never discarded
    assert decision.status is ABSTAINED
    assert decision.reason_codes == (rs.RASTER_NO_OPENING_EVIDENCE,)


def test_a_single_line_in_the_gap_is_not_a_frame():
    sheet = Sheet()
    bare_gap(sheet)
    sheet.hline(120, 180, 60, 0.5)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert decision_reasons(result) == [(rs.RASTER_NO_OPENING_EVIDENCE,)]


def test_a_recess_outlined_on_the_wall_faces_is_not_an_opening():
    """A niche keeps its outline on both faces: the wall is not interrupted."""
    sheet = Sheet()
    top, bot = bare_gap(sheet)
    sheet.hline(120, 180, top + 0.5, 1.0)
    sheet.hline(120, 180, bot - 0.5, 1.0)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert decision_reasons(result) == [(rs.RASTER_WALL_FACE_CONTINUES,)]


def test_a_glazing_ribbon_with_dashes_in_its_core_is_not_a_row_of_openings():
    sheet = Sheet()
    sheet.rect(20, 58.2, 280, 61.8, value=140)  # gray core
    sheet.hline(20, 280, 58.6, 0.6)
    sheet.hline(20, 280, 61.4, 0.6)
    for x in (60, 120, 180, 240):
        sheet.rect(x, 59.0, x + 12, 61.0, value=255)  # clear dashes inside the faces only
    result = analyse(sheet.gray)
    assert result.records == ()
    assert result.decisions
    assert all(reasons == (rs.RASTER_WALL_FACE_CONTINUES,) for reasons in decision_reasons(result))


def test_a_gap_narrower_than_the_paper_unit_floor_is_rejected():
    sheet = Sheet()
    window_wall(sheet, 120, 120 + rs.MIN_OPENING_GAP_PT - 2.0)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert decision_reasons(result) == [(rs.RASTER_GAP_TOO_SMALL,)]


def test_only_hairlines_count_as_swing_ink():
    """A leaf or curve as heavy as the poche is lettering, not a door symbol."""
    sheet = Sheet()
    sheet.hline(20, 100, 20, 0.5)  # hairline
    sheet.hline(20, 100, 40, rs.POCHE_MIN_PT + 0.4)  # as heavy as poche
    sheet.rect(20, 56.3, 100, 59.7)  # a wall band
    sheet.hline(20, 100, 59.9, 0.5)  # hairline laid against the band: inside its halo
    mass = (sheet.gray < rs.MASS_THRESHOLD).astype(np.uint8)
    line = (sheet.gray < rs.LINE_THRESHOLD).astype(np.uint8)
    solid = rs._odd(rs._px(rs.POCHE_MIN_PT, DPI))
    thick = cv2.morphologyEx(mass, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (solid, solid)))
    thin = rs._hairline_mask(line, thick)
    assert thin[_px(20), _px(60) : _px(90)].all()  # the hairline survives
    assert not thin[_px(40), _px(30) : _px(90)].any()  # the heavy stroke does not
    assert not thin[_px(57) : _px(60), _px(30) : _px(90)].any()  # nor the wall
    assert not thin[_px(59.5) : _px(60.4), _px(30) : _px(90)].any()  # nor ink touching the wall


def test_a_heavy_swing_curve_does_not_prove_a_door():
    top = 60 - WALL / 2
    heavy = Sheet()
    bare_gap(heavy, 120, 144)
    heavy.vline(top - 24, top, 120.25, 0.5)
    heavy.arc(120, top, 24, 270, 360, rs.POCHE_MIN_PT + 0.4)
    result = analyse(heavy.gray)
    assert result.records == ()
    assert all(rs.RASTER_OPENING_EXISTENCE_PROVEN not in reasons for reasons in decision_reasons(result))

    hairline = Sheet()
    bare_gap(hairline, 120, 144)
    hairline.vline(top - 24, top, 120.25, 0.5)
    hairline.arc(120, top, 24, 270, 360, 0.5)
    assert [r.gap_length_pt for r in analyse(hairline.gray).records] == pytest.approx([24.0], abs=0.5)


def test_a_short_jamb_stub_beside_a_long_wall_is_still_an_opening():
    sheet = Sheet()
    top, bot = 60 - WALL / 2, 60 + WALL / 2
    sheet.rect(20, top, 114, bot)
    sheet.rect(144, top, 151, bot)  # 7 pt stub: the other flank is the wall run
    sheet.hline(114, 144, top + 0.75, 0.5)
    sheet.hline(114, 144, bot - 0.75, 0.5)
    result = analyse(sheet.gray)
    (record,) = result.records
    assert record.gap_length_pt == pytest.approx(30.0, abs=0.5)


def test_a_step_in_wall_thickness_is_not_collinear_continuing_wall():
    sheet = Sheet()
    top, bot = 60 - WALL / 2, 60 + WALL / 2
    sheet.rect(20, top, 120, bot)
    sheet.rect(180, 60 - 3.0, 280, 60 + 3.0)  # much heavier continuation
    sheet.hline(120, 180, top + 0.75, 0.5)
    sheet.hline(120, 180, bot - 0.75, 0.5)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert decision_reasons(result) == [(rs.RASTER_FLANKS_NOT_COLLINEAR_BANDS,)]


def test_a_laterally_offset_continuation_forms_no_candidate():
    sheet = Sheet()
    top, bot = 60 - WALL / 2, 60 + WALL / 2
    sheet.rect(20, top, 120, bot)
    sheet.rect(180, top + 2.0, 280, bot + 2.0)
    sheet.hline(120, 180, top + 0.75, 0.5)
    sheet.hline(120, 180, bot - 0.75, 0.5)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert result.decisions == ()


def test_a_free_ended_wall_has_no_partner_and_proves_nothing():
    sheet = Sheet()
    sheet.rect(20, 58.3, 200, 61.7)
    result = analyse(sheet.gray)
    assert result.records == () and result.decisions == ()
    assert result.reason_codes == (rs.RASTER_NO_OPENING_CANDIDATES,)


def test_a_sheet_without_poche_bands_abstains():
    sheet = Sheet()
    sheet.hline(20, 280, 60, 0.5)  # linework only
    result = analyse(sheet.gray)
    assert result.status is ABSTAINED
    assert result.reason_codes == (rs.RASTER_NO_POCHE_WALL_BANDS,)


def test_speckle_noise_on_a_continuous_wall_creates_no_opening():
    sheet = Sheet()
    sheet.rect(20, 58.3, 280, 61.7)
    rng = np.random.default_rng(7)
    sheet.gray[rng.random(sheet.gray.shape) < 0.01] = 0
    result = analyse(sheet.gray)
    assert result.records == ()


def test_scattered_noise_on_blank_paper_creates_no_opening():
    rng = np.random.default_rng(11)
    gray = np.where(rng.random((600, 1400)) < 0.03, 0, 255).astype(np.uint8)
    result = analyse(gray)
    assert result.records == ()


def test_an_arc_whose_radius_does_not_match_the_gap_is_not_a_swing():
    sheet = Sheet()
    top, _ = bare_gap(sheet, 120, 144)
    sheet.vline(top - 48, top, 120.25, 0.5)
    sheet.arc(120, top, 48, 270, 360, 0.5)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert decision_reasons(result) == [(rs.RASTER_NO_OPENING_EVIDENCE,)]


def test_an_arc_without_a_leaf_is_not_a_swing():
    sheet = Sheet()
    top, _ = bare_gap(sheet, 120, 144)
    sheet.arc(120, top, 24, 270, 360, 0.5)
    result = analyse(sheet.gray)
    assert result.records == ()


def test_two_equally_plausible_swings_conflict_and_prove_nothing():
    sheet = Sheet()
    top, bot = bare_gap(sheet, 120, 144)
    sheet.vline(top - 24, top, 120.25, 0.5)
    sheet.arc(120, top, 24, 270, 360, 0.5)
    sheet.vline(bot, bot + 24, 143.75, 0.5)
    sheet.arc(144, bot, 24, 90, 180, 0.5)
    result = analyse(sheet.gray)
    assert result.records == ()
    assert result.status is CONFLICT
    assert result.reason_codes == (rs.RASTER_DOOR_SWING_AMBIGUOUS,)
    (decision,) = result.decisions
    assert decision.status is CONFLICT and decision.record is None


def test_swing_evidence_is_independent_of_hairlines_that_continue_across_the_faces():
    sheet = Sheet()
    top, bot = door_wall(sheet)
    sheet.hline(120, 144, top + 0.125, 0.25)
    sheet.hline(120, 144, bot - 0.125, 0.25)
    result = analyse(sheet.gray)
    (record,) = result.records
    assert [e.kind for e in record.symbol_evidence] == [rs.EVIDENCE_DOOR_SWING]


def test_a_window_symbol_that_cannot_be_resolved_from_the_faces_abstains():
    """At 144 dpi the 0.5 pt inset is one pixel: the rule must not guess."""
    sheet = Sheet(dpi=144)
    window_wall(sheet)
    result = analyse(sheet.gray, 144)
    assert result.records == ()


def test_dark_page_margins_and_title_blocks_do_not_become_openings():
    sheet = Sheet()
    sheet.rect(0, 0, 300, 3)  # border band
    sheet.rect(0, 117, 300, 120)
    sheet.rect(0, 0, 3, 120)
    sheet.rect(297, 0, 300, 120)
    result = analyse(sheet.gray)
    assert result.records == ()


# ---------------------------------------------------------------------------
# Duplicate suppression and competing readings
# ---------------------------------------------------------------------------


def _decision(box, *, record=None, status=ABSTAINED, reasons=(rs.RASTER_NO_OPENING_EVIDENCE,)):
    piece = rs.PochePiece(axis="horizontal", box_px=(0, 0, 9, 9), box_pt=(0.0, 0.0, 2.0, 2.0), thickness_px=10)
    return rs.RasterOpeningDecision(
        status=status,
        reason_codes=reasons,
        axis="horizontal",
        gap_box_px=box,
        gap_box_pt=(0.0, 0.0, 1.0, 1.0),
        flank_a=piece,
        flank_b=piece,
        record=record,
    )


def _proven(box):
    sheet = Sheet()
    window_wall(sheet)
    record = analyse(sheet.gray).records[0]
    record = replace(record, gap_box_px=box)
    return _decision(box, record=record, status=CORROBORATED, reasons=(rs.RASTER_OPENING_EXISTENCE_PROVEN,))


def test_duplicate_evidence_collapses_to_one_decision_that_keeps_the_record():
    bare = _decision((100, 50, 200, 63))
    proven = _proven((101, 50, 200, 63))
    kept = rs._suppress_duplicates_and_conflicts([bare, proven, _decision((100, 50, 199, 63))])
    assert len(kept) == 1
    assert kept[0].record is proven.record
    assert kept[0].suppressed_duplicates == 2


def test_overlapping_proven_readings_of_one_void_are_all_withdrawn_to_conflict():
    first = _proven((100, 50, 200, 63))
    second = _proven((150, 50, 260, 63))
    apart = _proven((400, 50, 500, 63))
    result = rs._suppress_duplicates_and_conflicts([first, second, apart])
    by_box = {d.gap_box_px: d for d in result}
    assert by_box[(100, 50, 200, 63)].status is CONFLICT and by_box[(100, 50, 200, 63)].record is None
    assert by_box[(150, 50, 260, 63)].status is CONFLICT and by_box[(150, 50, 260, 63)].record is None
    assert by_box[(400, 50, 500, 63)].record is not None
    assert by_box[(100, 50, 200, 63)].reason_codes == (rs.RASTER_COMPETING_CANDIDATES,)


def test_distinct_adjacent_gaps_are_not_conflated():
    kept = rs._suppress_duplicates_and_conflicts([_proven((100, 50, 200, 63)), _proven((201, 50, 300, 63))])
    assert all(d.record is not None for d in kept) and len(kept) == 2


# ---------------------------------------------------------------------------
# Invariance: dpi, translation, rotation, mirroring, padding, unrelated content
# ---------------------------------------------------------------------------


def _plan(dpi: int) -> Sheet:
    """Three walls on separate rows: a window, a swing door and a second window."""
    sheet = Sheet(dpi=dpi)
    window_wall(sheet, 60, 120, yc=20)
    door_wall(sheet, 160, 184, yc=62, hinge="low", swing="up")
    window_wall(sheet, 80, 150, yc=100, inset=0.75)
    return sheet


@pytest.mark.parametrize("dpi", [192, 240, 288, 300])
def test_the_same_drawing_proves_the_same_openings_at_any_resolution(dpi):
    reference = analyse(_plan(288).gray, 288)
    result = analyse(_plan(dpi).gray, dpi)
    assert len(result.records) == len(reference.records) == 3
    assert [tuple(sorted(e.kind for e in r.symbol_evidence)) for r in result.records] == [
        tuple(sorted(e.kind for e in r.symbol_evidence)) for r in reference.records
    ]
    for got, want in zip(result.records, reference.records):
        assert got.axis == want.axis
        assert got.gap_length_pt == pytest.approx(want.gap_length_pt, abs=0.75)
        assert got.gap_box_pt[0] == pytest.approx(want.gap_box_pt[0], abs=0.75)
        assert got.gap_box_pt[1] == pytest.approx(want.gap_box_pt[1], abs=0.75)


@pytest.mark.parametrize("offset_pt", [(0, 0), (13, 7), (90, 41)])
def test_translation_moves_every_record_by_exactly_the_offset(offset_pt):
    base = _plan(DPI)
    canvas = Sheet(width_pt=300 + 100, height_pt=120 + 60)
    dx, dy = _px(offset_pt[0]), _px(offset_pt[1])
    canvas.gray[dy : dy + base.gray.shape[0], dx : dx + base.gray.shape[1]] = base.gray
    moved = analyse(canvas.gray)
    reference = analyse(base.gray)
    assert len(moved.records) == len(reference.records) == 3
    for got, want in zip(moved.records, reference.records):
        assert got.axis == want.axis
        assert got.gap_box_px == (
            want.gap_box_px[0] + dx,
            want.gap_box_px[1] + dy,
            want.gap_box_px[2] + dx,
            want.gap_box_px[3] + dy,
        )
        assert got.gap_length_pt == want.gap_length_pt
        assert [e.kind for e in got.symbol_evidence] == [e.kind for e in want.symbol_evidence]


@pytest.mark.parametrize("quarter_turns", [1, 2, 3])
def test_rotating_the_raster_swaps_axes_and_keeps_the_openings(quarter_turns):
    base = _plan(DPI)
    reference = analyse(base.gray)
    rotated = analyse(np.ascontiguousarray(np.rot90(base.gray, quarter_turns)))
    assert len(rotated.records) == len(reference.records) == 3
    assert sorted(r.gap_length_pt for r in rotated.records) == sorted(r.gap_length_pt for r in reference.records)
    expected_axes = (
        {"horizontal": "vertical", "vertical": "horizontal"}
        if quarter_turns % 2
        else {"horizontal": "horizontal", "vertical": "vertical"}
    )
    assert sorted(r.axis for r in rotated.records) == sorted(expected_axes[r.axis] for r in reference.records)
    assert sorted(tuple(e.kind for e in r.symbol_evidence) for r in rotated.records) == sorted(
        tuple(e.kind for e in r.symbol_evidence) for r in reference.records
    )


@pytest.mark.parametrize("flip", [0, 1, -1])
def test_mirroring_the_raster_keeps_the_openings(flip):
    base = _plan(DPI)
    reference = analyse(base.gray)
    mirrored = analyse(np.ascontiguousarray(cv2.flip(base.gray, flip)))
    assert len(mirrored.records) == len(reference.records) == 3
    assert sorted(r.gap_length_pt for r in mirrored.records) == sorted(r.gap_length_pt for r in reference.records)


def test_unrelated_content_and_a_larger_viewport_do_not_change_the_proven_openings():
    base = _plan(DPI)
    reference = analyse(base.gray)
    canvas = Sheet(width_pt=300 + 200, height_pt=120 + 150)
    dx, dy = _px(60), _px(80)
    canvas.gray[dy : dy + base.gray.shape[0], dx : dx + base.gray.shape[1]] = base.gray
    canvas.rect(5, 5, 55, 40)  # title-block-like mass
    canvas.hline(5, 495, 215, 0.5)
    for i in range(12):  # text-like specks well away from every wall
        canvas.rect(300 + i * 12, 10, 304 + i * 12, 16)
    padded = analyse(canvas.gray)
    assert [r.gap_box_px for r in padded.records] == [
        (
            r.gap_box_px[0] + dx,
            r.gap_box_px[1] + dy,
            r.gap_box_px[2] + dx,
            r.gap_box_px[3] + dy,
        )
        for r in reference.records
    ]


def test_input_order_of_nothing_matters_for_a_pure_function_of_pixels():
    base = _plan(DPI)
    first = analyse(base.gray)
    second = analyse(base.gray.copy())
    assert first.to_dict() == second.to_dict()


# ---------------------------------------------------------------------------
# Determinism, identity, no mutation
# ---------------------------------------------------------------------------


def test_replay_is_deterministic_and_ids_are_stable():
    base = _plan(DPI)
    runs = [analyse(base.gray) for _ in range(3)]
    assert runs[0].to_dict() == runs[1].to_dict() == runs[2].to_dict()
    prefix = "raster_physical_opening_existence_"
    assert all(r.record_id.startswith(prefix) and len(r.record_id) == len(prefix) + 32 for r in runs[0].records)
    assert len({r.record_id for r in runs[0].records}) == 3


def test_record_ids_depend_on_the_layer_lineage():
    base = _plan(DPI)
    one = rs.analyse_raster_layer(base.gray, dpi=DPI, lineage=lineage_for(base.gray, layer_id="A" * 32))
    other = rs.analyse_raster_layer(base.gray, dpi=DPI, lineage=lineage_for(base.gray, layer_id="B" * 32))
    assert [r.gap_box_px for r in one.records] == [r.gap_box_px for r in other.records]
    assert {r.record_id for r in one.records}.isdisjoint({r.record_id for r in other.records})


def test_analysis_does_not_mutate_its_input():
    base = _plan(DPI)
    before = base.gray.copy()
    analyse(base.gray)
    assert np.array_equal(base.gray, before)


def _document_snapshot(doc: fitz.Document):
    """Every object and raw stream (tobytes() is not stable: it mints a fresh /ID)."""
    objects, streams = [], []
    for xref in range(1, doc.xref_length()):
        objects.append(doc.xref_object(xref, compressed=False))
        try:
            streams.append(hashlib.sha256(doc.xref_stream_raw(xref)).hexdigest())
        except Exception:  # noqa: BLE001 - non-stream objects
            streams.append("")
    return objects, streams, doc.page_count, doc.metadata


def test_the_source_document_is_not_mutated():
    sheet = Sheet()
    window_wall(sheet)
    doc = new_pdf([(sheet.gray, (10, 10))])
    before = _document_snapshot(doc)
    result = propose(doc)
    assert len(result.records) == 1
    assert _document_snapshot(doc) == before
    assert doc.is_dirty is False


# ---------------------------------------------------------------------------
# PDF level: raster layer extraction, lineage, text/vector isolation
# ---------------------------------------------------------------------------


def _plan_sheet() -> Sheet:
    sheet = Sheet()
    window_wall(sheet, 60, 120, yc=20)
    door_wall(sheet, 160, 184, yc=80)
    return sheet


def _plan_pdf(**kwargs) -> fitz.Document:
    return new_pdf([(_plan_sheet().gray, (10, 10))], **kwargs)


def test_raster_underlay_page_proves_openings_through_the_pdf_path():
    result = propose(_plan_pdf())
    assert result.status is CORROBORATED
    assert [r.axis for r in result.records] == ["horizontal", "horizontal"]
    window, door = result.records  # ordered top to bottom on the page
    assert [e.kind for e in window.symbol_evidence] == [rs.EVIDENCE_FRAME_LINES]
    assert [e.kind for e in door.symbol_evidence] == [rs.EVIDENCE_DOOR_SWING]
    # page points: the image sits at (10, 10)
    assert window.gap_box_pt[0] == pytest.approx(10 + 60, abs=1.0)
    assert window.gap_box_pt[1] == pytest.approx(10 + 20 - WALL / 2, abs=1.0)
    assert door.gap_box_pt[0] == pytest.approx(10 + 160, abs=1.0)
    assert result.lineage is not None and result.lineage.render_dpi == DPI


def test_lineage_names_the_exact_source_pixels():
    doc = _plan_pdf()
    result = propose(doc, sha="cd" * 32)
    lineage = result.lineage
    assert lineage is not None
    assert lineage.source_sha256 == "cd" * 32 and lineage.page_number == 1
    (placement,) = lineage.placements
    assert placement.image_xref > 0 and len(placement.image_sha256) == 64
    assert placement.bbox_pt[0] == pytest.approx(10.0, abs=0.01)
    assert placement.native_dpi == pytest.approx(DPI, abs=0.5)
    for record in result.records:
        assert record.source_sha256 == "cd" * 32
        assert record.layer_id == lineage.layer_id and record.page_number == 1 and record.render_dpi == DPI
    other = propose(doc, sha="ef" * 32)
    assert other.lineage.layer_id != lineage.layer_id
    assert [r.gap_box_px for r in other.records] == [r.gap_box_px for r in result.records]
    assert {r.record_id for r in other.records}.isdisjoint({r.record_id for r in result.records})


def test_document_metadata_and_filename_never_enter_the_result():
    doc = _plan_pdf()
    before = propose(doc)
    doc.set_metadata({"title": "Lot16 Power REV E", "author": "expected_boq 27"})
    after = propose(doc)
    assert before.to_dict() == after.to_dict()


def test_text_callouts_cannot_mint_an_opening_on_a_continuous_wall():
    sheet = Sheet()
    sheet.rect(20, 58.3, 280, 61.7)

    def overlay(page: fitz.Page) -> None:
        for x, label in ((60, "1218 SGW"), (140, "0915 SGW obs"), (220, "2124 CRNR STACK")):
            page.insert_text((x, 30), label, fontsize=9)

    result = propose(new_pdf([(sheet.gray, (10, 10))], overlay=overlay))
    assert result.records == ()


def test_text_callouts_cannot_mint_an_opening_on_a_bare_wall_break():
    sheet = Sheet()
    bare_gap(sheet)

    def overlay(page: fitz.Page) -> None:
        page.insert_text((90, 50), "1218 SGW", fontsize=9)
        page.insert_text((70, 100), "1.2m x 1.8m window", fontsize=9)

    result = propose(new_pdf([(sheet.gray, (10, 10))], overlay=overlay))
    assert result.records == ()
    assert any(rs.RASTER_NO_OPENING_EVIDENCE in reasons for reasons in decision_reasons(result))


def test_vector_text_and_dimension_chains_do_not_change_a_proven_opening():
    sheet = Sheet()
    window_wall(sheet)
    plain = propose(new_pdf([(sheet.gray, (10, 10))]))

    def overlay(page: fitz.Page) -> None:
        page.insert_text((90, 45), "1218 SGW", fontsize=9)
        page.draw_line(fitz.Point(40, 30), fitz.Point(240, 30), color=(0, 0, 0), width=1.5)
        page.draw_rect(fitz.Rect(60, 55, 140, 66), color=(0, 0, 0), fill=(0, 0, 0))  # vector poche look-alike

    annotated = propose(new_pdf([(sheet.gray, (10, 10))], overlay=overlay))
    assert plain.to_dict() == annotated.to_dict()
    assert len(annotated.records) == 1


def test_a_vector_native_plan_has_no_raster_layer_and_proves_nothing():
    doc = fitz.open()
    page = doc.new_page(width=400, height=260)
    page.draw_rect(fitz.Rect(30, 28.3, 130, 31.7), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(190, 28.3, 290, 31.7), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_line(fitz.Point(130, 29.0), fitz.Point(190, 29.0), color=(0, 0, 0), width=0.5)
    page.draw_line(fitz.Point(130, 31.0), fitz.Point(190, 31.0), color=(0, 0, 0), width=0.5)
    result = propose(fitz.open(stream=doc.tobytes(), filetype="pdf"))
    assert result.status is ABSTAINED
    assert result.reason_codes == (rs.RASTER_NO_RASTER_LAYER,)
    assert result.records == () and result.decisions == ()


def test_a_vector_plan_next_to_an_unrelated_raster_logo_stays_invisible():
    logo = np.full((80, 200), 255, np.uint8)
    logo[20:60, 20:180] = 0  # a heavy logo block
    holder = fitz.open()
    page = holder.new_page(width=400, height=260)
    page.insert_image(fitz.Rect(300, 200, 350, 220), stream=png_bytes(logo), keep_proportion=False)
    page.draw_rect(fitz.Rect(30, 28.3, 130, 31.7), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(190, 28.3, 290, 31.7), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_line(fitz.Point(130, 29.0), fitz.Point(190, 29.0), color=(0, 0, 0), width=0.5)
    page.draw_line(fitz.Point(130, 31.0), fitz.Point(190, 31.0), color=(0, 0, 0), width=0.5)
    result = propose(fitz.open(stream=holder.tobytes(), filetype="pdf"))
    assert result.records == ()
    assert result.reason_codes != (rs.RASTER_NO_RASTER_LAYER,)


def test_the_module_never_reads_page_text_or_vector_drawings(monkeypatch):
    """Only image placement metadata may come out of the page: no text, no vector paths."""

    def boom(*_args, **_kwargs):
        raise AssertionError("the raster authority must not read text or vector drawings")

    for name in (
        "get_text",
        "get_text_words",
        "get_text_blocks",
        "get_text_selection",
        "get_textbox",
        "search_for",
        "get_drawings",
        "get_cdrawings",
    ):
        if hasattr(fitz.Page, name):
            monkeypatch.setattr(fitz.Page, name, boom)
    for name in (
        "extractText",
        "extractBLOCKS",
        "extractWORDS",
        "extractDICT",
        "extractJSON",
        "extractRAWDICT",
        "extractXHTML",
        "extractHTML",
        "extractXML",
        "extractSelection",
        "extractTextbox",
        "search",
    ):
        if hasattr(fitz.TextPage, name):
            monkeypatch.setattr(fitz.TextPage, name, boom)
    result = propose(_plan_pdf())
    assert len(result.records) == 2


def test_tiling_and_placement_order_do_not_change_the_proven_openings():
    sheet = _plan_sheet()
    whole = propose(new_pdf([(sheet.gray, (10, 10))]))
    width = sheet.gray.shape[1]
    left, middle, right = (
        sheet.gray[:, : width // 3],
        sheet.gray[:, width // 3 : 2 * width // 3],
        sheet.gray[:, 2 * width // 3 :],
    )
    step = left.shape[1] * 72.0 / DPI
    step2 = (left.shape[1] + middle.shape[1]) * 72.0 / DPI
    tiles = [
        (np.ascontiguousarray(right), (10 + step2, 10)),
        (np.ascontiguousarray(left), (10, 10)),
        (np.ascontiguousarray(middle), (10 + step, 10)),
    ]
    tiled = propose(new_pdf(tiles))
    assert boxes(tiled) == boxes(whole)
    assert len(tiled.lineage.placements) == 3


def test_a_quarter_turn_placed_raster_keeps_its_true_resolution_and_openings():
    sheet = _plan_sheet()
    height, width = sheet.gray.shape
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    rect = fitz.Rect(10, 10, 10 + height * 72.0 / DPI, 10 + width * 72.0 / DPI)  # width and height swap
    page.insert_image(rect, stream=png_bytes(sheet.gray), keep_proportion=False, rotate=90)
    result = propose(fitz.open(stream=doc.tobytes(), filetype="pdf"))
    (placement,) = result.lineage.placements
    assert placement.native_dpi == pytest.approx(DPI, abs=0.5)
    assert result.lineage.render_dpi == DPI
    assert sorted(r.gap_length_pt for r in result.records) == pytest.approx([24.0, 60.0], abs=0.75)
    assert {r.axis for r in result.records} == {"vertical"}


def test_page_annotations_never_enter_the_raster_layer():
    sheet = Sheet()
    bare_gap(sheet)
    doc = new_pdf([(sheet.gray, (10, 10))])
    page = doc[0]
    page.add_rect_annot(fitz.Rect(70, 30, 190, 50)).update()  # an annotation drawn over the wall break
    page.add_line_annot(fitz.Point(80, 40), fitz.Point(180, 40)).update()
    annotated = propose(fitz.open(stream=doc.tobytes(), filetype="pdf"))
    assert annotated.records == ()
    plain = propose(new_pdf([(sheet.gray, (10, 10))]))
    assert annotated.to_dict() == plain.to_dict()


def test_non_uint8_pixels_abstain():
    sheet = Sheet()
    window_wall(sheet)
    result = rs.analyse_raster_layer(sheet.gray.astype(np.float32), dpi=DPI, lineage=lineage_for(sheet.gray))
    assert result.status is ABSTAINED and result.reason_codes == (rs.RASTER_LAYER_UNREADABLE,)


def test_a_rotated_page_abstains_instead_of_guessing_a_frame():
    result = propose(_plan_pdf(rotation=90))
    assert result.status is ABSTAINED
    assert result.reason_codes == (rs.RASTER_PAGE_ROTATION_UNSUPPORTED,)
    assert result.records == ()


def test_a_page_without_images_has_no_raster_layer():
    doc = fitz.open()
    doc.new_page(width=200, height=100)
    result = propose(fitz.open(stream=doc.tobytes(), filetype="pdf"))
    assert result.reason_codes == (rs.RASTER_NO_RASTER_LAYER,)


def test_an_oversized_raster_layer_abstains(monkeypatch):
    monkeypatch.setattr(rs, "MAX_PIXELS", 10_000)
    result = propose(_plan_pdf())
    assert result.reason_codes == (rs.RASTER_LAYER_TOO_LARGE,)
    assert result.records == ()


def test_a_band_storm_abstains_instead_of_pairing_noise(monkeypatch):
    monkeypatch.setattr(rs, "MAX_BAND_PIECES", 1)
    result = propose(_plan_pdf())
    assert result.reason_codes == (rs.RASTER_TOO_MANY_WALL_BANDS,)
    assert result.records == ()


def test_unreadable_layers_abstain():
    result = rs.analyse_raster_layer(np.zeros((0, 0), np.uint8), dpi=DPI, lineage=lineage_for(np.zeros((1, 1), np.uint8)))
    assert result.status is ABSTAINED and result.reason_codes == (rs.RASTER_LAYER_UNREADABLE,)


# ---------------------------------------------------------------------------
# Architecture: shadow only, no production importer, no authority, no benchmark inputs
# ---------------------------------------------------------------------------

NON_PRODUCTION_DIRS = {"tests", "benchmarks", "scripts", "node_modules", "docs"}
MODULE = "pb_raster_opening_existence_shadow"


def _production_python_files():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in NON_PRODUCTION_DIRS or any(part.startswith(".") for part in rel.parts):
            continue
        yield path


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value  # dynamic import strings are caught too


def test_no_production_module_imports_the_raster_shadow():
    offenders = []
    for path in _production_python_files():
        if path.name == f"{MODULE}.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        if any(name == MODULE or name.startswith(f"{MODULE}.") for name in _imports(tree)):
            offenders.append(path.name)
    assert offenders == []


def test_only_the_diff_script_imports_the_raster_shadow_outside_tests():
    importers = [
        path.name
        for path in sorted((ROOT / "scripts").glob("*.py"))
        if MODULE in set(_imports(ast.parse(path.read_text(encoding="utf-8-sig"))))
    ]
    assert importers == [
        "raster_opening_callout_control.py",  # read-only CONTROL: counts callouts, feeds nothing back
        "raster_opening_existence_shadow_diff.py",
    ]


FIRM_SEAM_MODULES = (
    "pb_page_scale_calibration_authority",
    "pb_viewport_scale_binding",
    "pb_measurement_input_authority",
    "pb_figured_dimension_authority",
    "pb_wall_length_quantity",
    "pb_wall_height_authority",
    "pb_physical_wall_candidate_authority",
    "pb_physical_opening_authority",
    "pb_opening_host_binding_authority",
    "pb_wall_room_topology_canonical_adapter",
    "pb_planreader_pdf_extractor",
    "pb_vector_geometry_v130",
)


def test_firm_seam_modules_do_not_import_the_raster_shadow():
    for name in FIRM_SEAM_MODULES:
        path = ROOT / f"{name}.py"
        if not path.exists():
            continue
        assert MODULE not in set(_imports(ast.parse(path.read_text(encoding="utf-8-sig")))), name


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def test_the_module_imports_only_stdlib_numpy_cv2_and_the_contract_module():
    imported = _top_level_imports(ROOT / f"{MODULE}.py")
    local = {name for name in imported if (ROOT / f"{name}.py").exists()}
    assert local == {"pb_migration_contracts"}
    assert imported - local <= set(sys.stdlib_module_names) | {"__future__", "numpy", "cv2"}


def test_importing_the_module_leaves_no_authority_module_loaded():
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        f"import {MODULE}\n"
        f"loaded = sorted(m for m in sys.modules if m.startswith('pb_') and m not in ({MODULE!r}, 'pb_migration_contracts'))\n"
        "print(','.join(loaded))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert proc.stdout.strip() == ""


def test_the_module_reads_no_text_vector_scale_or_benchmark_inputs():
    source = (ROOT / f"{MODULE}.py").read_text(encoding="utf-8")
    for fragment in (
        "get_text",
        "get_textpage",
        "get_drawings",
        "get_cdrawings",
        "search_for",
        "ocr",
        "tesseract",
        "drawing_scale",
        "scale_ratio",
        "title_block",
        "expected_boq",
        "reference_takeoff",
        "benchmark_rules",
        "item_mappings",
        "holdout_suite",
        "scoring_tolerance",
        "object_universe",
        "lot16",
        "ghazi",
        "murera",
        "3laurel",
        "kstvet",
    ):
        assert fragment not in source.lower(), fragment


def test_the_result_is_not_a_g17_existence_record_and_uses_its_own_proposition():
    import pb_physical_opening_authority as g17

    sheet = Sheet()
    window_wall(sheet)
    (record,) = analyse(sheet.gray).records
    assert not isinstance(record, g17.PhysicalOpeningExistenceRecord)
    assert record.proposition == rs.RASTER_PHYSICAL_OPENING_EXISTS
    assert record.proposition != g17.PHYSICAL_OPENING_EXISTS


def test_w10_adapter_authority_flags_are_still_hardcoded_false():
    tree = ast.parse((ROOT / "pb_wall_room_topology_canonical_adapter.py").read_text(encoding="utf-8"))
    flags = {"takeoff_eligible": [], "deduction_authority": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in flags:
            flags[node.arg].append(isinstance(node.value, ast.Constant) and node.value.value is False)
    assert len(flags["takeoff_eligible"]) >= 3 and len(flags["deduction_authority"]) >= 3
    assert all(flags["takeoff_eligible"]) and all(flags["deduction_authority"])


def test_thresholds_are_paper_units_or_ratios():
    assert rs.MIN_OPENING_GAP_PT == 8.0
    assert 0.0 < rs.LINE_COVERAGE <= 1.0 and 0.0 < rs.END_COVERAGE <= 1.0
    for name in ("POCHE_MIN_PT", "BAND_MIN_RUN_PT", "BAND_MAX_THICKNESS_PT", "END_WINDOW_PT", "LINE_ROW_PAD_PT"):
        assert getattr(rs, name) > 0.0
