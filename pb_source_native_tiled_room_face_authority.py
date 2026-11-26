"""Native PDF tile-faced room candidate, owned by physical ink and two raster reads.

This is a reusable ORIGINAL PlanReader source witness, not a parallel takeoff
engine, quantity issuer, estimate, or benchmark lookup.  The original PDF
drawings prove each boundary; OCR may NAME a bounded scope but cannot create it.
An ambiguous or unowned scope returns no source-owned room face.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import math
import re
from collections.abc import Sequence
from typing import Any

import fitz
from PIL import Image
from shapely.geometry import Point, Polygon

from pb_portable_raster_ocr_authority import RapidOCRBackend
from pb_source_coincident_fixture_boundary_support_shadow import (
    evaluate_coincident_fixture_boundary_support_shadow,
)
from pb_source_multi_wall_open_room_face_shadow import (
    MarkedOpeningOrFinishThresholdInput,
    MultiWallOpenRoomFaceResult,
    SourceWallSegmentInput,
    compose_multi_wall_open_room_face_shadow,
)
from pb_source_same_page_figured_scale_shadow import (
    DEFAULT_MAX_REL_SCALE_TOLERANCE,
    OrthogonalFiguredSpanWitness,
    SamePageFiguredScaleReport,
    ShadowRoomMetricEstimate,
    corroborate_same_page_figured_scale_shadow,
    measure_room_face_from_same_page_scale_shadow,
)

SOURCE_PRIMITIVE_CAP = 20_000
SOURCE_SNAP_PT = 2.5
# PDF-native coordinate float32 jitter is not a physical wall/junction snap.
# This tolerance is 25,000 times smaller than SOURCE_SNAP_PT.
SOURCE_PDF_FLOAT_EPS_PT = 0.0001


@dataclass(frozen=True)
class NativeTiledRoomFace:
    page_number: int
    source_boundary_path_id: int
    room_label: str
    source_bbox_pts: tuple[float, float, float, float]
    finished_width_pts: float
    finished_depth_pts: float
    wall_support_source_path_ids: tuple[int, ...]
    hatch_support_source_path_ids: tuple[int, ...]
    raster_ocr_render_dpis: tuple[int, ...]
    physical_source_verified: bool = True
    commercial_permission: bool = False


def _norm_room_label(word: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", "", str(word).upper()).strip()


def _segments(path: dict[str, Any]) -> tuple[tuple[float, float, float, float], ...]:
    result = []
    for item in path.get("items", ()):
        if not isinstance(item, (tuple, list)) or len(item) < 3 or item[0] != "l":
            return ()
        try:
            x1, y1, x2, y2 = (float(item[1].x), float(item[1].y),
                             float(item[2].x), float(item[2].y))
        except (ValueError, TypeError, AttributeError):
            return ()
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
            return ()
        if min(abs(x1 - x2), abs(y1 - y2)) > 0.1:
            return ()
        if math.hypot(x1 - x2, y1 - y2) < 0.1:
            return ()
        result.append((x1, y1, x2, y2))
    return tuple(result)


def _candidate_ring(path: dict[str, Any]):
    if (
        type(path) is not dict or path.get("type") != "s"
        or tuple(path.get("color") or ()) != (0.0, 0.0, 0.0)
        or not isinstance(path.get("width"), (float, int))
        or not 0.12 <= float(path["width"]) <= 0.6
    ):
        return None
    items = path.get("items", ())
    if not isinstance(items, (list, tuple)) or not 8 <= len(items) <= 64:
        return None
    segments = _segments(path)
    if len(segments) != len(items):
        return None
    for previous, next_seg in zip(segments, segments[1:]):
        if math.dist(previous[2:], next_seg[:2]) > 0.1:
            return None
    if math.dist(segments[-1][2:], segments[0][:2]) > 0.1:
        return None
    polygon = Polygon(tuple((seg[0], seg[1]) for seg in segments))
    if not polygon.is_valid or not polygon.is_simple:
        return None
    x0, y0, x1, y1 = polygon.bounds
    w, h = x1 - x0, y1 - y0
    if (
        w < 35 or h < 35 or w > 350 or h > 350
        or not 0.25 < w / h < 4.0
        or polygon.area < 600 or polygon.area / (w * h) < 0.85
    ):
        return None

    horizontals = sorted((
        (min(x, X), max(x, X), (y + Y) / 2)
        for x, y, X, Y in segments
        if abs(y - Y) <= 0.1
    ), key=lambda z: z[1] - z[0], reverse=True)
    if not horizontals:
        return None
    longest = horizontals[0]
    if longest[1] - longest[0] < 0.65 * w:
        return None
    equal_longest = [
        item for item in horizontals
        if abs((item[1] - item[0]) - (longest[1] - longest[0])) <= 0.1
    ]
    if any(
        abs(item[0] - longest[0]) > 0.1
        or abs(item[1] - longest[1]) > 0.1
        for item in equal_longest
    ):
        return None
    verticals = sorted((
        (min(y, Y), max(y, Y), (x + X) / 2)
        for x, y, X, Y in segments
        if abs(x - X) <= 0.1
    ), key=lambda z: z[1] - z[0], reverse=True)
    matching = sorted({round(item[2], 3) for item in equal_longest})
    if len(matching) == 2 and matching[1] - matching[0] >= 0.7 * h:
        # Preserve the existing source-CAD grouping/quantity precision.
        # The rounded boundary may exceed the raw float32 polygon by <0.0001pt,
        # far below the physical snap threshold. Validate that difference
        # numerically rather than rejecting a genuinely native closed face.
        top, bottom = matching
    elif verticals and verticals[0][1] - verticals[0][0] >= 0.7 * h:
        top, bottom = verticals[0][:2]
    else:
        return None
    box = (longest[0], top, longest[1], bottom)
    if (not 0 < box[2] - box[0] <= w
            or not 0 < box[3] - box[1] <= h + SOURCE_PDF_FLOAT_EPS_PT):
        return None
    return polygon, box


def _side_support(drawings, bbox):
    x0, y0, x1, y1 = bbox
    sides = (("L", x0, y0, y1), ("R", x1, y0, y1),
             ("T", y0, x0, x1), ("B", y1, x0, x1))
    found = {}
    for side, at, start, end in sides:
        intervals = []
        for path_id, path in enumerate(drawings):
            if (
                path.get("type") != "s" or
                tuple(path.get("color") or ()) != (0.0, 0.0, 0.0) or
                not isinstance(path.get("width"), (float, int)) or
                not 0.72 <= float(path["width"]) <= 2.4
            ):
                continue
            rect = path.get("rect")
            if rect is None:
                continue
            if side in ("L", "R"):
                if rect.x0 > at + SOURCE_SNAP_PT or rect.x1 < at - SOURCE_SNAP_PT:
                    continue
            else:
                if rect.y0 > at + SOURCE_SNAP_PT or rect.y1 < at - SOURCE_SNAP_PT:
                    continue
            for X, Y, XX, YY in _segments(path):
                if side in ("L", "R"):
                    if abs(X - XX) > 0.1 or abs(X - at) > SOURCE_SNAP_PT:
                        continue
                    low, high = min(Y, YY), max(Y, YY)
                else:
                    if abs(Y - YY) > 0.1 or abs(Y - at) > SOURCE_SNAP_PT:
                        continue
                    low, high = min(X, XX), max(X, XX)
                lo, hi = max(start, low), min(end, high)
                if hi - lo > 0.1:
                    intervals.append((lo, hi, path_id))
        if not intervals:
            return ()
        intervals.sort()
        union = []
        for lo, hi, _ in intervals:
            if not union or lo > union[-1][1] + .05:
                union.append([lo, hi])
            else:
                union[-1][1] = max(union[-1][1], hi)
        covered = sum(b - a for a, b in union) / (end - start)
        if covered < 0.40:
            return ()
        found[side] = tuple(idx for _, _, idx in intervals)
    return tuple(sorted({idx for ids in found.values() for idx in ids}))


def _tiled_hatch_ids(drawings, box):
    x0, y0, x1, y1 = box
    h, v = set(), set()
    used = 0
    for path_id, path in enumerate(drawings):
        if (
            path.get("type") != "s"
            or tuple(path.get("color") or ()) != (0.0, 0.0, 0.0)
            or not isinstance(path.get("width"), (float, int))
            or not .1 <= float(path["width"]) <= .6
        ):
            continue
        rect = path.get("rect")
        if rect is None or (rect.x1 < x0 or rect.x0 > x1
                            or rect.y1 < y0 or rect.y0 > y1):
            continue
        for X, Y, XX, YY in _segments(path):
            used += 1
            if used > SOURCE_PRIMITIVE_CAP:
                return ()
            if (
                min(X, XX) <= x0 + .2 or max(X, XX) >= x1 - .2 or
                min(Y, YY) <= y0 + .2 or max(Y, YY) >= y1 - .2
            ):
                continue
            length = math.hypot(X - XX, Y - YY)
            if not 4 <= length <= 20:
                continue
            if abs(X - XX) < .1:
                v.add(path_id)
            if abs(Y - YY) < .1:
                h.add(path_id)
    if len(h) < 12 or len(v) < 12 or len(h | v) < 20:
        return ()
    return tuple(sorted(h | v))


def _source_ocr_label(page: fitz.Page, polygon, bbox, room_label: str, ocr):
    """Return only independently agreeing original raster label witnesses.

    The original Q5446 ground ENS is confidently ENS on 216/360 dpi but
    slightly below threshold at 288. One uncertain view may abstain without
    erasing two independent strong reads; conflicting room labels or locations
    always ABSTAIN, even if two other views support the requested name.
    """
    observed: list[tuple[int, float, float]] = []
    room_words = frozenset({
        "ENS", "BATH", "LDRY", "LAUNDRY", "WC", "POWDER", "BED",
        "BEDROOM", "LIVING", "FAMILY", "MEALS", "KITCHEN",
        "WIR", "GARAGE", "GUEST", "OFFICE", "ENTRY", "MPR",
    })
    for dpi in (216, 288, 360):
        clip = fitz.Rect(*bbox) + (-2.0, -2.0, 2.0, 2.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72),
                              clip=clip, alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        matches = []
        for line in ocr.extract_lines(image, dpi=dpi):
            if line.confidence is None or line.confidence < .90:
                continue
            cx = clip.x0 + (line.bbox_pt[0] + line.bbox_pt[2]) / 2
            cy = clip.y0 + (line.bbox_pt[1] + line.bbox_pt[3]) / 2
            if not polygon.contains(Point(cx, cy)):
                continue
            text = _norm_room_label(line.text)
            if text != room_label and text in room_words:
                # A confident different room name must never be outvoted.
                # Fixture labels and door dimensions are not room identities.
                return None
            if text == room_label:
                matches.append((cx, cy))
        if len(matches) > 1:
            return None
        if matches:
            observed.append((dpi, *matches[0]))
    if len(observed) < 2 or any(
        math.dist(a[1:], b[1:]) > SOURCE_SNAP_PT
        for i, a in enumerate(observed) for b in observed[i + 1:]
    ):
        return None
    return tuple(dpi for dpi, _, _ in observed)


def find_unique_native_tiled_room_face(
    *,
    page: fitz.Page,
    page_number: int,
    room_label: str,
    allow_coincident_fixture_boundary: bool = True,
) -> NativeTiledRoomFace | None:
    """One physical, uniquely named, cross-ink corroborated tile region.

    No caller-supplied OCR words, geometry, benchmark IDs or expected areas.
    This returns a NON-COMMERCIAL source-face witness; semantic and metric
    authorization remain independent issuer gates.
    """
    if type(allow_coincident_fixture_boundary) is not bool:
        raise ValueError("allow_coincident_fixture_boundary must be an explicit boolean")
    if type(page_number) is not int or page_number < 1:
        return None
    label = _norm_room_label(room_label)
    if not label or len(label) > 32:
        return None
    drawings = page.get_drawings()
    if len(drawings) > SOURCE_PRIMITIVE_CAP:
        return None
    ocr = RapidOCRBackend()
    if not ocr.is_available():
        return None
    matches = []
    for path_id, path in enumerate(drawings):
        candidate = _candidate_ring(path)
        if candidate is None:
            continue
        polygon, box = candidate
        supports = _side_support(drawings, box)
        hatch_ids = _tiled_hatch_ids(drawings, box)
        if not hatch_ids:
            continue
        if not supports and allow_coincident_fixture_boundary:
            fixture_support = evaluate_coincident_fixture_boundary_support_shadow(
                drawings=drawings,
                bbox_pts=box,
                source_sha256="0" * 64,
                page_number=page_number,
                hatch_support_count=len(hatch_ids),
                exclude_ring_path_id=path_id,
                structural_snap_pt=SOURCE_SNAP_PT,
            )
            if fixture_support.supported:
                supports = fixture_support.all_support_path_ids
        if not supports:
            continue
        accepted_dpis = _source_ocr_label(page, polygon, polygon.bounds, label, ocr)
        if accepted_dpis is None:
            continue
        matches.append(NativeTiledRoomFace(
            page_number=page_number, source_boundary_path_id=path_id,
            room_label=label, source_bbox_pts=box,
            # Preserve accepted original-source quantity precision across
            # source-native float jitter, not a new metric or scale authority.
            finished_width_pts=round(box[2] - box[0], 5),
            finished_depth_pts=round(box[3] - box[1], 5),
            wall_support_source_path_ids=supports,
            hatch_support_source_path_ids=hatch_ids,
            raster_ocr_render_dpis=accepted_dpis,
        ))
    return matches[0] if len(matches) == 1 else None


def compose_multi_wall_open_room_face_evidence(
    *,
    wall_segments: tuple[SourceWallSegmentInput, ...] | list[SourceWallSegmentInput],
    thresholds: tuple[MarkedOpeningOrFinishThresholdInput, ...] | list[MarkedOpeningOrFinishThresholdInput],
    room_label: str,
    room_label_anchor_pts: tuple[float, float],
    source_sha256: str,
    page_id: str,
    viewport_id: str,
    mm_per_pt_x: float | None = None,
    mm_per_pt_y: float | None = None,
) -> MultiWallOpenRoomFaceResult:
    """Generic multi-wall room-face evidence entrypoint for non-single-path rooms.

    Returns a NON-COMMERCIAL shadow candidate (commercial_projection_allowed=False).
    """
    return compose_multi_wall_open_room_face_shadow(
        wall_segments=wall_segments,
        thresholds=thresholds,
        room_label=room_label,
        room_label_anchor_pts=room_label_anchor_pts,
        source_sha256=source_sha256,
        page_id=page_id,
        viewport_id=viewport_id,
        mm_per_pt_x=mm_per_pt_x,
        mm_per_pt_y=mm_per_pt_y,
    )


@dataclass(frozen=True)
class NativeTiledRoomFaceSamePageScaleShadowResult:
    """Shadow-only consumer wiring linking a verified room face to viewport-bound same-page scale."""

    status: str  # "SHADOW_ROOM_FACE_SCALE_CORROBORATED" | "ABSTAINED"
    room_label: str
    page_number: int
    viewport_id: str
    scale_report: SamePageFiguredScaleReport
    metric_estimate: ShadowRoomMetricEstimate | None
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    shadow_only: bool = True

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed is not False:
            raise ValueError("NativeTiledRoomFaceSamePageScaleShadowResult cannot authorize commercial projection")
        if self.takeoff_eligible is not False:
            raise ValueError("NativeTiledRoomFaceSamePageScaleShadowResult cannot be takeoff-eligible")
        if self.shadow_only is not True:
            raise ValueError("NativeTiledRoomFaceSamePageScaleShadowResult must remain shadow_only=True")


def corroborate_native_tiled_room_face_same_page_scale_shadow(
    *,
    face: NativeTiledRoomFace,
    source_sha256: str,
    target_viewport_id: str,
    page_rect_pts: tuple[float, float, float, float],
    same_page_witnesses: tuple[OrthogonalFiguredSpanWitness, ...] | list[OrthogonalFiguredSpanWitness],
    target_viewport_bbox_pdf_pts: tuple[float, float, float, float] | None = None,
    reference_mm_per_pt_x: float | None = None,
    reference_mm_per_pt_y: float | None = None,
    reference_page_rect_pts: tuple[float, float, float, float] | None = None,
    max_rel_tolerance: float = DEFAULT_MAX_REL_SCALE_TOLERANCE,
) -> NativeTiledRoomFaceSamePageScaleShadowResult:
    """Source-neutral shadow consumer wiring for viewport-bound same-page orthogonal scale.

    Requires an already-verified NativeTiledRoomFace plus explicit same-page, same-viewport
    source-owned orthogonal figured-span witnesses. Never authorizes commercial projection.
    """
    if (
        not isinstance(face, NativeTiledRoomFace)
        or not face.physical_source_verified
        or face.commercial_permission
    ):
        empty_report = corroborate_same_page_figured_scale_shadow(
            source_sha256="",
            page_number=0,
            target_viewport_id="",
            page_rect_pts=(0.0, 0.0, 1.0, 1.0),
            witnesses=(),
        )
        return NativeTiledRoomFaceSamePageScaleShadowResult(
            status="ABSTAINED",
            room_label="",
            page_number=0,
            viewport_id="",
            scale_report=empty_report,
            metric_estimate=None,
            reason_codes=("unverified_or_invalid_native_tiled_room_face",),
        )

    scale_report = corroborate_same_page_figured_scale_shadow(
        source_sha256=source_sha256,
        page_number=face.page_number,
        target_viewport_id=target_viewport_id,
        page_rect_pts=page_rect_pts,
        witnesses=same_page_witnesses,
        target_viewport_bbox_pdf_pts=target_viewport_bbox_pdf_pts,
        target_room_bbox_pdf_pts=face.source_bbox_pts,
        reference_mm_per_pt_x=reference_mm_per_pt_x,
        reference_mm_per_pt_y=reference_mm_per_pt_y,
        reference_page_rect_pts=reference_page_rect_pts,
        max_rel_tolerance=max_rel_tolerance,
    )
    if scale_report.status != "CORROBORATED_SAME_PAGE_FIGURED_SCALE_SHADOW":
        return NativeTiledRoomFaceSamePageScaleShadowResult(
            status="ABSTAINED",
            room_label=face.room_label,
            page_number=face.page_number,
            viewport_id=scale_report.viewport_id,
            scale_report=scale_report,
            metric_estimate=None,
            reason_codes=scale_report.reason_codes,
        )

    estimate = measure_room_face_from_same_page_scale_shadow(
        scale_report=scale_report,
        finished_width_pts=face.finished_width_pts,
        finished_depth_pts=face.finished_depth_pts,
    )
    if estimate.status != "SHADOW_METRIC_COMPUTED":
        return NativeTiledRoomFaceSamePageScaleShadowResult(
            status="ABSTAINED",
            room_label=face.room_label,
            page_number=face.page_number,
            viewport_id=scale_report.viewport_id,
            scale_report=scale_report,
            metric_estimate=estimate,
            reason_codes=estimate.reason_codes,
        )

    return NativeTiledRoomFaceSamePageScaleShadowResult(
        status="SHADOW_ROOM_FACE_SCALE_CORROBORATED",
        room_label=face.room_label,
        page_number=face.page_number,
        viewport_id=scale_report.viewport_id,
        scale_report=scale_report,
        metric_estimate=estimate,
        reason_codes=tuple(sorted(set(scale_report.reason_codes) | set(estimate.reason_codes))),
    )
