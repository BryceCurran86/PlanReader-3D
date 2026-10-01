"""Producer-owned source-native physical-scale authority.

This module proves one narrow proposition only: an exact source page or exact
producer-derived drawing viewport has a physical mapping from native PDF points
to millimetres, established by authenticated graphic scale-bar geometry and
trusted explicit physical labels.

Text ratio such as ``1:100`` may corroborate or contradict a graphic bar but
cannot mint authority by itself.  Caller calibration, ratio, conversion factor,
status, confidence, coordinates, completeness, nearest/first choice, or
viewport boxes are never accepted as truth inputs.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import hashlib
import math
import re
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_pdf_text_integrity_authority import TRUSTED_PDF_TEXT
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    SourceVisibilityProducer,
    VISIBLE_SOURCE_OBSERVATION_EXISTS,
)
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    segment_page_viewports,
)

PHYSICAL_SCALE_SCHEMA_VERSION = "1.0.0"
PHYSICAL_SCALE_RESOLVED = "physical_scale_resolved"
PHYSICAL_SCALE_SCOPE_UNAVAILABLE = "physical_scale_scope_unavailable"
PHYSICAL_SCALE_VIEWPORT_REQUIRED = "physical_scale_viewport_required"
PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE = "physical_scale_viewport_unavailable"
PHYSICAL_SCALE_BAR_UNAVAILABLE = "physical_scale_bar_unavailable"
PHYSICAL_SCALE_CONFLICT = "physical_scale_conflict"
PHYSICAL_SCALE_SOURCE_INTEGRITY_FAILURE = "physical_scale_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, Optional[str]]
_Point = tuple[float, float]

_PHYSICAL_LABEL_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(mm|cm|m)\s*$", re.I)
_ZERO_RE = re.compile(r"^\s*0(?:\.0+)?\s*$")
_RATIO_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b")
_SEGMENT_PRIMITIVE_RE = re.compile(r"^visible:segment:d(\d+)i(\d+)$")


@dataclass(frozen=True)
class PhysicalScaleSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be non-empty")
        if self.viewport_id is not None and not str(self.viewport_id).strip():
            raise ValueError("viewport_id must be non-empty when provided")

    @property
    def key(self) -> _Key:
        return (
            str(self.document_id),
            str(self.revision_id),
            str(self.source_sha256),
            str(self.snapshot_id),
            str(self.page_id),
            None if self.viewport_id is None else str(self.viewport_id),
        )


@dataclass(frozen=True)
class PhysicalScaleEvidence:
    selector: PhysicalScaleSelector
    record_id: str
    source_kind: str
    source_span_pt: float
    physical_span_mm: float
    points_per_mm: float
    mm_per_point: float
    source_segment_observation_ids: tuple[str, ...]
    source_text_observation_ids: tuple[str, ...]
    viewport_id: Optional[str]
    schema_version: str = PHYSICAL_SCALE_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalScaleResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: Optional[PhysicalScaleEvidence] = None
    schema_version: str = PHYSICAL_SCALE_SCHEMA_VERSION


@dataclass(frozen=True)
class _TrustedWord:
    observation_id: str
    text: str
    bbox: tuple[float, float, float, float]

    @property
    def center(self) -> _Point:
        return ((self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0)

    @property
    def height(self) -> float:
        return max(0.0, self.bbox[3] - self.bbox[1])


@dataclass(frozen=True)
class _VisibleSegment:
    observation_id: str
    source_primitive_ref: str
    start: _Point
    end: _Point
    duplicate_observation_ids: tuple[str, ...] = ()

    @property
    def length(self) -> float:
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])

    @property
    def observation_ids(self) -> tuple[str, ...]:
        return tuple(sorted((self.observation_id, *self.duplicate_observation_ids)))


@dataclass(frozen=True)
class _BarCandidate:
    span_pt: float
    physical_span_mm: float
    segment_ids: tuple[str, ...]
    text_ids: tuple[str, ...]

    @property
    def points_per_mm(self) -> float:
        return self.span_pt / self.physical_span_mm


def _blocked(status: EvidenceResolutionStatus, *reasons: str) -> PhysicalScaleResult:
    clean = tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason)))
    return PhysicalScaleResult(
        status=status,
        reason_codes=clean or (PHYSICAL_SCALE_SCOPE_UNAVAILABLE,),
        evidence=None,
    )


def _point_in_bbox(point: _Point, bbox: Sequence[float]) -> bool:
    return (
        float(bbox[0]) <= point[0] <= float(bbox[2])
        and float(bbox[1]) <= point[1] <= float(bbox[3])
    )


def _segment_in_bbox(segment: _VisibleSegment, bbox: Sequence[float]) -> bool:
    return _point_in_bbox(segment.start, bbox) and _point_in_bbox(segment.end, bbox)


def _vector(segment: _VisibleSegment) -> _Point:
    return (segment.end[0] - segment.start[0], segment.end[1] - segment.start[1])


def _unit(segment: _VisibleSegment) -> Optional[_Point]:
    length = segment.length
    if length <= 1e-9:
        return None
    dx, dy = _vector(segment)
    return (dx / length, dy / length)


def _dot(left: _Point, right: _Point) -> float:
    return left[0] * right[0] + left[1] * right[1]


def _distance(left: _Point, right: _Point) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


_TICK_MAX_LENGTH_RATIO = 0.75
_TICK_PERPENDICULAR_TOLERANCE_DEG = 5.0
_TICK_PARAMETER_MIN = 0.15
_TICK_PARAMETER_MAX = 0.85
_TICK_MAX_DISTANCE_PT = 0.5
_TICK_INDEX_ANGLE_BUCKET_DEG = 5.0


class _TickEndpointIndex:
    """Conservative broad phase for physical-scale endpoint ticks.

    The exact tick predicate remains in _tick_for_endpoint. This index only
    removes segments that cannot possibly pass it.

    For any accepted tick:
    - tick.length <= 0.75 * baseline.length;
    - the baseline endpoint projects into tick parameter [0.15, 0.85];
    - perpendicular distance to the tick is at most 0.5pt.

    Therefore the tick midpoint is within
    hypot(0.35 * 0.75 * baseline.length, 0.5) of the endpoint. Midpoints
    are indexed once by orientation and sorted X coordinate. Query results are
    still rechecked by the unchanged exact predicate.
    """

    def __init__(self, segments: Sequence[_VisibleSegment]) -> None:
        self._segments = tuple(segments)
        self._index_by_identity = {
            id(segment): index for index, segment in enumerate(self._segments)
        }
        lengths: list[float] = []
        units: list[Optional[_Point]] = []
        vectors: list[_Point] = []
        denoms: list[float] = []
        observation_id_sets: list[frozenset[str]] = []
        for segment in self._segments:
            dx = segment.end[0] - segment.start[0]
            dy = segment.end[1] - segment.start[1]
            length = math.hypot(dx, dy)
            lengths.append(length)
            vectors.append((dx, dy))
            denoms.append(dx * dx + dy * dy)
            units.append(
                None if length <= 1e-9 else (dx / length, dy / length)
            )
            observation_id_sets.append(frozenset(segment.observation_ids))
        self._lengths = tuple(lengths)
        self._units = tuple(units)
        self._vectors = tuple(vectors)
        self._denoms = tuple(denoms)
        self._observation_id_sets = tuple(observation_id_sets)
        self._angle_width = _TICK_INDEX_ANGLE_BUCKET_DEG
        self._angle_bucket_count = max(
            1, int(math.ceil(180.0 / self._angle_width))
        )
        by_angle: dict[int, list[tuple[float, float, int]]] = {}
        unindexed: list[int] = []
        for index, segment in enumerate(self._segments):
            unit = self._units[index]
            if unit is None:
                continue
            angle = math.degrees(math.atan2(unit[1], unit[0])) % 180.0
            midpoint_x = (segment.start[0] + segment.end[0]) / 2.0
            midpoint_y = (segment.start[1] + segment.end[1]) / 2.0
            if not all(
                math.isfinite(value)
                for value in (angle, midpoint_x, midpoint_y, self._lengths[index])
            ):
                # Preserve legacy behavior for malformed source geometry by
                # keeping it in every exact candidate universe instead of
                # attempting to bucket a non-finite coordinate.
                unindexed.append(index)
                continue
            bucket = self._angle_bucket(angle)
            by_angle.setdefault(bucket, []).append(
                (midpoint_x, midpoint_y, index)
            )
        self._by_angle = {
            bucket: tuple(sorted(rows))
            for bucket, rows in by_angle.items()
        }
        self._x_by_angle = {
            bucket: tuple(row[0] for row in rows)
            for bucket, rows in self._by_angle.items()
        }
        self._unindexed = tuple(unindexed)

    def _angle_bucket(self, angle_deg: float) -> int:
        return (
            int(math.floor((float(angle_deg) % 180.0) / self._angle_width))
            % self._angle_bucket_count
        )

    def candidates(
        self,
        baseline: _VisibleSegment,
        endpoint: _Point,
    ) -> tuple[_VisibleSegment, ...]:
        baseline_index = self._index_by_identity.get(id(baseline))
        if baseline_index is None:
            baseline_unit = _unit(baseline)
            baseline_length = baseline.length
        else:
            baseline_unit = self._units[baseline_index]
            baseline_length = self._lengths[baseline_index]
        if baseline_unit is None:
            return ()
        if not all(
            math.isfinite(value)
            for value in (
                baseline_length,
                baseline.start[0],
                baseline.start[1],
                baseline.end[0],
                baseline.end[1],
                endpoint[0],
                endpoint[1],
                baseline_unit[0],
                baseline_unit[1],
            )
        ):
            return self._segments

        perpendicular_angle = (
            math.degrees(math.atan2(baseline_unit[1], baseline_unit[0]))
            + 90.0
        ) % 180.0
        center_bucket = self._angle_bucket(perpendicular_angle)

        max_along_midpoint = (
            max(
                abs(0.5 - _TICK_PARAMETER_MIN),
                abs(_TICK_PARAMETER_MAX - 0.5),
            )
            * _TICK_MAX_LENGTH_RATIO
            * baseline_length
        )
        radius = math.hypot(max_along_midpoint, _TICK_MAX_DISTANCE_PT) + 1e-9
        min_x = endpoint[0] - radius
        max_x = endpoint[0] + radius
        min_y = endpoint[1] - radius
        max_y = endpoint[1] + radius

        found: set[int] = set(self._unindexed)
        # Bucket width equals the exact +/-5 degree acceptance tolerance.
        # The target bucket plus its two neighbors is therefore a complete
        # superset, including the 0/180 wrap boundary.
        for offset in (-1, 0, 1):
            bucket = (center_bucket + offset) % self._angle_bucket_count
            rows = self._by_angle.get(bucket, ())
            xs = self._x_by_angle.get(bucket, ())
            if not rows:
                continue
            first = bisect_left(xs, min_x)
            last = bisect_right(xs, max_x)
            for _mid_x, mid_y, index in rows[first:last]:
                if min_y <= mid_y <= max_y:
                    found.add(index)

        return tuple(self._segments[index] for index in sorted(found))

    def exact_ticks_for_endpoint(
        self,
        baseline: _VisibleSegment,
        endpoint: _Point,
    ) -> tuple[_VisibleSegment, ...]:
        """Return exact legacy tick matches using one cached metric set per segment."""
        baseline_index = self._index_by_identity.get(id(baseline))
        if baseline_index is None:
            return _tick_for_endpoint(
                baseline, endpoint, self.candidates(baseline, endpoint)
            )
        baseline_unit = self._units[baseline_index]
        baseline_length = self._lengths[baseline_index]
        if baseline_unit is None:
            return ()
        baseline_ids = self._observation_id_sets[baseline_index]
        perpendicular_dot_max = math.sin(
            math.radians(_TICK_PERPENDICULAR_TOLERANCE_DEG)
        )
        matches: list[_VisibleSegment] = []
        for tick in self.candidates(baseline, endpoint):
            tick_index = self._index_by_identity.get(id(tick))
            if tick_index is None:
                # Defensive compatibility; this cannot occur for index-owned rows.
                if _tick_for_endpoint(baseline, endpoint, (tick,)):
                    matches.append(tick)
                continue
            if self._observation_id_sets[tick_index] & baseline_ids:
                continue
            tick_length = self._lengths[tick_index]
            if (
                tick_length <= 1e-9
                or tick_length > baseline_length * _TICK_MAX_LENGTH_RATIO
            ):
                continue
            tick_unit = self._units[tick_index]
            if (
                tick_unit is None
                or abs(_dot(baseline_unit, tick_unit)) > perpendicular_dot_max
            ):
                continue
            vx, vy = self._vectors[tick_index]
            denom = self._denoms[tick_index]
            if denom <= 1e-12:
                distance = _distance(endpoint, tick.start)
                parameter = 0.0
            else:
                parameter = (
                    (endpoint[0] - tick.start[0]) * vx
                    + (endpoint[1] - tick.start[1]) * vy
                ) / denom
                clamped = min(1.0, max(0.0, parameter))
                projection = (
                    tick.start[0] + clamped * vx,
                    tick.start[1] + clamped * vy,
                )
                distance = _distance(endpoint, projection)
            tolerance = max(
                1e-4,
                min(_TICK_MAX_DISTANCE_PT, tick_length * 0.01),
            )
            if distance > tolerance:
                continue
            if not (_TICK_PARAMETER_MIN <= parameter <= _TICK_PARAMETER_MAX):
                continue
            matches.append(tick)
        return tuple(sorted(matches, key=lambda item: item.observation_id))


def _primitive_position(segment: _VisibleSegment) -> Optional[tuple[int, int]]:
    match = _SEGMENT_PRIMITIVE_RE.match(segment.source_primitive_ref)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _coalesce_retraced_segments(
    segments: Sequence[_VisibleSegment],
) -> tuple[_VisibleSegment, ...]:
    """Coalesce only exact reverse retraces from one adjacent native path.

    PyMuPDF can expose a terminal line in a multi-line path twice in opposite
    directions.  Both authenticated observation IDs remain in provenance; this
    normalization only prevents that source representation detail from looking
    like two competing scale ticks.
    """
    # Only adjacent primitives in the same native drawing can pass the
    # existing predicate. Index that immutable ancestry once instead of
    # reparsing all N source references for every segment. Keep every entry
    # in a bucket: competing retraces must still prevent coalescing.
    positions = [_primitive_position(segment) for segment in segments]
    by_position: dict[tuple[int, int], list[_VisibleSegment]] = {}
    for segment, position in zip(segments, positions):
        if position is not None:
            by_position.setdefault(position, []).append(segment)

    consumed: set[str] = set()
    normalized: list[_VisibleSegment] = []
    for index, segment in sorted(enumerate(segments), key=lambda item: item[1].observation_id):
        if segment.observation_id in consumed:
            continue
        position = positions[index]
        matches = []
        if position is not None:
            drawing_index, primitive_index = position
            neighbours = (
                *by_position.get((drawing_index, primitive_index - 1), ()),
                *by_position.get((drawing_index, primitive_index + 1), ()),
            )
            for other in neighbours:
                if (
                    other.observation_id != segment.observation_id
                    and other.observation_id not in consumed
                    and _distance(segment.start, other.end) <= 1e-6
                    and _distance(segment.end, other.start) <= 1e-6
                ):
                    matches.append(other)
        if len(matches) == 1:
            other = matches[0]
            consumed.add(other.observation_id)
            normalized.append(
                _VisibleSegment(
                    observation_id=segment.observation_id,
                    source_primitive_ref=segment.source_primitive_ref,
                    start=segment.start,
                    end=segment.end,
                    duplicate_observation_ids=tuple(
                        sorted((*segment.duplicate_observation_ids, *other.observation_ids))
                    ),
                )
            )
        else:
            normalized.append(segment)
        consumed.add(segment.observation_id)
    return tuple(normalized)


def _distance_point_to_segment(point: _Point, segment: _VisibleSegment) -> tuple[float, float]:
    vx, vy = _vector(segment)
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return _distance(point, segment.start), 0.0
    t = ((point[0] - segment.start[0]) * vx + (point[1] - segment.start[1]) * vy) / denom
    clamped = min(1.0, max(0.0, t))
    projection = (segment.start[0] + clamped * vx, segment.start[1] + clamped * vy)
    return _distance(point, projection), t


def _physical_mm(text: str) -> Optional[float]:
    match = _PHYSICAL_LABEL_RE.match(str(text))
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if not math.isfinite(value) or value <= 0:
        return None
    if unit == "m":
        return value * 1000.0
    if unit == "cm":
        return value * 10.0
    return value


def _scope_words(words: Sequence[_TrustedWord], bbox: Sequence[float]) -> tuple[_TrustedWord, ...]:
    return tuple(word for word in words if _point_in_bbox(word.center, bbox))


def _scope_segments(
    segments: Sequence[_VisibleSegment], bbox: Sequence[float]
) -> tuple[_VisibleSegment, ...]:
    return tuple(segment for segment in segments if _segment_in_bbox(segment, bbox))


def _endpoint_words(
    baseline: _VisibleSegment,
    endpoint: _Point,
    tick_length: float,
    words: Sequence[_TrustedWord],
) -> tuple[_TrustedWord, ...]:
    baseline_unit = _unit(baseline)
    if baseline_unit is None:
        return ()
    normal = (-baseline_unit[1], baseline_unit[0])
    max_word_height = max((word.height for word in words), default=0.0)
    cross_margin = max(1.5 * tick_length, 2.2 * max_word_height)
    # Endpoint label windows must not overlap along the bar.  This preserves
    # ambiguity within each endpoint while avoiding nearest/first assignment.
    along_margin = min(cross_margin, baseline.length * 0.45)
    return tuple(
        word
        for word in words
        if abs(_dot((word.center[0] - endpoint[0], word.center[1] - endpoint[1]), baseline_unit))
        <= along_margin
        and abs(_dot((word.center[0] - endpoint[0], word.center[1] - endpoint[1]), normal))
        <= cross_margin
    )


def _endpoint_semantics(words: Sequence[_TrustedWord]) -> tuple[bool, tuple[tuple[float, str], ...]]:
    has_zero = any(_ZERO_RE.match(word.text) is not None for word in words)
    physical: list[tuple[float, str]] = []
    for word in words:
        value = _physical_mm(word.text)
        if value is not None:
            physical.append((value, word.observation_id))
    unique: dict[float, str] = {}
    for value, observation_id in physical:
        unique.setdefault(round(value, 9), observation_id)
    return has_zero, tuple((value, unique[value]) for value in sorted(unique))


def _tick_for_endpoint(
    baseline: _VisibleSegment,
    endpoint: _Point,
    segments: Sequence[_VisibleSegment],
) -> tuple[_VisibleSegment, ...]:
    baseline_unit = _unit(baseline)
    if baseline_unit is None:
        return ()
    candidates: list[_VisibleSegment] = []
    for tick in segments:
        if set(tick.observation_ids) & set(baseline.observation_ids):
            continue
        if (
            tick.length <= 1e-9
            or tick.length > baseline.length * _TICK_MAX_LENGTH_RATIO
        ):
            continue
        tick_unit = _unit(tick)
        if (
            tick_unit is None
            or abs(_dot(baseline_unit, tick_unit))
            > math.sin(math.radians(_TICK_PERPENDICULAR_TOLERANCE_DEG))
        ):
            continue
        distance, parameter = _distance_point_to_segment(endpoint, tick)
        tolerance = max(
            1e-4,
            min(_TICK_MAX_DISTANCE_PT, tick.length * 0.01),
        )
        if distance > tolerance:
            continue
        # A scale tick crosses the bar endpoint in its interior.  Rectangle
        # corners terminate at the endpoint and therefore do not qualify.
        if not (_TICK_PARAMETER_MIN <= parameter <= _TICK_PARAMETER_MAX):
            continue
        candidates.append(tick)
    return tuple(sorted(candidates, key=lambda item: item.observation_id))


def _bar_candidates(
    segments: Sequence[_VisibleSegment],
    words: Sequence[_TrustedWord],
) -> tuple[_BarCandidate, ...]:
    candidates: list[_BarCandidate] = []
    tick_index = _TickEndpointIndex(segments)
    for baseline in segments:
        if baseline.length <= 1e-6:
            continue
        left_ticks = tick_index.exact_ticks_for_endpoint(
            baseline, baseline.start
        )
        right_ticks = tick_index.exact_ticks_for_endpoint(
            baseline, baseline.end
        )
        if len(left_ticks) != 1 or len(right_ticks) != 1:
            continue
        left_tick, right_tick = left_ticks[0], right_ticks[0]
        if set(left_tick.observation_ids) & set(right_tick.observation_ids):
            continue
        left_words = _endpoint_words(baseline, baseline.start, left_tick.length, words)
        right_words = _endpoint_words(baseline, baseline.end, right_tick.length, words)
        left_zero, left_physical = _endpoint_semantics(left_words)
        right_zero, right_physical = _endpoint_semantics(right_words)

        physical_value: Optional[float] = None
        label_id: Optional[str] = None
        zero_ids: tuple[str, ...] = ()
        if left_zero and not left_physical and len(right_physical) == 1 and not right_zero:
            physical_value, label_id = right_physical[0]
            zero_ids = tuple(sorted(word.observation_id for word in left_words if _ZERO_RE.match(word.text)))
        elif right_zero and not right_physical and len(left_physical) == 1 and not left_zero:
            physical_value, label_id = left_physical[0]
            zero_ids = tuple(sorted(word.observation_id for word in right_words if _ZERO_RE.match(word.text)))
        else:
            continue
        if physical_value is None or label_id is None or not zero_ids:
            continue

        candidates.append(
            _BarCandidate(
                span_pt=float(baseline.length),
                physical_span_mm=float(physical_value),
                segment_ids=tuple(
                    sorted(
                        (*baseline.observation_ids, *left_tick.observation_ids, *right_tick.observation_ids)
                    )
                ),
                text_ids=tuple(sorted((*zero_ids, label_id))),
            )
        )

    unique: dict[tuple[tuple[str, ...], tuple[str, ...]], _BarCandidate] = {}
    for candidate in candidates:
        unique.setdefault((candidate.segment_ids, candidate.text_ids), candidate)
    return tuple(unique[key] for key in sorted(unique))


def _ratios(words: Sequence[_TrustedWord]) -> tuple[float, ...]:
    values: set[float] = set()
    for word in words:
        for match in _RATIO_RE.finditer(word.text):
            numerator = float(match.group(1))
            denominator = float(match.group(2))
            if numerator > 0 and denominator > 0:
                values.add(round(denominator / numerator, 9))
    return tuple(sorted(values))


class PhysicalScaleAuthority:
    """Sealed selector-only lookup for published physical-scale evidence."""

    def __init__(self, results: Mapping[_Key, PhysicalScaleResult], *, _seal: object = None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("PhysicalScaleAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: PhysicalScaleSelector) -> PhysicalScaleResult:
        if type(selector) is not PhysicalScaleSelector:
            raise TypeError("selector must be PhysicalScaleSelector")
        return self._results.get(
            selector.key,
            _blocked(EvidenceResolutionStatus.ABSTAINED, PHYSICAL_SCALE_SCOPE_UNAVAILABLE),
        )


class PhysicalScaleProducer:
    """Trusted writer derived only from a producer-owned source-visibility root."""

    def __init__(self, source_visibility_producer: SourceVisibilityProducer, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "PhysicalScaleProducer must be obtained from from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._results: dict[_Key, PhysicalScaleResult] = {}
        self._scope_bbox_cache: dict[_Key, tuple[object, object]] = {}
        self._bar_candidates_cache: dict[_Key, tuple[object, ...]] = {}
        self._trusted_words_by_snapshot: dict[
            tuple[str, str, str, str], dict[str, tuple[_TrustedWord, ...]]
        ] = {}
        self._visible_segments_by_snapshot: dict[
            tuple[str, str, str, str], dict[str, tuple[_VisibleSegment, ...]]
        ] = {}

    @classmethod
    def from_source_visibility_producer(
        cls, source_visibility_producer: SourceVisibilityProducer
    ) -> "PhysicalScaleProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    @staticmethod
    def capabilities() -> Mapping[str, bool]:
        return MappingProxyType(
            {
                "source_native_graphic_scale_bar": True,
                "title_block_text_can_mint_firm": False,
                "caller_calibration_can_mint_firm": False,
                "inferred_scale_can_mint_firm": False,
                "viewport_scoped_scale": True,
            }
        )

    def _revision_inputs(self, selector: PhysicalScaleSelector):
        published = self._source.published_snapshot_for_revision(selector.revision_id)
        if published is None:
            return None
        if (
            published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or int(selector.page_id) not in tuple(int(value) for value in published.coverage.decoded_pages)
            or self._source._producer.current_revision_id(selector.document_id) != selector.revision_id
        ):
            return None
        source_bytes = self._source._producer._store.source_bytes_by_revision.get(selector.revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != selector.source_sha256:
            raise RuntimeError(PHYSICAL_SCALE_SOURCE_INTEGRITY_FAILURE)
        return published, bytes(source_bytes)

    @staticmethod
    def _snapshot_key(selector: PhysicalScaleSelector) -> tuple[str, str, str, str]:
        return (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
        )

    def _trusted_words(
        self,
        selector: PhysicalScaleSelector,
        published,
    ) -> tuple[_TrustedWord, ...]:
        snapshot_key = self._snapshot_key(selector)
        cached = self._trusted_words_by_snapshot.get(snapshot_key)
        if cached is None:
            authority = self._source.text_integrity_authority()
            by_page: dict[str, list[_TrustedWord]] = {}
            for observation_id in published.text_observation_ids:
                result = authority.resolve_text(
                    ObservationSelector(
                        document_id=selector.document_id,
                        revision_id=selector.revision_id,
                        source_sha256=selector.source_sha256,
                        snapshot_id=selector.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                receipt = result.receipt
                if (
                    result.status is EvidenceResolutionStatus.CORROBORATED
                    and result.proposition == TRUSTED_PDF_TEXT
                    and result.trusted_text is not None
                    and receipt is not None
                    and len(receipt.geometry) >= 4
                ):
                    by_page.setdefault(str(receipt.page_id), []).append(
                        _TrustedWord(
                            observation_id=observation_id,
                            text=result.trusted_text,
                            bbox=tuple(
                                float(receipt.geometry[index]) for index in range(4)
                            ),
                        )
                    )
            cached = {
                page_id: tuple(words)
                for page_id, words in by_page.items()
            }
            self._trusted_words_by_snapshot[snapshot_key] = cached
        return cached.get(str(selector.page_id), ())

    def _visible_segments(
        self,
        selector: PhysicalScaleSelector,
        published,
    ) -> tuple[_VisibleSegment, ...]:
        snapshot_key = self._snapshot_key(selector)
        cached = self._visible_segments_by_snapshot.get(snapshot_key)
        if cached is None:
            authority = self._source.authority()
            by_page: dict[str, list[_VisibleSegment]] = {}
            for observation_id in published.visible_observation_ids:
                result = authority.resolve_visible(
                    ObservationSelector(
                        document_id=selector.document_id,
                        revision_id=selector.revision_id,
                        source_sha256=selector.source_sha256,
                        snapshot_id=selector.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                observation = result.observation
                if (
                    result.status is EvidenceResolutionStatus.CORROBORATED
                    and result.proposition == VISIBLE_SOURCE_OBSERVATION_EXISTS
                    and observation is not None
                    and len(observation.geometry) == 4
                ):
                    x0, y0, x1, y1 = (
                        float(value) for value in observation.geometry
                    )
                    by_page.setdefault(str(observation.page_id), []).append(
                        _VisibleSegment(
                            observation_id=observation_id,
                            source_primitive_ref=observation.source_primitive_ref,
                            start=(x0, y0),
                            end=(x1, y1),
                        )
                    )
            cached = {
                page_id: _coalesce_retraced_segments(segments)
                for page_id, segments in by_page.items()
            }
            self._visible_segments_by_snapshot[snapshot_key] = cached
        return cached.get(str(selector.page_id), ())

    @staticmethod
    def _scope_bbox(selector: PhysicalScaleSelector, source_bytes: bytes):
        page_index = int(selector.page_id) - 1
        if page_index < 0:
            return None, PHYSICAL_SCALE_SCOPE_UNAVAILABLE
        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            if page_index >= pdf.page_count:
                return None, PHYSICAL_SCALE_SCOPE_UNAVAILABLE
            page = pdf.load_page(page_index)
            viewports = segment_page_viewports(page, page_number=page_index + 1)
            usable = tuple(
                viewport
                for viewport in viewports
                if viewport.status in {
                    ViewportSegmentationStatus.RESOLVED.value,
                    ViewportSegmentationStatus.DERIVED.value,
                }
                and viewport.bounding_box is not None
            )
            if selector.viewport_id is None:
                if usable:
                    return None, PHYSICAL_SCALE_VIEWPORT_REQUIRED
                rect = page.rect
                return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)), None
            matches = tuple(
                viewport
                for viewport in usable
                if viewport.view_id == selector.viewport_id
                and viewport.status == ViewportSegmentationStatus.RESOLVED.value
            )
            if len(matches) != 1:
                return None, PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE
            return tuple(float(value) for value in matches[0].bounding_box), None
        finally:
            pdf.close()

    def publish_scope(self, selector: PhysicalScaleSelector) -> PhysicalScaleResult:
        if type(selector) is not PhysicalScaleSelector:
            raise TypeError("selector must be PhysicalScaleSelector")
        # Published scale evidence is immutable for one exact source/page/viewport
        # selector. Return producer-owned prior evidence before reopening the PDF,
        # re-segmenting viewports, and rescanning scale-bar geometry.
        existing = self._results.get(selector.key)
        if existing is not None:
            return existing
        inputs = self._revision_inputs(selector)
        if inputs is None:
            return _blocked(EvidenceResolutionStatus.ABSTAINED, PHYSICAL_SCALE_SCOPE_UNAVAILABLE)
        published, source_bytes = inputs
        cached_scope = self._scope_bbox_cache.get(selector.key)
        if cached_scope is None:
            scope_bbox, scope_error = self._scope_bbox(selector, source_bytes)
            self._scope_bbox_cache[selector.key] = (scope_bbox, scope_error)
        else:
            scope_bbox, scope_error = cached_scope
        if scope_bbox is None:
            return _blocked(EvidenceResolutionStatus.ABSTAINED, scope_error or PHYSICAL_SCALE_SCOPE_UNAVAILABLE)

        words = _scope_words(self._trusted_words(selector, published), scope_bbox)
        segments = _scope_segments(self._visible_segments(selector, published), scope_bbox)
        cached_bars = self._bar_candidates_cache.get(selector.key)
        if cached_bars is None:
            bars = tuple(_bar_candidates(segments, words))
            self._bar_candidates_cache[selector.key] = bars
        else:
            bars = cached_bars
        if not bars:
            return _blocked(EvidenceResolutionStatus.ABSTAINED, PHYSICAL_SCALE_BAR_UNAVAILABLE)

        mappings = {round(bar.points_per_mm, 9) for bar in bars}
        if len(mappings) != 1:
            return _blocked(EvidenceResolutionStatus.CONFLICT, PHYSICAL_SCALE_CONFLICT)
        representative = sorted(bars, key=lambda bar: (bar.segment_ids, bar.text_ids))[0]
        span_pt = float(representative.span_pt)
        points_per_mm = float(representative.points_per_mm)

        ratios = _ratios(words)
        if len(ratios) > 1:
            return _blocked(EvidenceResolutionStatus.CONFLICT, PHYSICAL_SCALE_CONFLICT)
        if len(ratios) == 1:
            denominator = ratios[0]
            expected_points_per_mm = POINTS_PER_METRE_AT_1_1 / denominator / 1000.0
            tolerance = max(1e-9, expected_points_per_mm * 1e-5)
            if abs(points_per_mm - expected_points_per_mm) > tolerance:
                return _blocked(EvidenceResolutionStatus.CONFLICT, PHYSICAL_SCALE_CONFLICT)
            # Ratio text may corroborate the source-native bar measurement,
            # but it is not measurement authority and must not rewrite the
            # bar's observed geometry or geometry-derived mapping.

        if (
            not math.isfinite(points_per_mm)
            or points_per_mm <= 0
            or not math.isfinite(span_pt)
            or span_pt <= 0
        ):
            return _blocked(EvidenceResolutionStatus.CONFLICT, PHYSICAL_SCALE_CONFLICT)
        mm_per_point = 1.0 / points_per_mm

        payload = {
            "selector": selector.key,
            "source_kind": "native_graphic_scale_bar",
            "source_span_pt": round(span_pt, 12),
            "physical_span_mm": round(representative.physical_span_mm, 9),
            "points_per_mm": round(points_per_mm, 15),
            "source_segment_observation_ids": representative.segment_ids,
            "source_text_observation_ids": representative.text_ids,
        }
        evidence = PhysicalScaleEvidence(
            selector=selector,
            record_id=stable_contract_id("physical_scale_v1", payload, digest_chars=32),
            source_kind="native_graphic_scale_bar",
            source_span_pt=span_pt,
            physical_span_mm=float(representative.physical_span_mm),
            points_per_mm=points_per_mm,
            mm_per_point=mm_per_point,
            source_segment_observation_ids=representative.segment_ids,
            source_text_observation_ids=representative.text_ids,
            viewport_id=selector.viewport_id,
        )
        result = PhysicalScaleResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(PHYSICAL_SCALE_RESOLVED,),
            evidence=evidence,
        )
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            raise RuntimeError("physical scale producer equivocation")
        self._results[selector.key] = result
        return result

    def authority(self) -> PhysicalScaleAuthority:
        return PhysicalScaleAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )


__all__ = [
    "PHYSICAL_SCALE_BAR_UNAVAILABLE",
    "PHYSICAL_SCALE_CONFLICT",
    "PHYSICAL_SCALE_RESOLVED",
    "PHYSICAL_SCALE_SCHEMA_VERSION",
    "PHYSICAL_SCALE_SCOPE_UNAVAILABLE",
    "PHYSICAL_SCALE_VIEWPORT_REQUIRED",
    "PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE",
    "PhysicalScaleAuthority",
    "PhysicalScaleEvidence",
    "PhysicalScaleProducer",
    "PhysicalScaleResult",
    "PhysicalScaleSelector",
]
