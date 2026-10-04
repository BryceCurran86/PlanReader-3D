"""Producer-owned gross-frame area authority from marked opening elevations.

This authority does not create physical openings.  It publishes a TYPE-level
gross-frame area only when source-owned elevation evidence proves all of:

* an explicit opening mark (for example W1 / D2);
* two orthogonal native figured dimensions, each witness-bound to vector
  geometry;
* those two spans form a closed axis-aligned frame around the mark; and
* that closed frame contains exactly one explicit opening mark.

The last condition prevents a composite window+door assembly from being
mistaken for the gross frame of one member (for example a sidelight beside a
door).  Project identity, benchmark values, hard-coded coordinates and drawing
scale never participate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionOrientation,
    ObservedGeometrySegment,
    calibrate_dimension_layout,
    extract_dimension_evidence_bundle,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_tag_normalization import normalize_opening_tag
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


OPENING_ELEVATION_FRAME_AREA_SCHEMA_VERSION = "1.0.0"
OPENING_ELEVATION_FRAME_AREA_RESOLVED = "opening_elevation_frame_area_resolved"
OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE = "opening_elevation_frame_area_unavailable"
OPENING_ELEVATION_FRAME_AREA_AMBIGUOUS = "opening_elevation_frame_area_ambiguous"
OPENING_ELEVATION_FRAME_AREA_CONFLICT = "opening_elevation_frame_area_conflict"

_RECORD_SEAL = object()
_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()

_MIN_FRAME_DIMENSION_MM = 150.0
_MAX_FRAME_DIMENSION_MM = 20_000.0
_EDGE_COVERAGE_FRACTION = 0.80
_ASPECT_RELATIVE_TOLERANCE = 0.12


@dataclass(frozen=True)
class OpeningElevationFrameAreaSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    type_mark: str


@dataclass(frozen=True)
class OpeningElevationFrameAreaRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    type_mark: str
    opening_kind: str
    axis_x_mm: float
    axis_y_mm: float
    area_m2: float
    mark_observation_id: str
    dimension_observation_ids: tuple[str, str]
    title_observation_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    dimension_line_ids: tuple[str, str]
    witness_line_ids: tuple[str, ...]
    frame_geometry_ids: tuple[str, ...]
    frame_bbox: tuple[float, float, float, float]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = OPENING_ELEVATION_FRAME_AREA_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("OpeningElevationFrameAreaRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive frame-area record must be CORROBORATED")
        if self.opening_kind not in {"door", "window"}:
            raise ValueError("opening_kind must be door or window")
        if not (
            math.isfinite(self.axis_x_mm)
            and math.isfinite(self.axis_y_mm)
            and self.axis_x_mm > 0.0
            and self.axis_y_mm > 0.0
            and math.isfinite(self.area_m2)
            and self.area_m2 > 0.0
        ):
            raise ValueError("frame dimensions and area must be positive finite values")


@dataclass(frozen=True)
class OpeningElevationFrameAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[OpeningElevationFrameAreaRecord] = None
    schema_version: str = OPENING_ELEVATION_FRAME_AREA_SCHEMA_VERSION


@dataclass(frozen=True)
class _TrustedWord:
    observation_id: str
    text: str
    bbox: tuple[float, float, float, float]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _claim_norm(value: object) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _source_bytes(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
    source_sha256: str,
) -> bytes | None:
    store = getattr(getattr(source, "_producer", None), "_store", None)
    by_revision = getattr(store, "source_bytes_by_revision", None) or {}
    payload = by_revision.get(str(revision_id))
    if payload is None:
        return None
    payload = bytes(payload)
    if hashlib.sha256(payload).hexdigest() != str(source_sha256):
        return None
    return payload


def _center(bbox: Sequence[float]) -> tuple[float, float]:
    return (
        (float(bbox[0]) + float(bbox[2])) / 2.0,
        (float(bbox[1]) + float(bbox[3])) / 2.0,
    )


def _inside(
    point: tuple[float, float],
    bbox: tuple[float, float, float, float],
    *,
    margin: float = 0.0,
) -> bool:
    return (
        bbox[0] - margin <= point[0] <= bbox[2] + margin
        and bbox[1] - margin <= point[1] <= bbox[3] + margin
    )


def _dimension_mm(observation) -> float | None:
    try:
        value = float(observation.value)
    except (TypeError, ValueError, OverflowError):
        return None
    unit = _clean(getattr(observation, "unit", "")).lower()
    if unit == "mm":
        mm = value
    elif unit == "m":
        mm = value * 1000.0
    elif unit == "in":
        mm = value * 25.4
    else:
        return None
    if (
        not math.isfinite(mm)
        or mm < _MIN_FRAME_DIMENSION_MM
        or mm > _MAX_FRAME_DIMENSION_MM
    ):
        return None
    return mm


def _binding_axis(binding) -> tuple[str, float, float] | None:
    endpoints = getattr(binding, "endpoints", None)
    if endpoints is None or len(endpoints) != 2:
        return None
    try:
        x0, y0 = float(endpoints[0][0]), float(endpoints[0][1])
        x1, y1 = float(endpoints[1][0]), float(endpoints[1][1])
    except (TypeError, ValueError, IndexError):
        return None
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dx <= 0.0 and dy <= 0.0:
        return None
    if dx >= dy * 4.0:
        return ("x", min(x0, x1), max(x0, x1))
    if dy >= dx * 4.0:
        return ("y", min(y0, y1), max(y0, y1))
    return None


def _union_coverage(intervals: Sequence[tuple[float, float]], lo: float, hi: float) -> float:
    span = float(hi) - float(lo)
    if span <= 0.0:
        return 0.0
    clipped = []
    for a, b in intervals:
        left, right = max(lo, min(a, b)), min(hi, max(a, b))
        if right > left:
            clipped.append((left, right))
    if not clipped:
        return 0.0
    clipped.sort()
    covered = 0.0
    cur_lo, cur_hi = clipped[0]
    for left, right in clipped[1:]:
        if left <= cur_hi:
            cur_hi = max(cur_hi, right)
        else:
            covered += cur_hi - cur_lo
            cur_lo, cur_hi = left, right
    covered += cur_hi - cur_lo
    return covered / span


def _edge_support(
    segments: Sequence[ObservedGeometrySegment],
    *,
    edge_axis: str,
    coordinate: float,
    span_lo: float,
    span_hi: float,
    tolerance: float,
) -> tuple[float, tuple[str, ...]]:
    intervals = []
    ids = []
    wanted = (
        DimensionOrientation.VERTICAL.value
        if edge_axis == "x"
        else DimensionOrientation.HORIZONTAL.value
    )
    for segment in segments:
        if segment.orientation != wanted:
            continue
        if edge_axis == "x":
            axis = (float(segment.start[0]) + float(segment.end[0])) / 2.0
            interval = (float(segment.start[1]), float(segment.end[1]))
        else:
            axis = (float(segment.start[1]) + float(segment.end[1])) / 2.0
            interval = (float(segment.start[0]), float(segment.end[0]))
        if abs(axis - float(coordinate)) > tolerance:
            continue
        left, right = min(interval), max(interval)
        if right <= span_lo or left >= span_hi:
            continue
        intervals.append(interval)
        ids.append(str(segment.segment_id))
    return (
        _union_coverage(intervals, span_lo, span_hi),
        tuple(sorted(set(ids))),
    )


def _match_trusted_dimension_word(
    trusted_words: Sequence[_TrustedWord],
    observation,
    *,
    tolerance: float,
) -> _TrustedWord | None:
    bbox = getattr(observation, "bbox", None)
    if bbox is None or len(bbox) != 4:
        return None
    target_text = _claim_norm(getattr(observation, "raw_text", ""))
    if not target_text:
        return None
    candidates = []
    for word in trusted_words:
        if _claim_norm(word.text) != target_text:
            continue
        if max(abs(float(word.bbox[i]) - float(bbox[i])) for i in range(4)) <= tolerance:
            candidates.append(word)
    if len(candidates) != 1:
        return None
    return candidates[0]


def _page_family_and_title_ids(
    trusted_words: Sequence[_TrustedWord],
) -> tuple[str | None, tuple[str, ...]]:
    windows = [
        word for word in trusted_words
        if _claim_norm(word.text) in {"window", "windows"}
    ]
    doors = [
        word for word in trusted_words
        if _claim_norm(word.text) in {"door", "doors"}
    ]
    elevations = [
        word for word in trusted_words
        if _claim_norm(word.text) in {"elevation", "elevations"}
    ]
    if not elevations:
        return None, ()
    if bool(windows) == bool(doors):
        return None, ()
    family = "window" if windows else "door"
    title = tuple(
        sorted(
            {
                word.observation_id
                for word in (
                    (*(windows if family == "window" else doors), *elevations)
                )
            }
        )
    )
    return family, title


def _opening_tags(
    trusted_words: Sequence[_TrustedWord],
) -> tuple[tuple[_TrustedWord, str, str], ...]:
    out = []
    for word in trusted_words:
        normalized = normalize_opening_tag(word.text)
        if normalized is None:
            continue
        kind = "window" if normalized.trade_type == "windows" else "door"
        out.append((word, normalized.tag, kind))
    return tuple(out)


def _record_candidates_for_page(
    *,
    page,
    page_id: str,
    published,
    trusted_words: Sequence[_TrustedWord],
) -> tuple[OpeningElevationFrameAreaRecord, ...]:
    family, title_ids = _page_family_and_title_ids(trusted_words)
    all_tags = _opening_tags(trusted_words)
    if family is None or not all_tags:
        return ()

    # Do not raster-scale an elevation. Figured dimensions are source values;
    # vector geometry is used only to prove the frame topology and association.
    bundle = extract_dimension_evidence_bundle(
        page,
        page_num=int(page_id),
        view_id=f"page:{page_id}:opening_elevation_frame",
        view_type=DrawingViewType.ELEVATION.value,
    )
    if not bundle.observations or not bundle.bindings:
        return ()

    layout = calibrate_dimension_layout(page)
    geometry_tolerance = max(
        float(layout.chain_axis_tolerance_pt) * 2.0,
        float(layout.median_word_height_pt) * 0.75,
        1.0,
    )
    word_tolerance = max(float(layout.median_word_height_pt) * 0.20, 0.75)

    binding_by_id = {
        str(binding.observation_id): binding
        for binding in bundle.bindings
        if binding.status == BindingStatus.WITNESS_BOUND.value
        and binding.endpoints is not None
    }
    dimensions = []
    for observation in bundle.observations:
        binding = binding_by_id.get(str(observation.dimension_id))
        if binding is None:
            continue
        mm = _dimension_mm(observation)
        axis = _binding_axis(binding)
        trusted = _match_trusted_dimension_word(
            trusted_words,
            observation,
            tolerance=word_tolerance,
        )
        if mm is None or axis is None or trusted is None:
            continue
        dimensions.append((observation, binding, mm, axis, trusted))

    x_dims = [item for item in dimensions if item[3][0] == "x"]
    y_dims = [item for item in dimensions if item[3][0] == "y"]
    if not x_dims or not y_dims:
        return ()

    records = []
    seen_semantic = set()
    for mark_word, mark, mark_kind in all_tags:
        if mark_kind != family:
            continue
        mark_center = _center(mark_word.bbox)

        for x_item in x_dims:
            x_observation, x_binding, x_mm, x_axis, x_trusted = x_item
            x_lo, x_hi = float(x_axis[1]), float(x_axis[2])
            if not (x_lo < mark_center[0] < x_hi):
                continue
            for y_item in y_dims:
                y_observation, y_binding, y_mm, y_axis, y_trusted = y_item
                y_lo, y_hi = float(y_axis[1]), float(y_axis[2])
                if not (y_lo < mark_center[1] < y_hi):
                    continue

                frame_bbox = (x_lo, y_lo, x_hi, y_hi)
                contained = {
                    contained_mark
                    for contained_word, contained_mark, _kind in all_tags
                    if _inside(_center(contained_word.bbox), frame_bbox)
                }
                # Composite assemblies are not one opening's gross frame.
                if contained != {mark}:
                    continue

                geo_ratio = (x_hi - x_lo) / (y_hi - y_lo)
                physical_ratio = x_mm / y_mm
                if (
                    geo_ratio <= 0.0
                    or physical_ratio <= 0.0
                    or abs(geo_ratio / physical_ratio - 1.0)
                    > _ASPECT_RELATIVE_TOLERANCE
                ):
                    continue

                left_cov, left_ids = _edge_support(
                    bundle.observed_geometry,
                    edge_axis="x",
                    coordinate=x_lo,
                    span_lo=y_lo,
                    span_hi=y_hi,
                    tolerance=geometry_tolerance,
                )
                right_cov, right_ids = _edge_support(
                    bundle.observed_geometry,
                    edge_axis="x",
                    coordinate=x_hi,
                    span_lo=y_lo,
                    span_hi=y_hi,
                    tolerance=geometry_tolerance,
                )
                top_cov, top_ids = _edge_support(
                    bundle.observed_geometry,
                    edge_axis="y",
                    coordinate=y_lo,
                    span_lo=x_lo,
                    span_hi=x_hi,
                    tolerance=geometry_tolerance,
                )
                bottom_cov, bottom_ids = _edge_support(
                    bundle.observed_geometry,
                    edge_axis="y",
                    coordinate=y_hi,
                    span_lo=x_lo,
                    span_hi=x_hi,
                    tolerance=geometry_tolerance,
                )
                if min(left_cov, right_cov, top_cov, bottom_cov) < _EDGE_COVERAGE_FRACTION:
                    continue

                area_m2 = (x_mm * y_mm) / 1_000_000.0
                semantic_key = (
                    mark,
                    round(x_mm, 6),
                    round(y_mm, 6),
                    tuple(round(v, 4) for v in frame_bbox),
                )
                if semantic_key in seen_semantic:
                    continue
                seen_semantic.add(semantic_key)

                source_ids = tuple(
                    sorted(
                        {
                            mark_word.observation_id,
                            x_trusted.observation_id,
                            y_trusted.observation_id,
                            *title_ids,
                        }
                    )
                )
                dimension_line_ids = tuple(
                    sorted(
                        {
                            str(x_binding.dimension_line_id or ""),
                            str(y_binding.dimension_line_id or ""),
                        }
                        - {""}
                    )
                )
                witness_ids = tuple(
                    sorted(
                        {
                            *tuple(str(v) for v in x_binding.witness_line_ids),
                            *tuple(str(v) for v in y_binding.witness_line_ids),
                        }
                    )
                )
                frame_ids = tuple(
                    sorted(
                        {
                            *left_ids,
                            *right_ids,
                            *top_ids,
                            *bottom_ids,
                        }
                    )
                )
                payload = {
                    "schema_version": OPENING_ELEVATION_FRAME_AREA_SCHEMA_VERSION,
                    "document_id": published.revision.document_id,
                    "revision_id": published.revision.revision_id,
                    "source_sha256": published.revision.source_sha256,
                    "snapshot_id": published.snapshot.snapshot_id,
                    "page_id": str(page_id),
                    "type_mark": mark,
                    "opening_kind": mark_kind,
                    "axis_x_mm": x_mm,
                    "axis_y_mm": y_mm,
                    "frame_bbox": tuple(round(v, 6) for v in frame_bbox),
                    "source_observation_ids": source_ids,
                    "dimension_line_ids": dimension_line_ids,
                    "witness_line_ids": witness_ids,
                    "frame_geometry_ids": frame_ids,
                }
                records.append(
                    OpeningElevationFrameAreaRecord(
                        record_id=stable_contract_id(
                            "opening_elevation_frame_area",
                            payload,
                            digest_chars=32,
                        ),
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        page_id=str(page_id),
                        type_mark=mark,
                        opening_kind=mark_kind,
                        axis_x_mm=float(x_mm),
                        axis_y_mm=float(y_mm),
                        area_m2=float(area_m2),
                        mark_observation_id=mark_word.observation_id,
                        dimension_observation_ids=(
                            x_trusted.observation_id,
                            y_trusted.observation_id,
                        ),
                        title_observation_ids=title_ids,
                        source_observation_ids=source_ids,
                        dimension_line_ids=(
                            str(x_binding.dimension_line_id),
                            str(y_binding.dimension_line_id),
                        ),
                        witness_line_ids=witness_ids,
                        frame_geometry_ids=frame_ids,
                        frame_bbox=frame_bbox,
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(OPENING_ELEVATION_FRAME_AREA_RESOLVED,),
                        _seal=_RECORD_SEAL,
                    )
                )
    return tuple(sorted(records, key=lambda item: item.record_id))


class OpeningElevationFrameAreaAuthority:
    def __init__(self, results: Mapping[tuple[str, ...], OpeningElevationFrameAreaResult], *, _seal=None):
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningElevationFrameAreaAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: OpeningElevationFrameAreaSelector,
    ) -> OpeningElevationFrameAreaResult:
        normalized = normalize_opening_tag(selector.type_mark)
        if normalized is None:
            return OpeningElevationFrameAreaResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE,),
            )
        key = (
            _clean(selector.document_id),
            _clean(selector.revision_id),
            _clean(selector.source_sha256),
            _clean(selector.snapshot_id),
            normalized.tag,
        )
        return self._results.get(
            key,
            OpeningElevationFrameAreaResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE,),
            ),
        )


class OpeningElevationFrameAreaProducer:
    def __init__(self, source: SourceVisibilityProducer, *, _seal=None):
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("use from_source_visibility_producer()")
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be an actual SourceVisibilityProducer")
        self._source = source
        self._results: dict[tuple[str, ...], OpeningElevationFrameAreaResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source: SourceVisibilityProducer,
    ) -> "OpeningElevationFrameAreaProducer":
        producer = cls(source, _seal=_PRODUCER_SEAL)
        producer._build()
        return producer

    def _build(self) -> None:
        text_authority = self._source.text_integrity_authority()
        for revision_id, published in sorted(self._source._published_by_revision.items()):
            if (
                self._source._producer.current_revision_id(
                    published.revision.document_id
                )
                != revision_id
            ):
                continue

            words_by_page: dict[str, list[_TrustedWord]] = {}
            for observation_id in published.text_observation_ids:
                result = text_authority.resolve_text(
                    ObservationSelector(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                receipt = result.receipt
                if (
                    result.status is not EvidenceResolutionStatus.CORROBORATED
                    or receipt is None
                    or not result.trusted_text
                ):
                    continue
                try:
                    geometry = tuple(float(v) for v in receipt.geometry)
                except (TypeError, ValueError):
                    continue
                if (
                    len(geometry) != 4
                    or not all(math.isfinite(v) for v in geometry)
                    or geometry[2] <= geometry[0]
                    or geometry[3] <= geometry[1]
                ):
                    continue
                words_by_page.setdefault(str(receipt.page_id), []).append(
                    _TrustedWord(
                        observation_id=str(observation_id),
                        text=str(result.trusted_text),
                        bbox=geometry,
                    )
                )

            payload = _source_bytes(
                self._source,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
            )
            if payload is None:
                continue
            try:
                document = fitz.open(stream=payload, filetype="pdf")
            except Exception:
                continue

            records_by_mark: dict[str, list[OpeningElevationFrameAreaRecord]] = {}
            try:
                for page_id, trusted_words in sorted(
                    words_by_page.items(),
                    key=lambda item: int(item[0]) if item[0].isdigit() else 10**9,
                ):
                    # Cheap source-text gate before vector/dimension extraction.
                    family, _title_ids = _page_family_and_title_ids(trusted_words)
                    if family is None or not _opening_tags(trusted_words):
                        continue
                    if not page_id.isdigit():
                        continue
                    page_index = int(page_id) - 1
                    if page_index < 0 or page_index >= int(document.page_count):
                        continue
                    try:
                        records = _record_candidates_for_page(
                            page=document.load_page(page_index),
                            page_id=page_id,
                            published=published,
                            trusted_words=trusted_words,
                        )
                    except Exception:
                        # Source evidence failure is an abstention, never a
                        # reason to synthesize a commercial measurement.
                        continue
                    for record in records:
                        records_by_mark.setdefault(record.type_mark, []).append(record)
            finally:
                document.close()

            for mark, records in sorted(records_by_mark.items()):
                key = (
                    published.revision.document_id,
                    published.revision.revision_id,
                    published.revision.source_sha256,
                    published.snapshot.snapshot_id,
                    mark,
                )
                # One type mark must resolve to exactly one gross-frame
                # proposition. Repeated/competing frames fail closed.
                semantic = {
                    (
                        round(record.axis_x_mm, 6),
                        round(record.axis_y_mm, 6),
                        round(record.area_m2, 9),
                    )
                    for record in records
                }
                if len(records) == 1:
                    self._results[key] = OpeningElevationFrameAreaResult(
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(OPENING_ELEVATION_FRAME_AREA_RESOLVED,),
                        record=records[0],
                    )
                elif len(semantic) == 1:
                    self._results[key] = OpeningElevationFrameAreaResult(
                        status=EvidenceResolutionStatus.ABSTAINED,
                        reason_codes=(OPENING_ELEVATION_FRAME_AREA_AMBIGUOUS,),
                    )
                else:
                    self._results[key] = OpeningElevationFrameAreaResult(
                        status=EvidenceResolutionStatus.CONFLICT,
                        reason_codes=(OPENING_ELEVATION_FRAME_AREA_CONFLICT,),
                    )

    def authority(self) -> OpeningElevationFrameAreaAuthority:
        return OpeningElevationFrameAreaAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )


__all__ = [
    "OPENING_ELEVATION_FRAME_AREA_AMBIGUOUS",
    "OPENING_ELEVATION_FRAME_AREA_CONFLICT",
    "OPENING_ELEVATION_FRAME_AREA_RESOLVED",
    "OPENING_ELEVATION_FRAME_AREA_SCHEMA_VERSION",
    "OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE",
    "OpeningElevationFrameAreaAuthority",
    "OpeningElevationFrameAreaProducer",
    "OpeningElevationFrameAreaRecord",
    "OpeningElevationFrameAreaResult",
    "OpeningElevationFrameAreaSelector",
    "_edge_support",
    "_record_candidates_for_page",
]
