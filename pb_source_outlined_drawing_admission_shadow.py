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
import math
import re
from typing import Sequence

SHADOW_SCHEMA_VERSION = "1.1.0"
SOURCE_PRIMITIVE_CAP = 20_000
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

# Longest-first alternatives with strict numeric boundaries so 1:100 never matches 1:10
# and 1:1000 / 21:100 never match at all.
_SCALE_TOKEN_RE = re.compile(
    r"(?<![\d:])1\s*:\s*(?:500|250|200|150|100|75|50|25|20|10)(?!\d)"
)

# Specific architectural sheet roles MUST precede generic roles; bare "PLAN" is never
# sufficient to classify a sheet as floor_plan (prevents SITE PLAN / ROOF PLAN misrouting).
_PRIMARY_ROLE_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "site_or_cover",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"SITE\s+PLAN",
                r"SITE\s+LAYOUT",
                r"COVER\s+SHEET",
                r"LOCALITY\s+PLAN",
                r"DRAWING\s+LIST",
                r"SHEET\s+INDEX",
            )
        ),
    ),
    (
        "roof_plan",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (r"ROOF\s+PLAN", r"ROOF\s+FRAMING\s+PLAN", r"ROOFING\s+PLAN")
        ),
    ),
    (
        "rcp",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"REFLECTED\s+CEILING\s+PLAN",
                r"REFLECTED\s+CEILING",
                r"CEILING\s+PLAN",
                r"RCP",
            )
        ),
    ),
    (
        "schedule",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"WINDOW\s+SCHEDULE",
                r"DOOR\s+SCHEDULE",
                r"FINISHES\s+SCHEDULE",
                r"ROOM\s+SCHEDULE",
                r"SCHEDULE",
            )
        ),
    ),
    (
        "section",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"CROSS\s+SECTION",
                r"LONGITUDINAL\s+SECTION",
                r"BUILDING\s+SECTION",
                r"SECTION",
            )
        ),
    ),
    (
        "elevation",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"NORTH\s+ELEVATION",
                r"SOUTH\s+ELEVATION",
                r"EAST\s+ELEVATION",
                r"WEST\s+ELEVATION",
                r"FRONT\s+ELEVATION",
                r"REAR\s+ELEVATION",
                r"SIDE\s+ELEVATION",
                r"ELEVATION",
            )
        ),
    ),
    (
        "floor_plan",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"GROUND\s+FLOOR\s+PLAN",
                r"FIRST\s+FLOOR\s+PLAN",
                r"SECOND\s+FLOOR\s+PLAN",
                r"UPPER\s+FLOOR\s+PLAN",
                r"LOWER\s+FLOOR\s+PLAN",
                r"BASEMENT\s+FLOOR\s+PLAN",
                r"FLOOR\s+PLAN",
                r"GROUND\s+FLOOR",
                r"FIRST\s+FLOOR",
                r"UPPER\s+FLOOR",
                r"LOWER\s+FLOOR",
            )
        ),
    ),
)

_FALLBACK_ROLE_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "detail",
        tuple(
            re.compile(rf"\b{p}\b")
            for p in (
                r"CONSTRUCTION\s+DETAIL",
                r"TYPICAL\s+DETAIL",
                r"SETOUT",
                r"SET\s+OUT",
                r"DETAIL",
            )
        ),
    ),
)


@dataclass(frozen=True)
class SheetRoleAssessment:
    """Generic per-sheet admission assessment for vector-outlined drawing sets."""

    page_index: int
    page_width_pts: float
    page_height_pts: float
    page_rotation_deg: int
    total_native_words: int
    border_native_words: int
    body_native_words: int
    vector_drawing_count: int
    raster_image_count: int
    outlined_text_suspected: bool
    detected_role: str
    matched_roles: tuple[str, ...]
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


def _classify_role_from_text(upper_text: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    matched_primary: list[str] = []
    hits: list[str] = []
    for role, patterns in _PRIMARY_ROLE_PATTERNS:
        role_hits = sorted({m.group(0) for pat in patterns for m in pat.finditer(upper_text)})
        if role_hits:
            matched_primary.append(role)
            hits.extend(role_hits)
    if len(matched_primary) == 1:
        return matched_primary[0], (matched_primary[0],), tuple(sorted(set(hits)))
    if len(matched_primary) > 1:
        return "mixed_role", tuple(matched_primary), tuple(sorted(set(hits)))
    for role, patterns in _FALLBACK_ROLE_PATTERNS:
        role_hits = sorted({m.group(0) for pat in patterns for m in pat.finditer(upper_text)})
        if role_hits:
            return role, (role,), tuple(role_hits)
    return "unknown", (), ()


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


def _valid_fraction(val: object) -> bool:
    if type(val) is bool or not isinstance(val, (int, float)):
        return False
    f = float(val)
    return math.isfinite(f) and 0.0 < f < 1.0


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
    max_drawings_per_page: int = SOURCE_PRIMITIVE_CAP,
) -> OutlinedDrawingAdmissionReport:
    """Evaluate a PDF drawing set for generic vector-outlined text admission."""
    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
        return _abstain_admission(source_sha256="", reasons=("empty_or_invalid_pdf_bytes",))

    if (
        type(finish_specification_present) is not bool
        or not _valid_fraction(right_border_fraction)
        or not _valid_fraction(bottom_border_fraction)
        or type(max_body_words_for_outlined) is not int
        or max_body_words_for_outlined < 0
        or type(min_vector_drawings_for_outlined) is not int
        or min_vector_drawings_for_outlined < 1
        or type(max_pages) is not int
        or max_pages < 1
        or type(max_drawings_per_page) is not int
        or max_drawings_per_page < 1
        or max_drawings_per_page > SOURCE_PRIMITIVE_CAP
    ):
        return _abstain_admission(source_sha256="", reasons=("invalid_admission_parameters",))

    actual_sha = hashlib.sha256(bytes(pdf_bytes)).hexdigest()
    if expected_source_sha256 is not None:
        if type(expected_source_sha256) is not str:
            return _abstain_admission(source_sha256=actual_sha, reasons=("invalid_expected_source_sha256",))
        clean_expected = expected_source_sha256.strip()
        if not _SHA256_HEX_RE.fullmatch(clean_expected):
            return _abstain_admission(source_sha256=actual_sha, reasons=("invalid_expected_source_sha256",))
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
            rot = int(getattr(page, "rotation", 0) or 0) % 360
            if not (math.isfinite(pw) and math.isfinite(ph) and pw > 0.0 and ph > 0.0):
                return _abstain_admission(
                    source_sha256=actual_sha,
                    page_count=page_count,
                    reasons=("invalid_page_dimensions",),
                )
            drawings = page.get_drawings() or ()
            if len(drawings) > max_drawings_per_page:
                return _abstain_admission(
                    source_sha256=actual_sha,
                    page_count=page_count,
                    reasons=("source_primitive_cap_exceeded",),
                )
            words = page.get_text("words") or ()
            images = page.get_images() or ()

            # Inspect title-block border strips in displayed (post-rotation) coordinates.
            # On rotated sheets, title blocks may sit along right/bottom OR left/top strips;
            # keep primary right/bottom margins plus narrow opposite-edge strip when rotated.
            body_words = 0
            border_tokens: list[str] = []
            for w in words:
                wx0, wy0, wx2, wy2 = float(w[0]), float(w[1]), float(w[2]), float(w[3])
                in_primary_border = wx2 >= pw * right_border_fraction or wy2 >= ph * bottom_border_fraction
                in_rotated_border = rot != 0 and (
                    wx0 <= pw * (1.0 - right_border_fraction)
                    or wy0 <= ph * (1.0 - bottom_border_fraction)
                )
                if in_primary_border or in_rotated_border:
                    border_tokens.append(str(w[4]))
                else:
                    body_words += 1

            total_words = len(words)
            border_words = total_words - body_words
            suspected = (
                body_words <= max_body_words_for_outlined
                and len(drawings) >= min_vector_drawings_for_outlined
                and len(images) == 0
            )
            border_upper = " ".join(border_tokens).upper()
            role, matched_roles, role_hits = _classify_role_from_text(border_upper)
            scale_tokens = tuple(sorted({m.group(0).replace(" ", "") for m in _SCALE_TOKEN_RE.finditer(border_upper)}))
            role_counter[role] = role_counter.get(role, 0) + 1

            assessments.append(
                SheetRoleAssessment(
                    page_index=idx,
                    page_width_pts=round(pw, 2),
                    page_height_pts=round(ph, 2),
                    page_rotation_deg=rot,
                    total_native_words=total_words,
                    border_native_words=border_words,
                    body_native_words=body_words,
                    vector_drawing_count=len(drawings),
                    raster_image_count=len(images),
                    outlined_text_suspected=suspected,
                    detected_role=role,
                    matched_roles=matched_roles,
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
