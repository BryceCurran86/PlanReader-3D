"""Default-off, read-only MEASUREMENT of the locality evidence behind an elevation frame-area record, strictly SHADOW.

The existing `OpeningElevationFrameAreaProducer` abstains (with one generic reason, `opening_elevation_frame_area_unavailable`)
for a mark when no pair of figured dimensions that bracket the mark also lies within its locality limit of the frame. That
single reason hides WHICH quantity failed and by how much. This module measures, from the producer's own trusted words and
the repository's own figured-dimension extractor, the numbers that gate uses, for every window or door tag on a page:

* every witness-bound figured dimension, its span, its line coordinate and whether its value word is a unique trusted word;
* for every (x dimension, y dimension) pair whose spans bracket a tag, the frame they imply, the distance from each
  dimension line to that frame's edges, the authority's locality limit computed the same way, the aspect agreement, and
  the other tags inside the implied frame.

It decides nothing: it is a measurement, never a verdict, never a frame, never an area. The authority's own verdict is
optional (`include_authority_verdicts`, default False) and, when requested, is simply that authority's answer for the mark.
It issues no `OpeningElevationFrameAreaRecord`, imports nothing from the issuer, binders, count producer or host
resolver, and is not imported by production.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields
from typing import Optional, Sequence

from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import BindingStatus, calibrate_dimension_layout, extract_dimension_evidence_bundle
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_tag_normalization import normalize_opening_tag

ELEVATION_LOCALITY_CENSUS_SCHEMA_VERSION = "1.0.0"
CENSUS_DISABLED = "elevation_locality_census_disabled"
SOURCE_UNPROVEN = "elevation_locality_census_source_unproven"
NO_TRUSTED_TAGS = "elevation_locality_census_no_trusted_tags"
NO_FIGURED_DIMENSIONS = "elevation_locality_census_no_figured_dimensions"
BUDGET_EXCEEDED = "elevation_locality_census_budget_exceeded"
CENSUS_PRODUCED = "elevation_locality_measurements_produced"

# Mirrors of the authority's unit-range and layout rules. A parity test reads the authority's own constants and fails
# if they ever change, so this module cannot silently measure a different gate.
_MIN_FRAME_DIMENSION_MM = 150.0
_MAX_FRAME_DIMENSION_MM = 20_000.0
_MAX_DIMENSIONS = 2_000
_MAX_PAIRS = 20_000

_GRANT_FLAGS = (
    "frame_granted", "physical_opening_granted", "host_granted", "opening_kind_granted", "scale_granted",
    "metric_granted", "area_granted", "count_granted", "quantity_granted", "commercial_projection_allowed",
    "customer_publication_granted", "takeoff_eligible", "deduction_authority", "frame_record_issued",
)


@dataclass(frozen=True)
class CensusOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str


@dataclass(frozen=True)
class LayoutNumbers:
    median_word_height_pt: float
    line_search_distance_pt: float
    chain_axis_tolerance_pt: float
    geometry_tolerance_pt: float
    locality_limit_pt: float
    word_tolerance_pt: float


@dataclass(frozen=True)
class TrustedWordRef:
    observation_id: str
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class DimensionMeasure:
    observation_id: str
    axis: str                         # "x" | "y": the direction the dimension measures
    span: tuple[float, float]
    line_coordinate: float            # y of an x dimension line, x of a y dimension line
    millimetres: Optional[float]      # None when unit or range is not usable by the authority
    value_word_trusted: bool          # exactly one trusted word equals the printed value at the authority's tolerance


@dataclass(frozen=True)
class TagOccurrence:
    observation_id: str
    key: str                          # the repository's own normalised opening tag
    kind: str                         # "window" | "door"
    centre: tuple[float, float]
    x_dimensions_bracketing: tuple[str, ...]
    y_dimensions_bracketing: tuple[str, ...]


@dataclass(frozen=True)
class PairMeasure:
    tag_observation_id: str
    x_dimension_id: str
    y_dimension_id: str
    frame_bbox: tuple[float, float, float, float]
    x_line_to_frame_edge_pt: float
    y_line_to_frame_edge_pt: float
    x_line_exceeds_locality_limit: bool
    y_line_exceeds_locality_limit: bool
    other_tag_keys_inside_frame: tuple[str, ...]
    geometric_aspect: float
    physical_aspect: Optional[float]
    aspect_relative_deviation: Optional[float]


@dataclass(frozen=True)
class MarkVerdict:
    key: str
    status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ElevationLocalityCensus:
    ownership: Optional[CensusOwnership]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    layout: Optional[LayoutNumbers]
    dimensions: tuple[DimensionMeasure, ...]
    tags: tuple[TagOccurrence, ...]
    pairs: tuple[PairMeasure, ...]
    authority_verdicts: tuple[MarkVerdict, ...]
    record_id: Optional[str]
    shadow_only: bool = True
    frame_granted: bool = False
    physical_opening_granted: bool = False
    host_granted: bool = False
    opening_kind_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    area_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    takeoff_eligible: bool = False
    deduction_authority: bool = False
    frame_record_issued: bool = False
    schema_version: str = ELEVATION_LOCALITY_CENSUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("a locality census cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"a locality census cannot grant {name}")
        if self.status not in (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED):
            raise ValueError("a locality census is CANDIDATE or ABSTAINED only")
        if not set(_GRANT_FLAGS) <= {f.name for f in fields(self)}:
            raise ValueError("grant flag set is out of date")


def _claim_norm(value: object) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _millimetres(value: object, unit: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    u = str(unit or "").strip().lower()
    mm = number if u == "mm" else number * 1000.0 if u == "m" else number * 25.4 if u == "in" else None
    if mm is None or not math.isfinite(mm) or mm < _MIN_FRAME_DIMENSION_MM or mm > _MAX_FRAME_DIMENSION_MM:
        return None
    return mm


def _axis_of(endpoints) -> Optional[tuple[str, float, float, float]]:
    """(axis, lo, hi, line coordinate) exactly as the authority reads a witness-bound dimension."""
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
        return ("x", min(x0, x1), max(x0, x1), (y0 + y1) / 2.0)
    if dy >= dx * 4.0:
        return ("y", min(y0, y1), max(y0, y1), (x0 + x1) / 2.0)
    return None


def layout_numbers(median_word_height_pt: float, line_search_distance_pt: float, chain_axis_tolerance_pt: float) -> LayoutNumbers:
    geometry_tolerance = max(chain_axis_tolerance_pt * 2.0, median_word_height_pt * 0.75, 1.0)
    return LayoutNumbers(
        median_word_height_pt=float(median_word_height_pt), line_search_distance_pt=float(line_search_distance_pt),
        chain_axis_tolerance_pt=float(chain_axis_tolerance_pt), geometry_tolerance_pt=float(geometry_tolerance),
        locality_limit_pt=float(max(line_search_distance_pt * 2.5, geometry_tolerance)),
        word_tolerance_pt=float(max(median_word_height_pt * 0.20, 0.75)))


def measure_locality(
    *, trusted_words: Sequence[TrustedWordRef], dimension_rows: Sequence[tuple[str, str, object, object, tuple[float, float, float, float], object]],
    layout: LayoutNumbers,
) -> tuple[tuple[DimensionMeasure, ...], tuple[TagOccurrence, ...], tuple[PairMeasure, ...]]:
    """Pure core. `dimension_rows` are (observation id, printed text, value, unit, value-word bbox, binding endpoints)
    of witness-bound dimensions only."""
    dims: list[DimensionMeasure] = []
    for observation_id, text, value, unit, bbox, endpoints in dimension_rows:
        axis = _axis_of(endpoints)
        if axis is None:
            continue
        target = _claim_norm(text)
        matches = [w for w in trusted_words if target and _claim_norm(w.text) == target
                   and max(abs(w.bbox[i] - bbox[i]) for i in range(4)) <= layout.word_tolerance_pt]
        dims.append(DimensionMeasure(
            observation_id=str(observation_id), axis=axis[0], span=(axis[1], axis[2]), line_coordinate=axis[3],
            millimetres=_millimetres(value, unit), value_word_trusted=len(matches) == 1))
    dims.sort(key=lambda d: (d.axis, d.span, d.observation_id))
    if len(dims) > _MAX_DIMENSIONS:
        return tuple(), tuple(), tuple()

    tags: list[TagOccurrence] = []
    raw_tags = []
    for word in trusted_words:
        normalized = normalize_opening_tag(word.text)
        if normalized is None:
            continue
        centre = ((word.bbox[0] + word.bbox[2]) / 2.0, (word.bbox[1] + word.bbox[3]) / 2.0)
        raw_tags.append((word, normalized.tag, "window" if normalized.trade_type == "windows" else "door", centre))
    for word, key, kind, centre in sorted(raw_tags, key=lambda t: (t[1], t[0].observation_id)):
        xs = tuple(d.observation_id for d in dims if d.axis == "x" and d.span[0] < centre[0] < d.span[1])
        ys = tuple(d.observation_id for d in dims if d.axis == "y" and d.span[0] < centre[1] < d.span[1])
        tags.append(TagOccurrence(word.observation_id, key, kind, centre, xs, ys))

    by_id = {d.observation_id: d for d in dims}
    pairs: list[PairMeasure] = []
    for tag in tags:
        for xid in tag.x_dimensions_bracketing:
            for yid in tag.y_dimensions_bracketing:
                x, y = by_id[xid], by_id[yid]
                frame = (x.span[0], y.span[0], x.span[1], y.span[1])
                x_line = min(abs(x.line_coordinate - frame[1]), abs(x.line_coordinate - frame[3]))
                y_line = min(abs(y.line_coordinate - frame[0]), abs(y.line_coordinate - frame[2]))
                inside = tuple(sorted(t.key for t in tags if t.observation_id != tag.observation_id
                                      and frame[0] <= t.centre[0] <= frame[2] and frame[1] <= t.centre[1] <= frame[3]))
                height = frame[3] - frame[1]
                geometric = (frame[2] - frame[0]) / height if height > 0.0 else float("nan")
                physical = (x.millimetres / y.millimetres) if (x.millimetres and y.millimetres) else None
                deviation = abs(geometric / physical - 1.0) if (physical and math.isfinite(geometric)) else None
                pairs.append(PairMeasure(
                    tag_observation_id=tag.observation_id, x_dimension_id=xid, y_dimension_id=yid, frame_bbox=frame,
                    x_line_to_frame_edge_pt=x_line, y_line_to_frame_edge_pt=y_line,
                    x_line_exceeds_locality_limit=x_line > layout.locality_limit_pt,
                    y_line_exceeds_locality_limit=y_line > layout.locality_limit_pt,
                    other_tag_keys_inside_frame=inside, geometric_aspect=geometric,
                    physical_aspect=physical, aspect_relative_deviation=deviation))
                if len(pairs) > _MAX_PAIRS:
                    return tuple(dims), tuple(tags), tuple()
    return tuple(dims), tuple(tags), tuple(pairs)


class ElevationFrameLocalityCensusShadow:
    """Read-only census bound to one `SourceVisibilityProducer`; default OFF."""

    def __init__(self, source, *, enabled: bool = False):
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        if type(enabled) is not bool:
            raise ValueError("elevation locality census gate must be an explicit boolean")
        self._source = source
        self._enabled = enabled

    @staticmethod
    def _empty(reason: str, ownership: Optional[CensusOwnership] = None, **parts) -> ElevationLocalityCensus:
        return ElevationLocalityCensus(
            ownership=ownership, status=EvidenceResolutionStatus.ABSTAINED, reason_codes=(reason,),
            layout=parts.get("layout"), dimensions=parts.get("dimensions", ()), tags=parts.get("tags", ()),
            pairs=parts.get("pairs", ()), authority_verdicts=(), record_id=None)

    def census(self, *, revision_id: str, page_id: int, include_authority_verdicts: bool = False) -> ElevationLocalityCensus:
        if not self._enabled:
            return self._empty(CENSUS_DISABLED)
        if (type(revision_id) is not str or type(page_id) is not int or isinstance(page_id, bool)
                or type(include_authority_verdicts) is not bool):
            raise ValueError("revision id, integer page id and an explicit bool required")
        import fitz

        from pb_pdf_text_integrity_authority import TRUSTED_PDF_TEXT
        from pb_source_observation_authority import ObservationSelector

        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return self._empty(SOURCE_UNPROVEN)
        document_id = published.revision.document_id
        if (page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return self._empty(SOURCE_UNPROVEN)
        payload = source._producer._store.source_bytes_by_revision.get(revision_id)
        if payload is None or hashlib.sha256(payload).hexdigest() != published.revision.source_sha256:
            return self._empty(SOURCE_UNPROVEN)
        ownership = CensusOwnership(document_id, revision_id, published.snapshot.snapshot_id,
                                    published.revision.source_sha256, str(page_id))

        text_authority = source.text_integrity_authority()
        trusted: list[TrustedWordRef] = []
        for observation_id in published.text_observation_ids:
            result = text_authority.resolve_text(ObservationSelector(
                document_id, revision_id, ownership.source_sha256, ownership.snapshot_id, observation_id))
            receipt = result.receipt
            if (receipt is None or str(receipt.page_id) != str(page_id)
                    or result.status is not EvidenceResolutionStatus.CORROBORATED
                    or result.proposition != TRUSTED_PDF_TEXT or not result.trusted_text
                    or len(receipt.geometry) < 4):
                continue
            trusted.append(TrustedWordRef(str(observation_id), str(result.trusted_text),
                                          tuple(float(v) for v in receipt.geometry[:4])))
        if not trusted:
            return self._empty(NO_TRUSTED_TAGS, ownership)

        with fitz.open(stream=bytes(payload), filetype="pdf") as document:
            page = document.load_page(page_id - 1)
            bundle = extract_dimension_evidence_bundle(
                page, page_num=page_id, view_id=f"page:{page_id}:opening_elevation_frame",
                view_type=DrawingViewType.ELEVATION.value)
            calibration = calibrate_dimension_layout(page)
        layout = layout_numbers(calibration.median_word_height_pt, calibration.line_search_distance_pt,
                                calibration.chain_axis_tolerance_pt)
        witness = {str(b.observation_id): b for b in bundle.bindings
                   if b.status == BindingStatus.WITNESS_BOUND.value and b.endpoints is not None}
        rows = []
        for observation in bundle.observations:
            binding = witness.get(str(observation.dimension_id))
            bbox = getattr(observation, "bbox", None)
            if binding is None or bbox is None or len(bbox) != 4:
                continue
            rows.append((str(observation.dimension_id), getattr(observation, "raw_text", ""), observation.value,
                         getattr(observation, "unit", ""), tuple(float(v) for v in bbox), binding.endpoints))
        dims, tags, pairs = measure_locality(trusted_words=trusted, dimension_rows=rows, layout=layout)
        if not dims and rows:
            return self._empty(BUDGET_EXCEEDED, ownership, layout=layout)
        if not dims:
            return self._empty(NO_FIGURED_DIMENSIONS, ownership, layout=layout, tags=tags)
        if len(pairs) == 0 and any(t.x_dimensions_bracketing and t.y_dimensions_bracketing for t in tags):
            return self._empty(BUDGET_EXCEEDED, ownership, layout=layout, dimensions=dims, tags=tags)

        verdicts: list[MarkVerdict] = []
        if include_authority_verdicts:
            from pb_opening_elevation_frame_area_authority import (
                OpeningElevationFrameAreaProducer, OpeningElevationFrameAreaSelector)

            authority = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source).authority()
            for tag in sorted({(t.key, t.observation_id) for t in tags if t.kind == "window"}):
                result = authority.resolve(OpeningElevationFrameAreaSelector(
                    document_id, revision_id, ownership.source_sha256, ownership.snapshot_id, tag[0]))
                verdicts.append(MarkVerdict(tag[0], result.status.value, tuple(result.reason_codes)))
            verdicts = sorted({(v.key, v.status, v.reason_codes): v for v in verdicts}.values(), key=lambda v: v.key)

        root = (ownership.document_id, ownership.revision_id, ownership.snapshot_id, ownership.source_sha256,
                ownership.page_id)
        record_id = stable_contract_id("shadow_elevation_locality_census", {
            "root": root, "dims": tuple((d.observation_id, d.span, d.line_coordinate) for d in dims),
            "pairs": tuple((p.tag_observation_id, p.x_dimension_id, p.y_dimension_id) for p in pairs)})
        return ElevationLocalityCensus(
            ownership=ownership, status=EvidenceResolutionStatus.CANDIDATE, reason_codes=(CENSUS_PRODUCED,),
            layout=layout, dimensions=dims, tags=tags, pairs=pairs, authority_verdicts=tuple(verdicts),
            record_id=record_id)


__all__ = [
    "CENSUS_DISABLED", "CensusOwnership", "DimensionMeasure", "ELEVATION_LOCALITY_CENSUS_SCHEMA_VERSION",
    "ElevationFrameLocalityCensusShadow", "ElevationLocalityCensus", "LayoutNumbers", "MarkVerdict", "PairMeasure",
    "TagOccurrence", "TrustedWordRef", "layout_numbers", "measure_locality",
]
