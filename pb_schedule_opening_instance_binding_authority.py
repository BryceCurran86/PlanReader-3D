"""Producer-owned schedule-row -> physical-opening-instance binding authority.

This authority proves only which producer-owned schedule row governs an already
G17-proven physical opening instance. It does not publish opening height.

Authority is fail-closed:
- the caller cannot choose tag observations or schedule rows;
- the complete trusted text universe comes from the SourceVisibilityProducer;
- plan tags must be inside the actual jamb-bounded opening aperture;
- more than one distinct matching schedule row is ambiguous even if values agree.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_schedule_v171 import ScheduleEntry, detect_header, parse_schedule_rows
from pb_opening_tag_normalization import normalize_opening_tag
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationRecord
from pb_source_visibility_authority import SourceVisibilityProducer

SCHEDULE_OPENING_INSTANCE_BINDING_SCHEMA_VERSION = "2.1.0"

BINDING_RESOLVED = "schedule_opening_instance_binding_resolved"
BINDING_OPENING_UNRESOLVED = "schedule_opening_instance_binding_opening_unresolved"
BINDING_SOURCE_SCOPE_UNAVAILABLE = "schedule_opening_instance_binding_source_scope_unavailable"
BINDING_PARTIAL_SOURCE_COVERAGE = "schedule_opening_instance_binding_partial_source_coverage"
BINDING_GEOMETRY_UNAVAILABLE = "schedule_opening_instance_binding_geometry_unavailable"
BINDING_NO_CONTAINED_TAG = "schedule_opening_instance_binding_no_contained_tag"
BINDING_AMBIGUOUS_TAGS = "schedule_opening_instance_binding_ambiguous_tags"
BINDING_NO_MATCHING_ROW = "schedule_opening_instance_binding_no_matching_row"
BINDING_AMBIGUOUS_ROWS = "schedule_opening_instance_binding_ambiguous_rows"

_BINDING_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_COORD_TOL = 1e-6
_PARALLEL_REL_TOL = 1e-9
_ROW_Y_TOLERANCE = 8.0

Point = tuple[float, float]
Line = tuple[float, float, float, float]
BBox = tuple[float, float, float, float]
_RecordKey = tuple[str, str, str, str, str, str]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


@dataclass(frozen=True)
class ScheduleOpeningInstanceBindingSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "decision_scope_id", "opening_record_id",
        ):
            _require_nonempty(getattr(self, name), name)


@dataclass(frozen=True)
class ScheduleOpeningInstanceBindingRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_record_id: str
    tag_observation_id: str
    tag_mark: str
    schedule_page_id: str
    schedule_row_observation_ids: tuple[str, ...]
    schedule_row_type_mark: str
    schedule_row_width_mm: int | None
    schedule_row_height_mm: int | None
    # A schedule parser historically defaults count to 1 when no quantity
    # column exists.  Preserve that diagnostic value separately, but expose
    # whether the count was explicitly source-backed so downstream commercial
    # reconciliation can never treat the default as evidence.
    schedule_row_count: int | None = None
    schedule_row_count_explicit: bool = False
    schema_version: str = SCHEDULE_OPENING_INSTANCE_BINDING_SCHEMA_VERSION


@dataclass(frozen=True)
class ScheduleOpeningInstanceBindingResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: ScheduleOpeningInstanceBindingRecord | None = None
    schema_version: str = SCHEDULE_OPENING_INSTANCE_BINDING_SCHEMA_VERSION


@dataclass(frozen=True)
class _FaceBreak:
    axis: Point
    start_point: Point
    end_point: Point
    gap_start: float
    gap_end: float


@dataclass(frozen=True)
class _OpeningAperture:
    axis: Point
    normal: Point
    along_min: float
    along_max: float
    normal_min: float
    normal_max: float


def _record_key(
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    opening_record_id: str,
) -> _RecordKey:
    return (
        str(document_id), str(revision_id), str(source_sha256),
        str(snapshot_id), str(decision_scope_id), str(opening_record_id),
    )


def _blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> ScheduleOpeningInstanceBindingResult:
    cleaned = tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason)))
    return ScheduleOpeningInstanceBindingResult(
        status=status,
        reason_codes=cleaned or ("schedule_opening_instance_binding_unavailable",),
        record=None,
    )


def _bbox_of_points(points: Sequence[Point]) -> BBox | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _geometry_points(geometry: Sequence[float]) -> tuple[Point, ...]:
    coords = [float(value) for value in geometry]
    if len(coords) % 2:
        return ()
    return tuple((coords[index], coords[index + 1]) for index in range(0, len(coords), 2))


def _bbox_overlap_fraction_of_smaller(left: BBox, right: BBox) -> float:
    """Return intersection area as a fraction of the smaller source box.

    Native PDF word boxes and OCR line boxes often describe the same printed
    mark with different ascender/descender height. IoU penalizes that harmless
    envelope difference. A high overlap fraction of the smaller box is the
    appropriate duplicate-observation test while two spatially distinct marks
    still score zero.
    """
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    ix0, iy0 = max(lx0, rx0), max(ly0, ry0)
    ix1, iy1 = min(lx1, rx1), min(ly1, ry1)
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if intersection <= 0.0:
        return 0.0
    left_area = max(0.0, lx1 - lx0) * max(0.0, ly1 - ly0)
    right_area = max(0.0, rx1 - rx0) * max(0.0, ry1 - ry0)
    smaller = min(left_area, right_area)
    return intersection / smaller if smaller > 0.0 else 0.0


def _bbox_overlap_fraction_of_smaller(left: BBox, right: BBox) -> float:
    """Fraction of the smaller observation box covered by the intersection.

    Native PDF word boxes and OCR boxes often have different ascender/descender
    extents for the same printed mark, so IoU alone can understate duplicate
    overlap. Distinct nearby marks still score zero when their boxes do not
    physically overlap.
    """
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    ix0, iy0 = max(lx0, rx0), max(ly0, ry0)
    ix1, iy1 = min(lx1, rx1), min(ly1, ry1)
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    left_area = max(0.0, lx1 - lx0) * max(0.0, ly1 - ly0)
    right_area = max(0.0, rx1 - rx0) * max(0.0, ry1 - ry0)
    smaller = min(left_area, right_area)
    return intersection / smaller if smaller > 0.0 else 0.0


def _line(record: SourceObservationRecord) -> Line | None:
    if len(record.geometry) != 4:
        return None
    try:
        values = tuple(float(value) for value in record.geometry)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    if math.hypot(values[2] - values[0], values[3] - values[1]) <= _COORD_TOL:
        return None
    return values  # type: ignore[return-value]


def _endpoints(line: Sequence[float]) -> tuple[Point, Point]:
    return ((float(line[0]), float(line[1])), (float(line[2]), float(line[3])))


def _canonical_unit(line: Sequence[float]) -> Point | None:
    dx = float(line[2]) - float(line[0])
    dy = float(line[3]) - float(line[1])
    length = math.hypot(dx, dy)
    if length <= _COORD_TOL:
        return None
    ux, uy = dx / length, dy / length
    if ux < -_COORD_TOL or (abs(ux) <= _COORD_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    return (ux, uy)


def _cross(left: Point, right: Point) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _dot(left: Point, right: Point) -> float:
    return left[0] * right[0] + left[1] * right[1]


def _parallel(left: Sequence[float], right: Sequence[float]) -> bool:
    left_axis = _canonical_unit(left)
    right_axis = _canonical_unit(right)
    if left_axis is None or right_axis is None:
        return False
    return abs(_cross(left_axis, right_axis)) <= _PARALLEL_REL_TOL


def _collinear(left: Sequence[float], right: Sequence[float]) -> bool:
    if not _parallel(left, right):
        return False
    axis = _canonical_unit(left)
    assert axis is not None
    first = _endpoints(left)[0]
    other = _endpoints(right)[0]
    delta = (other[0] - first[0], other[1] - first[1])
    return abs(_cross(axis, delta)) <= _COORD_TOL


def _scalar_interval(line: Sequence[float], axis: Point) -> tuple[float, float]:
    values = [_dot(point, axis) for point in _endpoints(line)]
    return (min(values), max(values))


def _point_at_scalar(line: Sequence[float], axis: Point, target: float) -> Point | None:
    for point in _endpoints(line):
        if abs(_dot(point, axis) - target) <= _COORD_TOL:
            return point
    return None


def _segment_matches(line: Sequence[float], first: Point, second: Point) -> bool:
    a, b = _endpoints(line)

    def close(left: Point, right: Point) -> bool:
        return (
            abs(left[0] - right[0]) <= _COORD_TOL
            and abs(left[1] - right[1]) <= _COORD_TOL
        )

    return (close(a, first) and close(b, second)) or (close(a, second) and close(b, first))


def _face_breaks(lines: Sequence[Line]) -> tuple[_FaceBreak, ...]:
    found: list[_FaceBreak] = []
    for index, first in enumerate(lines):
        for second in lines[index + 1 :]:
            if not _collinear(first, second):
                continue
            axis = _canonical_unit(first)
            assert axis is not None
            first_iv = _scalar_interval(first, axis)
            second_iv = _scalar_interval(second, axis)
            if first_iv[0] <= second_iv[0]:
                left, left_iv, right, right_iv = first, first_iv, second, second_iv
            else:
                left, left_iv, right, right_iv = second, second_iv, first, first_iv
            if right_iv[0] - left_iv[1] <= _COORD_TOL:
                continue
            start = _point_at_scalar(left, axis, left_iv[1])
            end = _point_at_scalar(right, axis, right_iv[0])
            if start is None or end is None:
                continue
            found.append(
                _FaceBreak(
                    axis=axis,
                    start_point=start,
                    end_point=end,
                    gap_start=left_iv[1],
                    gap_end=right_iv[0],
                )
            )
    return tuple(found)


def _opening_aperture(records: Sequence[SourceObservationRecord]) -> _OpeningAperture | None:
    """Derive the actual jamb-bounded G17 opening aperture.

    The six G17 support segments include long wall continuations. Their overall
    bbox is therefore not the opening. We independently recover the two matching
    face breaks and require the two jamb segments that connect their endpoints.
    """
    lines = tuple(line for record in records if (line := _line(record)) is not None)
    if len(lines) != len(records) or len(lines) != 6:
        return None

    candidates: list[_OpeningAperture] = []
    breaks = _face_breaks(lines)
    for index, first in enumerate(breaks):
        for second in breaks[index + 1 :]:
            if abs(abs(_dot(first.axis, second.axis)) - 1.0) > _PARALLEL_REL_TOL:
                continue
            if (
                abs(first.gap_start - second.gap_start) > _COORD_TOL
                or abs(first.gap_end - second.gap_end) > _COORD_TOL
            ):
                continue

            has_left_jamb = any(
                _segment_matches(line, first.start_point, second.start_point)
                for line in lines
            )
            has_right_jamb = any(
                _segment_matches(line, first.end_point, second.end_point)
                for line in lines
            )
            if not has_left_jamb or not has_right_jamb:
                continue

            axis = first.axis
            normal = (-axis[1], axis[0])
            along_values = (
                _dot(first.start_point, axis),
                _dot(first.end_point, axis),
                _dot(second.start_point, axis),
                _dot(second.end_point, axis),
            )
            normal_values = (
                _dot(first.start_point, normal),
                _dot(first.end_point, normal),
                _dot(second.start_point, normal),
                _dot(second.end_point, normal),
            )
            along_min, along_max = min(along_values), max(along_values)
            normal_min, normal_max = min(normal_values), max(normal_values)
            if (
                along_max - along_min <= _COORD_TOL
                or normal_max - normal_min <= _COORD_TOL
            ):
                continue
            candidates.append(
                _OpeningAperture(
                    axis=axis,
                    normal=normal,
                    along_min=along_min,
                    along_max=along_max,
                    normal_min=normal_min,
                    normal_max=normal_max,
                )
            )

    unique: dict[tuple[float, ...], _OpeningAperture] = {}
    for candidate in candidates:
        key = (
            round(candidate.axis[0], 9),
            round(candidate.axis[1], 9),
            round(candidate.along_min, 6),
            round(candidate.along_max, 6),
            round(candidate.normal_min, 6),
            round(candidate.normal_max, 6),
        )
        unique.setdefault(key, candidate)
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def _aperture_contains_bbox(aperture: _OpeningAperture, bbox: BBox) -> bool:
    """Return True if the text bounding box overlaps the opening aperture.

    Both the along-axis centroid and normal-axis centroid of the bbox must
    lie strictly within the authenticated jamb-bounded aperture.
    """
    x0, y0, x1, y1 = bbox
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    along_vals = [_dot(c, aperture.axis) for c in corners]
    normal_vals = [_dot(c, aperture.normal) for c in corners]
    
    bbox_along_center = sum(along_vals) / 4.0
    along_overlap = (
        bbox_along_center >= aperture.along_min - _COORD_TOL
        and bbox_along_center <= aperture.along_max + _COORD_TOL
    )
    
    bbox_normal_center = sum(normal_vals) / 4.0
    normal_overlap = (
        bbox_normal_center >= aperture.normal_min - _COORD_TOL
        and bbox_normal_center <= aperture.normal_max + _COORD_TOL
    )
    return along_overlap and normal_overlap


def _row_groups_for_page(
    words: Sequence[tuple[str, str, Sequence[float]]],
    *,
    tol: float = _ROW_Y_TOLERANCE,
) -> list[tuple[dict[str, Any], tuple[str, ...]]]:
    usable: list[tuple[float, float, float, float, str, str]] = []
    for observation_id, text, geometry in words:
        bbox = _bbox_of_points(_geometry_points(geometry))
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        usable.append((x0, y0, x1, y1, text, observation_id))
    if not usable:
        return []

    usable.sort(key=lambda item: ((item[1] + item[3]) / 2.0, item[0]))
    rows: list[list[tuple[float, float, float, float, str, str]]] = []
    row_centers: list[float] = []
    for item in usable:
        center = (item[1] + item[3]) / 2.0
        best_index = -1
        best_delta = math.inf
        for index, row_center in enumerate(row_centers):
            delta = abs(center - row_center)
            if delta <= tol and delta < best_delta:
                best_index, best_delta = index, delta
        if best_index < 0:
            rows.append([item])
            row_centers.append(center)
        else:
            rows[best_index].append(item)
            row_centers[best_index] = sum(
                (row[1] + row[3]) / 2.0 for row in rows[best_index]
            ) / len(rows[best_index])

    result: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    for row in rows:
        row.sort(key=lambda item: item[0])
        result.append(
            (
                {
                    "text": "\t".join(item[4] for item in row),
                    "bounds": [(item[0], item[2]) for item in row],
                    "center_y": sum((item[1] + item[3]) / 2.0 for item in row) / len(row),
                },
                tuple(item[5] for item in row),
            )
        )
    return result


def _is_header_row(cells: Sequence[str]) -> bool:
    mapping = detect_header(cells)
    return "mark" in mapping or "dims" in mapping


def _header_table_specs(
    row: dict[str, Any],
    ids: Sequence[str],
) -> list[tuple[dict[str, Any], float, float]]:
    """Split one visual header line into independent horizontal tables.

    The page row grouper intentionally groups by Y only. Construction drawings
    can place door and window schedules side-by-side at the same Y coordinates;
    treating that visual line as one table can silently let the first header
    consume cells from the second. This helper finds every MARK/TYPE-style
    header start, validates each slice with the shared header rules, and gives
    each table a non-overlapping horizontal source-derived window.
    """
    cells = [cell.strip() for cell in str(row.get("text", "")).split("\t")]
    bounds = list(row.get("bounds", []) or [])
    if not cells or len(bounds) != len(cells):
        return []

    raw_mark_starts = [
        index
        for index, cell in enumerate(cells)
        if "mark" in detect_header([cell])
    ]
    if not raw_mark_starts:
        if not _is_header_row(cells):
            return []
        mark_starts = [0]
    else:
        # Header phrases such as "DOOR TYPE WIDTH HEIGHT" legitimately contain
        # more than one token that individually maps to the mark role. Treat a
        # later mark-like token as a new table only after the current slice has
        # already established at least one non-mark schedule column.
        mark_starts = [raw_mark_starts[0]]
        for candidate_start in raw_mark_starts[1:]:
            current_slice = cells[mark_starts[-1]:candidate_start]
            current_mapping = detect_header(current_slice)
            if (
                "mark" in current_mapping
                and any(
                    key in current_mapping
                    for key in ("dims", "width", "height", "count", "desc")
                )
            ):
                mark_starts.append(candidate_start)

    specs: list[tuple[dict[str, Any], float, float]] = []
    for position, start in enumerate(mark_starts):
        end = mark_starts[position + 1] if position + 1 < len(mark_starts) else len(cells)
        table_cells = cells[start:end]
        mapping = detect_header(table_cells)
        if "mark" not in mapping:
            continue
        if not any(key in mapping for key in ("dims", "width", "height", "count", "desc")):
            continue

        if position == 0:
            left = float(bounds[start][0]) - 20.0
        else:
            left = (float(bounds[start - 1][1]) + float(bounds[start][0])) / 2.0

        if position + 1 < len(mark_starts):
            next_start = mark_starts[position + 1]
            right = (
                float(bounds[next_start - 1][1]) + float(bounds[next_start][0])
            ) / 2.0
        else:
            right = math.inf

        specs.append(
            (
                {
                    "text": "\t".join(table_cells),
                    "bounds": bounds[start:end],
                    "center_y": row.get("center_y", -math.inf),
                    "header_observation_ids": tuple(ids[start:end]),
                },
                left,
                right,
            )
        )
    return specs


def _row_slice_for_window(
    row: dict[str, Any],
    ids: Sequence[str],
    *,
    left: float,
    right: float,
) -> tuple[dict[str, Any], tuple[str, ...]] | None:
    cells = [cell.strip() for cell in str(row.get("text", "")).split("\t")]
    bounds = list(row.get("bounds", []) or [])
    if not cells or len(bounds) != len(cells) or len(ids) != len(cells):
        return None

    selected: list[tuple[str, tuple[float, float], str]] = []
    for cell, bound, observation_id in zip(cells, bounds, ids):
        center_x = (float(bound[0]) + float(bound[1])) / 2.0
        if center_x < left or center_x >= right:
            continue
        selected.append(
            (
                cell,
                (float(bound[0]), float(bound[1])),
                str(observation_id),
            )
        )

    if not selected:
        return None
    return (
        {
            "text": "\t".join(item[0] for item in selected),
            "bounds": [item[1] for item in selected],
            "center_y": row.get("center_y", math.inf),
        },
        tuple(item[2] for item in selected),
    )


def _schedule_entries_for_page(
    page_rows: Sequence[tuple[dict[str, Any], tuple[str, ...]]],
    page_no: int,
) -> list[tuple[ScheduleEntry, tuple[str, ...]]]:
    """Discover every authenticated schedule table on one page.

    Each header gets an independent horizontal window. If two distinct source
    rows bind the same mark, downstream authority sees both and fails closed
    instead of silently choosing whichever table appeared first in reading
    order.
    """
    header_specs: list[tuple[int, dict[str, Any], float, float]] = []
    for index, (row, ids) in enumerate(page_rows):
        for header_row, left, right in _header_table_specs(row, ids):
            header_specs.append((index, header_row, left, right))

    result: list[tuple[ScheduleEntry, tuple[str, ...]]] = []
    if not header_specs:
        return result

    max_y_gap = 50.0
    for header_index, header_row, left, right in header_specs:
        last_y = float(header_row.get("center_y", -math.inf))
        for row_index in range(header_index + 1, len(page_rows)):
            row, ids = page_rows[row_index]
            current_y = float(row.get("center_y", math.inf))
            if current_y - last_y > max_y_gap:
                break

            later_headers = _header_table_specs(row, ids)
            if any(
                not (candidate_right <= left or candidate_left >= right)
                for _candidate, candidate_left, candidate_right in later_headers
            ):
                break

            sliced = _row_slice_for_window(row, ids, left=left, right=right)
            if sliced is None:
                continue
            table_row, table_ids = sliced
            last_y = current_y
            for entry in parse_schedule_rows([header_row, table_row], page_no=page_no):
                result.append((entry, table_ids))
    return result


class ScheduleOpeningInstanceBindingAuthority:
    def __init__(
        self,
        results: Mapping[_RecordKey, ScheduleOpeningInstanceBindingResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("ScheduleOpeningInstanceBindingAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: ScheduleOpeningInstanceBindingSelector,
    ) -> ScheduleOpeningInstanceBindingResult:
        if not isinstance(selector, ScheduleOpeningInstanceBindingSelector):
            raise TypeError("selector must be ScheduleOpeningInstanceBindingSelector")
        result = self._results.get(
            _record_key(
                selector.document_id,
                selector.revision_id,
                selector.source_sha256,
                selector.snapshot_id,
                selector.decision_scope_id,
                selector.opening_record_id,
            )
        )
        if result is not None:
            return result
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "schedule_opening_instance_binding_record_unavailable",
        )


class ScheduleOpeningInstanceBindingProducer:
    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _BINDING_PRODUCER_SEAL:
            raise TypeError(
                "ScheduleOpeningInstanceBindingProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source_visibility_producer = source_visibility_producer
        self._results: dict[_RecordKey, ScheduleOpeningInstanceBindingResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> ScheduleOpeningInstanceBindingProducer:
        return cls(source_visibility_producer, _seal=_BINDING_PRODUCER_SEAL)

    def publish_scope(
        self,
        *,
        opening_selector: ObservationSelector,
        decision_scope_id: str,
    ) -> ScheduleOpeningInstanceBindingResult:
        _require_nonempty(decision_scope_id, "decision_scope_id")
        if not isinstance(opening_selector, ObservationSelector):
            raise TypeError("opening_selector must be ObservationSelector")

        visibility = self._source_visibility_producer.authority()
        text_integrity = self._source_visibility_producer.text_integrity_authority()
        physical = PhysicalOpeningAuthority(visibility)

        existence = physical.prove_existence(opening_selector)
        opening = existence.existence_record
        if (
            existence.status is not EvidenceResolutionStatus.CORROBORATED
            or existence.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
        ):
            key = _record_key(
                opening_selector.document_id,
                opening_selector.revision_id,
                opening_selector.source_sha256,
                opening_selector.snapshot_id,
                decision_scope_id,
                "unresolved",
            )
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    BINDING_OPENING_UNRESOLVED,
                ),
            )

        key = _record_key(
            opening.document_id,
            opening.revision_id,
            opening.source_sha256,
            opening.snapshot_id,
            decision_scope_id,
            opening.record_id,
        )

        published = self._source_visibility_producer.published_snapshot_for_revision(
            opening.revision_id
        )
        if (
            published is None
            or published.revision.document_id != opening.document_id
            or published.revision.source_sha256 != opening.source_sha256
            or published.snapshot.snapshot_id != opening.snapshot_id
        ):
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    BINDING_SOURCE_SCOPE_UNAVAILABLE,
                ),
            )

        if published.coverage.state != "complete" or published.coverage.failed_pages:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    BINDING_PARTIAL_SOURCE_COVERAGE,
                ),
            )

        opening_records: list[SourceObservationRecord] = []
        for observation_id in opening.source_observation_ids:
            resolved = visibility.resolve_visible(
                ObservationSelector(
                    document_id=opening.document_id,
                    revision_id=opening.revision_id,
                    source_sha256=opening.source_sha256,
                    snapshot_id=opening.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or resolved.observation is None
            ):
                return self._store(
                    key,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        BINDING_GEOMETRY_UNAVAILABLE,
                    ),
                )
            opening_records.append(resolved.observation)

        aperture = _opening_aperture(opening_records)
        if aperture is None:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    BINDING_GEOMETRY_UNAVAILABLE,
                ),
            )

        trusted_by_page: dict[str, list[tuple[str, str, tuple[float, ...]]]] = {}
        for observation_id in published.text_observation_ids:
            text_result = text_integrity.resolve_text(
                ObservationSelector(
                    document_id=opening.document_id,
                    revision_id=opening.revision_id,
                    source_sha256=opening.source_sha256,
                    snapshot_id=opening.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                text_result.status is not EvidenceResolutionStatus.CORROBORATED
                or text_result.trusted_text is None
                or text_result.receipt is None
            ):
                continue
            receipt = text_result.receipt
            trusted_by_page.setdefault(receipt.page_id, []).append(
                (
                    observation_id,
                    text_result.trusted_text,
                    tuple(float(value) for value in receipt.geometry),
                )
            )

        contained_tag_candidates: list[tuple[str, str, BBox, str]] = []
        for observation_id, text, geometry in trusted_by_page.get(opening.page_id, []):
            bbox = _bbox_of_points(_geometry_points(geometry))
            if bbox is None or not _aperture_contains_bbox(aperture, bbox):
                continue
            normalized = normalize_opening_tag(text)
            if normalized is not None:
                contained_tag_candidates.append(
                    (observation_id, normalized.tag, bbox, "native")
                )

        # OCR tags are admitted only through SourceVisibilityProducer's
        # producer-owned, immutable-page lineage handoff.  They may classify
        # a plan aperture, but they are never used as schedule-row text.
        for observation in self._source_visibility_producer.authenticated_ocr_tag_observations(
            opening.revision_id
        ):
            if str(observation.page_id) != str(opening.page_id):
                continue
            bbox = _bbox_of_points(_geometry_points(observation.geometry))
            if bbox is None or not _aperture_contains_bbox(aperture, bbox):
                continue
            normalized = normalize_opening_tag(observation.raw_text)
            if normalized is not None:
                contained_tag_candidates.append(
                    (observation.observation_id, normalized.tag, bbox, "ocr")
                )

        if not contained_tag_candidates:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    BINDING_NO_CONTAINED_TAG,
                ),
            )

        # Native text and OCR can legitimately observe the same printed mark.
        # Collapse only same-mark, substantially-overlapping duplicates; two
        # spatially distinct marks or two different marks remain ambiguous.
        deduped_tags: list[tuple[str, str, BBox, str]] = []
        for candidate in contained_tag_candidates:
            observation_id, mark, bbox, source_kind = candidate
            duplicate_index = next(
                (
                    index
                    for index, existing in enumerate(deduped_tags)
                    if (
                        existing[1] == mark
                        and _bbox_overlap_fraction_of_smaller(existing[2], bbox) >= 0.75
                    )
                ),
                None,
            )
            if duplicate_index is None:
                deduped_tags.append(candidate)
                continue
            # Prefer the independently text-integrity-receipted native word
            # when both native and OCR describe the same physical mark.
            if deduped_tags[duplicate_index][3] == "ocr" and source_kind == "native":
                deduped_tags[duplicate_index] = candidate

        if len(deduped_tags) != 1:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    BINDING_AMBIGUOUS_TAGS,
                ),
            )
        tag_observation_id, tag_mark, _tag_bbox, _tag_source = deduped_tags[0]

        discovered: dict[
            tuple[str, tuple[str, ...]],
            tuple[ScheduleEntry, tuple[str, ...], str],
        ] = {}
        for page_id, words in trusted_by_page.items():
            page_rows = _row_groups_for_page(words)
            if not page_rows:
                continue
            try:
                page_no = int(page_id)
            except (TypeError, ValueError):
                continue
            for entry, ids in _schedule_entries_for_page(page_rows, page_no):
                normalized = normalize_opening_tag(entry.type_mark)
                if normalized is None or normalized.tag != tag_mark:
                    continue
                provenance = (page_id, tuple(sorted(ids)))
                discovered.setdefault(provenance, (entry, tuple(ids), page_id))

        matching_rows = tuple(discovered.values())
        if not matching_rows:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    BINDING_NO_MATCHING_ROW,
                ),
            )
        if len(matching_rows) != 1:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    BINDING_AMBIGUOUS_ROWS,
                ),
            )

        entry, schedule_row_observation_ids, schedule_page_id = matching_rows[0]
        payload = {
            "schema_version": SCHEDULE_OPENING_INSTANCE_BINDING_SCHEMA_VERSION,
            "document_id": opening.document_id,
            "revision_id": opening.revision_id,
            "source_sha256": opening.source_sha256,
            "snapshot_id": opening.snapshot_id,
            "page_id": opening.page_id,
            "decision_scope_id": decision_scope_id,
            "opening_record_id": opening.record_id,
            "tag_observation_id": tag_observation_id,
            "tag_mark": tag_mark,
            "schedule_page_id": schedule_page_id,
            "schedule_row_observation_ids": schedule_row_observation_ids,
            "schedule_row_type_mark": entry.type_mark,
            "schedule_row_width_mm": entry.width_mm,
            "schedule_row_height_mm": entry.height_mm,
            "schedule_row_count": entry.count if entry.count_explicit else None,
            "schedule_row_count_explicit": bool(entry.count_explicit),
        }
        record = ScheduleOpeningInstanceBindingRecord(
            record_id=stable_contract_id(
                "schedule_opening_instance_binding",
                payload,
            ),
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            page_id=opening.page_id,
            decision_scope_id=decision_scope_id,
            opening_record_id=opening.record_id,
            tag_observation_id=tag_observation_id,
            tag_mark=tag_mark,
            schedule_page_id=schedule_page_id,
            schedule_row_observation_ids=schedule_row_observation_ids,
            schedule_row_type_mark=entry.type_mark,
            schedule_row_width_mm=entry.width_mm,
            schedule_row_height_mm=entry.height_mm,
            schedule_row_count=entry.count if entry.count_explicit else None,
            schedule_row_count_explicit=bool(entry.count_explicit),
        )
        return self._store(
            key,
            ScheduleOpeningInstanceBindingResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(BINDING_RESOLVED,),
                record=record,
            ),
        )

    def authority(self) -> ScheduleOpeningInstanceBindingAuthority:
        return ScheduleOpeningInstanceBindingAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        key: _RecordKey,
        result: ScheduleOpeningInstanceBindingResult,
    ) -> ScheduleOpeningInstanceBindingResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("schedule opening-instance binding producer equivocation")
        self._results[key] = result
        return result


__all__ = [
    "BINDING_AMBIGUOUS_ROWS",
    "BINDING_AMBIGUOUS_TAGS",
    "BINDING_GEOMETRY_UNAVAILABLE",
    "BINDING_NO_CONTAINED_TAG",
    "BINDING_NO_MATCHING_ROW",
    "BINDING_OPENING_UNRESOLVED",
    "BINDING_PARTIAL_SOURCE_COVERAGE",
    "BINDING_RESOLVED",
    "BINDING_SOURCE_SCOPE_UNAVAILABLE",
    "SCHEDULE_OPENING_INSTANCE_BINDING_SCHEMA_VERSION",
    "ScheduleOpeningInstanceBindingAuthority",
    "ScheduleOpeningInstanceBindingProducer",
    "ScheduleOpeningInstanceBindingRecord",
    "ScheduleOpeningInstanceBindingResult",
    "ScheduleOpeningInstanceBindingSelector",
]
