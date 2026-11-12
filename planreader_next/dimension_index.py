"""Per-page inventory of printed figures and their unique dim-line geometry.

Registers every figured millimetre word as soon as a NativePage exists, then
attaches dimension-line, hash and extension-line source refs only when that
geometry uniquely owns the word. This is not a second parser, scale resolver
or quantity issuer. Roles stay UNMATCHED: a cavity-slider 870 is not a room
height, and an unclassified number is not a room dimension.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .engine import NativePage, NativeSegment, NativeWord, SourceConflict, _figured_mm
from .hash_chain import (
    _DIM_OFFSET_MAX_PT,
    _FACE_PT,
    _TICK_MAX_PT,
    _TICK_MIN_PT,
    _WORD_LINE_PT,
    _cluster_stations,
)

ROLE_UNMATCHED = "UNMATCHED"
STATUS_UNIQUE = "unique"
STATUS_UNMATCHED = "unmatched"
STATUS_AMBIGUOUS = "ambiguous"
_DIM_LINE_MIN_PT = 40.0
_CACHE: dict[tuple[str, int], "PageDimensionIndex"] = {}


@dataclass(frozen=True)
class DimensionEvidence:
    word_ref: str
    text: str
    millimetres: Decimal
    bbox: tuple[float, float, float, float]
    orientation: str
    dimension_line_refs: tuple[str, ...]
    hash_segment_refs: tuple[str, ...]
    extension_segment_refs: tuple[str, ...]
    hash_stations: tuple[float, ...]
    endpoint_stations: tuple[float, float] | None
    geometry_status: str
    role: str = ROLE_UNMATCHED


@dataclass(frozen=True)
class PageDimensionIndex:
    source_sha256: str
    page_index: int
    figures: tuple[DimensionEvidence, ...]
    commercial_publishable: bool = False
    official_score: None = None

    def unique_geometry(self) -> tuple[DimensionEvidence, ...]:
        return tuple(item for item in self.figures if item.geometry_status == STATUS_UNIQUE)


def clear_dimension_index_cache() -> None:
    _CACHE.clear()


def inventory_page_dimensions(page: NativePage) -> PageDimensionIndex:
    """Extract-once cache of figured words and unique dim-line/hash/extension refs."""
    key = (page.source_sha256, page.page_index)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    dim_lines, ticks, extensions = _classify_segments(page.segments)
    raw: list[DimensionEvidence] = []
    for word in page.words:
        try:
            millimetres = _figured_mm(word)
        except SourceConflict:
            continue
        raw.append(_bind_figure(word, millimetres, dim_lines, ticks, extensions))
    claimed: dict[tuple[str, float, float], list[int]] = {}
    for index, item in enumerate(raw):
        if item.geometry_status != STATUS_UNIQUE or item.endpoint_stations is None:
            continue
        line_ref = item.dimension_line_refs[0] if item.dimension_line_refs else ""
        key_span = (line_ref, round(item.endpoint_stations[0], 2), round(item.endpoint_stations[1], 2))
        claimed.setdefault(key_span, []).append(index)
    figures = list(raw)
    for indexes in claimed.values():
        if len(indexes) == 1:
            continue
        for index in indexes:
            item = figures[index]
            figures[index] = DimensionEvidence(
                word_ref=item.word_ref, text=item.text, millimetres=item.millimetres,
                bbox=item.bbox, orientation=item.orientation,
                dimension_line_refs=item.dimension_line_refs,
                hash_segment_refs=item.hash_segment_refs,
                extension_segment_refs=item.extension_segment_refs,
                hash_stations=item.hash_stations,
                endpoint_stations=item.endpoint_stations,
                geometry_status=STATUS_AMBIGUOUS, role=ROLE_UNMATCHED,
            )
    result = PageDimensionIndex(
        source_sha256=page.source_sha256, page_index=page.page_index,
        figures=tuple(figures),
    )
    _CACHE[key] = result
    return result


def dimension_index_payload(index: PageDimensionIndex) -> dict[str, object]:
    return {
        "source_sha256": index.source_sha256,
        "page_index": index.page_index,
        "figure_count": len(index.figures),
        "unique_geometry_count": len(index.unique_geometry()),
        "unmatched_count": sum(item.geometry_status == STATUS_UNMATCHED for item in index.figures),
        "ambiguous_count": sum(item.geometry_status == STATUS_AMBIGUOUS for item in index.figures),
        "role": ROLE_UNMATCHED,
        "figures": [_figure_payload(item) for item in index.figures],
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }


def _figure_payload(item: DimensionEvidence) -> dict[str, object]:
    return {
        "word_ref": item.word_ref,
        "text": item.text,
        "millimetres": format(item.millimetres.normalize(), "f"),
        "bbox_pdf_pts": list(item.bbox),
        "orientation": item.orientation,
        "dimension_line_refs": list(item.dimension_line_refs),
        "hash_segment_refs": list(item.hash_segment_refs),
        "extension_segment_refs": list(item.extension_segment_refs),
        "hash_stations": list(item.hash_stations),
        "endpoint_stations": list(item.endpoint_stations) if item.endpoint_stations else None,
        "geometry_status": item.geometry_status,
        "role": ROLE_UNMATCHED,
    }


def _classify_segments(
    segments: Sequence[NativeSegment],
) -> tuple[list[NativeSegment], list[NativeSegment], list[NativeSegment]]:
    dim_lines: list[NativeSegment] = []
    ticks: list[NativeSegment] = []
    extensions: list[NativeSegment] = []
    for seg in segments:
        axis = _axis(seg)
        if axis is None:
            continue
        length = _length(seg)
        if _TICK_MIN_PT <= length <= _TICK_MAX_PT:
            ticks.append(seg)
        elif length >= _DIM_LINE_MIN_PT:
            dim_lines.append(seg)
        elif length > _TICK_MAX_PT:
            extensions.append(seg)
    return dim_lines, ticks, extensions


def _length(seg: NativeSegment) -> float:
    return ((seg.x2 - seg.x1) ** 2 + (seg.y2 - seg.y1) ** 2) ** 0.5


def _axis(seg: NativeSegment) -> str | None:
    dx, dy = abs(seg.x2 - seg.x1), abs(seg.y2 - seg.y1)
    if dy <= _FACE_PT and dx > dy:
        return "h"
    if dx <= _FACE_PT and dy > dx:
        return "v"
    return None


def _along_perp(axis: str, x: float, y: float) -> tuple[float, float]:
    """Along-station first, perpendicular second. Horizontal dim-lines measure x."""
    return (x, y) if axis == "h" else (y, x)


def _seg_perp(seg: NativeSegment) -> float:
    axis = _axis(seg)
    if axis == "h":
        return (seg.y1 + seg.y2) / 2.0
    return (seg.x1 + seg.x2) / 2.0


def _seg_span(seg: NativeSegment) -> tuple[float, float]:
    axis = _axis(seg)
    if axis == "h":
        return sorted((seg.x1, seg.x2))
    return sorted((seg.y1, seg.y2))


def _bind_figure(
    word: NativeWord,
    millimetres: Decimal,
    dim_lines: Sequence[NativeSegment],
    ticks: Sequence[NativeSegment],
    extensions: Sequence[NativeSegment],
) -> DimensionEvidence:
    cx = (word.bbox[0] + word.bbox[2]) / 2.0
    cy = (word.bbox[1] + word.bbox[3]) / 2.0
    unmatched = DimensionEvidence(
        word_ref=word.ref, text=word.text, millimetres=millimetres, bbox=word.bbox,
        orientation="unknown", dimension_line_refs=(), hash_segment_refs=(),
        extension_segment_refs=(), hash_stations=(), endpoint_stations=None,
        geometry_status=STATUS_UNMATCHED, role=ROLE_UNMATCHED,
    )
    hits: list[tuple[str, NativeSegment, dict[float, list[float]]]] = []
    for axis in ("h", "v"):
        along, perp = _along_perp(axis, cx, cy)
        for line in dim_lines:
            if _axis(line) != axis:
                continue
            lo, hi = _seg_span(line)
            if along <= lo + _FACE_PT or along >= hi - _FACE_PT:
                continue
            if abs(perp - _seg_perp(line)) > _WORD_LINE_PT:
                continue
            stations = _ticks_on_line(line, ticks)
            if len(stations) < 2:
                continue
            if not _word_is_outside_ticks(line, ticks, stations, perp):
                continue
            hits.append((axis, line, stations))
    if not hits:
        return unmatched
    orientations = {axis for axis, _line, _stations in hits}
    if len(hits) != 1 or len(orientations) != 1:
        return DimensionEvidence(
            word_ref=word.ref, text=word.text, millimetres=millimetres, bbox=word.bbox,
            orientation="unknown" if len(orientations) != 1 else ("horizontal" if next(iter(orientations)) == "h" else "vertical"),
            dimension_line_refs=tuple(line.ref for _axis_name, line, _stations in hits),
            hash_segment_refs=(), extension_segment_refs=(), hash_stations=(),
            endpoint_stations=None, geometry_status=STATUS_AMBIGUOUS, role=ROLE_UNMATCHED,
        )
    axis, line, stations = hits[0]
    along, _perp = _along_perp(axis, cx, cy)
    owned = _unique_owning_interval(stations, along)
    if owned is None:
        return DimensionEvidence(
            word_ref=word.ref, text=word.text, millimetres=millimetres, bbox=word.bbox,
            orientation="horizontal" if axis == "h" else "vertical",
            dimension_line_refs=(line.ref,), hash_segment_refs=(),
            extension_segment_refs=(), hash_stations=tuple(sorted(stations)),
            endpoint_stations=None, geometry_status=STATUS_AMBIGUOUS, role=ROLE_UNMATCHED,
        )
    start, end = owned
    hash_refs = _segments_at_stations(ticks, line, (start, end))
    extension_refs = _segments_at_stations(extensions, line, (start, end), max_length=_DIM_OFFSET_MAX_PT + _TICK_MAX_PT)
    return DimensionEvidence(
        word_ref=word.ref, text=word.text, millimetres=millimetres, bbox=word.bbox,
        orientation="horizontal" if axis == "h" else "vertical",
        dimension_line_refs=(line.ref,),
        hash_segment_refs=hash_refs,
        extension_segment_refs=extension_refs,
        hash_stations=(start, end),
        endpoint_stations=(start, end),
        geometry_status=STATUS_UNIQUE, role=ROLE_UNMATCHED,
    )


def _word_is_outside_ticks(
    line: NativeSegment,
    ticks: Sequence[NativeSegment],
    stations: dict[float, list[float]],
    word_perp: float,
) -> bool:
    """Text sits on the dim-line side, opposite the measured wall/opening ticks."""
    axis = _axis(line)
    if axis is None:
        return False
    line_perp = _seg_perp(line)
    tick_axis = "v" if axis == "h" else "h"
    sides: set[int] = set()
    for tick in ticks:
        if _axis(tick) != tick_axis:
            continue
        along = (tick.x1 + tick.x2) / 2.0 if tick_axis == "v" else (tick.y1 + tick.y2) / 2.0
        if not any(abs(along - station) <= _FACE_PT for station in stations):
            continue
        perps = (tick.y1, tick.y2) if tick_axis == "v" else (tick.x1, tick.x2)
        on_line = [value for value in perps if abs(value - line_perp) <= _FACE_PT]
        off_line = [value for value in perps if abs(value - line_perp) > _FACE_PT]
        if len(on_line) != 1 or len(off_line) != 1:
            continue
        sides.add(1 if off_line[0] > line_perp else -1)
    if len(sides) != 1:
        return False
    tick_dir = sides.pop()
    word_dir = 1 if word_perp > line_perp else -1
    return word_dir != tick_dir


def _ticks_on_line(
    line: NativeSegment, ticks: Sequence[NativeSegment],
) -> dict[float, list[float]]:
    axis = _axis(line)
    if axis is None:
        return {}
    line_perp = _seg_perp(line)
    lo, hi = _seg_span(line)
    tick_axis = "v" if axis == "h" else "h"
    stations: dict[float, list[float]] = {}
    for tick in ticks:
        if _axis(tick) != tick_axis:
            continue
        along = (tick.x1 + tick.x2) / 2.0 if tick_axis == "v" else (tick.y1 + tick.y2) / 2.0
        if along < lo - _FACE_PT or along > hi + _FACE_PT:
            continue
        perps = (tick.y1, tick.y2) if tick_axis == "v" else (tick.x1, tick.x2)
        if min(perps) - _FACE_PT <= line_perp <= max(perps) + _FACE_PT:
            stations.setdefault(round(along, 2), []).append(line_perp)
    return _cluster_stations(stations)


def _unique_owning_interval(
    stations: dict[float, list[float]], along: float,
) -> tuple[float, float] | None:
    chain = sorted(stations)
    if len(chain) < 2:
        return None
    owned = [
        (left, right) for left, right in zip(chain, chain[1:])
        if left + _FACE_PT < along < right - _FACE_PT
    ]
    if len(owned) != 1:
        return None
    return owned[0]


def _segments_at_stations(
    pool: Sequence[NativeSegment],
    line: NativeSegment,
    stations: Sequence[float],
    *,
    max_length: float | None = None,
) -> tuple[str, ...]:
    axis = _axis(line)
    if axis is None:
        return ()
    tick_axis = "v" if axis == "h" else "h"
    line_perp = _seg_perp(line)
    found: list[str] = []
    for seg in pool:
        if _axis(seg) != tick_axis:
            continue
        length = _length(seg)
        if max_length is not None and length > max_length:
            continue
        along = (seg.x1 + seg.x2) / 2.0 if tick_axis == "v" else (seg.y1 + seg.y2) / 2.0
        # A matching hash station is not sufficient source ownership: an
        # unrelated distant tick/extension can share the same x or y station.
        # Require the actual segment to touch/cross the specific dim line.
        perps = (seg.y1, seg.y2) if tick_axis == "v" else (seg.x1, seg.x2)
        if not (min(perps) - _FACE_PT <= line_perp <= max(perps) + _FACE_PT):
            continue
        if any(abs(along - station) <= _FACE_PT for station in stations):
            found.append(seg.ref)
    return tuple(sorted(set(found)))
