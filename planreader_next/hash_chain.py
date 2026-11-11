"""Bind a wall's two ends to outside dimension hashes, then read the unique figure.

Walks the source-drawn hash stations on a dimension line that the wall ends
actually meet. The printed millimetre value between those hashes is the
measurement. Geometric PDF length is never used to pick a number, and 2.5 pt
production snap is not used here: inner and outer wall faces are ~2 pt apart.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from typing import Sequence

from .engine import NativePage, NativeSegment, NativeWord, SourceConflict, _figured_mm

# Face identity only. Must stay below typical wall thickness (~2 pt).
_FACE_PT = 0.35
_TICK_MIN_PT = 1.4
_TICK_MAX_PT = 8.0
_WORD_LINE_PT = 24.0


@dataclass(frozen=True)
class HashBoundLength:
    length_mm: Decimal
    word_refs: tuple[str, ...]
    hash_stations: tuple[float, ...]
    dimension_line_perp: float
    side: str


def _along_perp(horizontal: bool, x: float, y: float) -> tuple[float, float]:
    return (x, y) if horizontal else (y, x)


def _tick_stations(
    segments: Sequence[NativeSegment],
    *,
    horizontal_wall: bool,
    face_perp: float,
    lo: float,
    hi: float,
    outward: float,
) -> dict[float, list[float]]:
    """Map along-station -> outer perp of witness hashes that leave this face."""
    stations: dict[float, list[float]] = {}
    for seg in segments:
        dx, dy = seg.x2 - seg.x1, seg.y2 - seg.y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < _TICK_MIN_PT or length > _TICK_MAX_PT:
            continue
        if horizontal_wall:
            if abs(dx) > _FACE_PT or abs(dy) < _TICK_MIN_PT:
                continue
            along = (seg.x1 + seg.x2) / 2.0
            perps = (seg.y1, seg.y2)
        else:
            if abs(dy) > _FACE_PT or abs(dx) < _TICK_MIN_PT:
                continue
            along = (seg.y1 + seg.y2) / 2.0
            perps = (seg.x1, seg.x2)
        if along < lo - _FACE_PT or along > hi + _FACE_PT:
            continue
        on_face = [value for value in perps if abs(value - face_perp) <= _FACE_PT]
        off_face = [value for value in perps if abs(value - face_perp) > _FACE_PT]
        if len(on_face) != 1 or len(off_face) != 1:
            continue
        if (off_face[0] - face_perp) * outward <= 0:
            continue
        stations.setdefault(round(along, 2), []).append(off_face[0])
    return _cluster_stations(stations)


def _cluster_stations(stations: dict[float, list[float]]) -> dict[float, list[float]]:
    """Merge duplicate hash ink at one station. Does not pick among distinct faces."""
    grouped: dict[float, list[float]] = {}
    for along in sorted(stations):
        if grouped and along - next(reversed(grouped)) <= _FACE_PT:
            grouped[next(reversed(grouped))].extend(stations[along])
        else:
            grouped[along] = list(stations[along])
    return grouped


def _unique_end_station(stations: dict[float, list[float]], target: float) -> float | None:
    hits = [key for key in stations if abs(key - target) <= _FACE_PT]
    if len(hits) != 1:
        return None
    return hits[0]


def _complete_chain(
    page: NativePage,
    *,
    horizontal_wall: bool,
    lo: float,
    hi: float,
    face_perp: float,
    line_perp: float,
    start: float,
    end: float,
    stations: Sequence[float],
) -> HashBoundLength | None:
    between = [value for value in stations if start - _FACE_PT <= value <= end + _FACE_PT]
    chain = sorted({round(value, 2) for value in between})
    if abs(chain[0] - start) > _FACE_PT or abs(chain[-1] - end) > _FACE_PT:
        return None
    figures = _chain_figures(
        page, horizontal_wall=horizontal_wall, face_perp=face_perp,
        line_perp=line_perp, start=chain[0], end=chain[-1],
    )
    if not figures:
        return None
    intervals = [
        (left, right, Decimal(str(right - left)))
        for left, right in zip(chain, chain[1:])
    ]
    owned = _unique_interval_words(intervals, figures, horizontal_wall)
    if owned is None:
        owned = _unique_ratio_cover(intervals, figures)
    if owned is None:
        return None
    total = sum((_figured_mm(word) for word in owned), Decimal("0"))
    side = "horizontal" if horizontal_wall else "vertical"
    return HashBoundLength(
        length_mm=total,
        word_refs=tuple(word.ref for word in owned),
        hash_stations=tuple(chain),
        dimension_line_perp=line_perp,
        side=side,
    )


def _chain_figures(
    page: NativePage, *, horizontal_wall: bool, face_perp: float,
    line_perp: float, start: float, end: float,
) -> list[NativeWord]:
    found: list[NativeWord] = []
    for word in page.words:
        try:
            _figured_mm(word)
        except SourceConflict:
            continue
        cx = (word.bbox[0] + word.bbox[2]) / 2.0
        cy = (word.bbox[1] + word.bbox[3]) / 2.0
        along, perp = _along_perp(horizontal_wall, cx, cy)
        if not (start + _FACE_PT < along < end - _FACE_PT):
            continue
        if abs(perp - line_perp) > _WORD_LINE_PT:
            continue
        if (perp - face_perp) * (line_perp - face_perp) <= 0:
            continue
        found.append(word)
    return found


def _word_along(word: NativeWord, horizontal_wall: bool) -> float:
    cx = (word.bbox[0] + word.bbox[2]) / 2.0
    cy = (word.bbox[1] + word.bbox[3]) / 2.0
    along, _perp = _along_perp(horizontal_wall, cx, cy)
    return along


def _unique_interval_words(
    intervals: Sequence[tuple[float, float, Decimal]],
    figures: Sequence[NativeWord],
    horizontal_wall: bool,
) -> list[NativeWord] | None:
    owned: list[NativeWord] = []
    spans: list[tuple[Decimal, Decimal]] = []
    for left, right, span in intervals:
        inside = [
            word for word in figures
            if left + _FACE_PT < _word_along(word, horizontal_wall) < right - _FACE_PT
        ]
        if len(inside) != 1:
            return None
        millimetres = _figured_mm(inside[0])
        if millimetres == 0:
            return None
        owned.append(inside[0])
        spans.append((span, millimetres))
    if len(spans) > 1:
        ratios = [span / millimetres for span, millimetres in spans]
        first = ratios[0]
        if any(abs(ratio / first - 1) > Decimal("0.05") for ratio in ratios[1:]):
            return None
    return owned


def _unique_ratio_cover(
    intervals: Sequence[tuple[float, float, Decimal]],
    figures: Sequence[NativeWord],
) -> list[NativeWord] | None:
    """Split a crowded hash run when exactly one interval-to-figure cover has one pt/mm.

    Geometric PDF wall length is not an input. The only comparison is hash-interval
    span versus the printed millimetres already on this same dimension chain.
    """
    count_intervals = len(intervals)
    count_figures = len(figures)
    if count_intervals < 2 or count_figures < 2 or count_intervals > 8 or count_figures > 6:
        return None
    millimetres = [_figured_mm(word) for word in figures]
    if any(value == 0 for value in millimetres):
        return None
    signatures: dict[tuple[Decimal, ...], list[tuple[int, ...]]] = {}
    for assignment in product(range(count_figures), repeat=count_intervals):
        if len(set(assignment)) != count_figures:
            continue
        spans = [Decimal("0")] * count_figures
        for index, figure_index in enumerate(assignment):
            spans[figure_index] += intervals[index][2]
        ratios = [spans[index] / millimetres[index] for index in range(count_figures)]
        first = ratios[0]
        if any(abs(ratio / first - 1) > Decimal("0.05") for ratio in ratios[1:]):
            continue
        signature = tuple(millimetres[figure_index] for figure_index in assignment)
        signatures.setdefault(signature, []).append(assignment)
    if len(signatures) != 1:
        return None
    return list(figures)


def bind_wall_hash_length(
    page: NativePage,
    *,
    horizontal_wall: bool,
    face_perp: float,
    lo: float,
    hi: float,
    outward: float,
) -> HashBoundLength | None:
    """Return the unique outside hash-chain length for one wall, or None."""
    if hi - lo < 8.0:
        return None
    ticks = _tick_stations(
        page.segments,
        horizontal_wall=horizontal_wall,
        face_perp=face_perp,
        lo=lo,
        hi=hi,
        outward=outward,
    )
    start = _unique_end_station(ticks, lo)
    finish = _unique_end_station(ticks, hi)
    if start is None or finish is None:
        return None
    line_values = []
    for station in (start, finish):
        line_values.extend(ticks[station])
    shared: list[float] = []
    for value in {round(item, 2) for item in line_values}:
        if any(abs(item - value) <= _FACE_PT for item in ticks[start]) and any(
            abs(item - value) <= _FACE_PT for item in ticks[finish]
        ):
            shared.append(value)
    if not shared:
        return None
    complete: list[HashBoundLength] = []
    for line_perp in sorted(set(shared)):
        stations = [
            station
            for station, outers in ticks.items()
            if any(abs(outer - line_perp) <= _FACE_PT for outer in outers)
        ]
        bound = _complete_chain(
            page,
            horizontal_wall=horizontal_wall,
            lo=lo,
            hi=hi,
            face_perp=face_perp,
            line_perp=line_perp,
            start=start,
            end=finish,
            stations=stations,
        )
        if bound is not None:
            complete.append(bound)
    if not complete:
        return None
    totals = {item.length_mm for item in complete}
    if len(totals) != 1:
        return None
    if len(complete) == 1:
        return complete[0]
    refs = tuple(sorted({ref for item in complete for ref in item.word_refs}))
    first = complete[0]
    return HashBoundLength(
        length_mm=first.length_mm,
        word_refs=refs,
        hash_stations=first.hash_stations,
        dimension_line_perp=first.dimension_line_perp,
        side=first.side,
    )


def bind_room_hash_axes(page: NativePage, bbox: Sequence[float]) -> tuple[HashBoundLength | None, HashBoundLength | None]:
    """Unique width (horizontal wall) and height (vertical wall) hash chains."""
    x0, y0, x1, y1 = (float(value) for value in bbox)
    widths = [
        bind_wall_hash_length(
            page, horizontal_wall=True, face_perp=y1, lo=x0, hi=x1, outward=1.0,
        ),
        bind_wall_hash_length(
            page, horizontal_wall=True, face_perp=y0, lo=x0, hi=x1, outward=-1.0,
        ),
    ]
    heights = [
        bind_wall_hash_length(
            page, horizontal_wall=False, face_perp=x1, lo=y0, hi=y1, outward=1.0,
        ),
        bind_wall_hash_length(
            page, horizontal_wall=False, face_perp=x0, lo=y0, hi=y1, outward=-1.0,
        ),
    ]
    return _unique_length(widths), _unique_length(heights)


def _unique_length(hits: Sequence[HashBoundLength | None]) -> HashBoundLength | None:
    found = [item for item in hits if item is not None]
    if not found:
        return None
    if len({item.length_mm for item in found}) != 1:
        return None
    return found[0]
