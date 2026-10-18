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
            if not _table_witnesses_valid(page.get_drawings()):
                return _abstain("original_area_schedule_vector_table_witness_missing", source_sha)
    except Exception:
        return _abstain("original_area_schedule_native_pdf_unavailable", source_sha)

    rows = tuple(
        OriginalAreaScheduleCandidate(
            original_row_id=f"q5446_source_p1_area_schedule_row_{i + 1}_{key}",
            printed_label=label, printed_area_m2=value, is_rollup=rollup,
            original_page_index=SOURCE_PAGE_INDEX,
            table_row_number=i + 1,
            original_source_sha256=source_sha,
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
            "original_area_numerals_vector_glyphs_unauthenticated",
            "physical_floor_owner_and_gross_net_semantics_unresolved",
            "rollups_not_independent_physical_quantities",
        ),
        rows=rows, actual_source_sha256=source_sha,
        printed_floor_subtotal_delta_m2=floor_delta,
        printed_total_rollup_delta_m2=total_delta,
    )
