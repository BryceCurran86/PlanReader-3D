"""Figured-dimension evidence extraction and binding (Phase F.13 completion).

This module closes the raw-evidence gap deliberately left by
``pb_dimension_graph_constraint_engine``.  It converts native PDF text,
vector linework, and explicitly transformed OCR candidates into traceable
``DimensionObservation`` records without conflating four distinct concepts:

1. observed page geometry (PDF vector segments),
2. figured-dimension constraints (printed dimension values),
3. candidate bindings (dimension / witness-line associations), and
4. resolved construction geometry (owned by the F.13 constraint engine).

Important safety properties:
- project/file/benchmark identity is never an input to semantic decisions;
- non-dimension drafting tokens are typed rather than value-blacklisted;
- OCR does not overwrite native evidence -- both candidates are preserved;
- raster coordinates require an explicit transform before they can be mixed
  with PDF-point coordinates;
- figured dimensions do not require drawing scale, while scaled vector
  measurements require a page-matched usable ScaleCalibration;
- ambiguous line/witness association fails closed rather than picking the
  value or geometry that looks most convenient.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
import statistics
from typing import Any, Iterable, Optional, Sequence

from pb_dimension_graph_constraint_engine import (
    ConstraintStatus,
    DimensionChain,
    DimensionObservation,
    DimensionOrientation,
    reconcile_duplicate_observations,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_geometry_takeoff_model import (
    AuthorityStatus,
    MeasurementAuthorityType,
    ScaleCalibration,
)
from pb_page_scale_calibration_authority import measurement_authority_for_page_scale


class CoordinateSpace(str, Enum):
    PDF_POINTS = "pdf_points"
    RASTER_PIXELS = "raster_pixels"


class DimensionTokenKind(str, Enum):
    LINEAR_DIMENSION = "linear_dimension"
    SCALE = "scale"
    DRAWING_REFERENCE = "drawing_reference"
    ROOM_NUMBER = "room_number"
    OPENING_TAG = "opening_tag"
    GRID_LABEL = "grid_label"
    REVISION = "revision"
    YEAR = "year"
    SHEET_NUMBER = "sheet_number"
    DRAWING_NUMBER = "drawing_number"
    OTHER = "other"


class BindingStatus(str, Enum):
    WITNESS_BOUND = "witness_bound"
    LINE_BOUND = "line_bound"
    PARTIAL_WITNESS = "partial_witness"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class DimensionEvidenceTier(str, Enum):
    WITNESS_BOUND = "witness_bound"
    LINE_BOUND = "line_bound"
    TEXT_ONLY = "text_only"
    OCR_ONLY = "ocr_only"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class TypedDimensionToken:
    raw_text: str
    kind: str
    value: Optional[float] = None
    unit: Optional[str] = None
    normalized_text: str = ""
    reason: str = ""

    @property
    def is_linear_dimension(self) -> bool:
        return self.kind == DimensionTokenKind.LINEAR_DIMENSION.value and self.value is not None


@dataclass(frozen=True)
class ObservedGeometrySegment:
    segment_id: str
    source_page: int
    start: tuple[float, float]
    end: tuple[float, float]
    coordinate_space: str = CoordinateSpace.PDF_POINTS.value
    view_id: str = ""
    source_path_index: Optional[int] = None
    stroke_width_pt: Optional[float] = None
    stroke_color_rgb: Optional[tuple[float, float, float]] = None

    @property
    def dx(self) -> float:
        return self.end[0] - self.start[0]

    @property
    def dy(self) -> float:
        return self.end[1] - self.start[1]

    @property
    def length(self) -> float:
        return math.hypot(self.dx, self.dy)

    @property
    def orientation(self) -> str:
        if self.length <= 0:
            return DimensionOrientation.UNKNOWN.value
        # Axis classification is relative to the segment itself; no project
        # units or scale assumptions are involved.
        if abs(self.dx) >= abs(self.dy) * 4.0:
            return DimensionOrientation.HORIZONTAL.value
        if abs(self.dy) >= abs(self.dx) * 4.0:
            return DimensionOrientation.VERTICAL.value
        return DimensionOrientation.UNKNOWN.value


@dataclass(frozen=True)
class RasterCoordinateTransform:
    """Explicit raster-pixel -> PDF-point transform for one page.

    OCR boxes must never be mixed with PDF vector coordinates without this
    information. Rotation is intentionally explicit and limited to the four
    lossless page rotations used by the metamorphic suite.
    """

    page_width_pt: float
    page_height_pt: float
    raster_width_px: float
    raster_height_px: float
    rotation_deg: int = 0

    def __post_init__(self) -> None:
        if self.page_width_pt <= 0 or self.page_height_pt <= 0:
            raise ValueError("PDF page dimensions must be positive")
        if self.raster_width_px <= 0 or self.raster_height_px <= 0:
            raise ValueError("Raster dimensions must be positive")
        if self.rotation_deg not in (0, 90, 180, 270):
            raise ValueError("rotation_deg must be one of 0, 90, 180, 270")

    def point_to_pdf(self, point: tuple[float, float]) -> tuple[float, float]:
        x_px, y_px = point
        x = x_px * self.page_width_pt / self.raster_width_px
        y = y_px * self.page_height_pt / self.raster_height_px
        if self.rotation_deg == 0:
            return x, y
        if self.rotation_deg == 90:
            return self.page_width_pt - y, x
        if self.rotation_deg == 180:
            return self.page_width_pt - x, self.page_height_pt - y
        return y, self.page_height_pt - x

    def bbox_to_pdf(
        self, bbox: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = bbox
        points = [
            self.point_to_pdf((x0, y0)),
            self.point_to_pdf((x1, y0)),
            self.point_to_pdf((x0, y1)),
            self.point_to_pdf((x1, y1)),
        ]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True)
class DimensionLayoutCalibration:
    """Page-derived spatial tolerances used for evidence association."""

    median_word_height_pt: float
    line_search_distance_pt: float
    witness_endpoint_distance_pt: float
    chain_axis_tolerance_pt: float


@dataclass
class DimensionAnchorBinding:
    observation_id: str
    status: str
    dimension_line_id: Optional[str] = None
    witness_line_ids: tuple[str, ...] = field(default_factory=tuple)
    endpoints: Optional[tuple[tuple[float, float], tuple[float, float]]] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class DimensionCandidateGroup:
    group_id: str
    candidates: list[DimensionObservation]
    resolved: Optional[DimensionObservation]
    status: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ScaledSegmentMeasurement:
    segment_id: str
    status: str
    length_m: Optional[float]
    authority: str
    notes: list[str] = field(default_factory=list)


@dataclass
class DimensionEvidenceBundle:
    observations: list[DimensionObservation] = field(default_factory=list)
    observed_geometry: list[ObservedGeometrySegment] = field(default_factory=list)
    bindings: list[DimensionAnchorBinding] = field(default_factory=list)
    candidate_groups: list[DimensionCandidateGroup] = field(default_factory=list)
    chains: list[DimensionChain] = field(default_factory=list)


# Typed grammar: identity-like drafting tokens are recognized by shape/context.
# No benchmark/project-specific values occur here.
_SCALE_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?\s*$", re.I)
_REFERENCE_RE = re.compile(r"^\s*\d+\s*/\s*[A-Z]{1,4}\d{1,4}\s*$", re.I)
_DRAWING_NUMBER_RE = re.compile(r"^\s*[A-Z]{1,4}\d{2,4}\s*$", re.I)
_OPENING_TAG_RE = re.compile(r"^\s*(?:D|DR|W|WD)\s*[-_]?\s*\d{1,3}[A-Z]?\s*$", re.I)
_ROOM_RE = re.compile(r"^\s*(?:ROOM|RM)\s*[-:#]?\s*\d+[A-Z]?\s*$", re.I)
_GRID_RE = re.compile(r"^\s*GRID\s*[-:#]?\s*[A-Z0-9]+\s*$", re.I)
_REV_RE = re.compile(r"^\s*REV(?:ISION)?\s*[-:#]?\s*[A-Z0-9]+\s*$", re.I)
_SHEET_RE = re.compile(r"^\s*SHEET\s*[-:#]?\s*\d+\s*$", re.I)
_YEAR_RE = re.compile(r"^\s*(?:19|20)\d{2}\s*$")
_METRIC_MM_RE = re.compile(r"^\s*(\d+(?:[,.]\d+)?)\s*mm\s*$", re.I)
_METRIC_M_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*m\s*$", re.I)
_BARE_MM_RE = re.compile(r"^\s*(\d{2,5}|\d{1,2}[,.]\d{3})\s*$")
_IMPERIAL_RE = re.compile(
    r"^\s*(?:(\d+)\s*(?:'|ft))?\s*[-–]?\s*(?:(\d+(?:\.\d+)?)\s*(?:\"|in))?\s*$",
    re.I,
)
_YEARLIKE_PROMOTION_VIEW_TYPES = frozenset(
    {
        DrawingViewType.FLOOR_PLAN.value,
        DrawingViewType.ROOF_PLAN.value,
        DrawingViewType.ELEVATION.value,
        DrawingViewType.SECTION.value,
        DrawingViewType.DETAIL.value,
    }
)
_YEARLIKE_NON_DIMENSION_CONTEXT_RE = re.compile(
    r"\b(?:DATE|DATED|ISSUE|ISSUED|YEAR|REV|REVISION)\s*$",
    re.I,
)

_CONTEXT_KIND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:ROOM|RM)\s*$", re.I), DimensionTokenKind.ROOM_NUMBER.value),
    (re.compile(r"\bGRID\s*$", re.I), DimensionTokenKind.GRID_LABEL.value),
    (re.compile(r"\bREV(?:ISION)?\s*$", re.I), DimensionTokenKind.REVISION.value),
    (re.compile(r"\bSHEET\s*$", re.I), DimensionTokenKind.SHEET_NUMBER.value),
    (re.compile(r"\b(?:DWG|DRAWING\s*NO)\s*$", re.I), DimensionTokenKind.DRAWING_NUMBER.value),
    (re.compile(r"\bSCALE\s*$", re.I), DimensionTokenKind.SCALE.value),
)


def classify_dimension_token(text: str, *, preceding_context: str = "") -> TypedDimensionToken:
    """Classify one dimension candidate using typed drafting grammar.

    Bare numbers are accepted as millimetres only after typed non-dimension
    forms and immediate drafting-label context have been rejected. This keeps
    ordinary dimension strings usable without creating value blacklists.
    """
    raw = text
    normalized = " ".join(text.strip().split())
    for pattern, kind in (
        (_SCALE_RE, DimensionTokenKind.SCALE.value),
        (_REFERENCE_RE, DimensionTokenKind.DRAWING_REFERENCE.value),
        (_ROOM_RE, DimensionTokenKind.ROOM_NUMBER.value),
        (_GRID_RE, DimensionTokenKind.GRID_LABEL.value),
        (_REV_RE, DimensionTokenKind.REVISION.value),
        (_SHEET_RE, DimensionTokenKind.SHEET_NUMBER.value),
        (_OPENING_TAG_RE, DimensionTokenKind.OPENING_TAG.value),
        (_YEAR_RE, DimensionTokenKind.YEAR.value),
        (_DRAWING_NUMBER_RE, DimensionTokenKind.DRAWING_NUMBER.value),
    ):
        if pattern.match(normalized):
            return TypedDimensionToken(raw, kind, normalized_text=normalized, reason="typed drafting token")

    ctx = preceding_context[-40:]
    for pattern, kind in _CONTEXT_KIND_PATTERNS:
        if pattern.search(ctx):
            return TypedDimensionToken(raw, kind, normalized_text=normalized, reason="typed preceding context")

    m = _METRIC_MM_RE.match(normalized)
    if m:
        value = float(m.group(1).replace(",", ""))
        return TypedDimensionToken(raw, DimensionTokenKind.LINEAR_DIMENSION.value, value, "mm", normalized)

    m = _METRIC_M_RE.match(normalized)
    if m:
        return TypedDimensionToken(raw, DimensionTokenKind.LINEAR_DIMENSION.value, float(m.group(1)), "m", normalized)

    # Imperial notation is accepted only when it contains an explicit foot or
    # inch marker. A bare number therefore never becomes imperial by guess.
    if "'" in normalized or '"' in normalized or re.search(r"\b(?:ft|in)\b", normalized, re.I):
        m = _IMPERIAL_RE.match(normalized)
        if m and (m.group(1) or m.group(2)):
            feet = float(m.group(1) or 0.0)
            inches = float(m.group(2) or 0.0)
            return TypedDimensionToken(
                raw,
                DimensionTokenKind.LINEAR_DIMENSION.value,
                feet * 12.0 + inches,
                "in",
                normalized,
            )

    m = _BARE_MM_RE.match(normalized)
    if m:
        cleaned = m.group(1).replace(",", "").replace(".", "")
        if _YEAR_RE.match(cleaned):
            return TypedDimensionToken(raw, DimensionTokenKind.YEAR.value, normalized_text=normalized)
        value = float(cleaned)
        # The F.13 engine owns the general plausible range; retain only
        # positive finite values here and let constraint semantics decide use.
        if math.isfinite(value) and value > 0:
            return TypedDimensionToken(raw, DimensionTokenKind.LINEAR_DIMENSION.value, value, "mm", normalized)

    return TypedDimensionToken(raw, DimensionTokenKind.OTHER.value, normalized_text=normalized, reason="no dimension grammar matched")


_PAGE_NATIVE_PARSE_CACHE_ATTR = "_pb_figured_dimension_native_parse_cache"


def _page_native_parse_cache(page: Any) -> Optional[dict[str, Any]]:
    try:
        cache = getattr(page, _PAGE_NATIVE_PARSE_CACHE_ATTR, None)
    except Exception:
        cache = None
    if isinstance(cache, dict):
        return cache
    cache = {}
    try:
        setattr(page, _PAGE_NATIVE_PARSE_CACHE_ATTR, cache)
    except Exception:
        return None
    return cache


def _native_words(page: Any) -> tuple:
    cache = _page_native_parse_cache(page)
    if isinstance(cache, dict) and "words" in cache:
        return cache["words"]
    words = tuple(page.get_text("words") or ())
    if isinstance(cache, dict):
        cache["words"] = words
    return words


def _native_word_orientations(page: Any) -> dict[tuple[int, int], str]:
    """Return exact native text-line orientations keyed by word block/line.

    PyMuPDF word tuples carry block/line indices while the native text dict
    carries the corresponding source text direction. This is stronger than
    inferring orientation from an axis-aligned bbox, especially on rotated
    architectural sheets.
    """
    cache = _page_native_parse_cache(page)
    if isinstance(cache, dict) and "word_orientations" in cache:
        return cache["word_orientations"]
    out: dict[tuple[int, int], str] = {}
    try:
        data = page.get_text("dict") or {}
    except Exception:
        data = {}
    for block_index, block in enumerate(data.get("blocks", []) or []):
        if int(block.get("type", 0)) != 0:
            continue
        for line_index, line in enumerate(block.get("lines", []) or []):
            direction = line.get("dir")
            if not isinstance(direction, (tuple, list)) or len(direction) < 2:
                continue
            try:
                dx, dy = float(direction[0]), float(direction[1])
            except (TypeError, ValueError):
                continue
            if not math.isfinite(dx) or not math.isfinite(dy):
                continue
            if abs(dx) >= abs(dy) * 4.0:
                out[(block_index, line_index)] = DimensionOrientation.HORIZONTAL.value
            elif abs(dy) >= abs(dx) * 4.0:
                out[(block_index, line_index)] = DimensionOrientation.VERTICAL.value
    if isinstance(cache, dict):
        cache["word_orientations"] = out
    return out


def _native_drawings(page: Any) -> tuple:
    cache = _page_native_parse_cache(page)
    if isinstance(cache, dict) and "drawings" in cache:
        return cache["drawings"]
    drawings = tuple(page.get_drawings() or ())
    if isinstance(cache, dict):
        cache["drawings"] = drawings
    return drawings


def calibrate_dimension_layout_from_word_heights(
    word_heights_pt: Sequence[float],
) -> DimensionLayoutCalibration:
    """Derive dimension-association tolerances from source typography heights.

    The relationship multipliers are the existing figured-dimension contract;
    this helper simply makes the same page-derived calibration reusable by
    producer-owned consumers that already hold authenticated native word
    geometry without reopening/parsing the PDF page.
    """
    heights = [
        float(value)
        for value in word_heights_pt
        if math.isfinite(float(value)) and float(value) > 0.0
    ]
    median_h = statistics.median(heights) if heights else 8.0
    return DimensionLayoutCalibration(
        median_word_height_pt=median_h,
        line_search_distance_pt=max(median_h * 2.0, 2.0),
        witness_endpoint_distance_pt=max(median_h * 1.5, 2.0),
        chain_axis_tolerance_pt=max(median_h * 0.55, 1.0),
    )


def calibrate_dimension_layout(page: Any) -> DimensionLayoutCalibration:
    """Derive spatial association tolerances from this page's own typography."""
    heights = [
        float(w[3] - w[1])
        for w in _native_words(page)
        if float(w[3] - w[1]) > 0
    ]
    return calibrate_dimension_layout_from_word_heights(heights)


def _xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def extract_vector_segments(
    page: Any,
    *,
    page_num: int,
    view_id: str = "",
) -> list[ObservedGeometrySegment]:
    """Extract native vector line segments without assigning construction meaning."""
    segments: list[ObservedGeometrySegment] = []
    for path_index, path in enumerate(_native_drawings(page)):
        for item_index, item in enumerate(path.get("items", [])):
            if not item:
                continue
            kind = item[0]
            if kind == "l" and len(item) >= 3:
                start, end = _xy(item[1]), _xy(item[2])
                if start == end:
                    continue
                segments.append(
                    ObservedGeometrySegment(
                        segment_id=f"vec_p{page_num}_{path_index}_{item_index}",
                        source_page=page_num,
                        start=start,
                        end=end,
                        view_id=view_id,
                        source_path_index=path_index,
                        stroke_width_pt=(
                            float(path.get("width"))
                            if path.get("width") is not None
                            else None
                        ),
                        stroke_color_rgb=(
                            tuple(float(value) for value in path.get("color")[:3])
                            if isinstance(path.get("color"), (tuple, list))
                            and len(path.get("color")) >= 3
                            else None
                        ),
                    )
                )
            elif kind == "re" and len(item) >= 2:
                rect = item[1]
                x0, y0, x1, y1 = float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
                for edge_index, (start, end) in enumerate((
                    ((x0, y0), (x1, y0)),
                    ((x1, y0), (x1, y1)),
                    ((x1, y1), (x0, y1)),
                    ((x0, y1), (x0, y0)),
                )):
                    if start != end:
                        segments.append(
                            ObservedGeometrySegment(
                                segment_id=f"vec_p{page_num}_{path_index}_{item_index}_e{edge_index}",
                                source_page=page_num,
                                start=start,
                                end=end,
                                view_id=view_id,
                                source_path_index=path_index,
                                stroke_width_pt=(
                                    float(path.get("width"))
                                    if path.get("width") is not None
                                    else None
                                ),
                                stroke_color_rgb=(
                                    tuple(float(value) for value in path.get("color")[:3])
                                    if isinstance(path.get("color"), (tuple, list))
                                    and len(path.get("color")) >= 3
                                    else None
                                ),
                            )
                        )
    return segments


def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def _axis_distance(point: tuple[float, float], segment: ObservedGeometrySegment) -> float:
    if segment.orientation == DimensionOrientation.HORIZONTAL.value:
        return abs(point[1] - (segment.start[1] + segment.end[1]) / 2.0)
    if segment.orientation == DimensionOrientation.VERTICAL.value:
        return abs(point[0] - (segment.start[0] + segment.end[0]) / 2.0)
    return float("inf")


def _projection_contains(point: tuple[float, float], segment: ObservedGeometrySegment, margin: float) -> bool:
    if segment.orientation == DimensionOrientation.HORIZONTAL.value:
        lo, hi = sorted((segment.start[0], segment.end[0]))
        return lo - margin <= point[0] <= hi + margin
    if segment.orientation == DimensionOrientation.VERTICAL.value:
        lo, hi = sorted((segment.start[1], segment.end[1]))
        return lo - margin <= point[1] <= hi + margin
    return False


def _intersection_with_perpendicular(
    dimension_line: ObservedGeometrySegment,
    witness: ObservedGeometrySegment,
    tolerance: float,
) -> Optional[tuple[float, float]]:
    if dimension_line.orientation == DimensionOrientation.HORIZONTAL.value and witness.orientation == DimensionOrientation.VERTICAL.value:
        y = (dimension_line.start[1] + dimension_line.end[1]) / 2.0
        x = (witness.start[0] + witness.end[0]) / 2.0
        wy0, wy1 = sorted((witness.start[1], witness.end[1]))
        dx0, dx1 = sorted((dimension_line.start[0], dimension_line.end[0]))
        if wy0 - tolerance <= y <= wy1 + tolerance and dx0 - tolerance <= x <= dx1 + tolerance:
            return x, y
    if dimension_line.orientation == DimensionOrientation.VERTICAL.value and witness.orientation == DimensionOrientation.HORIZONTAL.value:
        x = (dimension_line.start[0] + dimension_line.end[0]) / 2.0
        y = (witness.start[1] + witness.end[1]) / 2.0
        wx0, wx1 = sorted((witness.start[0], witness.end[0]))
        dy0, dy1 = sorted((dimension_line.start[1], dimension_line.end[1]))
        if wx0 - tolerance <= x <= wx1 + tolerance and dy0 - tolerance <= y <= dy1 + tolerance:
            return x, y
    return None


def _merge_text_split_line_fragments(
    observation_bbox: tuple[float, float, float, float],
    seg_a: ObservedGeometrySegment,
    seg_b: ObservedGeometrySegment,
    *,
    axis_tolerance: float,
    text_margin: float,
) -> Optional[ObservedGeometrySegment]:
    """Merge two same-orientation, same-axis-coordinate line fragments into
    one logical dimension line when the gap between them is consistent with
    the observation's own figured-dimension text sitting directly on the
    line (a common CAD convention: the line is drawn right up to the text
    bbox on each side, breaking one visual line into two vector fragments).

    Never merges fragments whose gap does not bracket the observation's own
    text -- two genuinely separate, merely coincidentally-aligned dimension
    lines elsewhere on the page must not be merged. Overlapping fragments
    (not a clean split) are also refused.
    """
    if seg_a.orientation != seg_b.orientation:
        return None
    orientation = seg_a.orientation
    if orientation not in (DimensionOrientation.HORIZONTAL.value, DimensionOrientation.VERTICAL.value):
        return None

    if orientation == DimensionOrientation.HORIZONTAL.value:
        axis_a = (seg_a.start[1] + seg_a.end[1]) / 2.0
        axis_b = (seg_b.start[1] + seg_b.end[1]) / 2.0
        along_a = sorted((seg_a.start[0], seg_a.end[0]))
        along_b = sorted((seg_b.start[0], seg_b.end[0]))
        text_lo, text_hi = observation_bbox[0], observation_bbox[2]
    else:
        axis_a = (seg_a.start[0] + seg_a.end[0]) / 2.0
        axis_b = (seg_b.start[0] + seg_b.end[0]) / 2.0
        along_a = sorted((seg_a.start[1], seg_a.end[1]))
        along_b = sorted((seg_b.start[1], seg_b.end[1]))
        text_lo, text_hi = observation_bbox[1], observation_bbox[3]

    if abs(axis_a - axis_b) > axis_tolerance:
        return None

    if along_a[1] <= along_b[0]:
        gap_lo, gap_hi = along_a[1], along_b[0]
        far_lo, far_hi = along_a[0], along_b[1]
    elif along_b[1] <= along_a[0]:
        gap_lo, gap_hi = along_b[1], along_a[0]
        far_lo, far_hi = along_b[0], along_a[1]
    else:
        return None  # overlapping fragments -- not a clean text-gap split

    # The gap between the two fragments must bracket the observation's own
    # text span (the reason the line was split in the first place), and must
    # not be so much larger than the text that unrelated line ends elsewhere
    # on the page are being stitched together.
    if not (gap_lo <= text_hi + text_margin and gap_hi >= text_lo - text_margin):
        return None
    if (gap_hi - gap_lo) > (text_hi - text_lo) + 2.0 * text_margin:
        return None

    merged_axis = (axis_a + axis_b) / 2.0
    merged_id = f"{seg_a.segment_id}+{seg_b.segment_id}"
    if orientation == DimensionOrientation.HORIZONTAL.value:
        start, end = (far_lo, merged_axis), (far_hi, merged_axis)
    else:
        start, end = (merged_axis, far_lo), (merged_axis, far_hi)
    return ObservedGeometrySegment(
        segment_id=merged_id,
        source_page=seg_a.source_page,
        start=start,
        end=end,
        coordinate_space=seg_a.coordinate_space,
        view_id=seg_a.view_id or seg_b.view_id,
    )


def _segment_source_luminance(
    segment: ObservedGeometrySegment,
) -> Optional[float]:
    color = segment.stroke_color_rgb
    if color is None or len(color) != 3:
        return None
    if not all(math.isfinite(float(value)) for value in color):
        return None
    return (float(color[0]) + float(color[1]) + float(color[2])) / 3.0


def _strict_style_dominator(
    candidates: Sequence[ObservedGeometrySegment],
) -> Optional[ObservedGeometrySegment]:
    """Return one strict darker+thicker source-graphic-state winner.

    This is deliberately a tie-breaker, never a primary dimension detector.
    Equal, missing, or mixed source style remains ambiguous.
    """
    if len(candidates) < 2:
        return candidates[0] if candidates else None
    winners: list[ObservedGeometrySegment] = []
    for candidate in candidates:
        width = candidate.stroke_width_pt
        luminance = _segment_source_luminance(candidate)
        if (
            width is None
            or not math.isfinite(float(width))
            or float(width) <= 0.0
            or luminance is None
        ):
            continue
        dominates = True
        for other in candidates:
            if other is candidate:
                continue
            other_width = other.stroke_width_pt
            other_luminance = _segment_source_luminance(other)
            if (
                other_width is None
                or not math.isfinite(float(other_width))
                or float(other_width) <= 0.0
                or other_luminance is None
                or not (float(width) > float(other_width) + 1e-9)
                or not (luminance < other_luminance - 1e-9)
            ):
                dominates = False
                break
        if dominates:
            winners.append(candidate)
    return winners[0] if len(winners) == 1 else None


def bind_observation_to_vector_geometry(
    observation: DimensionObservation,
    segments: Sequence[ObservedGeometrySegment],
    calibration: DimensionLayoutCalibration,
    *,
    text_orientation_hint: Optional[str] = None,
) -> DimensionAnchorBinding:
    """Bind one figured dimension to a unique nearby dimension/witness-line system."""
    if observation.bbox is None:
        return DimensionAnchorBinding(observation.dimension_id, BindingStatus.UNSUPPORTED.value, notes=["observation has no PDF-space bbox"])
    center = _bbox_center(observation.bbox)
    same_scope = [
        s for s in segments
        if s.source_page == observation.source_page
        and s.coordinate_space == CoordinateSpace.PDF_POINTS.value
        and (not observation.view_id or not s.view_id or s.view_id == observation.view_id)
        and s.orientation != DimensionOrientation.UNKNOWN.value
    ]
    candidates = [
        s for s in same_scope
        if _axis_distance(center, s) <= calibration.line_search_distance_pt
        and _projection_contains(center, s, calibration.line_search_distance_pt)
    ]
    if not candidates:
        return DimensionAnchorBinding(observation.dimension_id, BindingStatus.UNSUPPORTED.value, notes=["no nearby axis-aligned vector dimension line"])

    tie_tolerance = calibration.median_word_height_pt * 0.25
    if text_orientation_hint in (
        DimensionOrientation.HORIZONTAL.value,
        DimensionOrientation.VERTICAL.value,
    ):
        hinted = [
            candidate
            for candidate in candidates
            if candidate.orientation == text_orientation_hint
        ]
        if len(hinted) >= 2:
            hinted.sort(key=lambda s: (_axis_distance(center, s), -s.length, s.segment_id))
            hinted_best = _axis_distance(center, hinted[0])
            hinted_tied = [
                candidate
                for candidate in hinted
                if abs(_axis_distance(center, candidate) - hinted_best) <= tie_tolerance
            ]
            # Native text direction is a tie-break hint only. It may narrow the
            # universe when same-orientation source geometry is itself ambiguous
            # and source graphic state independently proves one strict winner.
            # It must never create a binding by suppressing one perpendicular
            # nearby primitive.
            if (
                len(hinted_tied) >= 2
                and _strict_style_dominator(hinted_tied) is not None
            ):
                candidates = hinted

    candidates.sort(key=lambda s: (_axis_distance(center, s), -s.length, s.segment_id))
    best = candidates[0]
    if len(candidates) > 1:
        d0 = _axis_distance(center, candidates[0])
        tied = [
            candidate
            for candidate in candidates
            if abs(_axis_distance(center, candidate) - d0) <= tie_tolerance
        ]
        if len(tied) > 1:
            # A dimension line is frequently exported as two collinear vector
            # fragments split by its own text. Preserve that exact special case.
            merged = (
                _merge_text_split_line_fragments(
                    observation.bbox,
                    tied[0],
                    tied[1],
                    axis_tolerance=calibration.chain_axis_tolerance_pt,
                    text_margin=calibration.median_word_height_pt,
                )
                if len(tied) == 2
                else None
            )
            if merged is not None:
                best = merged
            else:
                # Native graphic state may prove that one near-tied line is a
                # foreground drafting primitive while every competitor is both
                # lighter and thinner. This is only a strict tie-break; absent
                # unanimous dominance, preserve the historical abstention.
                style_winner = _strict_style_dominator(tied)
                if style_winner is None:
                    return DimensionAnchorBinding(
                        observation.dimension_id,
                        BindingStatus.AMBIGUOUS.value,
                        notes=[
                            "multiple equally plausible dimension lines: "
                            + ", ".join(item.segment_id for item in tied)
                        ],
                    )
                best = style_winner

    witness_hits: list[tuple[ObservedGeometrySegment, tuple[float, float]]] = []
    for segment in same_scope:
        if segment.segment_id == best.segment_id:
            continue
        intersection = _intersection_with_perpendicular(best, segment, calibration.witness_endpoint_distance_pt)
        if intersection is not None:
            witness_hits.append((segment, intersection))

    # Collapse multiple vector fragments at effectively the same witness
    # coordinate; vector exporters commonly split one visual line into pieces.
    # Prefer a positively stroked drafting primitive over an unstroked/fill-only
    # representative inside the same tolerance cluster. This changes only the
    # representative provenance, never cluster membership or tolerance.
    def _positive_stroke(segment: ObservedGeometrySegment) -> bool:
        width = segment.stroke_width_pt
        return (
            width is not None
            and math.isfinite(float(width))
            and float(width) > 0.0
            and segment.stroke_color_rgb is not None
        )

    unique_hits: list[tuple[ObservedGeometrySegment, tuple[float, float]]] = []
    for segment, point in sorted(witness_hits, key=lambda h: (h[1][0], h[1][1], h[0].segment_id)):
        match_index = next(
            (
                index
                for index, (_prior_segment, prior_point) in enumerate(unique_hits)
                if math.hypot(point[0] - prior_point[0], point[1] - prior_point[1])
                <= calibration.witness_endpoint_distance_pt
            ),
            None,
        )
        if match_index is None:
            unique_hits.append((segment, point))
            continue
        prior_segment, _prior_point = unique_hits[match_index]
        if _positive_stroke(segment) and not _positive_stroke(prior_segment):
            unique_hits[match_index] = (segment, point)

    if best.orientation == DimensionOrientation.HORIZONTAL.value:
        unique_hits.sort(key=lambda h: h[1][0])
    else:
        unique_hits.sort(key=lambda h: h[1][1])

    if len(unique_hits) >= 2:
        first, last = unique_hits[0], unique_hits[-1]
        return DimensionAnchorBinding(
            observation.dimension_id,
            BindingStatus.WITNESS_BOUND.value,
            dimension_line_id=best.segment_id,
            witness_line_ids=(first[0].segment_id, last[0].segment_id),
            endpoints=(first[1], last[1]),
        )
    if len(unique_hits) == 1:
        return DimensionAnchorBinding(
            observation.dimension_id,
            BindingStatus.PARTIAL_WITNESS.value,
            dimension_line_id=best.segment_id,
            witness_line_ids=(unique_hits[0][0].segment_id,),
            notes=["only one witness/extension line resolved"],
        )
    return DimensionAnchorBinding(
        observation.dimension_id,
        BindingStatus.LINE_BOUND.value,
        dimension_line_id=best.segment_id,
        notes=["dimension line resolved but witness/extension endpoints did not"],
    )


def _same_line_preceding_context(
    words: Sequence[object],
    index: int,
    *,
    max_words: int = 2,
) -> str:
    """Return immediate preceding native words from the same PDF text line.

    Typed drafting context such as ROOM 300 is meaningful only when the label
    and number share one native line. Using prior words globally can
    misclassify an unrelated dimension on the next line merely because PDF
    extraction order places a room label immediately before it.
    """

    if index <= 0 or index >= len(words) or max_words <= 0:
        return ""
    current = words[index]
    try:
        current_block = int(current[5])  # type: ignore[index]
        current_line = int(current[6])  # type: ignore[index]
    except (IndexError, TypeError, ValueError):
        return ""

    collected: list[str] = []
    for prior in reversed(words[:index]):
        try:
            prior_block = int(prior[5])  # type: ignore[index]
            prior_line = int(prior[6])  # type: ignore[index]
            prior_text = str(prior[4])  # type: ignore[index]
        except (IndexError, TypeError, ValueError):
            break
        if (prior_block, prior_line) != (current_block, current_line):
            break
        collected.append(prior_text)
        if len(collected) >= max_words:
            break
    return " ".join(reversed(collected))


def extract_native_dimension_observations(
    page: Any,
    *,
    page_num: int,
    sheet: str = "",
    view_id: str = "",
    view_type: str = DrawingViewType.UNKNOWN.value,
) -> list[DimensionObservation]:
    """Extract typed native-text figured-dimension candidates from a PDF page."""
    words = list(_native_words(page))
    observations: list[DimensionObservation] = []
    for index, word in enumerate(words):
        text = str(word[4]).strip()
        preceding = _same_line_preceding_context(words, index)
        token = classify_dimension_token(text, preceding_context=preceding)
        if not token.is_linear_dimension:
            continue
        bbox = (float(word[0]), float(word[1]), float(word[2]), float(word[3]))
        observations.append(
            DimensionObservation(
                dimension_id=f"native_dim_p{page_num}_{index}",
                source_page=page_num,
                sheet=sheet,
                view_id=view_id,
                view_type=view_type,
                bbox=bbox,
                raw_text=text,
                value=float(token.value),
                unit=str(token.unit),
                authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                confidence=1.0,
                conflict_state=ConstraintStatus.FULLY_CONSTRAINED.value,
                extraction_method="native_text",
            )
        )
    return observations


def _extract_witness_promoted_yearlike_observations(
    page: Any,
    *,
    page_num: int,
    segments: Sequence[ObservedGeometrySegment],
    calibration: DimensionLayoutCalibration,
    sheet: str = "",
    view_id: str = "",
    view_type: str = DrawingViewType.UNKNOWN.value,
) -> tuple[list[DimensionObservation], list[DimensionAnchorBinding]]:
    """Promote year-shaped bare numbers only after source geometry proves dimension semantics.

    Four-digit values in the 19xx/20xx range remain typed as YEAR everywhere
    else.  In an explicitly geometric drawing view, a candidate may become a
    figured millimetre dimension only when the existing vector binder resolves
    one dimension line plus two witness lines.  Immediate date/revision context
    remains non-dimensional even if nearby linework is present.
    """
    if view_type not in _YEARLIKE_PROMOTION_VIEW_TYPES:
        return [], []

    words = list(_native_words(page))
    alphabetic_word_count_by_line: dict[tuple[int, int], int] = {}
    for candidate in words:
        try:
            line_key = (int(candidate[5]), int(candidate[6]))
            candidate_text = str(candidate[4] or "")
        except (IndexError, TypeError, ValueError):
            continue
        if re.search(r"[A-Za-z]", candidate_text):
            alphabetic_word_count_by_line[line_key] = (
                alphabetic_word_count_by_line.get(line_key, 0) + 1
            )

    promoted: list[DimensionObservation] = []
    bindings: list[DimensionAnchorBinding] = []
    for index, word in enumerate(words):
        text = str(word[4]).strip()
        preceding = " ".join(str(w[4]) for w in words[max(0, index - 2):index])
        token = classify_dimension_token(text, preceding_context=preceding)
        if token.kind != DimensionTokenKind.YEAR.value:
            continue
        if _YEARLIKE_NON_DIMENSION_CONTEXT_RE.search(preceding[-40:]):
            continue

        # A year-shaped value remains non-dimensional when its native text
        # line carries semantic lettering (for example a month/year title
        # block or copyright notice), even if box borders happen to resemble
        # a dimension/witness system. Ambiguous year-shaped values are only
        # eligible when their own text line is otherwise numeric/punctuation.
        try:
            block_no, line_no = int(word[5]), int(word[6])
        except (IndexError, TypeError, ValueError):
            continue
        if alphabetic_word_count_by_line.get((block_no, line_no), 0):
            continue

        match = _BARE_MM_RE.match(token.normalized_text)
        if match is None:
            continue
        cleaned = match.group(1).replace(",", "").replace(".", "")
        if _YEAR_RE.match(cleaned) is None:
            continue
        value = float(cleaned)
        if not math.isfinite(value) or value <= 0.0:
            continue

        bbox = (float(word[0]), float(word[1]), float(word[2]), float(word[3]))
        provisional = DimensionObservation(
            dimension_id=f"native_yearlike_dim_p{page_num}_{index}",
            source_page=page_num,
            sheet=sheet,
            view_id=view_id,
            view_type=view_type,
            bbox=bbox,
            raw_text=text,
            value=value,
            unit="mm",
            authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            confidence=1.0,
            conflict_state=ConstraintStatus.FULLY_CONSTRAINED.value,
            extraction_method="native_text_witness_promoted",
        )
        binding = bind_observation_to_vector_geometry(
            provisional,
            segments,
            calibration,
        )
        if (
            binding.status != BindingStatus.WITNESS_BOUND.value
            or binding.endpoints is None
            or len(binding.witness_line_ids) < 2
        ):
            continue
        promoted.append(apply_anchor_binding(provisional, binding))
        bindings.append(binding)

    return promoted, bindings


def make_ocr_dimension_observation(
    *,
    dimension_id: str,
    raw_text: str,
    bbox_px: tuple[float, float, float, float],
    transform: Optional[RasterCoordinateTransform],
    source_page: int,
    sheet: str = "",
    view_id: str = "",
    view_type: str = DrawingViewType.UNKNOWN.value,
    confidence: float = 0.7,
) -> Optional[DimensionObservation]:
    """Create an OCR candidate only when its coordinate transform is explicit."""
    token = classify_dimension_token(raw_text)
    if not token.is_linear_dimension:
        return None
    if transform is None:
        return None
    bbox = transform.bbox_to_pdf(bbox_px)
    return DimensionObservation(
        dimension_id=dimension_id,
        source_page=source_page,
        sheet=sheet,
        view_id=view_id,
        view_type=view_type,
        bbox=bbox,
        raw_text=raw_text,
        value=float(token.value),
        unit=str(token.unit),
        authority=MeasurementAuthorityType.AI_DETECTED.value,
        confidence=confidence,
        conflict_state=ConstraintStatus.PARTIALLY_CONSTRAINED.value,
        extraction_method="ocr",
    )


def reconcile_candidate_group(
    group_id: str,
    candidates: Sequence[DimensionObservation],
) -> DimensionCandidateGroup:
    """Preserve all candidates while delegating value arbitration to F.13."""
    resolved, status, notes = reconcile_duplicate_observations(candidates)
    return DimensionCandidateGroup(group_id, list(candidates), resolved, status, list(notes))


def apply_anchor_binding(
    observation: DimensionObservation,
    binding: DimensionAnchorBinding,
) -> DimensionObservation:
    """Return a bound copy without mutating the raw evidence object."""
    return DimensionObservation(
        dimension_id=observation.dimension_id,
        source_page=observation.source_page,
        sheet=observation.sheet,
        view_id=observation.view_id,
        view_type=observation.view_type,
        bbox=observation.bbox,
        raw_text=observation.raw_text,
        value=observation.value,
        unit=observation.unit,
        orientation=(
            DimensionOrientation.HORIZONTAL.value
            if binding.endpoints and abs(binding.endpoints[1][0] - binding.endpoints[0][0]) >= abs(binding.endpoints[1][1] - binding.endpoints[0][1])
            else DimensionOrientation.VERTICAL.value
            if binding.endpoints
            else observation.orientation
        ),
        endpoints=binding.endpoints,
        witness_targets=binding.witness_line_ids,
        candidate_geometry_ids=observation.candidate_geometry_ids,
        bound_geometry_id=observation.bound_geometry_id,
        authority=observation.authority,
        confidence=observation.confidence,
        conflict_state=(
            ConstraintStatus.CONFLICT_MANUAL_REVIEW.value
            if binding.status == BindingStatus.AMBIGUOUS.value
            else observation.conflict_state
        ),
        extraction_method=observation.extraction_method,
    )


def evidence_tier_for(
    observation: DimensionObservation,
    binding: Optional[DimensionAnchorBinding],
) -> str:
    if observation.conflict_state == ConstraintStatus.CONFLICT_MANUAL_REVIEW.value:
        return DimensionEvidenceTier.CONFLICT.value
    if observation.extraction_method == "ocr" and binding is None:
        return DimensionEvidenceTier.OCR_ONLY.value
    if binding is None:
        return DimensionEvidenceTier.TEXT_ONLY.value
    if binding.status == BindingStatus.WITNESS_BOUND.value:
        return DimensionEvidenceTier.WITNESS_BOUND.value
    if binding.status in (BindingStatus.LINE_BOUND.value, BindingStatus.PARTIAL_WITNESS.value):
        return DimensionEvidenceTier.LINE_BOUND.value
    if binding.status == BindingStatus.AMBIGUOUS.value:
        return DimensionEvidenceTier.CONFLICT.value
    return DimensionEvidenceTier.TEXT_ONLY.value


def build_chains_from_bound_observations(
    observations: Sequence[DimensionObservation],
    *,
    calibration: DimensionLayoutCalibration,
) -> list[DimensionChain]:
    """Build same-page/view/axis chains from bound or positioned observations."""
    buckets: dict[tuple[int, str, str, int], list[DimensionObservation]] = {}
    for observation in observations:
        if observation.conflict_state == ConstraintStatus.CONFLICT_MANUAL_REVIEW.value:
            continue
        if observation.bbox is None:
            continue
        orientation = observation.orientation
        if orientation == DimensionOrientation.UNKNOWN.value:
            # Native text without anchors remains horizontally row-groupable,
            # preserving the proven F.15 behavior. Vertical semantics require
            # vector anchors rather than guessing from text rotation metadata.
            orientation = DimensionOrientation.HORIZONTAL.value
        center = _bbox_center(observation.bbox)
        axis_coord = center[1] if orientation == DimensionOrientation.HORIZONTAL.value else center[0]
        axis_index = round(axis_coord / calibration.chain_axis_tolerance_pt)
        key = (observation.source_page, observation.view_id, orientation, axis_index)
        buckets.setdefault(key, []).append(observation)

    chains: list[DimensionChain] = []
    for seq, (key, bucket) in enumerate(sorted(buckets.items(), key=lambda kv: kv[0])):
        page_num, view_id, orientation, _ = key
        if orientation == DimensionOrientation.HORIZONTAL.value:
            ordered = sorted(bucket, key=lambda o: _bbox_center(o.bbox)[0] if o.bbox else 0.0)
        else:
            ordered = sorted(bucket, key=lambda o: _bbox_center(o.bbox)[1] if o.bbox else 0.0)
        chains.append(
            DimensionChain(
                chain_id=f"bound_chain_p{page_num}_{seq}",
                view_id=view_id,
                source_page=page_num,
                orientation=orientation,
                observations=ordered,
            )
        )
    return chains


def measure_segment_with_page_scale(
    segment: ObservedGeometrySegment,
    calibration: Optional[ScaleCalibration],
) -> ScaledSegmentMeasurement:
    """Convert PDF-point line length to metres only under a usable same-page scale."""
    if segment.coordinate_space != CoordinateSpace.PDF_POINTS.value:
        return ScaledSegmentMeasurement(segment.segment_id, AuthorityStatus.BLOCKED.value, None, MeasurementAuthorityType.PROVISIONAL.value, ["segment is not in canonical PDF-point coordinates"])
    if calibration is None:
        return ScaledSegmentMeasurement(segment.segment_id, AuthorityStatus.BLOCKED.value, None, MeasurementAuthorityType.PROVISIONAL.value, ["no page scale calibration"])
    if calibration.page_no != segment.source_page:
        return ScaledSegmentMeasurement(segment.segment_id, AuthorityStatus.BLOCKED.value, None, MeasurementAuthorityType.PROVISIONAL.value, ["scale calibration belongs to a different page"])
    status = measurement_authority_for_page_scale(calibration)
    if status == AuthorityStatus.BLOCKED.value or calibration.px_per_m <= 0:
        return ScaledSegmentMeasurement(segment.segment_id, AuthorityStatus.BLOCKED.value, None, MeasurementAuthorityType.PROVISIONAL.value, list(calibration.issues))
    return ScaledSegmentMeasurement(
        segment.segment_id,
        status,
        segment.length / calibration.px_per_m,
        MeasurementAuthorityType.PDF_SCALED.value,
        list(calibration.issues),
    )


def extract_dimension_evidence_bundle(
    page: Any,
    *,
    page_num: int,
    sheet: str = "",
    view_id: str = "",
    view_type: str = DrawingViewType.UNKNOWN.value,
    ocr_candidates: Iterable[DimensionObservation] = (),
) -> DimensionEvidenceBundle:
    """Extract native/vector evidence, bind candidates, preserve OCR, and form chains."""
    layout = calibrate_dimension_layout(page)
    segments = extract_vector_segments(page, page_num=page_num, view_id=view_id)
    native = extract_native_dimension_observations(
        page,
        page_num=page_num,
        sheet=sheet,
        view_id=view_id,
        view_type=view_type,
    )
    native_words = list(_native_words(page))
    word_orientations = _native_word_orientations(page)
    orientation_hints: dict[str, str] = {}
    prefix = f"native_dim_p{page_num}_"
    for observation in native:
        if not observation.dimension_id.startswith(prefix):
            continue
        try:
            word_index = int(observation.dimension_id[len(prefix):])
            word = native_words[word_index]
            hint = word_orientations.get((int(word[5]), int(word[6])))
        except (IndexError, TypeError, ValueError):
            hint = None
        if hint in (
            DimensionOrientation.HORIZONTAL.value,
            DimensionOrientation.VERTICAL.value,
        ):
            orientation_hints[observation.dimension_id] = hint

    bindings: list[DimensionAnchorBinding] = []
    bound_native: list[DimensionObservation] = []
    for observation in native:
        binding = bind_observation_to_vector_geometry(
            observation,
            segments,
            layout,
            text_orientation_hint=orientation_hints.get(observation.dimension_id),
        )
        bindings.append(binding)
        bound_native.append(apply_anchor_binding(observation, binding))

    promoted_yearlike, promoted_bindings = _extract_witness_promoted_yearlike_observations(
        page,
        page_num=page_num,
        segments=segments,
        calibration=layout,
        sheet=sheet,
        view_id=view_id,
        view_type=view_type,
    )
    bound_native.extend(promoted_yearlike)
    bindings.extend(promoted_bindings)

    observations = bound_native + list(ocr_candidates)
    chains = build_chains_from_bound_observations(bound_native, calibration=layout)
    return DimensionEvidenceBundle(
        observations=observations,
        observed_geometry=segments,
        bindings=bindings,
        chains=chains,
    )
