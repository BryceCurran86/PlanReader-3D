"""SHADOW-ONLY: title-block-declared single-view sheet -> floor-plan viewport candidate.

Many single-plan architectural sheets carry their drawing title only in the title
block ("DRAWING TITLE: FLOOR PLAN") and have no in-drawing view title and no drawn
drawing frame. F.07 (``pb_viewport_segmentation``) deliberately treats a
title-block field value as a title-field value, not a drawing-view title, so such a
sheet has no authenticated viewport and every downstream consumer that needs one
(opening scope, ceilings, source traces) fails closed.

This module proposes, in shadow only, whether such a sheet has exactly one
plausible floor-plan region. Contract:

* The title block TEXT only proposes a classification. It never supplies geometry.
* Geometry comes only from source-drawn evidence: a closed native drawing frame, or
  the page layout left over once the proven title-block furniture (page-title
  authority region plus the native frames that carry it) is removed.
* Every plausible region is retained. More than one distinct region is AMBIGUOUS
  (reported as ABSTAINED with ``ambiguous=True``); conflicting title or view evidence
  is CONFLICT; anything unproven is ABSTAINED.
* The result is never authoritative. Its status is at most ``CANDIDATE`` and the
  viewport it can describe is not stamped as an F.07 product, so
  ``is_segment_page_viewports_product`` and ``is_authoritative_derived_viewport``
  both reject it. Promoting it into F.07 needs a separate authority review and must
  reconcile the existing F.07 rule that a title-block value cannot create a viewport.
* No page numbers, coordinates, project names, filenames or known dimensions are
  read; every threshold derives from the page's own measured text calibration.

Nothing in the live extractor, customer path or F.07 imports this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Mapping, Optional, Sequence

import pb_page_title_authority as title_authority
from pb_drawing_evidence_binding import DrawingViewClassifier, DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportBoundarySource,
    ViewportSegmentationStatus,
    calibrate_viewport_layout,
    extract_vector_frames,
    extract_view_title_anchors,
    segment_page_viewports,
)


TITLE_BLOCK_VIEWPORT_SCHEMA_VERSION = "1.0.0"
TITLE_BLOCK_VIEWPORT_AUTHORITY = "title_block_single_view_viewport_shadow"
TITLE_BLOCK_VIEWPORT_PARTITION_MODE = "title_block_single_view_shadow"

TITLE_BLOCK_VIEWPORT_CANDIDATE = "title_block_floor_plan_viewport_candidate"
TITLE_BLOCK_VIEWPORT_PAGE_ROTATION_UNSUPPORTED = "title_block_viewport_page_rotation_unsupported"
TITLE_BLOCK_VIEWPORT_EVIDENCE_UNREADABLE = "title_block_viewport_evidence_unreadable"
TITLE_BLOCK_VIEWPORT_F07_FLOOR_PLAN_PRESENT = "title_block_viewport_f07_floor_plan_present"
TITLE_BLOCK_VIEWPORT_IN_DRAWING_FLOOR_PLAN_ANCHOR = (
    "title_block_viewport_in_drawing_floor_plan_anchor_present"
)
TITLE_BLOCK_VIEWPORT_TITLE_UNAVAILABLE = "title_block_viewport_title_unavailable"
TITLE_BLOCK_VIEWPORT_TITLE_NOT_FLOOR_PLAN = "title_block_viewport_title_not_floor_plan"
TITLE_BLOCK_VIEWPORT_TITLE_CONFLICT = "title_block_viewport_conflicting_titles"
TITLE_BLOCK_VIEWPORT_TITLE_MULTI_VIEW = "title_block_viewport_title_names_multiple_views"
TITLE_BLOCK_VIEWPORT_VIEW_ANCHOR_CONFLICT = "title_block_viewport_view_anchor_conflict"
TITLE_BLOCK_VIEWPORT_BLOCK_UNPROVEN = "title_block_viewport_title_block_unproven"
TITLE_BLOCK_VIEWPORT_BLOCK_NOT_IN_OUTER_BAND = "title_block_viewport_title_block_not_in_outer_band"
TITLE_BLOCK_VIEWPORT_NO_DRAWING_CONTENT = "title_block_viewport_no_drawing_content"
TITLE_BLOCK_VIEWPORT_NO_VALID_REGION = "title_block_viewport_no_valid_region"
TITLE_BLOCK_VIEWPORT_REGION_TOO_SMALL = "title_block_viewport_region_too_small"
TITLE_BLOCK_VIEWPORT_AMBIGUOUS_REGIONS = "title_block_viewport_ambiguous_floor_plan_regions"

BBox = tuple[float, float, float, float]

_DRAWING_VIEW_TYPES = frozenset(
    {
        DrawingViewType.FLOOR_PLAN.value,
        DrawingViewType.ROOF_PLAN.value,
        DrawingViewType.ELEVATION.value,
        DrawingViewType.SECTION.value,
        DrawingViewType.DETAIL.value,
    }
)
# Typed regions that are not plans but carry their own unproven extent. They
# contest ownership, so their presence is evidence against a single-view sheet.
_COMPETING_REGION_TYPES = frozenset(
    {
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.REPEATED_OR_REFERENCE.value,
        DrawingViewType.ADJACENT_SCOPE.value,
    }
)
_TITLE_SPLIT_RE = re.compile(r"\s*(?:&|/|\+|,|;|\band\b)\s*", re.IGNORECASE)
_MIN_TITLE_SCORE = 60.0
_TITLE_BLOCK_AREA_FRACTION = 0.35
_DRAWING_FRAME_AREA_FRACTION = 0.10
_EDGE_MARGIN_FRACTION = 0.05
_MIN_CONTENT_SEGMENTS = 2
_CLUSTER_MASS_FRACTION = 0.25
_FRAME_CONTENT_FRACTION = 0.90


@dataclass(frozen=True)
class TitleBlockViewportProposal:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    page_number: int
    ambiguous: bool = False
    view_type: Optional[str] = None
    title_text: Optional[str] = None
    title_score: Optional[float] = None
    viewport_id: Optional[str] = None
    bounding_box: Optional[BBox] = None
    boundary_evidence: str = ""
    furniture_boxes: tuple[BBox, ...] = ()
    candidate_regions: tuple[BBox, ...] = ()
    content_segment_count: int = 0
    competing_anchor_boxes: tuple[BBox, ...] = ()
    authoritative: bool = False
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = TITLE_BLOCK_VIEWPORT_SCHEMA_VERSION

    @property
    def is_candidate(self) -> bool:
        return self.status is EvidenceResolutionStatus.CANDIDATE and self.bounding_box is not None

    def to_segmented_viewport(self) -> Optional[SegmentedViewport]:
        """Describe the candidate in F.07's shape WITHOUT stamping it as an F.07 product."""
        if not self.is_candidate or self.viewport_id is None or self.bounding_box is None:
            return None
        return SegmentedViewport(
            view_id=self.viewport_id,
            page_number=self.page_number,
            view_type=DrawingViewType.FLOOR_PLAN.value,
            label=str(self.title_text or ""),
            title_bbox=self.furniture_boxes[0] if self.furniture_boxes else self.bounding_box,
            bounding_box=self.bounding_box,
            status=ViewportSegmentationStatus.DERIVED.value,
            boundary_source=ViewportBoundarySource.TITLE_PARTITION.value,
            confidence=0.5,
            notes=["shadow candidate: title-block title proposes floor plan; geometry is source-drawn layout"],
            provenance={
                **dict(self.provenance),
                "partition_mode": TITLE_BLOCK_VIEWPORT_PARTITION_MODE,
                "shadow_only": True,
                "authoritative": False,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "authority": TITLE_BLOCK_VIEWPORT_AUTHORITY,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "page_number": self.page_number,
            "ambiguous": self.ambiguous,
            "view_type": self.view_type,
            "title_text": self.title_text,
            "title_score": self.title_score,
            "viewport_id": self.viewport_id,
            "bounding_box": list(self.bounding_box) if self.bounding_box else None,
            "boundary_evidence": self.boundary_evidence,
            "furniture_boxes": [list(box) for box in self.furniture_boxes],
            "candidate_regions": [list(box) for box in self.candidate_regions],
            "content_segment_count": self.content_segment_count,
            "competing_anchor_boxes": [list(box) for box in self.competing_anchor_boxes],
            "authoritative": self.authoritative,
            "provenance": dict(self.provenance),
        }


def _result(
    status: EvidenceResolutionStatus,
    page_number: int,
    *reasons: str,
    **fields: Any,
) -> TitleBlockViewportProposal:
    return TitleBlockViewportProposal(
        status=status,
        reason_codes=tuple(dict.fromkeys(reason for reason in reasons if reason)),
        page_number=int(page_number),
        **fields,
    )


def _area(box: Sequence[float]) -> float:
    return max(0.0, float(box[2]) - float(box[0])) * max(0.0, float(box[3]) - float(box[1]))


def _overlaps(a: Sequence[float], b: Sequence[float]) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 1e-6 and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6


def _union(boxes: Sequence[Sequence[float]]) -> BBox:
    return (
        min(float(b[0]) for b in boxes),
        min(float(b[1]) for b in boxes),
        max(float(b[2]) for b in boxes),
        max(float(b[3]) for b in boxes),
    )


def _intersection(boxes: Sequence[Sequence[float]]) -> Optional[BBox]:
    box = (
        max(float(b[0]) for b in boxes),
        max(float(b[1]) for b in boxes),
        min(float(b[2]) for b in boxes),
        min(float(b[3]) for b in boxes),
    )
    return box if box[2] > box[0] and box[3] > box[1] else None


def _inside(segment: Sequence[float], box: Sequence[float], tol: float) -> bool:
    return all(
        box[0] - tol <= x <= box[2] + tol and box[1] - tol <= y <= box[3] + tol
        for x, y in ((segment[0], segment[1]), (segment[2], segment[3]))
    )


def _rounded(box: Sequence[float]) -> BBox:
    return tuple(round(float(v), 3) for v in box)  # type: ignore[return-value]


def _title_view_types(text: str) -> frozenset[str]:
    types = set()
    for part in _TITLE_SPLIT_RE.split(str(text or "")):
        if not part.strip():
            continue
        view_type = DrawingViewClassifier.classify_text(part).value
        if view_type != DrawingViewType.UNKNOWN.value:
            types.add(view_type)
    return frozenset(types)


def _title_minimum_score() -> float:
    scores = getattr(title_authority, "_MIN_SCORE", None)
    if isinstance(scores, Mapping):
        try:
            return float(scores.get("label", _MIN_TITLE_SCORE))
        except (TypeError, ValueError):
            return _MIN_TITLE_SCORE
    return _MIN_TITLE_SCORE


def _content_segments(
    native: Mapping[str, Any],
    *,
    minimum_length: float,
    page_width: float,
    page_height: float,
    furniture: Optional[BBox],
    tol: float,
) -> list[tuple[float, float, float, float]]:
    """Long native segments that are neither sheet border nor title-block furniture."""
    margin = _EDGE_MARGIN_FRACTION * min(page_width, page_height)
    content: list[tuple[float, float, float, float]] = []
    for raw in native.get("segments") or ():
        try:
            segment = (float(raw["x1"]), float(raw["y1"]), float(raw["x2"]), float(raw["y2"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in segment):
            continue
        if math.hypot(segment[2] - segment[0], segment[3] - segment[1]) < minimum_length:
            continue
        xs = (segment[0], segment[2])
        ys = (segment[1], segment[3])
        if (
            max(xs) <= margin
            or min(xs) >= page_width - margin
            or max(ys) <= margin
            or min(ys) >= page_height - margin
        ):
            continue  # sheet border zone
        if furniture is not None and _inside(segment, furniture, tol):
            continue
        content.append(segment)
    return content


def _on_frame_edge(segment: Sequence[float], frame: Sequence[float], tol: float) -> bool:
    """True when the segment lies along one side of the frame (a border, not content)."""
    x0, y0, x1, y1 = frame
    sx = (segment[0], segment[2])
    sy = (segment[1], segment[3])
    on_vertical = all(abs(x - x0) <= tol or abs(x - x1) <= tol for x in sx) and abs(sx[0] - sx[1]) <= tol
    on_horizontal = all(abs(y - y0) <= tol or abs(y - y1) <= tol for y in sy) and abs(sy[0] - sy[1]) <= tol
    within_x = min(sx) >= x0 - tol and max(sx) <= x1 + tol
    within_y = min(sy) >= y0 - tol and max(sy) <= y1 + tol
    return (on_vertical and within_y) or (on_horizontal and within_x)


def _length(segment: Sequence[float]) -> float:
    return math.hypot(segment[2] - segment[0], segment[3] - segment[1])


def _segment_box(segment: Sequence[float]) -> BBox:
    return (
        min(segment[0], segment[2]),
        min(segment[1], segment[3]),
        max(segment[0], segment[2]),
        max(segment[1], segment[3]),
    )


def _separated_clusters(
    segments: Sequence[Sequence[float]],
    *,
    minimum_gap: float,
) -> list[BBox]:
    """Substantial drawing clusters separated by an empty gap on either axis.

    A cluster counts only if it carries a real share of the total linework, so a
    small notes panel beside a plan does not read as a second plan.
    """
    total = sum(_length(s) for s in segments)
    if total <= 0.0:
        return []
    for axis in (0, 1):
        ordered = sorted(
            segments,
            key=lambda s: (_segment_box(s)[axis], _segment_box(s)[axis + 2]),
        )
        groups: list[list[Sequence[float]]] = []
        reach = -math.inf
        for segment in ordered:
            low, high = _segment_box(segment)[axis], _segment_box(segment)[axis + 2]
            if not groups or low - reach >= minimum_gap:
                groups.append([segment])
                reach = high
            else:
                groups[-1].append(segment)
                reach = max(reach, high)
        if len(groups) < 2:
            continue
        heavy = [
            group
            for group in groups
            if sum(_length(s) for s in group) / total >= _CLUSTER_MASS_FRACTION
        ]
        if len(heavy) >= 2:
            return [_union([_segment_box(s) for s in group]) for group in heavy]
    return []


def _is_nested_chain(boxes: Sequence[Sequence[float]], tol: float) -> bool:
    """True when every pair of boxes is nested: one drawing area with several borders."""

    def contains(outer: Sequence[float], inner: Sequence[float]) -> bool:
        return (
            outer[0] - tol <= inner[0]
            and outer[1] - tol <= inner[1]
            and outer[2] + tol >= inner[2]
            and outer[3] + tol >= inner[3]
        )

    return all(
        contains(a, b) or contains(b, a)
        for index, a in enumerate(boxes)
        for b in boxes[index + 1 :]
    )


def propose_title_block_floor_plan_viewport(
    page: Any,
    *,
    page_number: int,
    f07_viewports: Optional[Sequence[SegmentedViewport]] = None,
) -> TitleBlockViewportProposal:
    """Propose, in shadow, the single floor-plan region of a title-block-only sheet."""
    try:
        if int(getattr(page, "rotation", 0) or 0) != 0:
            return _result(
                EvidenceResolutionStatus.ABSTAINED,
                page_number,
                TITLE_BLOCK_VIEWPORT_PAGE_ROTATION_UNSUPPORTED,
            )
        width = float(page.rect.width)
        height = float(page.rect.height)
        if not (width > 0.0 and height > 0.0):
            raise ValueError("empty page")
        calibration = calibrate_viewport_layout(page)
        existing = (
            list(f07_viewports)
            if f07_viewports is not None
            else segment_page_viewports(page, page_number=page_number)
        )
        anchors = extract_view_title_anchors(page)
        analysis = title_authority.analyse_cells(
            title_authority.page_cells(page), width, height, int(page_number), "native"
        )
        frames = extract_vector_frames(page, calibration)
        native = extract_native_page(page)
    except Exception:  # noqa: BLE001 - unreadable evidence must fail closed, never raise
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_EVIDENCE_UNREADABLE,
        )

    # F.07 already owns a floor plan on this page: this authority adds nothing.
    if any(
        viewport.view_type == DrawingViewType.FLOOR_PLAN.value
        and viewport.bounding_box is not None
        and viewport.status
        in (ViewportSegmentationStatus.RESOLVED.value, ViewportSegmentationStatus.DERIVED.value)
        for viewport in existing
    ):
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_F07_FLOOR_PLAN_PRESENT,
        )

    anchor_types = {str(anchor.view_type) for anchor in anchors}
    if DrawingViewType.FLOOR_PLAN.value in anchor_types:
        # In-drawing titled plans belong to F.07's own (deliberately strict) rules.
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_IN_DRAWING_FLOOR_PLAN_ANCHOR,
        )
    competing_anchors = tuple(
        _rounded(anchor.bbox)
        for anchor in anchors
        if str(anchor.view_type) not in _DRAWING_VIEW_TYPES
    )

    # --- E1: title text proposes a classification (never geometry) -------------
    minimum_score = _title_minimum_score()
    titles = [
        candidate
        for candidate in analysis.candidates
        if candidate.kind == "label"
        and candidate.label_strength == "title_explicit"
        and not candidate.rejected
        and candidate.text
        and float(candidate.score) >= minimum_score
    ]
    if not titles:
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_TITLE_UNAVAILABLE,
            competing_anchor_boxes=competing_anchors,
        )
    per_title_types = [_title_view_types(candidate.text) for candidate in titles]
    distinct = {types for types in per_title_types if types}
    all_types = frozenset().union(*per_title_types)
    if any(len(types) > 1 for types in per_title_types):
        return _result(
            EvidenceResolutionStatus.CONFLICT,
            page_number,
            TITLE_BLOCK_VIEWPORT_TITLE_MULTI_VIEW,
            title_text=titles[0].text,
            competing_anchor_boxes=competing_anchors,
        )
    if len(distinct) > 1:
        return _result(
            EvidenceResolutionStatus.CONFLICT,
            page_number,
            TITLE_BLOCK_VIEWPORT_TITLE_CONFLICT,
            title_text=titles[0].text,
            competing_anchor_boxes=competing_anchors,
        )
    if all_types != frozenset({DrawingViewType.FLOOR_PLAN.value}):
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_TITLE_NOT_FLOOR_PLAN,
            title_text=titles[0].text,
            competing_anchor_boxes=competing_anchors,
        )
    title = max(
        (c for c, types in zip(titles, per_title_types) if types),
        key=lambda c: (float(c.score), str(c.text)),
    )

    # --- conflicting in-drawing view evidence ----------------------------------
    if any(
        kind in _DRAWING_VIEW_TYPES or kind in _COMPETING_REGION_TYPES
        for kind in anchor_types
    ):
        return _result(
            EvidenceResolutionStatus.CONFLICT,
            page_number,
            TITLE_BLOCK_VIEWPORT_VIEW_ANCHOR_CONFLICT,
            view_type=DrawingViewType.FLOOR_PLAN.value,
            title_text=title.text,
            title_score=float(title.score),
            competing_anchor_boxes=competing_anchors,
        )

    # --- E2: positive page-layout evidence (proven title-block furniture) -------
    block = analysis.title_block
    if block is None:
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_BLOCK_UNPROVEN,
            view_type=DrawingViewType.FLOOR_PLAN.value,
            title_text=title.text,
            title_score=float(title.score),
            competing_anchor_boxes=competing_anchors,
        )
    page_area = width * height
    block_box: BBox = tuple(float(v) for v in block)  # type: ignore[assignment]
    furniture_boxes = [block_box] + [
        frame
        for frame in frames
        if _overlaps(frame, block_box) and _area(frame) <= _TITLE_BLOCK_AREA_FRACTION * page_area
    ]
    furniture = _union(furniture_boxes)
    common = dict(
        view_type=DrawingViewType.FLOOR_PLAN.value,
        title_text=title.text,
        title_score=float(title.score),
        furniture_boxes=tuple(_rounded(box) for box in furniture_boxes),
        competing_anchor_boxes=competing_anchors,
    )
    if not (
        furniture[0] <= width * 0.25
        or furniture[2] >= width * 0.75
        or furniture[1] <= height * 0.25
        or furniture[3] >= height * 0.75
    ):
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_BLOCK_NOT_IN_OUTER_BAND,
            **common,
        )

    tol = max(calibration.median_word_height_pt * 0.1, 0.5)
    content = _content_segments(
        native,
        minimum_length=calibration.minimum_frame_span_pt,
        page_width=width,
        page_height=height,
        furniture=furniture,
        tol=tol,
    )
    if len(content) < _MIN_CONTENT_SEGMENTS:
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_NO_DRAWING_CONTENT,
            content_segment_count=len(content),
            **common,
        )

    drawing_frames = [
        frame
        for frame in frames
        if not _overlaps(frame, furniture)
        and _area(frame) >= _DRAWING_FRAME_AREA_FRACTION * page_area
    ]
    # Frame sides are borders, not drawing content: they must not bridge two
    # drawings or count towards what a frame holds.
    framed_content = [
        segment
        for segment in content
        if not any(_on_frame_edge(segment, frame, tol) for frame in drawing_frames)
    ]
    if len(framed_content) < _MIN_CONTENT_SEGMENTS:
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_NO_DRAWING_CONTENT,
            content_segment_count=len(framed_content),
            **common,
        )
    clusters = _separated_clusters(framed_content, minimum_gap=calibration.minimum_frame_span_pt)
    if clusters:
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_AMBIGUOUS_REGIONS,
            ambiguous=True,
            candidate_regions=tuple(_rounded(box) for box in clusters),
            content_segment_count=len(framed_content),
            boundary_evidence="separated_drawing_clusters",
            **common,
        )

    # --- geometry: a source-drawn drawing frame wins over page-layout bands -----
    boundary_evidence = "title_block_layout_band"
    band_decisions: list[dict[str, Any]] = []
    region: Optional[BBox] = None
    candidate_regions: list[BBox] = []

    if drawing_frames:
        total_mass = sum(_length(s) for s in framed_content)

        def held(frame: BBox) -> list[Sequence[float]]:
            return [s for s in framed_content if _inside(s, frame, tol)]

        holders = [
            frame
            for frame in drawing_frames
            if len(held(frame)) / len(framed_content) >= _FRAME_CONTENT_FRACTION
        ]
        substantial = [
            frame
            for frame in drawing_frames
            if total_mass > 0.0
            and sum(_length(s) for s in held(frame)) / total_mass >= _CLUSTER_MASS_FRACTION
        ]
        candidate_regions = [_rounded(frame) for frame in (substantial or drawing_frames)]
        if holders and _is_nested_chain(holders, tol):
            # One drawing area described by one or more nested borders: the
            # region no border excludes is their intersection.
            region = _intersection(holders)
            boundary_evidence = "closed_native_drawing_frame"
        elif holders or (len(substantial) > 1 and not _is_nested_chain(substantial, tol)):
            return _result(
                EvidenceResolutionStatus.ABSTAINED,
                page_number,
                TITLE_BLOCK_VIEWPORT_AMBIGUOUS_REGIONS,
                ambiguous=True,
                candidate_regions=tuple(candidate_regions),
                content_segment_count=len(framed_content),
                boundary_evidence="multiple_closed_native_drawing_frames",
                **common,
            )

    if region is None:
        gap = calibration.title_frame_gap_pt
        span = calibration.minimum_frame_span_pt
        bands: list[tuple[str, BBox]] = []
        if furniture[1] - gap >= span:
            bands.append(("above_title_block", (0.0, 0.0, width, furniture[1] - gap)))
        if height - (furniture[3] + gap) >= span:
            bands.append(("below_title_block", (0.0, furniture[3] + gap, width, height)))
        if furniture[0] - gap >= span:
            bands.append(("left_of_title_block", (0.0, 0.0, furniture[0] - gap, height)))
        if width - (furniture[2] + gap) >= span:
            bands.append(("right_of_title_block", (furniture[2] + gap, 0.0, width, height)))
        valid: list[BBox] = []
        for name, band in bands:
            inside = sum(1 for s in content if _inside(s, band, tol))
            excluded = len(content) - inside
            ok = excluded == 0 and inside >= _MIN_CONTENT_SEGMENTS
            band_decisions.append(
                {
                    "band": name,
                    "bounding_box": list(_rounded(band)),
                    "inside_segments": inside,
                    "excluded_segments": excluded,
                    "valid": ok,
                }
            )
            if ok:
                valid.append(band)
        if not valid:
            return _result(
                EvidenceResolutionStatus.ABSTAINED,
                page_number,
                TITLE_BLOCK_VIEWPORT_NO_VALID_REGION,
                content_segment_count=len(content),
                provenance={"band_decisions": band_decisions},
                **common,
            )
        candidate_regions = [_rounded(band) for band in valid]
        # Every valid reading contains all drawing content; the region no reading
        # excludes is their intersection (one reading: that band).
        region = _intersection(valid) if len(valid) > 1 else valid[0]
        if region is None:
            return _result(
                EvidenceResolutionStatus.ABSTAINED,
                page_number,
                TITLE_BLOCK_VIEWPORT_NO_VALID_REGION,
                content_segment_count=len(content),
                candidate_regions=tuple(candidate_regions),
                provenance={"band_decisions": band_decisions},
                **common,
            )

    if (region[2] - region[0]) < calibration.minimum_frame_span_pt or (
        region[3] - region[1]
    ) < calibration.minimum_frame_span_pt:
        return _result(
            EvidenceResolutionStatus.ABSTAINED,
            page_number,
            TITLE_BLOCK_VIEWPORT_REGION_TOO_SMALL,
            candidate_regions=tuple(candidate_regions),
            content_segment_count=len(content),
            **common,
        )

    bounding_box = _rounded(region)
    viewport_id = stable_contract_id(
        "title_block_viewport",
        {
            "page_number": int(page_number),
            "bounding_box": list(bounding_box),
            "title": " ".join(str(title.text).upper().split()),
            "furniture": [list(_rounded(box)) for box in furniture_boxes],
            "boundary_evidence": boundary_evidence,
        },
        digest_chars=24,
    )
    return _result(
        EvidenceResolutionStatus.CANDIDATE,
        page_number,
        TITLE_BLOCK_VIEWPORT_CANDIDATE,
        viewport_id=viewport_id,
        bounding_box=bounding_box,
        boundary_evidence=boundary_evidence,
        candidate_regions=tuple(candidate_regions),
        content_segment_count=len(content),
        provenance={
            "single_view_validated": True,
            "drawing_vector_primitive_count": len(content),
            "title_block_bbox": list(_rounded(block_box)),
            "band_decisions": band_decisions,
            "calibration": {
                "median_word_height_pt": round(calibration.median_word_height_pt, 3),
                "minimum_frame_span_pt": round(calibration.minimum_frame_span_pt, 3),
                "title_frame_gap_pt": round(calibration.title_frame_gap_pt, 3),
            },
        },
        **common,
    )


__all__ = [
    "TITLE_BLOCK_VIEWPORT_AMBIGUOUS_REGIONS",
    "TITLE_BLOCK_VIEWPORT_AUTHORITY",
    "TITLE_BLOCK_VIEWPORT_BLOCK_NOT_IN_OUTER_BAND",
    "TITLE_BLOCK_VIEWPORT_BLOCK_UNPROVEN",
    "TITLE_BLOCK_VIEWPORT_CANDIDATE",
    "TITLE_BLOCK_VIEWPORT_EVIDENCE_UNREADABLE",
    "TITLE_BLOCK_VIEWPORT_F07_FLOOR_PLAN_PRESENT",
    "TITLE_BLOCK_VIEWPORT_IN_DRAWING_FLOOR_PLAN_ANCHOR",
    "TITLE_BLOCK_VIEWPORT_NO_DRAWING_CONTENT",
    "TITLE_BLOCK_VIEWPORT_NO_VALID_REGION",
    "TITLE_BLOCK_VIEWPORT_PAGE_ROTATION_UNSUPPORTED",
    "TITLE_BLOCK_VIEWPORT_PARTITION_MODE",
    "TITLE_BLOCK_VIEWPORT_REGION_TOO_SMALL",
    "TITLE_BLOCK_VIEWPORT_SCHEMA_VERSION",
    "TITLE_BLOCK_VIEWPORT_TITLE_CONFLICT",
    "TITLE_BLOCK_VIEWPORT_TITLE_MULTI_VIEW",
    "TITLE_BLOCK_VIEWPORT_TITLE_NOT_FLOOR_PLAN",
    "TITLE_BLOCK_VIEWPORT_TITLE_UNAVAILABLE",
    "TITLE_BLOCK_VIEWPORT_VIEW_ANCHOR_CONFLICT",
    "TitleBlockViewportProposal",
    "propose_title_block_floor_plan_viewport",
]
