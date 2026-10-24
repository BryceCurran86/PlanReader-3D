"""SHA-gated Q5446 ORIGINAL outlined-ink area schedule source observation.

This records directly observed, manually transcribed original PDF source values.
It does NOT decode outlined font glyphs, prove net internal floors, or authorize
FIRM QuantityEvidence, customer rows or benchmark matches. Original source PDF
bytes must remain on the owner's private machine / Library, not in GitHub.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from pathlib import Path
from typing import Any

SOURCE_SHA256 = "5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0"
SOURCE_BYTE_COUNT = 1769126
SOURCE_PAGE_COUNT = 10
SOURCE_PAGE_INDEX = 0

# Actual ORIGINAL PyMuPDF get_drawings() native path IDs / bounding rectangles,
# verified from SHA-authenticated PDF p1 original ink. Source row-rule receipts.
ORIGINAL_TABLE_RULES = (
    (324, 979.44, 646.68, 1147.20, 647.04),
    (330, 979.44, 657.00, 1147.20, 657.36),
    (336, 979.44, 667.56, 1147.20, 667.92),
    (342, 979.44, 677.88, 1147.20, 678.24),
    (348, 979.44, 688.20, 1147.20, 688.56),
    (354, 979.44, 698.76, 1147.20, 699.12),
    (360, 979.44, 709.08, 1147.20, 709.44),
)
ORIGINAL_LEFT_BORDER = (366, 979.32, 646.92, 979.68, 728.52)
ORIGINAL_LABEL_DIVIDER = (372, 1038.84, 646.92, 1039.20, 728.52)
GEOMETRY_EPSILON_PT = 0.05

# Direct original-source transcription, not frozen truth. A gross/summary
# architect schedule is NOT evidence of net wall-face floor-finish extent.
PRINTED_ORIGINAL_ROWS = (
    ("ground_floor", "Ground Floor", Decimal("123.89"), False),
    ("first_floor", "First Floor", Decimal("121.81"), False),
    ("subtotal", "Subtotal", Decimal("245.71"), True),
    ("porch", "Porch", Decimal("4.08"), False),
    ("garage", "Garage", Decimal("36.40"), False),
    ("alfresco", "Alfresco", Decimal("12.00"), False),
    ("total", "Total Area", Decimal("298.19"), True),
)


@dataclass(frozen=True)
class OriginalAreaScheduleCandidate:
    original_row_id: str
    printed_label: str
    printed_area_m2: Decimal
    is_rollup: bool
    original_page_index: int
    table_row_number: int
    original_source_sha256: str
    status: str = "CANDIDATE"
    glyph_correspondence_authenticated: bool = False
    physical_surface_owner_authenticated: bool = False
    customer_projection_allowed: bool = False
    original_numeric_vector_path_ids: tuple[int, ...] = ()
    original_label_vector_path_ids: tuple[int, ...] = ()
    label_stroke_presence_verified: bool = False


@dataclass(frozen=True)
class Q5446SourceAreaScheduleShadow:
    status: str
    reason_codes: tuple[str, ...]
    rows: tuple[OriginalAreaScheduleCandidate, ...]
    actual_source_sha256: str | None
    printed_floor_subtotal_delta_m2: Decimal | None
    printed_total_rollup_delta_m2: Decimal | None
    diagnostic_only: bool = True


def _abstain(reason: str, source_sha: str | None = None) -> Q5446SourceAreaScheduleShadow:
    return Q5446SourceAreaScheduleShadow(
        "ABSTAIN", (reason,), (), source_sha, None, None,
    )


def _rule_matches(drawings: list[dict[str, Any]], receipt: tuple[int, float, float, float, float]) -> bool:
    idx, *expected = receipt
    if idx < 0 or idx >= len(drawings):
        return False
    record = drawings[idx]
    if record.get("type") != "fs":
        return False
    if record.get("fill") is None or record.get("color") is None:
        return False
    width = record.get("width")
    if type(width) not in (float, int) or abs(width - 0.375) > GEOMETRY_EPSILON_PT:
        return False
    rect = record.get("rect")
    if rect is None:
        return False
    try:
        return all(
            type(value) in (float, int) and abs(float(value) - target) <= GEOMETRY_EPSILON_PT
            for value, target in zip((rect.x0, rect.y0, rect.x1, rect.y1), expected)
        )
    except (TypeError, ValueError, OverflowError, AttributeError):
        return False


def _table_witnesses_valid(drawings: list[dict[str, Any]]) -> bool:
    # This is only TABLE GRID STRUCTURE corroboration. It does not recognize
    # the original vector-outlined numeric glyphs or authorize their use.
    return all(
        _rule_matches(drawings, receipt)
        for receipt in (*ORIGINAL_TABLE_RULES, ORIGINAL_LEFT_BORDER, ORIGINAL_LABEL_DIVIDER)
    )


# One isolated numeric glyph source stroke per printed character.
# These are original SHA-verified vector shapes, NOT OCR text guesses.
# The label/category characters are *not* decoded by this source module.
ORIGINAL_NUMERIC_COLUMNS = (1039.50, 1072.80)
ORIGINAL_ROW_Y_BOUNDS = (
    (646.68, 657.00),
    (657.00, 667.56),
    (667.56, 677.88),
    (677.88, 688.20),
    (688.20, 698.76),
    (698.76, 709.08),
    (709.08, 728.52),
)


# Fixed, original-plan, physical vector stroke witnesses within each source
# category's left table cell. Multiple strokes can form one outlined character.
# This proves that the printed label ink still occupies the original row, but
# is NOT a free-standing glyph-to-letter semantic decoder.
ORIGINAL_LABEL_STROKE_PATHS = (
    (9, 11, 12, 13, 16, 18, 19, 22, 23, 25, 26, 27),
    (52, 54, 57, 58, 59, 61, 64, 65, 67, 68, 69),
    (94, 95, 98, 99, 101, 102, 105, 107, 108),
    (133, 134, 136, 137, 139, 140, 141),
    (163, 165, 167, 169, 170, 171, 172, 173, 174),
    (197, 200, 203, 204, 205, 206, 207, 208, 209),
    (234, 235, 238, 240, 243, 244, 246, 247, 248),
)


def _original_label_stroke_receipts(drawings: list[dict[str, Any]]) -> tuple[tuple[int, ...], ...] | None:
    if len(ORIGINAL_LABEL_STROKE_PATHS) != len(PRINTED_ORIGINAL_ROWS):
        return None
    found = []
    for row, (y0, y1) in zip(ORIGINAL_LABEL_STROKE_PATHS, ORIGINAL_ROW_Y_BOUNDS):
        if len(set(row)) != len(row):
            return None
        for idx in row:
            if type(idx) is not int or idx < 0 or idx >= len(drawings):
                return None
            record = drawings[idx]
            rect = record.get("rect")
            width = record.get("width")
            if (
                record.get("type") != "s"
                or record.get("color") != (0.0, 0.0, 0.0)
                or type(width) not in (int, float)
                or abs(width - 0.72) > GEOMETRY_EPSILON_PT
                or rect is None
            ):
                return None
            try:
                if not (
                    980.0 < rect.x0 < rect.x1 < 1038.6
                    and y0 + 1.0 < rect.y0 < rect.y1 < y1 - 1.0
                ):
                    return None
            except (TypeError, ValueError, AttributeError):
                return None
        found.append(row)
    all_ids = tuple(index for row in found for index in row)
    if len(set(all_ids)) != len(all_ids):
        return None
    return tuple(found)


def _numeric_vector_digit(record: dict[str, Any]) -> str | None:
    """Classify ORIGINAL vector-stroked glyph topology, without raster OCR.

    The immutable original 0–9 font has independently distinct path profiles:
    command count, normalized first stroke and character width. All ten
    digits and decimal point occur in the authenticated source table.
    """
    if record.get("type") != "s" or record.get("color") != (0.0, 0.0, 0.0):
        return None
    width = record.get("width")
    if type(width) not in (int, float) or abs(width - 0.96) > 0.05:
        return None
    rect = record.get("rect")
    items = record.get("items")
    if rect is None or not isinstance(items, (tuple, list)) or not items:
        return None
    try:
        w = float(rect.x1 - rect.x0)
        h = float(rect.y1 - rect.y0)
        if w <= 0 or h <= 0:
            return None
        first = items[0]
        if first[0] == "qu":
            if len(items) == 1 and 0.43 <= w <= 0.55 and 0.43 <= h <= 0.75:
                return "."
            return None
        if first[0] != "l":
            return None
        if not (5.45 <= h <= 5.85 and 1.15 <= w <= 3.75):
            return None
        px = (float(first[1].x) - float(rect.x0)) / w
        py = (float(first[1].y) - float(rect.y0)) / h
        if not (0 <= px <= 1.005 and 0 <= py <= 1.005):
            return None
        count = len(items)
        if count == 2:
            return "7" if w >= 3.4 else None
        if count == 3:
            return "1" if w < 1.6 else "4" if w >= 3.4 else None
        if count == 13:
            return "2"
        if count == 14:
            return "3"
        if count == 16:
            return "5" if px >= 0.7 else "0" if px <= 0.55 else None
        if count == 22:
            return "9" if px >= 0.97 and py > 0.26 else "6" if px < 0.97 and py < 0.26 else None
        if count == 28:
            return "8"
    except (TypeError, ValueError, OverflowError, IndexError, AttributeError):
        return None
    return None


def _original_numeric_glyph_receipts(
    drawings: list[dict[str, Any]],
) -> tuple[tuple[int, ...], ...] | None:
    """Require ALL seven row values from ordered, independent native vectors.

    Only source-numeric outlines are authenticated here, not their physical
    wall ownership, gross/net meaning, or printed category label glyphs.
    """
    results: list[tuple[int, ...]] = []
    for (_, _, numeric, _), (y0, y1) in zip(
        PRINTED_ORIGINAL_ROWS, ORIGINAL_ROW_Y_BOUNDS
    ):
        located = []
        for index, record in enumerate(drawings):
            rect = record.get("rect")
            if rect is None:
                continue
            try:
                if (
                    ORIGINAL_NUMERIC_COLUMNS[0] < rect.x0 < rect.x1 < ORIGINAL_NUMERIC_COLUMNS[1]
                    and y0 + 0.35 < rect.y0 < rect.y1 < y1 - 0.35
                ):
                    located.append((index, rect.x0, record))
            except (TypeError, ValueError, AttributeError):
                return None
        located.sort(key=lambda record: (record[1], record[0]))
        decoded = "".join(_numeric_vector_digit(record) or "?" for _, _, record in located)
        if decoded != str(numeric):
            return None
        ids = tuple(index for index, _, _ in located)
        if len(set(ids)) != len(ids):
            return None
        results.append(ids)
    if len(results) != len(PRINTED_ORIGINAL_ROWS):
        return None
    all_ids = tuple(index for ids in results for index in ids)
    if len(all_ids) != len(set(all_ids)):
        return None
    return tuple(results)


def inspect_original_q5446_printed_area_schedule(pdf_path: str | Path) -> Q5446SourceAreaScheduleShadow:
    """Original SHA and native ruled table geometry; no OCR, no FIRM issue."""
    source = Path(pdf_path)
    try:
        payload = source.read_bytes()
    except OSError:
        return _abstain("source_pdf_unavailable")
    source_sha = hashlib.sha256(payload).hexdigest()
    if len(payload) != SOURCE_BYTE_COUNT or source_sha != SOURCE_SHA256:
        return _abstain("original_source_sha_or_size_mismatch", source_sha)

    try:
        import fitz
        with fitz.open(stream=payload, filetype="pdf") as document:
            if len(document) != SOURCE_PAGE_COUNT:
                return _abstain("original_document_page_count_mismatch", source_sha)
            page = document[SOURCE_PAGE_INDEX]
            if page.rotation != 0 or not (
                abs(page.rect.width - 1190.52) < GEOMETRY_EPSILON_PT
                and abs(page.rect.height - 841.92) < GEOMETRY_EPSILON_PT
            ):
                return _abstain("original_source_page_frame_mismatch", source_sha)
            drawings = page.get_drawings()
            if not _table_witnesses_valid(drawings):
                return _abstain("original_area_schedule_vector_table_witness_missing", source_sha)
            original_numeric_source_ids = _original_numeric_glyph_receipts(drawings)
            if original_numeric_source_ids is None:
                return _abstain("original_area_schedule_numeric_vector_glyphs_unverified", source_sha)
            original_label_source_ids = _original_label_stroke_receipts(drawings)
            if original_label_source_ids is None:
                return _abstain("original_area_schedule_label_vector_ink_missing", source_sha)
    except Exception:
        return _abstain("original_area_schedule_native_pdf_unavailable", source_sha)

    rows = tuple(
        OriginalAreaScheduleCandidate(
            original_row_id=f"q5446_source_p1_area_schedule_row_{i + 1}_{key}",
            printed_label=label, printed_area_m2=value, is_rollup=rollup,
            original_page_index=SOURCE_PAGE_INDEX,
            table_row_number=i + 1,
            original_source_sha256=source_sha,
            glyph_correspondence_authenticated=True,
            original_numeric_vector_path_ids=original_numeric_source_ids[i],
            original_label_vector_path_ids=original_label_source_ids[i],
            label_stroke_presence_verified=True,
        )
        for i, (key, label, value, rollup) in enumerate(PRINTED_ORIGINAL_ROWS)
    )
    value_by_key = {key: val for key, _, val, _ in PRINTED_ORIGINAL_ROWS}
    floor_delta = value_by_key["subtotal"] - (
        value_by_key["ground_floor"] + value_by_key["first_floor"]
    )
    total_delta = value_by_key["total"] - sum(
        (value_by_key[k] for k in ("subtotal", "porch", "garage", "alfresco")),
        Decimal("0.00"),
    )
    return Q5446SourceAreaScheduleShadow(
        status="CANDIDATE",
        reason_codes=(
            "original_source_vector_table_ruled_geometry_verified",
            "original_area_numeric_vector_glyphs_authenticated",
            "source_category_label_original_strokes_verified_not_letters",
            "area_category_label_glyph_semantics_unverified",
            "physical_floor_owner_and_gross_net_semantics_unresolved",
            "rollups_not_independent_physical_quantities",
        ),
        rows=rows, actual_source_sha256=source_sha,
        printed_floor_subtotal_delta_m2=floor_delta,
        printed_total_rollup_delta_m2=total_delta,
    )
