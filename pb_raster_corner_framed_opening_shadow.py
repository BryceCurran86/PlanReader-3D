"""Source-owned raster corner framed-opening SHADOW nominations.

A corner opening (for example a corner stacking door) has two framed legs
that meet at a corner instead of a second collinear wall flank. Each leg is
bounded by exactly one producer-issued solid wall-band end, and the legs meet
in the square where the two bands' cross ranges intersect. The ordinary
``raster_framed_wall_band_interruption`` pattern needs a collinear partner
band, so it cannot nominate either leg.

This module only nominates. It consumes producer-issued raster opening
primitives and the producer's images-only render; callers cannot supply
pixels, masks, records, thresholds or geometry. Every pixel rule reuses the
existing raster framed-opening constants and the existing corner-aperture
bounds. A nomination never proves physical opening existence, a host wall, a
frame, a dimension, a label association or a quantity, and no production path
reads it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import cv2
import numpy as np

import pb_physical_opening_authority as _opening
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_raster_opening_source_primitives import (
    LINE_THRESHOLD,
    MASS_THRESHOLD,
    POCHE_MIN_PT,
    RASTER_LINE_RUN,
    RASTER_WALL_BAND_END,
    RASTER_WALL_BAND_FACE,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationRecord
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_corner_aperture_continuity_authority import (
    MAX_CORNER_POST_DIM_PT,
    MAX_LEG_SPAN_PT,
    MIN_LEG_SPAN_PT,
)

RASTER_CORNER_FRAMED_OPENING_SHADOW_SCHEMA_VERSION = "1.0.0"

CORNER_FRAMED_OPENING_NOMINATED = "raster_corner_framed_opening_nominated"
CORNER_FRAMED_OPENING_UNAVAILABLE = "raster_corner_framed_opening_unavailable"
CORNER_RASTER_PRIMITIVES_UNAVAILABLE = "raster_corner_primitives_unavailable"
CORNER_RENDER_UNAVAILABLE = "raster_corner_render_unavailable"
CORNER_ROTATED_RENDER_UNSUPPORTED = "raster_corner_rotated_render_unsupported"
CORNER_EXISTENCE_AUTHORITY_UNPROMOTED = "corner_opening_existence_authority_unpromoted"

CORNER_LEG_WALL_FACE_INK_CONTINUES = "corner_leg_wall_face_ink_continues"
CORNER_SQUARE_SOLID_UNRESOLVED = "corner_square_solid_unresolved"
CORNER_LEG_FRAME_SOURCE_UNOWNED = "corner_leg_frame_source_primitive_unowned"
CORNER_LEG_BAND_SOURCE_UNOWNED = "corner_leg_band_source_primitive_unowned"
CORNER_FRAME_DISCONNECTED = "corner_frame_disconnected"
CORNER_STRAIGHT_GAP_ALTERNATIVE = "corner_straight_gap_alternative"
CORNER_POST_DIMENSION_EXCESSIVE = "corner_post_dimension_excessive"
CORNER_BAND_END_OWNER_AMBIGUOUS = "corner_band_end_owner_ambiguous"

CORNER_ABSTENTION_REASONS = frozenset((
    CORNER_LEG_WALL_FACE_INK_CONTINUES,
    CORNER_SQUARE_SOLID_UNRESOLVED,
    CORNER_LEG_FRAME_SOURCE_UNOWNED,
    CORNER_LEG_BAND_SOURCE_UNOWNED,
    CORNER_FRAME_DISCONNECTED,
    CORNER_STRAIGHT_GAP_ALTERNATIVE,
    CORNER_POST_DIMENSION_EXCESSIVE,
    CORNER_BAND_END_OWNER_AMBIGUOUS,
))

HORIZONTAL = "horizontal"
VERTICAL = "vertical"


@dataclass(frozen=True)
class RasterCornerFramedLeg:
    """One leg, from its single wall-band jamb to the shared corner square."""

    axis: str
    band_box_pt: tuple[float, float, float, float]
    jamb_at_high_band_end: bool
    clear_span_along_pt: tuple[float, float]
    cross_range_pt: tuple[float, float]
    leg_span_pt: float
    jamb_end_observation_id: str
    face_observation_ids: tuple[str, ...]
    frame_line_observation_ids: tuple[str, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "axis": self.axis,
            "band_box_pt": list(self.band_box_pt),
            "jamb_at_high_band_end": self.jamb_at_high_band_end,
            "clear_span_along_pt": list(self.clear_span_along_pt),
            "cross_range_pt": list(self.cross_range_pt),
            "leg_span_pt": self.leg_span_pt,
            "jamb_end_observation_id": self.jamb_end_observation_id,
            "face_observation_ids": list(self.face_observation_ids),
            "frame_line_observation_ids": list(self.frame_line_observation_ids),
        }


@dataclass(frozen=True)
class RasterCornerFramedOpeningShadow:
    """A two-leg corner nomination or a typed near-miss; never an opening."""

    candidate_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    corner_box_pt: tuple[float, float, float, float]
    corner_post_dimension_pt: float
    horizontal_leg: RasterCornerFramedLeg
    vertical_leg: RasterCornerFramedLeg
    source_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    first_remaining_gate: str
    shadow_only: bool = True
    takeoff_eligible: bool = False
    physical_opening_authority: bool = False
    deduction_authority: bool = False

    def __post_init__(self) -> None:
        if (self.shadow_only is not True
                or self.takeoff_eligible is not False
                or self.physical_opening_authority is not False
                or self.deduction_authority is not False):
            raise ValueError("corner framed-opening shadow cannot grant authority")
        if self.status is EvidenceResolutionStatus.CANDIDATE:
            valid = (self.reason_codes == (CORNER_FRAMED_OPENING_NOMINATED,)
                     and self.first_remaining_gate == CORNER_EXISTENCE_AUTHORITY_UNPROMOTED)
        else:
            valid = (self.status is EvidenceResolutionStatus.ABSTAINED
                     and len(self.reason_codes) == 1
                     and self.reason_codes[0] in CORNER_ABSTENTION_REASONS
                     and self.first_remaining_gate == self.reason_codes[0])
        if not valid:
            raise ValueError("corner framed-opening status and gate conflict")
        if (self.horizontal_leg.axis != HORIZONTAL
                or self.vertical_leg.axis != VERTICAL
                or tuple(sorted(set(self.source_observation_ids))) != self.source_observation_ids):
            raise ValueError("corner framed-opening legs or source receipts are not canonical")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "schema_version": RASTER_CORNER_FRAMED_OPENING_SHADOW_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "page_id": self.page_id,
            "corner_box_pt": list(self.corner_box_pt),
            "corner_post_dimension_pt": self.corner_post_dimension_pt,
            "horizontal_leg": self.horizontal_leg.to_dict(),
            "vertical_leg": self.vertical_leg.to_dict(),
            "source_observation_ids": list(self.source_observation_ids),
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "first_remaining_gate": self.first_remaining_gate,
            "shadow_only": self.shadow_only,
            "takeoff_eligible": self.takeoff_eligible,
            "physical_opening_authority": self.physical_opening_authority,
            "deduction_authority": self.deduction_authority,
        }


@dataclass(frozen=True)
class RasterCornerFramedOpeningShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    revision_id: str
    page_id: str
    snapshot_id: Optional[str]
    nominations: tuple[RasterCornerFramedOpeningShadow, ...]
    rejected_geometric_corner_count: int
    shadow_only: bool = True
    takeoff_eligible: bool = False

    @property
    def candidates(self) -> tuple[RasterCornerFramedOpeningShadow, ...]:
        return tuple(n for n in self.nominations
                     if n.status is EvidenceResolutionStatus.CANDIDATE)

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "schema_version": RASTER_CORNER_FRAMED_OPENING_SHADOW_SCHEMA_VERSION,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "revision_id": self.revision_id,
            "page_id": self.page_id,
            "snapshot_id": self.snapshot_id,
            "nominations": [n.to_dict() for n in self.nominations],
            "rejected_geometric_corner_count": self.rejected_geometric_corner_count,
            "shadow_only": self.shadow_only,
            "takeoff_eligible": self.takeoff_eligible,
        }


@dataclass(frozen=True)
class _BandEnd:
    axis: str
    box: tuple[int, int, int, int]
    high: bool
    along: int
    cross: tuple[int, int]


def _masks(gray: np.ndarray, dpi: int, registration_scale: tuple[float, float]):
    mass = (gray < MASS_THRESHOLD).astype(np.uint8)
    line_mask = (gray < LINE_THRESHOLD).astype(np.uint8)
    sx, sy = registration_scale
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (
        _opening._raster_odd(_opening._raster_scaled_px(POCHE_MIN_PT, dpi, sx)),
        _opening._raster_odd(_opening._raster_scaled_px(POCHE_MIN_PT, dpi, sy)),
    ))
    return cv2.morphologyEx(mass, cv2.MORPH_OPEN, kernel), line_mask


def _band_ends(thick, *, dpi, registration_scale):
    ends: list[_BandEnd] = []
    boxes_by_axis = {}
    for axis in (HORIZONTAL, VERTICAL):
        along_scale, _cross = _opening._raster_axis_registration_scales(axis, registration_scale)
        work = thick if axis == HORIZONTAL else np.ascontiguousarray(thick.T)
        window = _opening._raster_scaled_px(_opening._RASTER_END_WINDOW_PT, dpi, along_scale)
        boxes = _opening._raster_band_boxes(
            thick, dpi=dpi, axis=axis, registration_scale=registration_scale)
        boxes_by_axis[axis] = boxes
        for box in boxes:
            analysis = _opening._raster_analysis_box(box, axis)
            for high in (False, True):
                cross = _opening._raster_end_interval(
                    work, analysis, at_high_end=high, window=window)
                if cross is not None:
                    ends.append(_BandEnd(axis, box, high,
                                         analysis[2] if high else analysis[0], cross))
    return ends, boxes_by_axis


def _covered_groups(profile: np.ndarray, offset: int) -> tuple[tuple[int, int], ...]:
    covered = profile >= _opening._RASTER_LINE_COVERAGE
    groups: list[tuple[int, int]] = []
    start: Optional[int] = None
    for index, flag in enumerate(covered.tolist() + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            groups.append((offset + start, offset + index - 1))
            start = None
    return tuple(groups)


class _Leg:
    """One leg in its analysis frame: x is along the leg, rows are across it."""

    def __init__(self, end: _BandEnd, gap: tuple[int, int], *, thick, line_mask,
                 dpi, registration_scale):
        self.end = end
        self.gap = gap
        self.along_scale, self.cross_scale = _opening._raster_axis_registration_scales(
            end.axis, registration_scale)
        self.work_thick = thick if end.axis == HORIZONTAL else thick.T
        self.work_line = line_mask if end.axis == HORIZONTAL else line_mask.T
        self.dpi = dpi

    def span_in_bounds(self) -> bool:
        length = self.gap[1] - self.gap[0] + 1
        return (_opening._raster_scaled_px(MIN_LEG_SPAN_PT, self.dpi, self.along_scale)
                <= length
                <= _opening._raster_scaled_px(MAX_LEG_SPAN_PT, self.dpi, self.along_scale))

    def gap_clean(self) -> bool:
        r0, r1 = self.end.cross
        region = self.work_thick[r0:r1 + 1, self.gap[0]:self.gap[1] + 1]
        return bool(region.size) and not bool(
            np.any(region.mean(axis=0) > _opening._RASTER_CLEAN_GAP_MAX_PARTIAL))

    def frame_groups(self) -> tuple[tuple[int, int], ...]:
        pad = _opening._raster_scaled_px(
            _opening._RASTER_LINE_ROW_PAD_PT, self.dpi, self.cross_scale, minimum=1)
        r0 = max(self.end.cross[0] - pad, 0)
        r1 = min(self.end.cross[1] + pad, self.work_line.shape[0] - 1)
        region = self.work_line[r0:r1 + 1, self.gap[0]:self.gap[1] + 1]
        if region.size == 0:
            return ()
        groups = _covered_groups(region.mean(axis=1), r0)
        return groups if len(groups) >= _opening._RASTER_MIN_FRAME_LINES else ()

    def face_continues(self) -> bool:
        for row in self.end.cross:
            if (0 <= row < self.work_line.shape[0]
                    and float(self.work_line[row, self.gap[0]:self.gap[1] + 1].mean())
                    >= _opening._RASTER_LINE_COVERAGE):
                return True
        return False


def _line_in_frame(record: SourceObservationRecord, axis: str, dpi: int):
    """(cross, along_start, along_end) in analysis px, or None if not axis-aligned."""
    x0, y0, x1, y1 = (float(value) * float(dpi) / 72.0 for value in record.geometry)
    if axis == VERTICAL:
        x0, y0, x1, y1 = y0, x0, y1, x1
    if abs(y0 - y1) > 0.51:
        return None
    start, end = sorted((x0, x1))
    return (y0 + y1) / 2.0, start, end


def _frame_records(leg: _Leg, groups, line_runs, dpi):
    """Like the framed pattern: every frame group needs a run covering the gap."""
    gap_length = leg.gap[1] - leg.gap[0] + 1
    selected: dict[str, tuple[SourceObservationRecord, float, float]] = {}
    for group_start, group_end in groups:
        matched = False
        for record in line_runs:
            line = _line_in_frame(record, leg.end.axis, dpi)
            if line is None:
                continue
            cross, start, end = line
            if cross < group_start - 0.51 or cross > group_end + 0.51:
                continue
            overlap = max(0.0, min(end, float(leg.gap[1])) - max(start, float(leg.gap[0])) + 1.0)
            if overlap / float(gap_length) + 1e-12 < _opening._RASTER_LINE_COVERAGE:
                continue
            selected[record.observation_id] = (record, start, end)
            matched = True
        if not matched:
            return None
    return selected


def _band_records(end: _BandEnd, by_kind_geometry, dpi):
    x0, y0, x1, y1 = end.box
    if end.axis == HORIZONTAL:
        faces = ((x0, y0, x1, y0), (x0, y1, x1, y1))
        jamb = (x1, y0, x1, y1) if end.high else (x0, y0, x0, y1)
    else:
        faces = ((x0, y0, x0, y1), (x1, y0, x1, y1))
        jamb = (x0, y1, x1, y1) if end.high else (x0, y0, x1, y0)

    def owner(kind, geometry_px):
        geometry_pt = tuple(round(value, 6) for value in _opening._raster_geometry_pt(geometry_px, dpi))
        owners = by_kind_geometry.get((kind, geometry_pt), ())
        return owners[0] if len(owners) == 1 else None

    face_records = tuple(owner(RASTER_WALL_BAND_FACE, face) for face in faces)
    jamb_record = owner(RASTER_WALL_BAND_END, jamb)
    if jamb_record is None or any(record is None for record in face_records):
        return None
    return jamb_record, face_records


def _straight_gap_through(pairs_by_axis, corner_cols, corner_rows) -> bool:
    """Any existing collinear raw gap, whatever its reasons, that spans the corner."""
    for axis, along, cross in ((HORIZONTAL, corner_cols, corner_rows),
                               (VERTICAL, corner_rows, corner_cols)):
        for pair in pairs_by_axis[axis]:
            if (pair.gap_x0 <= along[0] and pair.gap_x1 >= along[1]
                    and not (pair.row1 < cross[0] or pair.row0 > cross[1])):
                return True
    return False


def _nominate(gray: np.ndarray, records: Sequence[SourceObservationRecord], *,
              dpi: int, registration_scale: tuple[float, float]):
    """Pure nomination over one page render and its producer-issued primitives."""
    thick, line_mask = _masks(gray, dpi, registration_scale)
    ends, boxes_by_axis = _band_ends(thick, dpi=dpi, registration_scale=registration_scale)
    pairs_by_axis = {}
    for axis in (HORIZONTAL, VERTICAL):
        along_scale, cross_scale = _opening._raster_axis_registration_scales(axis, registration_scale)
        work = thick if axis == HORIZONTAL else np.ascontiguousarray(thick.T)
        pairs_by_axis[axis] = _opening._raster_pair_flanks(
            work, tuple(_opening._raster_analysis_box(box, axis) for box in boxes_by_axis[axis]),
            dpi=dpi, along_scale=along_scale, cross_scale=cross_scale)
    by_kind_geometry: dict[tuple[str, tuple[float, ...]], list[SourceObservationRecord]] = {}
    line_runs = []
    for record in records:
        geometry = tuple(round(float(value), 6) for value in record.geometry)
        if len(geometry) != 4:
            continue
        by_kind_geometry.setdefault((record.observation_kind, geometry), []).append(record)
        if record.observation_kind == RASTER_LINE_RUN:
            line_runs.append(record)
    line_runs.sort(key=lambda record: record.observation_id)

    horizontal = [end for end in ends if end.axis == HORIZONTAL]
    vertical = [end for end in ends if end.axis == VERTICAL]
    post_limits = tuple(
        _opening._raster_scaled_px(MAX_CORNER_POST_DIM_PT, dpi, scale)
        for scale in registration_scale)
    rejected = 0
    raw: list[dict] = []
    for h in horizontal:
        r0, r1 = h.cross
        for v in vertical:
            c0, c1 = v.cross
            if h.high and c0 > h.along:
                h_gap = (h.along + 1, c0 - 1)
            elif not h.high and c1 < h.along:
                h_gap = (c1 + 1, h.along - 1)
            else:
                continue
            if v.high and r0 > v.along:
                v_gap = (v.along + 1, r0 - 1)
            elif not v.high and r1 < v.along:
                v_gap = (r1 + 1, v.along - 1)
            else:
                continue
            legs = (
                _Leg(h, h_gap, thick=thick, line_mask=line_mask, dpi=dpi,
                     registration_scale=registration_scale),
                _Leg(v, v_gap, thick=thick, line_mask=line_mask, dpi=dpi,
                     registration_scale=registration_scale),
            )
            if not all(leg.span_in_bounds() for leg in legs):
                continue
            if not all(leg.gap_clean() for leg in legs):
                rejected += 1
                continue
            groups = tuple(leg.frame_groups() for leg in legs)
            if not all(groups):
                rejected += 1
                continue
            raw.append(_gate(h, v, legs, groups, thick=thick, line_runs=line_runs,
                             by_kind_geometry=by_kind_geometry, pairs_by_axis=pairs_by_axis,
                             post_limits=post_limits, dpi=dpi))

    passing = [item for item in raw if item["reason"] is None]
    ambiguous = [
        item for item in passing
        if any(other is not item and (other["ends"] & item["ends"]
                                      or _boxes_overlap(other["corner_px"], item["corner_px"]))
               for other in passing)
    ]
    for item in ambiguous:
        item["reason"] = CORNER_BAND_END_OWNER_AMBIGUOUS
    return raw, rejected


def _boxes_overlap(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _gate(h, v, legs, groups, *, thick, line_runs, by_kind_geometry, pairs_by_axis,
          post_limits, dpi):
    c0, c1 = v.cross
    r0, r1 = h.cross
    item = {"h": h, "v": v, "legs": legs, "corner_px": (c0, r0, c1, r1),
            "ends": {(h.axis, h.box, h.high), (v.axis, v.box, v.high)},
            "frames": (), "bands": (), "reason": None}

    def fail(reason):
        item["reason"] = reason
        return item

    if np.any(thick[r0:r1 + 1, c0:c1 + 1].mean(axis=0) > _opening._RASTER_CLEAN_GAP_MAX_PARTIAL):
        return fail(CORNER_SQUARE_SOLID_UNRESOLVED)
    if any(leg.face_continues() for leg in legs):
        return fail(CORNER_LEG_WALL_FACE_INK_CONTINUES)
    frames = tuple(_frame_records(leg, leg_groups, line_runs, dpi)
                   for leg, leg_groups in zip(legs, groups))
    if any(selected is None for selected in frames):
        return fail(CORNER_LEG_FRAME_SOURCE_UNOWNED)
    item["frames"] = frames
    bands = tuple(_band_records(leg.end, by_kind_geometry, dpi) for leg in legs)
    if any(band is None for band in bands):
        return fail(CORNER_LEG_BAND_SOURCE_UNOWNED)
    item["bands"] = bands
    # The frame must physically enter the shared corner square from each leg.
    corner_along = ((c0, c1), (r0, r1))
    for leg, selected, (lo, hi) in zip(legs, frames, corner_along):
        corner_low = lo < leg.gap[0]
        if not any((start <= hi + 0.51) if corner_low else (end >= lo - 0.51)
                   for _record, start, end in selected.values()):
            return fail(CORNER_FRAME_DISCONNECTED)
    if _straight_gap_through(pairs_by_axis, (c0, c1), (r0, r1)):
        return fail(CORNER_STRAIGHT_GAP_ALTERNATIVE)
    if c1 - c0 + 1 > post_limits[0] or r1 - r0 + 1 > post_limits[1]:
        return fail(CORNER_POST_DIMENSION_EXCESSIVE)
    return item


def _pt(value_px: float, dpi: int) -> float:
    return _opening._raster_pt(value_px, dpi)


def _leg_record(leg: _Leg, frames, bands, dpi) -> RasterCornerFramedLeg:
    end = leg.end
    gap0, gap1 = leg.gap
    along = (_pt(gap0, dpi), _pt(gap1 + 1, dpi))
    jamb, faces = bands if bands else (None, ())
    return RasterCornerFramedLeg(
        axis=end.axis,
        band_box_pt=_opening._raster_box_pt(end.box, dpi),
        jamb_at_high_band_end=end.high,
        clear_span_along_pt=along,
        cross_range_pt=(_pt(end.cross[0], dpi), _pt(end.cross[1] + 1, dpi)),
        leg_span_pt=round(along[1] - along[0], 6),
        jamb_end_observation_id=jamb.observation_id if jamb is not None else "",
        face_observation_ids=tuple(sorted(face.observation_id for face in faces)),
        frame_line_observation_ids=tuple(sorted(frames or ())),
    )


def detect_raster_corner_framed_openings_shadow(
    source_visibility_producer: SourceVisibilityProducer,
    *,
    revision_id: str,
    page_id: str,
) -> RasterCornerFramedOpeningShadowResult:
    """Nominate two-leg corner framed openings on one already-published page."""
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    revision_id, page_id = str(revision_id), str(page_id).strip()

    def unavailable(reason, snapshot_id=None):
        return RasterCornerFramedOpeningShadowResult(
            status=EvidenceResolutionStatus.ABSTAINED, reason_codes=(reason,),
            revision_id=revision_id, page_id=page_id, snapshot_id=snapshot_id,
            nominations=(), rejected_geometric_corner_count=0)

    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is None:
        return unavailable(CORNER_RASTER_PRIMITIVES_UNAVAILABLE)
    snapshot_id = published.snapshot.snapshot_id
    visibility = source_visibility_producer.authority()
    ids = visibility.raster_opening_primitive_observation_ids_for_snapshot(snapshot_id)
    if ids != frozenset(published.raster_opening_primitive_observation_ids):
        return unavailable(_opening.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, snapshot_id)
    records = []
    for observation_id in sorted(ids):
        result = visibility.resolve_raster_opening_primitive(ObservationSelector(
            document_id=published.revision.document_id, revision_id=revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=snapshot_id,
            observation_id=observation_id))
        if result.status is not EvidenceResolutionStatus.CORROBORATED or result.observation is None:
            return unavailable(_opening.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, snapshot_id)
        record = result.observation
        if record.page_id == page_id and record.viewport_id is None:
            records.append(record)
    if not records:
        return unavailable(CORNER_RASTER_PRIMITIVES_UNAVAILABLE, snapshot_id)
    try:
        png_bytes, _parent, native_frame, dpi = (
            source_visibility_producer.render_raster_opening_source_page(revision_id, page_id))
    except Exception:
        return unavailable(CORNER_RENDER_UNAVAILABLE, snapshot_id)
    if int(getattr(native_frame, "rotation", 0) or 0) != 0:
        return unavailable(CORNER_ROTATED_RENDER_UNSUPPORTED, snapshot_id)
    # Mixed tile transforms must not suppress the page; morphology then runs
    # in page coordinates.
    try:
        registration = source_visibility_producer.raster_opening_registration_scale(
            revision_id, page_id)
    except Exception:
        registration = None
    if registration is None:
        registration = (1.0, 1.0)
    gray = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.ndim != 2 or gray.size == 0:
        return unavailable(CORNER_RENDER_UNAVAILABLE, snapshot_id)

    raw, rejected = _nominate(gray, records, dpi=int(dpi),
                              registration_scale=tuple(float(v) for v in registration))
    nominations = []
    for item in raw:
        legs = item["legs"]
        frames = item["frames"] or ({}, {})
        bands = item["bands"] or (None, None)
        leg_records = tuple(_leg_record(leg, leg_frames, leg_bands, int(dpi))
                            for leg, leg_frames, leg_bands in zip(legs, frames, bands))
        support = sorted({
            observation_id
            for leg in leg_records
            for observation_id in (leg.jamb_end_observation_id, *leg.face_observation_ids,
                                   *leg.frame_line_observation_ids)
            if observation_id
        })
        c0, r0, c1, r1 = item["corner_px"]
        corner_box = _opening._raster_box_pt((c0, r0, c1, r1), int(dpi))
        identity = {
            "document_id": published.revision.document_id,
            "revision_id": revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": snapshot_id,
            "page_id": page_id,
            "corner_box_pt": corner_box,
            "legs": [leg.to_dict() for leg in leg_records],
        }
        reason = item["reason"]
        nominations.append(RasterCornerFramedOpeningShadow(
            candidate_id=stable_contract_id(
                "raster_corner_framed_opening_shadow", identity, digest_chars=32),
            document_id=published.revision.document_id,
            revision_id=revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=snapshot_id,
            page_id=page_id,
            corner_box_pt=corner_box,
            corner_post_dimension_pt=round(max(corner_box[2] - corner_box[0],
                                               corner_box[3] - corner_box[1]), 6),
            horizontal_leg=leg_records[0],
            vertical_leg=leg_records[1],
            source_observation_ids=tuple(support),
            status=(EvidenceResolutionStatus.CANDIDATE if reason is None
                    else EvidenceResolutionStatus.ABSTAINED),
            reason_codes=(CORNER_FRAMED_OPENING_NOMINATED,) if reason is None else (reason,),
            first_remaining_gate=CORNER_EXISTENCE_AUTHORITY_UNPROMOTED if reason is None else reason,
        ))
    nominations.sort(key=lambda nomination: nomination.candidate_id)
    has_candidate = any(n.status is EvidenceResolutionStatus.CANDIDATE for n in nominations)
    return RasterCornerFramedOpeningShadowResult(
        status=EvidenceResolutionStatus.CANDIDATE if has_candidate else EvidenceResolutionStatus.ABSTAINED,
        reason_codes=((CORNER_FRAMED_OPENING_NOMINATED,) if has_candidate
                      else (CORNER_FRAMED_OPENING_UNAVAILABLE,)),
        revision_id=revision_id,
        page_id=page_id,
        snapshot_id=snapshot_id,
        nominations=tuple(nominations),
        rejected_geometric_corner_count=rejected,
    )
