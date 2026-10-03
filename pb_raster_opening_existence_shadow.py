"""SHADOW-ONLY raster physical-opening existence authority (wall-poche interruption).

Some architectural plan sheets carry the plan itself as a raster underlay and only
annotations (text, dimension chains, title block) as vector. The vector G17
authority cannot see walls, windows or doors on such a sheet, so no compact callout
or label can ever be bound to an independently proven physical opening there.

This module proves, in shadow only, that a physical opening exists from RASTER
geometry alone:

    raster layer (page image placements only, composited at the source's own dpi)
      -> solid wall poche bands (thick ink or uniform fill; thin linework removed)
      -> wall-band interruption: two collinear bands, a clean gap between them
      -> positive opening evidence inside the gap:
            frame lines   two or more thin parallel lines spanning the gap, inside
                          (not on) the wall faces, or
            door swing    a hairline leaf plus a hairline quarter-circle arc whose
                          radius equals the gap, anchored at a jamb
      -> physical opening existence with exact raster lineage

Contract:

* Text, callouts, labels, room names, dimensions, quantities and vector linework are
  never read. Nothing here can mint an opening from an annotation.
* A gap only becomes an opening with positive physical evidence. A bare break, a gap
  with solid mass in it, a gap without both continuing walls, an ambiguous partner or
  overlapping competing candidates ABSTAIN or CONFLICT; every candidate decision is
  retained, never discarded.
* Every threshold is in paper units (points at the page's own render dpi) or is a
  ratio of the wall's own measured thickness. No drawing scale, project, file name,
  page number or coordinate is used.
* The output is never authoritative and never canonical. It is not a
  ``PhysicalOpeningExistenceRecord``; promoting it into G17 needs a separate review
  (see the bridge notes in docs/raster_opening_existence_shadow_report.md).

Nothing in the live extractor, customer path or G17 imports this module.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from typing import Any, Mapping, Optional, Sequence

import cv2
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


RASTER_OPENING_SCHEMA_VERSION = "1.0.0"
RASTER_OPENING_ALGORITHM_VERSION = "raster_poche_interruption_v1"
RASTER_OPENING_RENDER_SPEC = "page_images_only_gray_v1"
RASTER_PHYSICAL_OPENING_EXISTS = "raster_physical_opening_exists"

# page-level reasons
RASTER_LAYER_AVAILABLE = "raster_layer_available"
RASTER_NO_RASTER_LAYER = "raster_no_raster_layer"
RASTER_PAGE_ROTATION_UNSUPPORTED = "raster_page_rotation_unsupported"
RASTER_LAYER_UNREADABLE = "raster_layer_unreadable"
RASTER_LAYER_TOO_LARGE = "raster_layer_too_large"
RASTER_TOO_MANY_WALL_BANDS = "raster_too_many_wall_bands"
RASTER_NO_POCHE_WALL_BANDS = "raster_no_poche_wall_bands"
RASTER_NO_OPENING_CANDIDATES = "raster_no_opening_candidates"
RASTER_OPENING_EXISTENCE_PROVEN = "raster_opening_existence_proven"

# candidate-level reasons
RASTER_FLANKS_NOT_COLLINEAR_BANDS = "raster_flanks_not_collinear_bands"
RASTER_GAP_NOT_CLEAN = "raster_gap_not_clean"
RASTER_GAP_TOO_SMALL = "raster_gap_too_small"
RASTER_NO_OPENING_EVIDENCE = "raster_no_opening_evidence_in_gap"
RASTER_DOOR_SWING_AMBIGUOUS = "raster_door_swing_ambiguous"
RASTER_WALL_FACE_CONTINUES = "raster_wall_face_continues_across_gap"
RASTER_COMPETING_CANDIDATES = "raster_competing_candidates"

EVIDENCE_FRAME_LINES = "frame_lines"
EVIDENCE_DOOR_SWING = "door_swing"

BBox = tuple[float, float, float, float]
PixelBox = tuple[int, int, int, int]

# --- paper-unit constants (points at the page's own render dpi) -----------------
MASS_THRESHOLD = 200            # gray < 200: solid black or uniform mid-gray fill
LINE_THRESHOLD = 160            # gray < 160: drawn thin linework
POCHE_MIN_PT = 2.0              # structuring element for "solid" (thinner is linework)
BAND_MIN_RUN_PT = 4.0           # shortest wall-band run considered
BAND_MAX_THICKNESS_PT = 12.0    # thicker masses are not wall bands
BAND_MIN_ASPECT = 1.5           # band run length over thickness
END_WINDOW_PT = 1.5             # window used to measure the thickness at a band end
END_COVERAGE = 0.8              # fraction of a band end that must be solid
CLEAN_GAP_MAX_PARTIAL = 0.15    # mass between flanks above this is not a clean gap
THICKNESS_OVERLAP = 0.8         # flanks must share this fraction of the thinner band
THICKNESS_TOLERANCE = 0.35      # flank thickness may differ by this fraction
MIN_OPENING_GAP_PT = 8.0        # below ~3 mm on paper a gap cannot carry resolvable symbology
MIN_GAP_THICKNESS_RATIO = 2.0   # gap must be at least this many wall thicknesses
LINE_COVERAGE = 0.8             # a frame line spans this fraction of the gap
MIN_FRAME_LINES = 2
LINE_ROW_PAD_PT = 0.5           # rows searched beyond the band faces for frame lines
ARC_RADIUS_TOLERANCE = 0.15     # swing radius vs gap width
ARC_MIN_COVERAGE = 0.8          # fraction of arc samples that must carry ink
ARC_SAMPLE_STEP_DEG = 2
LEAF_MIN_COVERAGE = 0.9
LEAF_JAMB_PAD_PT = 1.5
DUPLICATE_IOU = 0.9
CONFLICT_IOU = 0.05
MIN_DPI = 100
MAX_DPI = 300
FALLBACK_DPI = 200
MAX_PIXELS = 60_000_000
MIN_PLAN_IMAGE_FRACTION = 0.02
MAX_BAND_PIECES = 4000


@dataclass(frozen=True)
class RasterImagePlacement:
    image_xref: int
    image_sha256: str
    pixel_width: int
    pixel_height: int
    bbox_pt: BBox
    native_dpi: float


@dataclass(frozen=True)
class RasterLayerLineage:
    source_sha256: str
    page_number: int
    render_dpi: int
    pixel_height: int
    pixel_width: int
    placements: tuple[RasterImagePlacement, ...]
    render_spec: str
    algorithm_version: str
    layer_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "page_number": self.page_number,
            "render_dpi": self.render_dpi,
            "pixel_shape": [self.pixel_height, self.pixel_width],
            "placements": [
                {
                    "image_xref": p.image_xref,
                    "image_sha256": p.image_sha256,
                    "pixel_size": [p.pixel_width, p.pixel_height],
                    "bbox_pt": list(p.bbox_pt),
                    "native_dpi": round(p.native_dpi, 3),
                }
                for p in self.placements
            ],
            "render_spec": self.render_spec,
            "algorithm_version": self.algorithm_version,
            "layer_id": self.layer_id,
        }


@dataclass(frozen=True)
class PochePiece:
    """A solid wall-band run measured in the raster layer."""

    axis: str
    box_px: PixelBox
    box_pt: BBox
    thickness_px: int


@dataclass(frozen=True)
class OpeningSymbolEvidence:
    kind: str
    detail: Mapping[str, Any]


@dataclass(frozen=True)
class RasterOpeningExistenceRecord:
    record_id: str
    proposition: str
    status: EvidenceResolutionStatus
    axis: str
    gap_box_px: PixelBox
    gap_box_pt: BBox
    gap_length_pt: float
    band_thickness_pt: float
    flank_a: PochePiece
    flank_b: PochePiece
    symbol_evidence: tuple[OpeningSymbolEvidence, ...]
    layer_id: str
    source_sha256: str
    page_number: int
    render_dpi: int
    algorithm_version: str = RASTER_OPENING_ALGORITHM_VERSION
    schema_version: str = RASTER_OPENING_SCHEMA_VERSION
    shadow_only: bool = True
    authoritative: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "proposition": self.proposition,
            "status": self.status.value,
            "axis": self.axis,
            "gap_box_px": list(self.gap_box_px),
            "gap_box_pt": list(self.gap_box_pt),
            "gap_length_pt": self.gap_length_pt,
            "band_thickness_pt": self.band_thickness_pt,
            "flank_a": {"box_px": list(self.flank_a.box_px), "box_pt": list(self.flank_a.box_pt)},
            "flank_b": {"box_px": list(self.flank_b.box_px), "box_pt": list(self.flank_b.box_pt)},
            "symbol_evidence": [
                {"kind": item.kind, "detail": dict(item.detail)} for item in self.symbol_evidence
            ],
            "layer_id": self.layer_id,
            "source_sha256": self.source_sha256,
            "page_number": self.page_number,
            "render_dpi": self.render_dpi,
            "algorithm_version": self.algorithm_version,
            "schema_version": self.schema_version,
            "shadow_only": self.shadow_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True)
class RasterOpeningDecision:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    axis: str
    gap_box_px: PixelBox
    gap_box_pt: BBox
    flank_a: PochePiece
    flank_b: PochePiece
    symbol_evidence: tuple[OpeningSymbolEvidence, ...] = ()
    record: Optional[RasterOpeningExistenceRecord] = None
    suppressed_duplicates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "axis": self.axis,
            "gap_box_px": list(self.gap_box_px),
            "gap_box_pt": list(self.gap_box_pt),
            "symbol_evidence": [
                {"kind": item.kind, "detail": dict(item.detail)} for item in self.symbol_evidence
            ],
            "record_id": self.record.record_id if self.record is not None else None,
            "suppressed_duplicates": self.suppressed_duplicates,
        }


@dataclass(frozen=True)
class RasterOpeningExistenceResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    page_number: int
    records: tuple[RasterOpeningExistenceRecord, ...] = ()
    decisions: tuple[RasterOpeningDecision, ...] = ()
    lineage: Optional[RasterLayerLineage] = None
    poche_piece_count: int = 0
    shadow_only: bool = True
    authoritative: bool = False
    canonical_publication: bool = False
    schema_version: str = RASTER_OPENING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "page_number": self.page_number,
            "poche_piece_count": self.poche_piece_count,
            "records": [record.to_dict() for record in self.records],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "lineage": self.lineage.to_dict() if self.lineage is not None else None,
            "shadow_only": self.shadow_only,
            "authoritative": self.authoritative,
            "canonical_publication": self.canonical_publication,
        }


def _px(value_pt: float, dpi: int, minimum: int = 1) -> int:
    return max(int(minimum), int(round(float(value_pt) * float(dpi) / 72.0)))


def _odd(value: int) -> int:
    return int(value) if int(value) % 2 == 1 else int(value) + 1


def _pt(value_px: float, dpi: int) -> float:
    return round(float(value_px) * 72.0 / float(dpi), 3)


def _box_pt(box: PixelBox, dpi: int) -> BBox:
    return (
        _pt(box[0], dpi),
        _pt(box[1], dpi),
        _pt(box[2] + 1, dpi),
        _pt(box[3] + 1, dpi),
    )


# ---------------------------------------------------------------------------
# Layer 1: raster layer extraction and solid-band primitives (pixels -> geometry)
# ---------------------------------------------------------------------------


def _band_pieces(
    thick: np.ndarray,
    *,
    dpi: int,
    axis: str,
) -> list[PochePiece]:
    """Solid wall-band runs along ``axis``. Vertical analysis runs on the transpose."""
    work = thick if axis == "horizontal" else np.ascontiguousarray(thick.T)
    run = _odd(_px(BAND_MIN_RUN_PT, dpi))  # even kernels shift morphology output by one pixel
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (run, 1))
    band = cv2.morphologyEx(work, cv2.MORPH_OPEN, kernel)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(band, connectivity=8)
    solid = _px(POCHE_MIN_PT, dpi)
    tmax = _px(BAND_MAX_THICKNESS_PT, dpi)
    pieces: list[PochePiece] = []
    for index in range(1, int(count)):
        x = int(stats[index, cv2.CC_STAT_LEFT])
        y = int(stats[index, cv2.CC_STAT_TOP])
        w = int(stats[index, cv2.CC_STAT_WIDTH])
        h = int(stats[index, cv2.CC_STAT_HEIGHT])
        if h < solid or h > tmax or w < BAND_MIN_ASPECT * h:
            continue
        box = (x, y, x + w - 1, y + h - 1)
        if axis == "vertical":
            box = (box[1], box[0], box[3], box[2])
        pieces.append(
            PochePiece(
                axis=axis,
                box_px=box,
                box_pt=_box_pt(box, dpi),
                thickness_px=h,
            )
        )
    pieces.sort(key=lambda p: (p.axis, p.box_px[1], p.box_px[0], p.box_px[3], p.box_px[2]))
    return pieces


def _end_interval(
    work_thick: np.ndarray,
    piece_box: tuple[int, int, int, int],
    *,
    at_high_end: bool,
    window: int,
) -> Optional[tuple[int, int]]:
    """Local thickness rows at one end of a band, in the analysis (horizontal) frame."""
    x0, y0, x1, y1 = piece_box
    if at_high_end:
        xs = max(x1 - window + 1, 0), x1 + 1
    else:
        xs = x0, min(x0 + window, work_thick.shape[1])
    sub = work_thick[y0 : y1 + 1, xs[0] : xs[1]]
    if sub.size == 0:
        return None
    coverage = sub.mean(axis=1)
    rows = np.where(coverage >= END_COVERAGE)[0]
    if rows.size == 0:
        return None
    return y0 + int(rows.min()), y0 + int(rows.max())


@dataclass(frozen=True)
class _Pair:
    """A candidate wall-band interruption in the horizontal analysis frame."""

    a: tuple[int, int, int, int]
    b: tuple[int, int, int, int]
    gap_x0: int
    gap_x1: int
    row0: int
    row1: int
    thickness_a: int
    thickness_b: int
    reasons: tuple[str, ...]


def _pair_flanks(
    work_thick: np.ndarray,
    boxes: Sequence[tuple[int, int, int, int]],
    *,
    dpi: int,
) -> list[_Pair]:
    window = _px(END_WINDOW_PT, dpi)
    min_gap_floor = _px(MIN_OPENING_GAP_PT, dpi)
    pairs: list[_Pair] = []
    width = work_thick.shape[1]
    box_array = np.asarray(boxes, dtype=np.int64).reshape(-1, 4)
    for a in boxes:
        ax1 = a[2]
        rows = _end_interval(work_thick, a, at_high_end=True, window=window)
        if rows is None:
            continue
        r0, r1 = rows
        start = ax1 + 1
        if start >= width:
            continue
        line = work_thick[r0 : r1 + 1, :].mean(axis=0)
        tail = line[start:]
        solid_hits = np.where(tail >= END_COVERAGE)[0]
        partial_hits = np.where(tail > CLEAN_GAP_MAX_PARTIAL)[0]
        if solid_hits.size == 0:
            continue  # free end with no collinear partner: not a candidate
        position = start + int(solid_hits[0])
        # the partner band must be one of the measured bands that contains `position`
        hit = np.where(
            (box_array[:, 0] <= position)
            & (position <= box_array[:, 2])
            & ~((box_array[:, 3] < r0) | (box_array[:, 1] > r1))
        )[0]
        if hit.size == 0:
            continue
        partner = tuple(int(v) for v in box_array[int(hit[0])])
        reasons: list[str] = []
        if partial_hits.size and start + int(partial_hits[0]) < position:
            reasons.append(RASTER_GAP_NOT_CLEAN)
        b_rows = _end_interval(work_thick, partner, at_high_end=False, window=window)
        if b_rows is None:
            continue
        c0, c1 = max(r0, b_rows[0]), min(r1, b_rows[1])
        t_a = r1 - r0 + 1
        t_b = b_rows[1] - b_rows[0] + 1
        if (
            c1 < c0
            or (c1 - c0 + 1) < THICKNESS_OVERLAP * min(t_a, t_b)
            or abs(t_a - t_b) > THICKNESS_TOLERANCE * max(t_a, t_b)
        ):
            reasons.append(RASTER_FLANKS_NOT_COLLINEAR_BANDS)
        gap_x0 = ax1 + 1
        gap_x1 = position - 1
        gap = gap_x1 - gap_x0 + 1
        thickness = max(min(t_a, t_b), 1)
        if gap < max(min_gap_floor, int(math.ceil(MIN_GAP_THICKNESS_RATIO * thickness))):
            reasons.append(RASTER_GAP_TOO_SMALL)
        if gap < 1:
            continue
        pairs.append(
            _Pair(
                a=a,
                b=partner,
                gap_x0=gap_x0,
                gap_x1=gap_x1,
                row0=c0 if c1 >= c0 else r0,
                row1=c1 if c1 >= c0 else r1,
                thickness_a=t_a,
                thickness_b=t_b,
                reasons=tuple(dict.fromkeys(reasons)),
            )
        )
    return pairs


# ---------------------------------------------------------------------------
# Layer 2: positive opening evidence inside the gap
# ---------------------------------------------------------------------------


def _frame_lines(
    line_mask: np.ndarray,
    pair: _Pair,
    *,
    dpi: int,
) -> Optional[OpeningSymbolEvidence]:
    pad = _px(LINE_ROW_PAD_PT, dpi, minimum=1)
    height = line_mask.shape[0]
    r0 = max(pair.row0 - pad, 0)
    r1 = min(pair.row1 + pad, height - 1)
    x0, x1 = pair.gap_x0, pair.gap_x1
    region = line_mask[r0 : r1 + 1, x0 : x1 + 1]
    if region.size == 0:
        return None
    coverage = region.mean(axis=1)
    rows = coverage >= LINE_COVERAGE
    lines: list[tuple[int, int]] = []
    start: Optional[int] = None
    for index, flag in enumerate(rows.tolist() + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            lines.append((r0 + start, r0 + index - 1))
            start = None
    if len(lines) < MIN_FRAME_LINES:
        return None
    return OpeningSymbolEvidence(
        kind=EVIDENCE_FRAME_LINES,
        detail={
            "line_rows_px": [list(item) for item in lines],
            "line_count": len(lines),
            "gap_coverage_min": LINE_COVERAGE,
        },
    )


def _wall_face_continues(line_mask: np.ndarray, pair: _Pair) -> bool:
    """True when either wall face keeps ink across the gap (outline, not interruption).

    A through-opening interrupts both wall faces and draws its frame inside them. A
    recess (niche), a glazing ribbon or a dashed pattern keeps the band's outline on
    the faces while only the interior is clear, so it must not read as an opening.
    """
    x0, x1 = pair.gap_x0, pair.gap_x1
    height = line_mask.shape[0]
    for row in (pair.row0, pair.row1):
        if 0 <= row < height and float(line_mask[row, x0 : x1 + 1].mean()) >= LINE_COVERAGE:
            return True
    return False


def _hairline_mask(line_mask: np.ndarray, thick: np.ndarray) -> np.ndarray:
    """Ink that is neither poche nor touching it.

    A door leaf and its swing are drawn thinner than the wall. Strokes as heavy as the
    poche are lettering or hatching, not opening symbols.
    """
    halo = cv2.dilate(thick, np.ones((3, 3), np.uint8))
    return (line_mask & (halo == 0)).astype(np.uint8)


def _arc_coverage(
    thin_mask: np.ndarray,
    center: tuple[float, float],
    radius: float,
    *,
    side: int,
    direction: int,
) -> float:
    """Fraction of quarter-circle samples carrying hairline ink (analysis frame, y down)."""
    height, width = thin_mask.shape
    hits = 0
    total = 0
    cx, cy = center
    for degrees in range(0, 91, ARC_SAMPLE_STEP_DEG):
        theta = math.radians(degrees)
        x = cx + direction * radius * math.cos(theta)
        y = cy + side * radius * math.sin(theta)
        xi, yi = int(round(x)), int(round(y))
        total += 1
        if (
            1 <= xi < width - 1
            and 1 <= yi < height - 1
            and thin_mask[yi - 1 : yi + 2, xi - 1 : xi + 2].any()
        ):
            hits += 1
    return hits / total if total else 0.0


def _door_swing(
    thin_mask: np.ndarray,
    pair: _Pair,
    *,
    dpi: int,
) -> tuple[Optional[OpeningSymbolEvidence], bool]:
    """Leaf line plus quarter-circle arc of radius equal to the gap, at one jamb.

    Returns (evidence, ambiguous). Two or more distinct hinge/side configurations
    that satisfy the rule are ambiguous and prove nothing.
    """
    gap = pair.gap_x1 - pair.gap_x0 + 1
    pad = _px(LEAF_JAMB_PAD_PT, dpi)
    found: list[dict[str, Any]] = []
    for hinge, hinge_x, direction in (
        ("low", pair.gap_x0, 1),
        ("high", pair.gap_x1, -1),
    ):
        for side, face_y in ((-1, pair.row0), (1, pair.row1)):
            best: Optional[tuple[float, int]] = None
            low_r = max(int(math.ceil(gap * (1.0 - ARC_RADIUS_TOLERANCE))), 2)
            high_r = int(math.floor(gap * (1.0 + ARC_RADIUS_TOLERANCE)))
            for radius in range(low_r, high_r + 1):
                coverage = _arc_coverage(
                    thin_mask,
                    (float(hinge_x), float(face_y)),
                    float(radius),
                    side=side,
                    direction=direction,
                )
                if best is None or coverage > best[0]:
                    best = (coverage, radius)
            if best is None or best[0] < ARC_MIN_COVERAGE:
                continue
            coverage, radius = best
            # the leaf: a thin line along the hinge jamb, perpendicular to the band
            leaf_x0 = hinge_x - pad
            leaf_x1 = hinge_x + pad
            if side == -1:
                ys = slice(max(face_y - radius, 0), face_y)
            else:
                ys = slice(face_y + 1, min(face_y + 1 + radius, thin_mask.shape[0]))
            strip = thin_mask[ys, max(leaf_x0, 0) : leaf_x1 + 1]
            if strip.size == 0:
                continue
            leaf_cov = float(strip.any(axis=1).mean())
            if leaf_cov < LEAF_MIN_COVERAGE:
                continue
            found.append(
                {
                    "hinge_end": hinge,
                    "swing_side": "low_rows" if side == -1 else "high_rows",
                    "radius_px": int(radius),
                    "arc_coverage": round(coverage, 3),
                    "leaf_coverage": round(leaf_cov, 3),
                }
            )
    if not found:
        return None, False
    if len(found) > 1:
        return None, True
    return OpeningSymbolEvidence(kind=EVIDENCE_DOOR_SWING, detail=found[0]), False


# ---------------------------------------------------------------------------
# Decisions, deduplication, conflicts, ids
# ---------------------------------------------------------------------------


def _iou(a: PixelBox, b: PixelBox) -> float:
    ix = min(a[2], b[2]) - max(a[0], b[0]) + 1
    iy = min(a[3], b[3]) - max(a[1], b[1]) + 1
    if ix <= 0 or iy <= 0:
        return 0.0
    inter = ix * iy
    area_a = (a[2] - a[0] + 1) * (a[3] - a[1] + 1)
    area_b = (b[2] - b[0] + 1) * (b[3] - b[1] + 1)
    return inter / float(area_a + area_b - inter)


def _record_id(
    *,
    layer_id: str,
    axis: str,
    gap_box_px: PixelBox,
    flank_a: PixelBox,
    flank_b: PixelBox,
) -> str:
    return stable_contract_id(
        "raster_physical_opening_existence",
        {
            "schema_version": RASTER_OPENING_SCHEMA_VERSION,
            "algorithm_version": RASTER_OPENING_ALGORITHM_VERSION,
            "layer_id": layer_id,
            "axis": axis,
            "gap_box_px": list(gap_box_px),
            "flank_a_px": list(flank_a),
            "flank_b_px": list(flank_b),
        },
        digest_chars=32,
    )


def _to_page_frame(
    box: tuple[int, int, int, int],
    axis: str,
) -> PixelBox:
    """Analysis-frame box -> page pixel frame (vertical analysis ran transposed)."""
    if axis == "horizontal":
        return box
    return (box[1], box[0], box[3], box[2])


def analyse_raster_layer(
    gray: np.ndarray,
    *,
    dpi: int,
    lineage: RasterLayerLineage,
) -> RasterOpeningExistenceResult:
    """Prove physical openings from a raster layer; pure on pixels, no text, no vector."""
    page_number = lineage.page_number
    if gray.ndim != 2 or gray.size == 0 or gray.dtype != np.uint8:
        return RasterOpeningExistenceResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(RASTER_LAYER_UNREADABLE,),
            page_number=page_number,
            lineage=lineage,
        )
    mass = (gray < MASS_THRESHOLD).astype(np.uint8)
    line_mask = (gray < LINE_THRESHOLD).astype(np.uint8)
    solid = _odd(_px(POCHE_MIN_PT, dpi))
    thick = cv2.morphologyEx(
        mass, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (solid, solid))
    )
    thin_mask = _hairline_mask(line_mask, thick)

    decisions: list[RasterOpeningDecision] = []
    total_pieces = 0
    for axis in ("horizontal", "vertical"):
        pieces = _band_pieces(thick, dpi=dpi, axis=axis)
        total_pieces += len(pieces)
        if len(pieces) > MAX_BAND_PIECES:
            return RasterOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(RASTER_TOO_MANY_WALL_BANDS,),
                page_number=page_number,
                lineage=lineage,
                poche_piece_count=total_pieces,
            )
        if not pieces:
            continue
        if axis == "horizontal":
            work_thick, work_line, work_thin = thick, line_mask, thin_mask
        else:
            work_thick = np.ascontiguousarray(thick.T)
            work_line = np.ascontiguousarray(line_mask.T)
            work_thin = np.ascontiguousarray(thin_mask.T)
        by_box: dict[tuple[int, int, int, int], PochePiece] = {}
        boxes: list[tuple[int, int, int, int]] = []
        for piece in pieces:
            analysis_box = (
                piece.box_px
                if axis == "horizontal"
                else (piece.box_px[1], piece.box_px[0], piece.box_px[3], piece.box_px[2])
            )
            boxes.append(analysis_box)
            by_box[analysis_box] = piece
        for pair in _pair_flanks(work_thick, boxes, dpi=dpi):
            reasons = list(pair.reasons)
            gap_analysis = (pair.gap_x0, pair.row0, pair.gap_x1, pair.row1)
            gap_page = _to_page_frame(gap_analysis, axis)
            flank_a = by_box[pair.a]
            flank_b = by_box[pair.b]
            symbols: list[OpeningSymbolEvidence] = []
            status = EvidenceResolutionStatus.ABSTAINED
            if not reasons:
                frame = _frame_lines(work_line, pair, dpi=dpi)
                face_continues = frame is not None and _wall_face_continues(work_line, pair)
                if frame is not None and not face_continues:
                    symbols.append(frame)
                swing, ambiguous = (None, False)
                if not symbols:
                    swing, ambiguous = _door_swing(work_thin, pair, dpi=dpi)
                if swing is not None:
                    symbols.append(swing)
                if ambiguous and not symbols:
                    reasons.append(RASTER_DOOR_SWING_AMBIGUOUS)
                    status = EvidenceResolutionStatus.CONFLICT
                elif face_continues and not symbols:
                    reasons.append(RASTER_WALL_FACE_CONTINUES)
                elif not symbols:
                    reasons.append(RASTER_NO_OPENING_EVIDENCE)
            record: Optional[RasterOpeningExistenceRecord] = None
            if not reasons and symbols:
                status = EvidenceResolutionStatus.CORROBORATED
                reasons.append(RASTER_OPENING_EXISTENCE_PROVEN)
                gap_length = pair.gap_x1 - pair.gap_x0 + 1
                record = RasterOpeningExistenceRecord(
                    record_id=_record_id(
                        layer_id=lineage.layer_id,
                        axis=axis,
                        gap_box_px=gap_page,
                        flank_a=flank_a.box_px,
                        flank_b=flank_b.box_px,
                    ),
                    proposition=RASTER_PHYSICAL_OPENING_EXISTS,
                    status=status,
                    axis=axis,
                    gap_box_px=gap_page,
                    gap_box_pt=_box_pt(gap_page, dpi),
                    gap_length_pt=_pt(gap_length, dpi),
                    band_thickness_pt=_pt(min(pair.thickness_a, pair.thickness_b), dpi),
                    flank_a=flank_a,
                    flank_b=flank_b,
                    symbol_evidence=tuple(symbols),
                    layer_id=lineage.layer_id,
                    source_sha256=lineage.source_sha256,
                    page_number=page_number,
                    render_dpi=dpi,
                )
            decisions.append(
                RasterOpeningDecision(
                    status=status,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    axis=axis,
                    gap_box_px=gap_page,
                    gap_box_pt=_box_pt(gap_page, dpi),
                    flank_a=flank_a,
                    flank_b=flank_b,
                    symbol_evidence=tuple(symbols),
                    record=record,
                )
            )

    decisions = _suppress_duplicates_and_conflicts(decisions)
    decisions.sort(key=lambda d: (d.gap_box_px[1], d.gap_box_px[0], d.axis, d.gap_box_px[3], d.gap_box_px[2]))
    records = tuple(d.record for d in decisions if d.record is not None)
    if records:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (RASTER_OPENING_EXISTENCE_PROVEN,)
    elif any(d.status is EvidenceResolutionStatus.CONFLICT for d in decisions):
        status = EvidenceResolutionStatus.CONFLICT
        reasons = tuple(
            sorted(
                {
                    code
                    for d in decisions
                    if d.status is EvidenceResolutionStatus.CONFLICT
                    for code in d.reason_codes
                }
            )
        )
    elif total_pieces == 0:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (RASTER_NO_POCHE_WALL_BANDS,)
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (RASTER_NO_OPENING_CANDIDATES,)
    return RasterOpeningExistenceResult(
        status=status,
        reason_codes=reasons,
        page_number=page_number,
        records=records,
        decisions=tuple(decisions),
        lineage=lineage,
        poche_piece_count=total_pieces,
    )


def _suppress_duplicates_and_conflicts(
    decisions: list[RasterOpeningDecision],
) -> list[RasterOpeningDecision]:
    """Identical evidence collapses to one decision; competing readings all CONFLICT.

    Duplicates (the same gap read twice) keep the decision that carries a record when
    there is one, and count what they absorbed. Proven decisions whose gaps overlap
    are two readings of one void: every one of them is withdrawn to CONFLICT.
    """
    ordered = sorted(
        decisions,
        key=lambda d: (d.gap_box_px[1], d.gap_box_px[0], d.axis, d.gap_box_px[3], d.gap_box_px[2]),
    )
    groups: list[list[RasterOpeningDecision]] = []
    for decision in ordered:
        for group in groups:
            if _iou(decision.gap_box_px, group[0].gap_box_px) >= DUPLICATE_IOU:
                group.append(decision)
                break
        else:
            groups.append([decision])
    kept: list[RasterOpeningDecision] = []
    for group in groups:
        chosen = next((d for d in group if d.record is not None), group[0])
        if len(group) > 1:
            chosen = replace(chosen, suppressed_duplicates=len(group) - 1)
        kept.append(chosen)
    proven = [d for d in kept if d.record is not None]
    conflicted: set[int] = set()
    for i, first in enumerate(proven):
        for second in proven[i + 1 :]:
            if _iou(first.gap_box_px, second.gap_box_px) > CONFLICT_IOU:
                conflicted.add(id(first))
                conflicted.add(id(second))
    if not conflicted:
        return kept
    return [
        replace(
            decision,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(RASTER_COMPETING_CANDIDATES,),
            record=None,
        )
        if id(decision) in conflicted
        else decision
        for decision in kept
    ]


# ---------------------------------------------------------------------------
# Raster layer extraction from a PDF page (page image placements only)
# ---------------------------------------------------------------------------


def _native_dpi(info: Mapping[str, Any], pixel_w: int, pixel_h: int, width_pt: float, height_pt: float) -> float:
    """Pixels per inch of one image placement, from its own matrix.

    A placement rotated a quarter turn swaps width and height in its page bbox, so the
    bbox alone would misstate the resolution; the matrix columns are the image axes.
    """
    transform = info.get("transform")
    try:
        a, b, c, d = (float(v) for v in tuple(transform)[:4])  # type: ignore[arg-type]
        scale_x, scale_y = math.hypot(a, b), math.hypot(c, d)
    except (TypeError, ValueError):
        scale_x, scale_y = width_pt, height_pt
    if scale_x <= 0.0 or scale_y <= 0.0:
        return 0.0
    return max(pixel_w / scale_x, pixel_h / scale_y) * 72.0


def extract_raster_layer(
    doc: Any,
    page_index: int,
    *,
    source_sha256: str,
) -> tuple[Optional[np.ndarray], Optional[RasterLayerLineage], tuple[str, ...]]:
    """Render ONLY the page's image placements to gray at the source's own dpi.

    Text, vector paths and annotations are removed from an in-memory copy first, so
    nothing but the embedded raster layer can reach the geometry analysis.
    """
    import fitz

    try:
        page = doc[page_index]
        if int(getattr(page, "rotation", 0) or 0) != 0:
            return None, None, (RASTER_PAGE_ROTATION_UNSUPPORTED,)
        infos = list(page.get_image_info(xrefs=True) or [])
    except Exception:  # noqa: BLE001
        return None, None, (RASTER_LAYER_UNREADABLE,)
    if not infos:
        return None, None, (RASTER_NO_RASTER_LAYER,)

    page_area = float(page.rect.width) * float(page.rect.height)
    placements: list[RasterImagePlacement] = []
    native: list[float] = []
    for info in infos:
        try:
            bbox = tuple(float(v) for v in info["bbox"])
            width_pt = bbox[2] - bbox[0]
            height_pt = bbox[3] - bbox[1]
            xref = int(info.get("xref") or 0)
            pixel_w = int(info.get("width") or 0)
            pixel_h = int(info.get("height") or 0)
            if width_pt <= 0 or height_pt <= 0 or pixel_w <= 0 or pixel_h <= 0:
                continue
            digest = ""
            if xref > 0:
                try:
                    digest = hashlib.sha256(doc.xref_stream_raw(xref)).hexdigest()
                except Exception:  # noqa: BLE001
                    digest = ""
            dpi = _native_dpi(info, pixel_w, pixel_h, width_pt, height_pt)
            if dpi <= 0.0:
                continue
            placements.append(
                RasterImagePlacement(
                    image_xref=xref,
                    image_sha256=digest,
                    pixel_width=pixel_w,
                    pixel_height=pixel_h,
                    bbox_pt=tuple(round(v, 3) for v in bbox),  # type: ignore[arg-type]
                    native_dpi=dpi,
                )
            )
            if width_pt * height_pt >= MIN_PLAN_IMAGE_FRACTION * page_area:
                native.append(dpi)
        except Exception:  # noqa: BLE001
            continue
    if not placements:
        return None, None, (RASTER_LAYER_UNREADABLE,)
    placements.sort(key=lambda p: (p.bbox_pt, p.image_xref))
    dpi = int(round(max(native))) if native else FALLBACK_DPI
    dpi = min(max(dpi, MIN_DPI), MAX_DPI)
    width_px = int(math.ceil(float(page.rect.width) * dpi / 72.0))
    height_px = int(math.ceil(float(page.rect.height) * dpi / 72.0))
    if width_px * height_px > MAX_PIXELS:
        return None, None, (RASTER_LAYER_TOO_LARGE,)

    try:
        scratch = fitz.open()
        scratch.insert_pdf(doc, from_page=page_index, to_page=page_index)
        copy = scratch[0]
        copy.add_redact_annot(copy.rect, fill=False)
        copy.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=fitz.PDF_REDACT_TEXT_REMOVE,
        )
        pixmap = copy.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False, annots=False)
        gray = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width).copy()
        scratch.close()
    except Exception:  # noqa: BLE001
        return None, None, (RASTER_LAYER_UNREADABLE,)

    layer_id = stable_contract_id(
        "raster_layer",
        {
            "source_sha256": str(source_sha256),
            "page_number": int(page_index) + 1,
            "render_dpi": dpi,
            "render_spec": RASTER_OPENING_RENDER_SPEC,
            "algorithm_version": RASTER_OPENING_ALGORITHM_VERSION,
            "placements": [
                [p.image_xref, p.image_sha256, list(p.bbox_pt)] for p in placements
            ],
        },
        digest_chars=32,
    )
    lineage = RasterLayerLineage(
        source_sha256=str(source_sha256),
        page_number=int(page_index) + 1,
        render_dpi=dpi,
        pixel_height=int(gray.shape[0]),
        pixel_width=int(gray.shape[1]),
        placements=tuple(placements),
        render_spec=RASTER_OPENING_RENDER_SPEC,
        algorithm_version=RASTER_OPENING_ALGORITHM_VERSION,
        layer_id=layer_id,
    )
    return gray, lineage, (RASTER_LAYER_AVAILABLE,)


def propose_raster_opening_existence(
    doc: Any,
    page_index: int,
    *,
    source_sha256: str,
) -> RasterOpeningExistenceResult:
    """Shadow proposal of physical openings proven from one page's raster layer."""
    page_number = int(page_index) + 1
    gray, lineage, reasons = extract_raster_layer(doc, page_index, source_sha256=source_sha256)
    if gray is None or lineage is None:
        return RasterOpeningExistenceResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=reasons,
            page_number=page_number,
        )
    return analyse_raster_layer(gray, dpi=lineage.render_dpi, lineage=lineage)


__all__ = [
    "EVIDENCE_DOOR_SWING",
    "EVIDENCE_FRAME_LINES",
    "OpeningSymbolEvidence",
    "PochePiece",
    "RASTER_COMPETING_CANDIDATES",
    "RASTER_NO_OPENING_CANDIDATES",
    "RASTER_NO_POCHE_WALL_BANDS",
    "RASTER_NO_RASTER_LAYER",
    "RASTER_TOO_MANY_WALL_BANDS",
    "RASTER_OPENING_ALGORITHM_VERSION",
    "RASTER_OPENING_EXISTENCE_PROVEN",
    "RASTER_OPENING_SCHEMA_VERSION",
    "RASTER_PHYSICAL_OPENING_EXISTS",
    "RasterImagePlacement",
    "RasterLayerLineage",
    "RasterOpeningDecision",
    "RasterOpeningExistenceRecord",
    "RasterOpeningExistenceResult",
    "analyse_raster_layer",
    "extract_raster_layer",
    "propose_raster_opening_existence",
]
