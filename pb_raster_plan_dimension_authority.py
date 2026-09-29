"""Shadow-only raster figured-dimension authority.

This module composes the existing producer-owned source boundaries:
- SourceVisibilityProducer owns immutable PDF bytes and raster-visible segments.
- A built-in OCR backend reads only a producer-rendered page.
- Numeric OCR is accepted only when raster line/witness geometry binds it to a
  physical dimension-line system.
- An overall span resolves only when one contiguous child chain spans the same
  endpoints and the child values sum exactly to the overall figured value.
- Orthogonal overall spans must reconcile through the canonical page-scale
  resolver.  No commercial quantity is emitted here.

Callers may address only an already-ingested revision and page. They cannot
supply page pixels, OCR strings, line coordinates, scale, tolerance, target
dimensions, or benchmark values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import io
import math
import re
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    ScaleCalibrationStatus,
    ScaleSourceReading,
    ScaleSourceType,
    resolve_page_scale_calibration,
)
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    NullOCRBackend,
    OCRLine,
    RapidOCRBackend,
    RasterOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT,
    RASTER_RENDER_DPI,
    SourceVisibilityProducer,
)


RASTER_PLAN_DIMENSION_SCHEMA_VERSION = "1.0.0"
RASTER_DIMENSION_OCR_DPI = 300
RASTER_DIMENSION_RESOLVED = "raster_dimension_chain_resolved"
RASTER_DIMENSION_TEXT_UNAVAILABLE = "raster_dimension_text_unavailable"
RASTER_DIMENSION_GEOMETRY_UNAVAILABLE = "raster_dimension_geometry_unavailable"
RASTER_DIMENSION_BINDING_AMBIGUOUS = "raster_dimension_binding_ambiguous"
RASTER_DIMENSION_CHILD_CHAIN_UNAVAILABLE = "raster_dimension_child_chain_unavailable"
RASTER_DIMENSION_ORTHOGONAL_SCOPE_UNAVAILABLE = "raster_dimension_orthogonal_scope_unavailable"
RASTER_DIMENSION_SCALE_CONFLICT = "raster_dimension_scale_conflict"
RASTER_DIMENSION_LINEAGE_CONFLICT = "raster_dimension_lineage_conflict"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()
_PRODUCTION_BACKENDS = (
    RapidOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
    NullOCRBackend,
)


@dataclass(frozen=True)
class RasterDimensionTextObservation:
    observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    parent_page_observation_id: str
    raw_text: str
    value_mm: int
    bbox_pt: tuple[float, float, float, float]
    backend_name: str
    backend_version: str
    confidence: Optional[float]
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("RasterDimensionTextObservation is producer-owned")


@dataclass(frozen=True)
class BoundRasterDimension:
    dimension_id: str
    text_observation_id: str
    value_mm: int
    orientation: str
    endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    span_pt: float
    dimension_line_observation_ids: tuple[str, ...]
    witness_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("BoundRasterDimension is producer-owned")


@dataclass(frozen=True)
class RasterOverallDimension:
    overall_dimension_id: str
    orientation: str
    value_mm: int
    span_pt: float
    endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    child_dimension_ids: tuple[str, ...]
    child_values_mm: tuple[int, ...]
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("RasterOverallDimension is producer-owned")


@dataclass(frozen=True)
class RasterPlanDimensionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    document_id: Optional[str] = None
    revision_id: Optional[str] = None
    source_sha256: Optional[str] = None
    snapshot_id: Optional[str] = None
    page_id: Optional[str] = None
    horizontal: Optional[RasterOverallDimension] = None
    vertical: Optional[RasterOverallDimension] = None
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    scale_status: Optional[str] = None
    scale_px_per_m: Optional[float] = None
    bound_dimensions: tuple[BoundRasterDimension, ...] = ()
    quantity_m2: None = None
    schema_version: str = RASTER_PLAN_DIMENSION_SCHEMA_VERSION


@dataclass(frozen=True)
class _VisibleSegment:
    observation_id: str
    geometry: tuple[float, float, float, float]
    orientation: str


@dataclass(frozen=True)
class _LogicalLine:
    orientation: str
    axis: float
    lo: float
    hi: float
    observation_ids: tuple[str, ...]

    @property
    def span(self) -> float:
        return self.hi - self.lo


def _choose_backend() -> RasterOCRBackend:
    for backend in (RapidOCRBackend(), TesseractOCRBackend(), WinOCRBackend()):
        if backend.is_available():
            return backend
    return NullOCRBackend()


def _parse_dimension_value_mm(text: str) -> Optional[int]:
    normalized = re.sub(r"\s+", "", str(text or "").strip()).lower()
    match = re.fullmatch(r"(?P<value>\d{2,6})(?:mm)?", normalized)
    if match is None:
        return None
    value = int(match.group("value"))
    return value if 0 < value <= 1_000_000 else None


def _segment_orientation(
    geometry: Sequence[float],
) -> Optional[str]:
    if len(geometry) != 4:
        return None
    x0, y0, x1, y1 = (float(v) for v in geometry)
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    tol = 72.0 / float(RASTER_RENDER_DPI)
    if dx >= 4.0 and dy <= tol:
        return "horizontal"
    if dy >= 4.0 and dx <= tol:
        return "vertical"
    return None


def _line_parts(segment: _VisibleSegment) -> tuple[float, float, float]:
    x0, y0, x1, y1 = segment.geometry
    if segment.orientation == "horizontal":
        return (0.5 * (y0 + y1), min(x0, x1), max(x0, x1))
    return (0.5 * (x0 + x1), min(y0, y1), max(y0, y1))


def _logical_lines_for_text(
    text: RasterDimensionTextObservation,
    segments: Sequence[_VisibleSegment],
) -> tuple[_LogicalLine, ...]:
    x0, y0, x1, y1 = text.bbox_pt
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    render_point = 72.0 / float(RASTER_RENDER_DPI)
    candidates: dict[tuple[object, ...], _LogicalLine] = {}

    for orientation in ("horizontal", "vertical"):
        if orientation == "horizontal":
            text_lo, text_hi, cross_lo, cross_hi, center = x0, x1, y0, y1, cx
            minor = max(render_point, y1 - y0)
        else:
            text_lo, text_hi, cross_lo, cross_hi, center = y0, y1, x0, x1, cy
            minor = max(render_point, x1 - x0)
        axis_margin = max(2.0 * render_point, 0.75 * minor)
        text_margin = max(2.0 * render_point, 0.35 * (text_hi - text_lo))

        scoped: list[tuple[_VisibleSegment, float, float, float]] = []
        for segment in segments:
            if segment.orientation != orientation:
                continue
            axis, lo, hi = _line_parts(segment)
            if not (cross_lo - axis_margin <= axis <= cross_hi + axis_margin):
                continue
            scoped.append((segment, axis, lo, hi))

            if lo - text_margin <= center <= hi + text_margin:
                key = (
                    orientation,
                    round(axis, 4),
                    round(lo, 4),
                    round(hi, 4),
                    (segment.observation_id,),
                )
                candidates[key] = _LogicalLine(
                    orientation, axis, lo, hi, (segment.observation_id,)
                )

        for index, first in enumerate(scoped):
            seg_a, axis_a, lo_a, hi_a = first
            for seg_b, axis_b, lo_b, hi_b in scoped[index + 1 :]:
                if abs(axis_a - axis_b) > 2.0 * render_point:
                    continue
                if hi_a <= lo_b:
                    gap_lo, gap_hi = hi_a, lo_b
                    far_lo, far_hi = lo_a, hi_b
                elif hi_b <= lo_a:
                    gap_lo, gap_hi = hi_b, lo_a
                    far_lo, far_hi = lo_b, hi_a
                else:
                    continue
                if not (
                    gap_lo <= text_hi + text_margin
                    and gap_hi >= text_lo - text_margin
                ):
                    continue
                if (gap_hi - gap_lo) > (text_hi - text_lo) + 2.0 * text_margin:
                    continue
                axis = 0.5 * (axis_a + axis_b)
                ids = tuple(sorted((seg_a.observation_id, seg_b.observation_id)))
                key = (
                    orientation,
                    round(axis, 4),
                    round(far_lo, 4),
                    round(far_hi, 4),
                    ids,
                )
                candidates[key] = _LogicalLine(
                    orientation, axis, far_lo, far_hi, ids
                )

    return tuple(
        sorted(
            candidates.values(),
            key=lambda line: (
                line.orientation,
                round(line.axis, 4),
                round(line.lo, 4),
                round(line.hi, 4),
                line.observation_ids,
            ),
        )
    )


def _cluster_coordinates(values: Sequence[float], tolerance: float) -> tuple[float, ...]:
    clusters: list[list[float]] = []
    for value in sorted(float(v) for v in values):
        if clusters and abs(value - (sum(clusters[-1]) / len(clusters[-1]))) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return tuple(sum(cluster) / len(cluster) for cluster in clusters)


def _bind_text_to_geometry(
    text: RasterDimensionTextObservation,
    segments: Sequence[_VisibleSegment],
) -> Optional[BoundRasterDimension]:
    logical = _logical_lines_for_text(text, segments)
    if len(logical) != 1:
        return None
    line = logical[0]
    render_point = 72.0 / float(RASTER_RENDER_DPI)
    witness_tol = 2.0 * render_point

    endpoint_coords = (line.lo, line.hi)
    witness_ids: list[str] = []
    witness_points: list[tuple[float, float]] = []
    for endpoint in endpoint_coords:
        hits: list[tuple[str, float]] = []
        for segment in segments:
            if segment.observation_id in line.observation_ids:
                continue
            if line.orientation == "horizontal" and segment.orientation == "vertical":
                axis, lo, hi = _line_parts(segment)
                if (
                    abs(axis - endpoint) <= witness_tol
                    and lo - witness_tol <= line.axis <= hi + witness_tol
                ):
                    hits.append((segment.observation_id, axis))
            elif line.orientation == "vertical" and segment.orientation == "horizontal":
                axis, lo, hi = _line_parts(segment)
                if (
                    abs(axis - endpoint) <= witness_tol
                    and lo - witness_tol <= line.axis <= hi + witness_tol
                ):
                    hits.append((segment.observation_id, axis))
        clusters = _cluster_coordinates([value for _obs, value in hits], witness_tol)
        if len(clusters) != 1:
            return None
        chosen = clusters[0]
        selected_ids = tuple(
            sorted(obs_id for obs_id, value in hits if abs(value - chosen) <= witness_tol)
        )
        if not selected_ids:
            return None
        witness_ids.extend(selected_ids)
        if line.orientation == "horizontal":
            witness_points.append((chosen, line.axis))
        else:
            witness_points.append((line.axis, chosen))

    first, second = witness_points
    span = math.hypot(second[0] - first[0], second[1] - first[1])
    if not math.isfinite(span) or span <= 0.0:
        return None
    payload = {
        "text_observation_id": text.observation_id,
        "value_mm": text.value_mm,
        "orientation": line.orientation,
        "endpoints_pt": (first, second),
        "dimension_line_observation_ids": line.observation_ids,
        "witness_observation_ids": tuple(sorted(set(witness_ids))),
    }
    dimension_id = stable_contract_id(
        "raster_bound_dimension", payload, digest_chars=32
    )
    return BoundRasterDimension(
        dimension_id=dimension_id,
        text_observation_id=text.observation_id,
        value_mm=text.value_mm,
        orientation=line.orientation,
        endpoints_pt=(first, second),
        span_pt=round(span, 4),
        dimension_line_observation_ids=line.observation_ids,
        witness_observation_ids=tuple(sorted(set(witness_ids))),
        _seal=_RECORD_SEAL,
    )


def _along_endpoints(dimension: BoundRasterDimension) -> tuple[float, float]:
    if dimension.orientation == "horizontal":
        values = (dimension.endpoints_pt[0][0], dimension.endpoints_pt[1][0])
    else:
        values = (dimension.endpoints_pt[0][1], dimension.endpoints_pt[1][1])
    return min(values), max(values)


def _unique_child_paths(
    overall: BoundRasterDimension,
    dimensions: Sequence[BoundRasterDimension],
) -> tuple[tuple[BoundRasterDimension, ...], ...]:
    render_point = 72.0 / float(RASTER_RENDER_DPI)
    tol = 2.0 * render_point
    start, end = _along_endpoints(overall)
    members: dict[tuple[float, float, int], BoundRasterDimension] = {}
    for candidate in dimensions:
        if (
            candidate.dimension_id == overall.dimension_id
            or candidate.orientation != overall.orientation
        ):
            continue
        lo, hi = _along_endpoints(candidate)
        if lo < start - tol or hi > end + tol:
            continue
        if hi - lo >= (end - start) - tol:
            continue
        key = (round(lo, 3), round(hi, 3), candidate.value_mm)
        prior = members.get(key)
        if prior is None or candidate.dimension_id < prior.dimension_id:
            members[key] = candidate

    ordered = tuple(
        sorted(
            members.values(),
            key=lambda item: (*_along_endpoints(item), item.value_mm, item.dimension_id),
        )
    )
    paths: list[tuple[BoundRasterDimension, ...]] = []

    def walk(position: float, used: tuple[str, ...], path: tuple[BoundRasterDimension, ...]) -> None:
        if abs(position - end) <= tol:
            if path and sum(item.value_mm for item in path) == overall.value_mm:
                paths.append(path)
            return
        if position > end + tol or len(path) > len(ordered):
            return
        for candidate in ordered:
            if candidate.dimension_id in used:
                continue
            lo, hi = _along_endpoints(candidate)
            if abs(lo - position) > tol or hi <= position + tol:
                continue
            walk(
                hi,
                (*used, candidate.dimension_id),
                (*path, candidate),
            )

    walk(start, (), ())
    canonical: dict[tuple[tuple[float, float, int], ...], tuple[BoundRasterDimension, ...]] = {}
    for path in paths:
        signature = tuple(
            (round(_along_endpoints(item)[0], 3), round(_along_endpoints(item)[1], 3), item.value_mm)
            for item in path
        )
        canonical.setdefault(signature, path)
    return tuple(canonical[key] for key in sorted(canonical))


def _resolve_overall(
    orientation: str,
    dimensions: Sequence[BoundRasterDimension],
) -> Optional[RasterOverallDimension]:
    candidates: list[tuple[BoundRasterDimension, tuple[BoundRasterDimension, ...]]] = []
    for dimension in dimensions:
        if dimension.orientation != orientation:
            continue
        paths = _unique_child_paths(dimension, dimensions)
        if len(paths) == 1 and len(paths[0]) >= 2:
            candidates.append((dimension, paths[0]))
    if len(candidates) != 1:
        return None
    overall, children = candidates[0]
    return RasterOverallDimension(
        overall_dimension_id=overall.dimension_id,
        orientation=orientation,
        value_mm=overall.value_mm,
        span_pt=overall.span_pt,
        endpoints_pt=overall.endpoints_pt,
        child_dimension_ids=tuple(item.dimension_id for item in children),
        child_values_mm=tuple(item.value_mm for item in children),
        _seal=_RECORD_SEAL,
    )


class RasterPlanDimensionAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, str], RasterPlanDimensionResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("RasterPlanDimensionAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, revision_id: str, page_id: str) -> RasterPlanDimensionResult:
        return self._results.get(
            (str(revision_id), str(page_id)),
            RasterPlanDimensionResult(
                EvidenceResolutionStatus.ABSTAINED,
                ("raster_dimension_scope_unavailable",),
            ),
        )


class RasterPlanDimensionProducer:
    def __init__(
        self,
        *,
        source_visibility: SourceVisibilityProducer,
        backend: RasterOCRBackend,
        allow_test_backend: bool,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("RasterPlanDimensionProducer must be obtained from create()")
        if type(source_visibility) is not SourceVisibilityProducer:
            raise TypeError("source_visibility must be exact SourceVisibilityProducer")
        if allow_test_backend:
            if type(backend) is not MockOCRBackend:
                raise TypeError("create_for_tests requires exact MockOCRBackend")
        elif type(backend) not in _PRODUCTION_BACKENDS:
            raise TypeError("production OCR backend type is not trusted")
        self._source_visibility = source_visibility
        self._backend = backend
        self._results: dict[tuple[str, str], RasterPlanDimensionResult] = {}

    @classmethod
    def create(
        cls,
        *,
        source_visibility: SourceVisibilityProducer,
    ) -> "RasterPlanDimensionProducer":
        return cls(
            source_visibility=source_visibility,
            backend=_choose_backend(),
            allow_test_backend=False,
            _seal=_PRODUCER_SEAL,
        )

    @classmethod
    def create_for_tests(
        cls,
        *,
        source_visibility: SourceVisibilityProducer,
        backend: MockOCRBackend,
    ) -> "RasterPlanDimensionProducer":
        return cls(
            source_visibility=source_visibility,
            backend=backend,
            allow_test_backend=True,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> RasterPlanDimensionAuthority:
        return RasterPlanDimensionAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self, revision_id: str, page_id: str, result: RasterPlanDimensionResult
    ) -> RasterPlanDimensionResult:
        self._results[(str(revision_id), str(page_id))] = result
        return result

    def publish(self, *, revision_id: str, page_id: str) -> RasterPlanDimensionResult:
        revision_id = str(revision_id or "").strip()
        page_id = str(page_id or "").strip()
        if not revision_id or not page_id:
            raise ValueError("revision_id and page_id are required")

        try:
            published = self._source_visibility.augment_with_raster_visible_segments(
                revision_id, page_ids=(page_id,)
            )
        except (ValueError, RuntimeError):
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.CONFLICT,
                    (RASTER_DIMENSION_LINEAGE_CONFLICT,),
                    revision_id=revision_id,
                    page_id=page_id,
                ),
            )

        if not self._backend.is_available():
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.ABSTAINED,
                    (RASTER_DIMENSION_TEXT_UNAVAILABLE,),
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                ),
            )

        visibility = self._source_visibility.authority()
        segments: list[_VisibleSegment] = []
        for observation_id in published.visible_observation_ids:
            result = visibility.resolve_visible(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = result.observation
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
                or observation.page_id != page_id
                or observation.observation_kind != RASTER_PDF_VISIBLE_SEGMENT
            ):
                continue
            orientation = _segment_orientation(observation.geometry)
            if orientation is None:
                continue
            segments.append(
                _VisibleSegment(
                    observation.observation_id,
                    tuple(float(v) for v in observation.geometry),
                    orientation,
                )
            )
        if not segments:
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.ABSTAINED,
                    (RASTER_DIMENSION_GEOMETRY_UNAVAILABLE,),
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                ),
            )

        # This composition is intentionally inside the trusted producer.  The
        # caller never sees or supplies the underlying source writer, page
        # pixels, OCR backend inputs, parent observation id, or partition id.
        source_writer = self._source_visibility._producer
        try:
            png_bytes, page_parent = source_writer.render_native_page_png(
                document_id=published.revision.document_id,
                revision_id=revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=page_id,
                dpi=float(RASTER_DIMENSION_OCR_DPI),
            )
            image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            raw_lines = self._backend.extract_lines(
                image, dpi=RASTER_DIMENSION_OCR_DPI
            )
        except Exception:
            raw_lines = ()

        text_observations: list[RasterDimensionTextObservation] = []
        page_width = float(page_parent.geometry[0]) if len(page_parent.geometry) >= 2 else 0.0
        page_height = float(page_parent.geometry[1]) if len(page_parent.geometry) >= 2 else 0.0
        px_to_pt = 72.0 / float(RASTER_DIMENSION_OCR_DPI)
        for line in raw_lines:
            value_mm = _parse_dimension_value_mm(line.text)
            if value_mm is None:
                continue
            bbox = line.bbox_pt
            if bbox is None:
                try:
                    bbox = tuple(float(v) * px_to_pt for v in line.bbox_px)
                except Exception:
                    continue
            if len(bbox) != 4:
                continue
            x0, y0, x1, y1 = (float(v) for v in bbox)
            if (
                not all(math.isfinite(v) for v in (x0, y0, x1, y1))
                or x1 <= x0
                or y1 <= y0
                or x0 < 0.0
                or y0 < 0.0
                or x1 > page_width
                or y1 > page_height
            ):
                continue
            payload = {
                "document_id": published.revision.document_id,
                "revision_id": revision_id,
                "source_sha256": published.revision.source_sha256,
                "snapshot_id": published.snapshot.snapshot_id,
                "page_id": page_id,
                "parent_page_observation_id": page_parent.observation_id,
                "raw_text": str(line.text).strip(),
                "bbox_pt": tuple(round(v, 4) for v in (x0, y0, x1, y1)),
                "backend_name": self._backend.name,
                "backend_version": self._backend.version,
            }
            obs_id = stable_contract_id(
                "raster_dimension_text", payload, digest_chars=32
            )
            text_observations.append(
                RasterDimensionTextObservation(
                    observation_id=obs_id,
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                    parent_page_observation_id=page_parent.observation_id,
                    raw_text=str(line.text).strip(),
                    value_mm=value_mm,
                    bbox_pt=tuple(round(v, 4) for v in (x0, y0, x1, y1)),
                    backend_name=self._backend.name,
                    backend_version=self._backend.version,
                    confidence=line.confidence,
                    _seal=_RECORD_SEAL,
                )
            )

        if not text_observations:
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.ABSTAINED,
                    (RASTER_DIMENSION_TEXT_UNAVAILABLE,),
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                ),
            )

        bound = tuple(
            item
            for text_obs in text_observations
            for item in (_bind_text_to_geometry(text_obs, segments),)
            if item is not None
        )
        horizontal = _resolve_overall("horizontal", bound)
        vertical = _resolve_overall("vertical", bound)
        if horizontal is None or vertical is None:
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.ABSTAINED,
                    (RASTER_DIMENSION_ORTHOGONAL_SCOPE_UNAVAILABLE,),
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                    horizontal=horizontal,
                    vertical=vertical,
                    bound_dimensions=bound,
                ),
            )

        readings: list[ScaleSourceReading] = []
        for name, overall in (("horizontal", horizontal), ("vertical", vertical)):
            metres = overall.value_mm / 1000.0
            if metres <= 0.0 or overall.span_pt <= 0.0:
                continue
            points_per_m = overall.span_pt / metres
            ratio = POINTS_PER_METRE_AT_1_1 / points_per_m
            readings.append(
                ScaleSourceReading(
                    source_type=ScaleSourceType.INFERRED.value,
                    scale_text=f"raster figured {name} chain",
                    ratio=ratio,
                    confidence=1.0,
                )
            )
        calibration = resolve_page_scale_calibration(
            page_no=int(page_id),
            sheet_label="",
            readings=readings,
            revision_id=revision_id,
        )
        if calibration.status == ScaleCalibrationStatus.CONFLICTING.value:
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.CONFLICT,
                    (RASTER_DIMENSION_SCALE_CONFLICT,),
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                    horizontal=horizontal,
                    vertical=vertical,
                    scale_status=calibration.status,
                    bound_dimensions=bound,
                ),
            )
        if calibration.status not in (
            ScaleCalibrationStatus.PROVISIONAL.value,
            ScaleCalibrationStatus.VALID.value,
        ):
            return self._store(
                revision_id,
                page_id,
                RasterPlanDimensionResult(
                    EvidenceResolutionStatus.ABSTAINED,
                    (RASTER_DIMENSION_SCALE_CONFLICT,),
                    document_id=published.revision.document_id,
                    revision_id=revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                    horizontal=horizontal,
                    vertical=vertical,
                    scale_status=calibration.status,
                    bound_dimensions=bound,
                ),
            )

        return self._store(
            revision_id,
            page_id,
            RasterPlanDimensionResult(
                EvidenceResolutionStatus.CANDIDATE,
                (RASTER_DIMENSION_RESOLVED,),
                document_id=published.revision.document_id,
                revision_id=revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=page_id,
                horizontal=horizontal,
                vertical=vertical,
                length_m=horizontal.value_mm / 1000.0,
                width_m=vertical.value_mm / 1000.0,
                scale_status=calibration.status,
                scale_px_per_m=calibration.px_per_m,
                bound_dimensions=bound,
            ),
        )


__all__ = [
    "BoundRasterDimension",
    "RASTER_PLAN_DIMENSION_SCHEMA_VERSION",
    "RasterOverallDimension",
    "RasterPlanDimensionAuthority",
    "RasterPlanDimensionProducer",
    "RasterPlanDimensionResult",
]
