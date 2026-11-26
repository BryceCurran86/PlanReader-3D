"""Generic same-page figured-dimension scale corroboration & open-plan boundary shadow.

Shadow-only, default-off source-evidence module. Corroborates isotropic `mm/pt`
calibration for a floor-plan page from any verified orthogonal figured-dimension
witnesses on that exact same page — allowing rooms without their own centered
internal `W x D` text to inherit the page's independently corroborated isotropic
scale without unverified cross-page scale transfer. Also extracts generic
structural wall boundary candidates surrounding open-plan room regions.

Never mutates live issuers or grants commercial publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Sequence

SHADOW_SCHEMA_VERSION = "1.0.0"
DEFAULT_MAX_REL_SCALE_TOLERANCE = 0.01
SOURCE_PRIMITIVE_CAP = 20_000


@dataclass(frozen=True)
class OrthogonalFiguredSpanWitness:
    """One source-owned figured-dimension span witness on a specific PDF page."""

    witness_id: str
    source_sha256: str
    page_number: int
    axis: str  # "x" (horizontal) or "y" (vertical)
    figured_mm: float
    span_pdf_pts: float
    source_path_ids: tuple[int, ...]
    bbox_pdf_pts: tuple[float, float, float, float]


@dataclass(frozen=True)
class SamePageFiguredScaleReport:
    """Immutable same-page isotropic scale corroboration receipt (shadow-only)."""

    status: str  # "CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW" | "ABSTAINED"
    source_sha256: str
    page_number: int
    mm_per_pt_x: float | None
    mm_per_pt_y: float | None
    isotropy_error: float | None
    max_intra_axis_spread: float | None
    horizontal_witness_ids: tuple[str, ...]
    vertical_witness_ids: tuple[str, ...]
    supporting_source_path_ids: tuple[int, ...]
    target_room_bbox_pdf_pts: tuple[float, float, float, float] | None
    target_page_rect_matches_calibration: bool
    receipt_sha256: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("SamePageFiguredScaleReport cannot authorize commercial projection")
        if self.shadow_only is not True:
            raise ValueError("SamePageFiguredScaleReport must remain shadow_only=True")


@dataclass(frozen=True)
class ShadowRoomMetricEstimate:
    """Shadow-only metric measurement derived from a corroborated same-page scale."""

    status: str  # "SHADOW_METRIC_COMPUTED" | "ABSTAINED"
    source_sha256: str
    page_number: int
    width_m: float | None
    depth_m: float | None
    area_m2: float | None
    scale_receipt_sha256: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("ShadowRoomMetricEstimate cannot authorize commercial projection")
        if self.shadow_only is not True:
            raise ValueError("ShadowRoomMetricEstimate must remain shadow_only=True")


@dataclass(frozen=True)
class OpenPlanWallBoundaryCandidate:
    """Generic structural stroke boundary candidate for open-plan room composition."""

    path_id: int
    orientation: str  # "horizontal" | "vertical"
    stroke_width_pts: float
    length_pts: float
    bbox_pdf_pts: tuple[float, float, float, float]


@dataclass(frozen=True)
class OpenPlanBoundaryExtractionReport:
    """Shadow-only summary of structural wall segments around an open-plan seed."""

    status: str  # "BOUNDARY_CANDIDATES_COLLECTED_SHADOW" | "ABSTAINED"
    source_sha256: str
    page_number: int
    seed_point_pdf_pts: tuple[float, float]
    search_bbox_pdf_pts: tuple[float, float, float, float]
    horizontal_candidates: tuple[OpenPlanWallBoundaryCandidate, ...]
    vertical_candidates: tuple[OpenPlanWallBoundaryCandidate, ...]
    total_drawings_inspected: int
    receipt_sha256: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("OpenPlanBoundaryExtractionReport cannot authorize commercial projection")
        if self.shadow_only is not True:
            raise ValueError("OpenPlanBoundaryExtractionReport must remain shadow_only=True")


def _finite_bbox(bbox: Sequence[object] | None) -> tuple[float, float, float, float] | None:
    if bbox is None or len(bbox) != 4:
        return None
    try:
        vals = tuple(float(v) for v in bbox)
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(v) for v in vals) or vals[2] <= vals[0] or vals[3] <= vals[1]:
        return None
    return vals  # type: ignore[return-value]


def _inside_rect(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
    tol: float = 0.5,
) -> bool:
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def _abstain_scale(
    *,
    source_sha256: str,
    page_number: int,
    reasons: tuple[str, ...],
    target_room_bbox_pdf_pts: tuple[float, float, float, float] | None = None,
    page_rect_match: bool = False,
) -> SamePageFiguredScaleReport:
    digest = hashlib.sha256(
        json.dumps(
            {
                "sha": source_sha256,
                "page": page_number,
                "reasons": list(reasons),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return SamePageFiguredScaleReport(
        status="ABSTAINED",
        source_sha256=source_sha256,
        page_number=page_number,
        mm_per_pt_x=None,
        mm_per_pt_y=None,
        isotropy_error=None,
        max_intra_axis_spread=None,
        horizontal_witness_ids=(),
        vertical_witness_ids=(),
        supporting_source_path_ids=(),
        target_room_bbox_pdf_pts=target_room_bbox_pdf_pts,
        target_page_rect_matches_calibration=page_rect_match,
        receipt_sha256=digest,
        reason_codes=reasons,
    )


def corroborate_same_page_figured_scale_shadow(
    *,
    source_sha256: str,
    page_number: int,
    page_rect_pts: tuple[float, float, float, float],
    witnesses: Sequence[OrthogonalFiguredSpanWitness],
    target_room_bbox_pdf_pts: tuple[float, float, float, float] | None = None,
    reference_mm_per_pt_x: float | None = None,
    reference_mm_per_pt_y: float | None = None,
    reference_page_rect_pts: tuple[float, float, float, float] | None = None,
    max_rel_tolerance: float = DEFAULT_MAX_REL_SCALE_TOLERANCE,
) -> SamePageFiguredScaleReport:
    """Corroborate isotropic same-page mm/pt scale from orthogonal figured spans."""
    clean_sha = str(source_sha256 or "").strip()
    page_box = _finite_bbox(page_rect_pts)
    if (
        len(clean_sha) < 16
        or type(page_number) is not int
        or page_number < 1
        or page_box is None
        or not math.isfinite(float(max_rel_tolerance))
        or float(max_rel_tolerance) <= 0.0
    ):
        return _abstain_scale(
            source_sha256=clean_sha,
            page_number=page_number if isinstance(page_number, int) else 0,
            reasons=("invalid_scale_input_or_provenance",),
        )

    page_rect_match = True
    if reference_page_rect_pts is not None:
        ref_box = _finite_bbox(reference_page_rect_pts)
        if ref_box is None or any(abs(a - b) > 0.5 for a, b in zip(page_box, ref_box)):
            return _abstain_scale(
                source_sha256=clean_sha,
                page_number=page_number,
                reasons=("page_rect_mismatch_against_reference",),
                page_rect_match=False,
            )

    clean_room_box: tuple[float, float, float, float] | None = None
    if target_room_bbox_pdf_pts is not None:
        clean_room_box = _finite_bbox(target_room_bbox_pdf_pts)
        if clean_room_box is None or not _inside_rect(clean_room_box, page_box):
            return _abstain_scale(
                source_sha256=clean_sha,
                page_number=page_number,
                reasons=("target_room_bbox_outside_page_rect",),
                target_room_bbox_pdf_pts=clean_room_box,
                page_rect_match=page_rect_match,
            )

    hx: list[tuple[float, OrthogonalFiguredSpanWitness]] = []
    vy: list[tuple[float, OrthogonalFiguredSpanWitness]] = []
    for w in witnesses:
        if w.source_sha256 != clean_sha:
            return _abstain_scale(
                source_sha256=clean_sha,
                page_number=page_number,
                reasons=("cross_revision_witness_sha_mismatch",),
                target_room_bbox_pdf_pts=clean_room_box,
                page_rect_match=page_rect_match,
            )
        if w.page_number != page_number:
            # Never silently transfer witnesses from another page.
            continue
        wbox = _finite_bbox(w.bbox_pdf_pts)
        if (
            wbox is None
            or not _inside_rect(wbox, page_box)
            or not math.isfinite(float(w.figured_mm))
            or not math.isfinite(float(w.span_pdf_pts))
            or float(w.figured_mm) <= 0.0
            or float(w.span_pdf_pts) <= 0.0
            or not w.source_path_ids
            or any(type(pid) is not int or pid < 0 for pid in w.source_path_ids)
        ):
            continue
        ratio = float(w.figured_mm) / float(w.span_pdf_pts)
        if not math.isfinite(ratio) or ratio <= 0.0:
            continue
        axis = str(w.axis or "").strip().lower()
        if axis == "x":
            hx.append((ratio, w))
        elif axis == "y":
            vy.append((ratio, w))

    if not hx or not vy:
        return _abstain_scale(
            source_sha256=clean_sha,
            page_number=page_number,
            reasons=("missing_same_page_orthogonal_figured_witnesses",),
            target_room_bbox_pdf_pts=clean_room_box,
            page_rect_match=page_rect_match,
        )

    def _axis_summary(items: list[tuple[float, OrthogonalFiguredSpanWitness]]) -> tuple[float, float]:
        vals = sorted(r for r, _ in items)
        median = vals[len(vals) // 2] if len(vals) % 2 == 1 else 0.5 * (vals[len(vals) // 2 - 1] + vals[len(vals) // 2])
        spread = max(abs(r / median - 1.0) for r in vals)
        return median, spread

    mx, spread_x = _axis_summary(hx)
    my, spread_y = _axis_summary(vy)
    max_spread = max(spread_x, spread_y)
    if max_spread > max_rel_tolerance:
        return _abstain_scale(
            source_sha256=clean_sha,
            page_number=page_number,
            reasons=("same_page_scale_axis_conflict",),
            target_room_bbox_pdf_pts=clean_room_box,
            page_rect_match=page_rect_match,
        )

    isotropy_err = abs(mx / my - 1.0)
    if isotropy_err > max_rel_tolerance:
        return _abstain_scale(
            source_sha256=clean_sha,
            page_number=page_number,
            reasons=("same_page_scale_anisotropy_conflict",),
            target_room_bbox_pdf_pts=clean_room_box,
            page_rect_match=page_rect_match,
        )

    if reference_mm_per_pt_x is not None or reference_mm_per_pt_y is not None:
        if (
            reference_mm_per_pt_x is None
            or reference_mm_per_pt_y is None
            or not math.isfinite(float(reference_mm_per_pt_x))
            or not math.isfinite(float(reference_mm_per_pt_y))
            or float(reference_mm_per_pt_x) <= 0.0
            or float(reference_mm_per_pt_y) <= 0.0
            or abs(mx / float(reference_mm_per_pt_x) - 1.0) > max_rel_tolerance
            or abs(my / float(reference_mm_per_pt_y) - 1.0) > max_rel_tolerance
        ):
            return _abstain_scale(
                source_sha256=clean_sha,
                page_number=page_number,
                reasons=("reference_calibration_mismatch",),
                target_room_bbox_pdf_pts=clean_room_box,
                page_rect_match=page_rect_match,
            )

    h_ids = tuple(sorted(w.witness_id for _, w in hx))
    v_ids = tuple(sorted(w.witness_id for _, w in vy))
    all_pids = tuple(sorted({pid for _, w in (*hx, *vy) for pid in w.source_path_ids}))

    payload = {
        "source_sha256": clean_sha,
        "page_number": page_number,
        "mm_per_pt_x": round(mx, 6),
        "mm_per_pt_y": round(my, 6),
        "h_ids": list(h_ids),
        "v_ids": list(v_ids),
        "pids": list(all_pids),
    }
    receipt_sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    return SamePageFiguredScaleReport(
        status="CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW",
        source_sha256=clean_sha,
        page_number=page_number,
        mm_per_pt_x=round(mx, 6),
        mm_per_pt_y=round(my, 6),
        isotropy_error=round(isotropy_err, 6),
        max_intra_axis_spread=round(max_spread, 6),
        horizontal_witness_ids=h_ids,
        vertical_witness_ids=v_ids,
        supporting_source_path_ids=all_pids,
        target_room_bbox_pdf_pts=clean_room_box,
        target_page_rect_matches_calibration=page_rect_match,
        receipt_sha256=receipt_sha,
        reason_codes=("same_page_orthogonal_figured_scale_corroborated_shadow",),
    )


def measure_room_face_from_same_page_scale_shadow(
    *,
    scale_report: SamePageFiguredScaleReport,
    finished_width_pts: float,
    finished_depth_pts: float,
    max_plausible_room_area_m2: float = 250.0,
) -> ShadowRoomMetricEstimate:
    """Compute a shadow-only metric room-face estimate from a corroborated same-page scale."""
    if (
        scale_report.status != "CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW"
        or scale_report.mm_per_pt_x is None
        or scale_report.mm_per_pt_y is None
        or not math.isfinite(float(finished_width_pts))
        or not math.isfinite(float(finished_depth_pts))
        or float(finished_width_pts) <= 0.0
        or float(finished_depth_pts) <= 0.0
    ):
        return ShadowRoomMetricEstimate(
            status="ABSTAINED",
            source_sha256=scale_report.source_sha256,
            page_number=scale_report.page_number,
            width_m=None,
            depth_m=None,
            area_m2=None,
            scale_receipt_sha256=scale_report.receipt_sha256,
            reason_codes=("same_page_scale_or_dimensions_unavailable",),
        )

    width_m = round(float(finished_width_pts) * scale_report.mm_per_pt_x / 1000.0, 6)
    depth_m = round(float(finished_depth_pts) * scale_report.mm_per_pt_y / 1000.0, 6)
    area_m2 = round(width_m * depth_m, 6)
    if (
        not all(math.isfinite(v) and v > 0.0 for v in (width_m, depth_m, area_m2))
        or area_m2 > float(max_plausible_room_area_m2)
    ):
        return ShadowRoomMetricEstimate(
            status="ABSTAINED",
            source_sha256=scale_report.source_sha256,
            page_number=scale_report.page_number,
            width_m=None,
            depth_m=None,
            area_m2=None,
            scale_receipt_sha256=scale_report.receipt_sha256,
            reason_codes=("shadow_room_metric_out_of_bounds",),
        )

    return ShadowRoomMetricEstimate(
        status="SHADOW_METRIC_COMPUTED",
        source_sha256=scale_report.source_sha256,
        page_number=scale_report.page_number,
        width_m=width_m,
        depth_m=depth_m,
        area_m2=area_m2,
        scale_receipt_sha256=scale_report.receipt_sha256,
        reason_codes=("shadow_metric_computed_from_corroborated_same_page_scale",),
    )


def _is_dark_stroke(color: Any) -> bool:
    if not color or not isinstance(color, (tuple, list)):
        return False
    try:
        vals = [float(c) for c in color]
    except (TypeError, ValueError):
        return False
    return bool(vals) and all(0.0 <= c <= 0.35 for c in vals)


def extract_open_plan_multi_wall_boundary_candidates_shadow(
    *,
    drawings: Sequence[dict[str, Any]],
    source_sha256: str,
    page_number: int,
    seed_point_pdf_pts: tuple[float, float],
    search_radius_pts: float = 160.0,
    min_wall_stroke_width_pts: float = 0.65,
    max_wall_stroke_width_pts: float = 2.60,
    min_segment_length_pts: float = 18.0,
) -> OpenPlanBoundaryExtractionReport:
    """Extract generic orthogonal structural wall candidates around an open-plan seed."""
    clean_sha = str(source_sha256 or "").strip()
    sx, sy = float(seed_point_pdf_pts[0]), float(seed_point_pdf_pts[1])
    rad = float(search_radius_pts)
    search_box = (sx - rad, sy - rad, sx + rad, sy + rad)

    def _abstain(reasons: tuple[str, ...]) -> OpenPlanBoundaryExtractionReport:
        digest = hashlib.sha256(
            json.dumps({"sha": clean_sha, "page": page_number, "reasons": list(reasons)}, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return OpenPlanBoundaryExtractionReport(
            status="ABSTAINED",
            source_sha256=clean_sha,
            page_number=page_number if isinstance(page_number, int) else 0,
            seed_point_pdf_pts=(sx, sy),
            search_bbox_pdf_pts=search_box,
            horizontal_candidates=(),
            vertical_candidates=(),
            total_drawings_inspected=len(drawings),
            receipt_sha256=digest,
            reason_codes=reasons,
        )

    if (
        len(clean_sha) < 16
        or type(page_number) is not int
        or page_number < 1
        or not (math.isfinite(sx) and math.isfinite(sy) and math.isfinite(rad) and rad > 0.0)
    ):
        return _abstain(("invalid_open_plan_seed_or_provenance",))
    if len(drawings) > SOURCE_PRIMITIVE_CAP:
        return _abstain(("source_primitive_cap_exceeded",))

    horiz: list[OpenPlanWallBoundaryCandidate] = []
    vert: list[OpenPlanWallBoundaryCandidate] = []
    for pid, rec in enumerate(drawings):
        width = rec.get("width")
        if width is None:
            continue
        try:
            sw = float(width)
        except (TypeError, ValueError):
            continue
        if not (min_wall_stroke_width_pts <= sw <= max_wall_stroke_width_pts):
            continue
        if not _is_dark_stroke(rec.get("color")):
            continue
        rect = rec.get("rect")
        if rect is None:
            continue
        try:
            bx = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
        except AttributeError:
            parsed = _finite_bbox(rect)
            if parsed is None:
                continue
            bx = parsed
        if not all(math.isfinite(v) for v in bx):
            continue
        # Must intersect search window
        if bx[2] < search_box[0] or bx[0] > search_box[2] or bx[3] < search_box[1] or bx[1] > search_box[3]:
            continue
        w_pts = bx[2] - bx[0]
        h_pts = bx[3] - bx[1]
        if w_pts >= min_segment_length_pts and h_pts <= 3.5:
            horiz.append(
                OpenPlanWallBoundaryCandidate(
                    path_id=pid,
                    orientation="horizontal",
                    stroke_width_pts=round(sw, 3),
                    length_pts=round(w_pts, 3),
                    bbox_pdf_pts=tuple(round(v, 3) for v in bx),  # type: ignore[arg-type]
                )
            )
        elif h_pts >= min_segment_length_pts and w_pts <= 3.5:
            vert.append(
                OpenPlanWallBoundaryCandidate(
                    path_id=pid,
                    orientation="vertical",
                    stroke_width_pts=round(sw, 3),
                    length_pts=round(h_pts, 3),
                    bbox_pdf_pts=tuple(round(v, 3) for v in bx),  # type: ignore[arg-type]
                )
            )

    if not horiz or not vert:
        return _abstain(("insufficient_orthogonal_open_plan_wall_candidates",))

    payload = {
        "sha": clean_sha,
        "page": page_number,
        "h_pids": [c.path_id for c in horiz],
        "v_pids": [c.path_id for c in vert],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return OpenPlanBoundaryExtractionReport(
        status="BOUNDARY_CANDIDATES_COLLECTED_SHADOW",
        source_sha256=clean_sha,
        page_number=page_number,
        seed_point_pdf_pts=(sx, sy),
        search_bbox_pdf_pts=search_box,
        horizontal_candidates=tuple(horiz),
        vertical_candidates=tuple(vert),
        total_drawings_inspected=len(drawings),
        receipt_sha256=digest,
        reason_codes=("open_plan_structural_wall_candidates_collected_shadow",),
    )
