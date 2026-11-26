"""Generic vector-outlined architectural drawing admission preflight shadow.

Shadow-only, default-off intake/admission module for architectural PDF sets
whose drawing bodies store text/dimensions as vector path outlines rather than
embedded font streams. Classifies sheets by generic architectural role from
native title-block/border metadata, verifies SHA-256 integrity, enforces
bounded vector-primitive safety, and keeps missing finish specifications
strictly ABSTAINED (`material_specification_missing`).

Never invents finish specifications or grants commercial publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Sequence

SHADOW_SCHEMA_VERSION = "1.0.0"

_SCALE_TOKEN_RE = re.compile(r"\b1\s*:\s*(?:10|20|25|50|75|100|150|200|250|500)\b")

_ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rcp", ("REFLECTED CEILING", "CEILING PLAN", "RCP")),
    ("schedule", ("SCHEDULE", "WINDOW SCHEDULE", "DOOR SCHEDULE", "FINISHES")),
    ("section", ("SECTION", "CROSS SECTION", "LONGITUDINAL SECTION")),
    ("elevation", ("ELEVATION", "NORTH ELEVATION", "SOUTH ELEVATION", "EAST ELEVATION", "WEST ELEVATION")),
    ("floor_plan", ("FLOOR PLAN", "GROUND FLOOR", "FIRST FLOOR", "UPPER FLOOR", "LOWER FLOOR", "PLAN")),
    ("site_or_cover", ("SITE PLAN", "COVER SHEET", "LOCALITY", "DRAWING LIST", "INDEX")),
    ("detail", ("DETAIL", "TYPICAL", "SETOUT", "SET OUT")),
)


@dataclass(frozen=True)
class SheetRoleAssessment:
    """Generic per-sheet admission assessment for vector-outlined drawing sets."""

    page_index: int
    page_width_pts: float
    page_height_pts: float
    total_native_words: int
    border_native_words: int
    body_native_words: int
    vector_drawing_count: int
    raster_image_count: int
    outlined_text_suspected: bool
    detected_role: str
    role_evidence_tokens: tuple[str, ...]
    native_scale_tokens: tuple[str, ...]


@dataclass(frozen=True)
class OutlinedDrawingAdmissionReport:
    """Immutable admission preflight receipt for vector-outlined PDF drawing sets."""

    status: str  # "ADMITTED_FOR_OUTLINED_TEXT_OCR_SHADOW" | "NATIVE_TEXT_DRAWING_SET" | "ABSTAINED"
    source_sha256: str
    page_count: int
    outlined_page_count: int
    role_counts: tuple[tuple[str, int], ...]
    sheet_assessments: tuple[SheetRoleAssessment, ...]
    geometry_admission_ready: bool
    finish_authority_status: str  # "ABSTAINED" | "REVIEW_ONLY_SPEC_PRESENT"
    finish_authority_reason: str
    receipt_sha256: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("OutlinedDrawingAdmissionReport cannot authorize commercial projection")
        if self.shadow_only is not True:
            raise ValueError("OutlinedDrawingAdmissionReport must remain shadow_only=True")


def _classify_role_from_text(upper_text: str) -> tuple[str, tuple[str, ...]]:
    for role, phrases in _ROLE_PATTERNS:
        hits = tuple(sorted({p for p in phrases if p in upper_text}))
        if hits:
            return role, hits
    return "unknown", ()


def _abstain_admission(
    *,
    source_sha256: str,
    reasons: tuple[str, ...],
    page_count: int = 0,
) -> OutlinedDrawingAdmissionReport:
    digest = hashlib.sha256(
        json.dumps({"sha": source_sha256, "pages": page_count, "reasons": list(reasons)}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return OutlinedDrawingAdmissionReport(
        status="ABSTAINED",
        source_sha256=source_sha256,
        page_count=page_count,
        outlined_page_count=0,
        role_counts=(),
        sheet_assessments=(),
        geometry_admission_ready=False,
        finish_authority_status="ABSTAINED",
        finish_authority_reason="material_specification_missing",
        receipt_sha256=digest,
        reason_codes=reasons,
    )


def evaluate_outlined_drawing_admission_shadow(
    pdf_bytes: bytes,
    *,
    expected_source_sha256: str | None = None,
    finish_specification_present: bool = False,
    right_border_fraction: float = 0.80,
    bottom_border_fraction: float = 0.85,
    max_body_words_for_outlined: int = 20,
    min_vector_drawings_for_outlined: int = 500,
    max_pages: int = 60,
) -> OutlinedDrawingAdmissionReport:
    """Evaluate a PDF drawing set for generic vector-outlined text admission."""
    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
        return _abstain_admission(source_sha256="", reasons=("empty_or_invalid_pdf_bytes",))

    actual_sha = hashlib.sha256(bytes(pdf_bytes)).hexdigest()
    if expected_source_sha256 is not None:
        clean_expected = str(expected_source_sha256).strip().lower()
        if actual_sha != clean_expected:
            return _abstain_admission(source_sha256=actual_sha, reasons=("source_sha256_mismatch",))

    import fitz

    try:
        doc = fitz.open(stream=bytes(pdf_bytes), filetype="pdf")
    except Exception:
        return _abstain_admission(source_sha256=actual_sha, reasons=("unreadable_pdf_stream",))

    try:
        page_count = len(doc)
        if page_count == 0 or page_count > max_pages:
            return _abstain_admission(
                source_sha256=actual_sha,
                page_count=page_count,
                reasons=("invalid_or_excessive_page_count",),
            )

        assessments: list[SheetRoleAssessment] = []
        role_counter: dict[str, int] = {}
        for idx in range(page_count):
            page = doc[idx]
            pw = float(page.rect.width)
            ph = float(page.rect.height)
            words = page.get_text("words") or ()
            drawings = page.get_drawings() or ()
            images = page.get_images() or ()

            body_words = 0
            border_tokens: list[str] = []
            for w in words:
                wx2, wy2 = float(w[2]), float(w[3])
                if wx2 < pw * right_border_fraction and wy2 < ph * bottom_border_fraction:
                    body_words += 1
                else:
                    border_tokens.append(str(w[4]))

            total_words = len(words)
            border_words = total_words - body_words
            suspected = (
                body_words <= max_body_words_for_outlined
                and len(drawings) >= min_vector_drawings_for_outlined
                and len(images) == 0
            )
            border_upper = " ".join(border_tokens).upper()
            role, role_hits = _classify_role_from_text(border_upper)
            scale_tokens = tuple(sorted({m.group(0).replace(" ", "") for m in _SCALE_TOKEN_RE.finditer(border_upper)}))
            role_counter[role] = role_counter.get(role, 0) + 1

            assessments.append(
                SheetRoleAssessment(
                    page_index=idx,
                    page_width_pts=round(pw, 2),
                    page_height_pts=round(ph, 2),
                    total_native_words=total_words,
                    border_native_words=border_words,
                    body_native_words=body_words,
                    vector_drawing_count=len(drawings),
                    raster_image_count=len(images),
                    outlined_text_suspected=suspected,
                    detected_role=role,
                    role_evidence_tokens=role_hits,
                    native_scale_tokens=scale_tokens,
                )
            )
    finally:
        doc.close()

    outlined_count = sum(1 for a in assessments if a.outlined_text_suspected)
    total_drawings = sum(a.vector_drawing_count for a in assessments)
    role_counts = tuple(sorted(role_counter.items()))

    fin_status = "REVIEW_ONLY_SPEC_PRESENT" if finish_specification_present else "ABSTAINED"
    fin_reason = (
        "finish_specification_present_pending_host_binding"
        if finish_specification_present
        else "material_specification_missing"
    )

    if total_drawings == 0:
        return _abstain_admission(
            source_sha256=actual_sha,
            page_count=page_count,
            reasons=("no_vector_drawings_present",),
        )

    if outlined_count > 0:
        has_plan = role_counter.get("floor_plan", 0) > 0
        status = "ADMITTED_FOR_OUTLINED_TEXT_OCR_SHADOW"
        reasons = ["vector_outlined_drawing_set_admitted_shadow"]
        if has_plan:
            reasons.append("floor_plan_role_detected")
        else:
            reasons.append("floor_plan_role_unclassified_from_border_text")
        if not finish_specification_present:
            reasons.append("material_specification_missing")
        geom_ready = True
    else:
        status = "NATIVE_TEXT_DRAWING_SET"
        reasons = ["embedded_native_text_present_outlined_ocr_not_required"]
        if not finish_specification_present:
            reasons.append("material_specification_missing")
        geom_ready = False

    payload = {
        "sha": actual_sha,
        "pages": page_count,
        "outlined": outlined_count,
        "roles": list(role_counts),
        "status": status,
        "fin_status": fin_status,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    return OutlinedDrawingAdmissionReport(
        status=status,
        source_sha256=actual_sha,
        page_count=page_count,
        outlined_page_count=outlined_count,
        role_counts=role_counts,
        sheet_assessments=tuple(assessments),
        geometry_admission_ready=geom_ready,
        finish_authority_status=fin_status,
        finish_authority_reason=fin_reason,
        receipt_sha256=digest,
        reason_codes=tuple(sorted(set(reasons))),
    )


def select_role_pages_for_outlined_ocr_shadow(
    report: OutlinedDrawingAdmissionReport,
    *,
    preferred_roles: Sequence[str] = ("floor_plan", "elevation", "section", "schedule"),
    max_pages_per_role: int = 1,
) -> tuple[int, ...]:
    """Deterministically pick representative outlined-text sheet indices by role."""
    if report.status != "ADMITTED_FOR_OUTLINED_TEXT_OCR_SHADOW" or max_pages_per_role < 1:
        return ()
    selected: list[int] = []
    counts: dict[str, int] = {}
    for role in preferred_roles:
        for a in report.sheet_assessments:
            if not a.outlined_text_suspected or a.detected_role != role:
                continue
            if counts.get(role, 0) >= max_pages_per_role:
                break
            selected.append(a.page_index)
            counts[role] = counts.get(role, 0) + 1
    return tuple(sorted(set(selected)))
