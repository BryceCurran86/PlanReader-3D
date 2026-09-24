"""Shadow-only binding of raster OCR dimensions to raster line geometry.

This module does not perform quantity publication and does not promote OCR to
FIRM measurement authority.  It consumes source-owned OCR evidence plus
explicit raster-space axis-line observations and preserves enough geometry to
support a later authority review.

The binding rule is intentionally conservative:

* a token must be typed as a linear figured dimension by the existing F.13
  grammar;
* exactly one candidate dimension line may own it;
* that line must terminate at one unique perpendicular witness coordinate at
  each end;
* competing OCR values at the same source position conflict;
* all geometry is transformed into PDF points with the existing
  RasterCoordinateTransform plus an explicit source-image placement offset.

No nearest/first/longest tie-break is used.  Unknown or ambiguous evidence
abstains/conflicts.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence

from pb_figured_dimension_evidence import (
    DimensionOrientation,
    RasterCoordinateTransform,
    classify_dimension_token,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_portable_raster_ocr_authority import OCRLine, RasterOCREvidenceRecord


RASTER_FIGURED_DIMENSION_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class RasterDimensionScope:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    image_id: str
    placement_bbox_pt: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        required = (
            self.document_id,
            self.revision_id,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
            self.image_id,
        )
        if any(not str(value or "").strip() for value in required):
            raise ValueError("document/revision/snapshot/page/viewport/image ownership is required")
        if (
            len(self.source_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.source_sha256)
        ):
            raise ValueError("source_sha256 must be a lower-case SHA-256 digest")
        x0, y0, x1, y1 = self.placement_bbox_pt
        if not all(math.isfinite(float(v)) for v in self.placement_bbox_pt):
            raise ValueError("placement_bbox_pt must be finite")
        if not (x1 > x0 and y1 > y0):
            raise ValueError("placement_bbox_pt must have positive width and height")


@dataclass(frozen=True)
class RasterAxisSegment:
    segment_id: str
    start_px: tuple[float, float]
    end_px: tuple[float, float]

    def __post_init__(self) -> None:
        if not self.segment_id:
            raise ValueError("segment_id is required")
        values = (*self.start_px, *self.end_px)
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError("segment coordinates must be finite")

    @property
    def orientation(self) -> str:
        dx = abs(float(self.end_px[0]) - float(self.start_px[0]))
        dy = abs(float(self.end_px[1]) - float(self.start_px[1]))
        if dx <= 0.0 and dy <= 0.0:
            return DimensionOrientation.UNKNOWN.value
        # Raster line detectors commonly return a one-pixel stair-step for
        # visually axis-aligned strokes.  Use a relative axis check only; no
        # drawing-unit or benchmark-derived magnitude enters this decision.
        if dy <= max(1.0, 0.02 * dx):
            return DimensionOrientation.HORIZONTAL.value
        if dx <= max(1.0, 0.02 * dy):
            return DimensionOrientation.VERTICAL.value
        return DimensionOrientation.UNKNOWN.value


@dataclass(frozen=True)
class RasterDimensionAlternative:
    dimension_line_ids: tuple[str, ...]
    witness_line_ids: tuple[str, ...]
    endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    candidate_id: str


@dataclass(frozen=True)
class RasterFiguredDimensionCandidate:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    raw_text: str
    value_mm: float
    unit: str
    confidence: Optional[float]
    bbox_px: tuple[float, float, float, float]
    bbox_pt: tuple[float, float, float, float]
    orientation: str = DimensionOrientation.UNKNOWN.value
    dimension_line_ids: tuple[str, ...] = ()
    witness_line_ids: tuple[str, ...] = ()
    endpoints_pt: Optional[tuple[tuple[float, float], tuple[float, float]]] = None
    candidate_id: Optional[str] = None
    alternatives: tuple[RasterDimensionAlternative, ...] = ()


@dataclass(frozen=True)
class RasterFiguredDimensionShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope: RasterDimensionScope
    candidates: tuple[RasterFiguredDimensionCandidate, ...]
    quantity_m2: None = None
    schema_version: str = RASTER_FIGURED_DIMENSION_SCHEMA_VERSION


def _line_value_mm(line: OCRLine) -> Optional[tuple[float, str]]:
    token = classify_dimension_token(line.text)
    if not token.is_linear_dimension or token.value is None or token.unit is None:
        return None
    value = float(token.value)
    unit = str(token.unit)
    if unit == "mm":
        mm = value
    elif unit == "m":
        mm = value * 1000.0
    elif unit == "in":
        mm = value * 25.4
    else:
        return None
    if not math.isfinite(mm) or mm <= 0.0:
        return None
    return mm, unit


def _bbox_center(bbox: Sequence[float]) -> tuple[float, float]:
    return (
        (float(bbox[0]) + float(bbox[2])) / 2.0,
        (float(bbox[1]) + float(bbox[3])) / 2.0,
    )


def _bbox_size(bbox: Sequence[float]) -> tuple[float, float]:
    return (
        max(0.0, float(bbox[2]) - float(bbox[0])),
        max(0.0, float(bbox[3]) - float(bbox[1])),
    )


def _segment_axis(segment: RasterAxisSegment) -> Optional[tuple[str, float, float, float]]:
    orientation = segment.orientation
    x0, y0 = (float(v) for v in segment.start_px)
    x1, y1 = (float(v) for v in segment.end_px)
    if orientation == DimensionOrientation.HORIZONTAL.value:
        return orientation, min(x0, x1), max(x0, x1), (y0 + y1) / 2.0
    if orientation == DimensionOrientation.VERTICAL.value:
        return orientation, min(y0, y1), max(y0, y1), (x0 + x1) / 2.0
    return None


def _merge_axis_segments(
    segments: Sequence[RasterAxisSegment],
    *,
    join_tolerance_px: float,
    axis_tolerance_px: float,
) -> tuple[tuple[str, float, float, float, tuple[str, ...]], ...]:
    """Merge source fragments only when collinear/touching within tolerance.

    Return (orientation, low, high, axis_coordinate, source_ids).  Input order
    does not affect output.
    """
    by_orientation: dict[str, list[tuple[float, float, float, str]]] = {
        DimensionOrientation.HORIZONTAL.value: [],
        DimensionOrientation.VERTICAL.value: [],
    }
    for segment in segments:
        axis = _segment_axis(segment)
        if axis is None:
            continue
        orientation, low, high, coord = axis
        by_orientation[orientation].append((low, high, coord, segment.segment_id))

    merged: list[tuple[str, float, float, float, tuple[str, ...]]] = []
    for orientation, rows in by_orientation.items():
        layers: list[list[tuple[float, float, float, str]]] = []
        for row in sorted(rows, key=lambda r: (r[2], r[0], r[1], r[3])):
            layer = next(
                (
                    existing
                    for existing in layers
                    if abs(existing[0][2] - row[2]) <= axis_tolerance_px
                ),
                None,
            )
            if layer is None:
                layers.append([row])
            else:
                layer.append(row)

        for layer in layers:
            coord = sum(row[2] for row in layer) / len(layer)
            runs: list[tuple[float, float, set[str]]] = []
            for low, high, _coord, source_id in sorted(layer):
                if runs and low <= runs[-1][1] + join_tolerance_px:
                    run_low, run_high, ids = runs[-1]
                    ids.add(source_id)
                    runs[-1] = (run_low, max(run_high, high), ids)
                else:
                    runs.append((low, high, {source_id}))
            for low, high, ids in runs:
                merged.append(
                    (orientation, low, high, coord, tuple(sorted(ids)))
                )
    return tuple(sorted(merged, key=lambda r: (r[0], r[3], r[1], r[2], r[4])))


def _point_to_pdf(
    point_px: tuple[float, float],
    *,
    transform: RasterCoordinateTransform,
    scope: RasterDimensionScope,
) -> tuple[float, float]:
    local_x, local_y = transform.point_to_pdf(point_px)
    return (
        round(float(scope.placement_bbox_pt[0]) + float(local_x), 6),
        round(float(scope.placement_bbox_pt[1]) + float(local_y), 6),
    )


def _bbox_to_pdf(
    bbox_px: tuple[float, float, float, float],
    *,
    transform: RasterCoordinateTransform,
    scope: RasterDimensionScope,
) -> tuple[float, float, float, float]:
    local = transform.bbox_to_pdf(bbox_px)
    x0, y0 = scope.placement_bbox_pt[0], scope.placement_bbox_pt[1]
    return tuple(round(float(v), 6) for v in (
        x0 + local[0], y0 + local[1], x0 + local[2], y0 + local[3]
    ))


def _validate_transform(
    transform: RasterCoordinateTransform,
    scope: RasterDimensionScope,
) -> None:
    width = float(scope.placement_bbox_pt[2]) - float(scope.placement_bbox_pt[0])
    height = float(scope.placement_bbox_pt[3]) - float(scope.placement_bbox_pt[1])
    if not math.isclose(float(transform.page_width_pt), width, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("transform width must equal source image placement width")
    if not math.isclose(float(transform.page_height_pt), height, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("transform height must equal source image placement height")


def _validate_ocr_lineage(
    record: RasterOCREvidenceRecord,
    scope: RasterDimensionScope,
) -> Optional[str]:
    if record.document_id != scope.document_id:
        return "ocr_document_mismatch"
    if record.revision_id != scope.revision_id:
        return "ocr_revision_mismatch"
    if record.source_sha256 != scope.source_sha256:
        return "ocr_source_hash_mismatch"
    if record.snapshot_id != scope.snapshot_id:
        return "ocr_snapshot_mismatch"
    if str(record.page_id) != str(scope.page_id):
        return "ocr_page_mismatch"
    if record.viewport_id not in (None, scope.viewport_id):
        return "ocr_viewport_mismatch"
    return None


def _candidate_lines_for_token(
    bbox: tuple[float, float, float, float],
    merged: Sequence[tuple[str, float, float, float, tuple[str, ...]]],
) -> tuple[tuple[str, float, float, float, tuple[str, ...]], ...]:
    cx, cy = _bbox_center(bbox)
    bw, bh = _bbox_size(bbox)
    horizontal_search = max(2.0, 2.5 * max(bh, 1.0))
    vertical_search = max(2.0, 2.5 * max(bw, 1.0))
    extension = max(2.0, 1.5 * max(bw, bh, 1.0))
    out = []
    for row in merged:
        orientation, low, high, coord, _ids = row
        if orientation == DimensionOrientation.HORIZONTAL.value:
            if low - extension <= cx <= high + extension and abs(coord - cy) <= horizontal_search:
                out.append(row)
        elif orientation == DimensionOrientation.VERTICAL.value:
            if low - extension <= cy <= high + extension and abs(coord - cx) <= vertical_search:
                out.append(row)
    return tuple(out)


def _witness_groups(
    dimension_line: tuple[str, float, float, float, tuple[str, ...]],
    merged: Sequence[tuple[str, float, float, float, tuple[str, ...]]],
    *,
    witness_tolerance_px: float,
) -> Optional[
    tuple[
        tuple[float, tuple[str, ...]],
        tuple[float, tuple[str, ...]],
    ]
]:
    orientation, low, high, coord, _ids = dimension_line
    perpendicular = (
        DimensionOrientation.VERTICAL.value
        if orientation == DimensionOrientation.HORIZONTAL.value
        else DimensionOrientation.HORIZONTAL.value
    )

    endpoint_hits: list[list[tuple[float, tuple[str, ...]]]] = [[], []]
    for row in merged:
        row_orientation, row_low, row_high, row_coord, row_ids = row
        if row_orientation != perpendicular:
            continue
        if not (row_low - witness_tolerance_px <= coord <= row_high + witness_tolerance_px):
            continue
        distances = (abs(row_coord - low), abs(row_coord - high))
        for endpoint_index, distance in enumerate(distances):
            if distance <= witness_tolerance_px:
                endpoint_hits[endpoint_index].append((row_coord, row_ids))

    resolved: list[tuple[float, tuple[str, ...]]] = []
    for hits in endpoint_hits:
        if not hits:
            return None
        coordinate_groups: list[list[tuple[float, tuple[str, ...]]]] = []
        for hit in sorted(hits, key=lambda h: (h[0], h[1])):
            group = next(
                (
                    existing
                    for existing in coordinate_groups
                    if abs(existing[0][0] - hit[0]) <= witness_tolerance_px / 4.0
                ),
                None,
            )
            if group is None:
                coordinate_groups.append([hit])
            else:
                group.append(hit)
        if len(coordinate_groups) != 1:
            return None
        group = coordinate_groups[0]
        coordinate = sum(item[0] for item in group) / len(group)
        ids = tuple(sorted({source_id for _coord, row_ids in group for source_id in row_ids}))
        resolved.append((coordinate, ids))
    return resolved[0], resolved[1]


def _alternative_for_line(
    *,
    line: tuple[str, float, float, float, tuple[str, ...]],
    witnesses: tuple[tuple[float, tuple[str, ...]], tuple[float, tuple[str, ...]]],
    value_mm: float,
    raw_text: str,
    bbox_px: tuple[float, float, float, float],
    transform: RasterCoordinateTransform,
    scope: RasterDimensionScope,
) -> RasterDimensionAlternative:
    orientation, low, high, coord, line_ids = line
    first, second = witnesses
    if orientation == DimensionOrientation.HORIZONTAL.value:
        endpoints_px = ((first[0], coord), (second[0], coord))
    else:
        endpoints_px = ((coord, first[0]), (coord, second[0]))
    endpoints_pt = tuple(sorted(
        (
            _point_to_pdf(point, transform=transform, scope=scope)
            for point in endpoints_px
        ),
        key=lambda point: (point[0], point[1]),
    ))
    witness_ids = tuple(sorted(set(first[1] + second[1])))
    payload = {
        "document_id": scope.document_id,
        "revision_id": scope.revision_id,
        "source_sha256": scope.source_sha256,
        "snapshot_id": scope.snapshot_id,
        "page_id": scope.page_id,
        "viewport_id": scope.viewport_id,
        "image_id": scope.image_id,
        "raw_text": raw_text,
        "value_mm": round(value_mm, 6),
        "bbox_pt": _bbox_to_pdf(bbox_px, transform=transform, scope=scope),
        "orientation": orientation,
        "endpoints_pt": endpoints_pt,
    }
    return RasterDimensionAlternative(
        dimension_line_ids=line_ids,
        witness_line_ids=witness_ids,
        endpoints_pt=endpoints_pt,
        candidate_id=stable_contract_id("raster_dimension", payload),
    )


def _same_source_position(
    left: OCRLine,
    right: OCRLine,
) -> bool:
    lw, lh = _bbox_size(left.bbox_px)
    rw, rh = _bbox_size(right.bbox_px)
    tol = max(1.0, 0.25 * max(lw, lh, rw, rh, 1.0))
    lc = _bbox_center(left.bbox_px)
    rc = _bbox_center(right.bbox_px)
    return math.hypot(lc[0] - rc[0], lc[1] - rc[1]) <= tol


def collect_raster_figured_dimension_shadow(
    *,
    ocr_record: RasterOCREvidenceRecord,
    segments: Sequence[RasterAxisSegment],
    transform: RasterCoordinateTransform,
    scope: RasterDimensionScope,
) -> RasterFiguredDimensionShadow:
    """Bind source-owned OCR dimension candidates to raster axis geometry.

    The function never computes physical area or changes OCR authority.
    """
    _validate_transform(transform, scope)
    lineage_reason = _validate_ocr_lineage(ocr_record, scope)
    if lineage_reason is not None:
        return RasterFiguredDimensionShadow(
            EvidenceResolutionStatus.ABSTAINED,
            (lineage_reason,),
            scope,
            (),
        )

    typed: list[tuple[OCRLine, float, str]] = []
    for line in ocr_record.lines:
        resolved = _line_value_mm(line)
        if resolved is None:
            continue
        typed.append((line, resolved[0], resolved[1]))

    if not typed:
        return RasterFiguredDimensionShadow(
            EvidenceResolutionStatus.ABSTAINED,
            ("no_typed_raster_dimensions",),
            scope,
            (),
        )

    # Mark materially different OCR values occupying the same source position
    # as conflict; repetition of the same value remains one observation group.
    conflicting_indexes: set[int] = set()
    for i, (left, left_mm, _left_unit) in enumerate(typed):
        for j in range(i + 1, len(typed)):
            right, right_mm, _right_unit = typed[j]
            if _same_source_position(left, right) and not math.isclose(
                left_mm, right_mm, rel_tol=1e-6, abs_tol=1e-6
            ):
                conflicting_indexes.update((i, j))

    sizes = [
        max(_bbox_size(line.bbox_px))
        for line, _mm, _unit in typed
        if max(_bbox_size(line.bbox_px)) > 0.0
    ]
    basis = sorted(sizes)[len(sizes) // 2] if sizes else 4.0
    join_tolerance = max(1.0, 0.35 * basis)
    axis_tolerance = max(1.0, 0.20 * basis)
    witness_tolerance = max(2.0, 0.75 * basis)
    merged = _merge_axis_segments(
        tuple(segments),
        join_tolerance_px=join_tolerance,
        axis_tolerance_px=axis_tolerance,
    )

    candidates: list[RasterFiguredDimensionCandidate] = []
    for index, (line, value_mm, unit) in enumerate(typed):
        bbox_px = tuple(float(v) for v in line.bbox_px)
        bbox_pt = _bbox_to_pdf(bbox_px, transform=transform, scope=scope)
        if index in conflicting_indexes:
            candidates.append(
                RasterFiguredDimensionCandidate(
                    EvidenceResolutionStatus.CONFLICT,
                    ("competing_ocr_values_same_source_position",),
                    line.text,
                    value_mm,
                    unit,
                    line.confidence,
                    bbox_px,
                    bbox_pt,
                )
            )
            continue

        candidate_lines = _candidate_lines_for_token(bbox_px, merged)
        full_alternatives: list[
            tuple[
                tuple[str, float, float, float, tuple[str, ...]],
                tuple[tuple[float, tuple[str, ...]], tuple[float, tuple[str, ...]]],
            ]
        ] = []
        for candidate_line in candidate_lines:
            witnesses = _witness_groups(
                candidate_line,
                merged,
                witness_tolerance_px=witness_tolerance,
            )
            if witnesses is not None:
                full_alternatives.append((candidate_line, witnesses))

        if not full_alternatives:
            reason = (
                "dimension_line_unavailable"
                if not candidate_lines
                else "two_sided_witness_binding_unavailable"
            )
            candidates.append(
                RasterFiguredDimensionCandidate(
                    EvidenceResolutionStatus.ABSTAINED,
                    (reason,),
                    line.text,
                    value_mm,
                    unit,
                    line.confidence,
                    bbox_px,
                    bbox_pt,
                )
            )
            continue

        alternatives = tuple(
            _alternative_for_line(
                line=dimension_line,
                witnesses=witnesses,
                value_mm=value_mm,
                raw_text=line.text,
                bbox_px=bbox_px,
                transform=transform,
                scope=scope,
            )
            for dimension_line, witnesses in full_alternatives
        )
        if len(alternatives) != 1:
            candidates.append(
                RasterFiguredDimensionCandidate(
                    EvidenceResolutionStatus.CONFLICT,
                    ("competing_dimension_line_bindings",),
                    line.text,
                    value_mm,
                    unit,
                    line.confidence,
                    bbox_px,
                    bbox_pt,
                    alternatives=alternatives,
                )
            )
            continue

        chosen = alternatives[0]
        orientation = full_alternatives[0][0][0]
        candidates.append(
            RasterFiguredDimensionCandidate(
                EvidenceResolutionStatus.CANDIDATE,
                ("raster_dimension_two_sided_witness_bound_candidate_only",),
                line.text,
                value_mm,
                unit,
                line.confidence,
                bbox_px,
                bbox_pt,
                orientation=orientation,
                dimension_line_ids=chosen.dimension_line_ids,
                witness_line_ids=chosen.witness_line_ids,
                endpoints_pt=chosen.endpoints_pt,
                candidate_id=chosen.candidate_id,
            )
        )

    # Preserve every OCR observation, including exact repeats from separate
    # passes.  A shared stable candidate_id records physical equivalence
    # without deleting source observations or selecting by confidence.
    retained = tuple(sorted(
        candidates,
        key=lambda c: (
            c.bbox_pt,
            c.value_mm,
            c.raw_text,
            c.candidate_id or "",
            c.status.value,
            -1.0 if c.confidence is None else float(c.confidence),
        ),
    ))

    statuses = {candidate.status for candidate in retained}
    if EvidenceResolutionStatus.CONFLICT in statuses:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = ("raster_dimension_conflict_retained",)
    elif EvidenceResolutionStatus.CANDIDATE in statuses:
        status = EvidenceResolutionStatus.CANDIDATE
        reasons = ("raster_dimensions_bound_candidate_only",)
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = ("no_two_sided_raster_dimension_binding",)

    return RasterFiguredDimensionShadow(
        status,
        reasons,
        scope,
        retained,
    )


__all__ = [
    "RASTER_FIGURED_DIMENSION_SCHEMA_VERSION",
    "RasterAxisSegment",
    "RasterDimensionAlternative",
    "RasterDimensionScope",
    "RasterFiguredDimensionCandidate",
    "RasterFiguredDimensionShadow",
    "collect_raster_figured_dimension_shadow",
]
