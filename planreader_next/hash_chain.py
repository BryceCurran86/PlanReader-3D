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
_DIM_OFFSET_MAX_PT = 36.0


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
        owned = _unique_ratio_cover(
            intervals, figures, horizontal_wall=horizontal_wall,
        )
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


def _contiguous_runs(owned: Sequence[int]) -> list[list[int]]:
    ordered = sorted(owned)
    runs: list[list[int]] = [[ordered[0]]]
    for index in ordered[1:]:
        if index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs


def _equal_leftover_runs(
    runs: Sequence[Sequence[int]],
    intervals: Sequence[tuple[float, float, Decimal]],
) -> bool:
    if len(runs) < 2:
        return True
    spans = [sum((intervals[index][2] for index in run), Decimal("0")) for run in runs]
    if any(span == 0 for span in spans):
        return False
    first = spans[0]
    return all(abs(span / first - 1) <= Decimal("0.05") for span in spans[1:])


def _word_in_owned_span(
    along: float,
    owned: Sequence[int],
    intervals: Sequence[tuple[float, float, Decimal]],
) -> bool:
    """Word must sit in an owned run, or in the gap between equal leftover runs."""
    runs = _contiguous_runs(owned)
    for run in runs:
        lo, hi = intervals[run[0]][0], intervals[run[-1]][1]
        if lo + _FACE_PT < along < hi - _FACE_PT:
            return True
    if len(runs) >= 2 and _equal_leftover_runs(runs, intervals):
        lo, hi = intervals[min(owned)][0], intervals[max(owned)][1]
        return lo + _FACE_PT < along < hi - _FACE_PT
    return False


def _unique_ratio_cover(
    intervals: Sequence[tuple[float, float, Decimal]],
    figures: Sequence[NativeWord],
    *,
    horizontal_wall: bool | None = None,
) -> list[NativeWord] | None:
    """Split a crowded hash run when exactly one interval-to-word cover has one pt/mm.

    Ownership is the native word ref, not the printed millimetres. Equal figures
    on separated intervals are ambiguous. A word may own equal leftover side
    runs only when that cover is unique. Geometric PDF wall length is not used.
    """
    count_intervals = len(intervals)
    count_figures = len(figures)
    if count_intervals < 2 or count_figures < 2 or count_intervals > 8 or count_figures > 6:
        return None
    millimetres = [_figured_mm(word) for word in figures]
    if any(value == 0 for value in millimetres):
        return None
    along_values = (
        None if horizontal_wall is None
        else [_word_along(word, horizontal_wall) for word in figures]
    )
    mappings: set[tuple[str, ...]] = set()
    for assignment in product(range(count_figures), repeat=count_intervals):
        if len(set(assignment)) != count_figures:
            continue
        owned_by_figure = [
            [index for index, figure_index in enumerate(assignment) if figure_index == figure]
            for figure in range(count_figures)
        ]
        if any(
            not _equal_leftover_runs(_contiguous_runs(owned), intervals)
            for owned in owned_by_figure
        ):
            continue
        if along_values is not None:
            if any(
                not _word_in_owned_span(along_values[figure], owned_by_figure[figure], intervals)
                for figure in range(count_figures)
            ):
                continue
        spans = [Decimal("0")] * count_figures
        for index, figure_index in enumerate(assignment):
            spans[figure_index] += intervals[index][2]
        ratios = [spans[index] / millimetres[index] for index in range(count_figures)]
        first = ratios[0]
        if any(abs(ratio / first - 1) > Decimal("0.05") for ratio in ratios[1:]):
            continue
        mappings.add(tuple(figures[figure_index].ref for figure_index in assignment))
    if len(mappings) != 1:
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
    face = _bind_from_ticks(
        page,
        _tick_stations(
            page.segments,
            horizontal_wall=horizontal_wall,
            face_perp=face_perp,
            lo=lo,
            hi=hi,
            outward=outward,
        ),
        horizontal_wall=horizontal_wall,
        lo=lo,
        hi=hi,
        face_perp=face_perp,
    )
    if face is not None:
        return face
    return _bind_from_ticks(
        page,
        _projected_tick_stations(
            page.segments,
            horizontal_wall=horizontal_wall,
            face_perp=face_perp,
            lo=lo,
            hi=hi,
            outward=outward,
        ),
        horizontal_wall=horizontal_wall,
        lo=lo,
        hi=hi,
        face_perp=face_perp,
    )


def _projected_tick_stations(
    segments: Sequence[NativeSegment],
    *,
    horizontal_wall: bool,
    face_perp: float,
    lo: float,
    hi: float,
    outward: float,
) -> dict[float, list[float]]:
    """Hashes on an outside dimension line whose stations line up with the wall ends.

    The tick does not have to touch the wall face. The wall ends and the hashes
    share the same along-station on a parallel dimension line further out.
    """
    dim_lines: list[float] = []
    min_span = max(40.0, (hi - lo) * 0.5)
    for seg in segments:
        dx, dy = seg.x2 - seg.x1, seg.y2 - seg.y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < min_span:
            continue
        if horizontal_wall:
            if abs(dy) > _FACE_PT or abs(dx) < min_span:
                continue
            line_perp = (seg.y1 + seg.y2) / 2.0
            along_lo, along_hi = sorted((seg.x1, seg.x2))
        else:
            if abs(dx) > _FACE_PT or abs(dy) < min_span:
                continue
            line_perp = (seg.x1 + seg.x2) / 2.0
            along_lo, along_hi = sorted((seg.y1, seg.y2))
        offset = (line_perp - face_perp) * outward
        if offset <= _FACE_PT or offset > _DIM_OFFSET_MAX_PT:
            continue
        if along_lo > lo + _FACE_PT or along_hi < hi - _FACE_PT:
            continue
        dim_lines.append(line_perp)
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
        for line_perp in dim_lines:
            if min(perps) - _FACE_PT <= line_perp <= max(perps) + _FACE_PT:
                stations.setdefault(round(along, 2), []).append(line_perp)
                break
    return _cluster_stations(stations)


def _bind_from_ticks(
    page: NativePage,
    ticks: dict[float, list[float]],
    *,
    horizontal_wall: bool,
    lo: float,
    hi: float,
    face_perp: float,
) -> HashBoundLength | None:
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
    return _bind_cardinal_axes(
        page,
        south=(y1, x0, x1),
        north=(y0, x0, x1),
        east=(x1, y0, y1),
        west=(x0, y0, y1),
    )


def bind_polygon_hash_axes(
    page: NativePage, coords: Sequence[Sequence[float]],
) -> tuple[HashBoundLength | None, HashBoundLength | None]:
    """Bind hashes to the ring's own internal faces, not the bounding rectangle."""
    faces = _cardinal_internal_faces(coords)
    if faces is None:
        return None, None
    return _bind_cardinal_axes(page, **faces)


def _cardinal_internal_faces(
    coords: Sequence[Sequence[float]],
) -> dict[str, tuple[float, float, float]] | None:
    """One merged axis-aligned edge on each extreme, or None if a side is split."""
    points = [(float(x), float(y)) for x, y in coords]
    if len(points) < 4:
        return None
    if points[0] == points[-1]:
        points = points[:-1]
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    extremes = {"west": min(xs), "east": max(xs), "north": min(ys), "south": max(ys)}
    buckets = {name: [] for name in extremes}
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        if abs(y0 - y1) <= _FACE_PT and abs(x1 - x0) > _FACE_PT:
            face = (y0 + y1) / 2.0
            lo, hi = sorted((x0, x1))
            if abs(face - extremes["south"]) <= _FACE_PT:
                buckets["south"].append((lo, hi))
            if abs(face - extremes["north"]) <= _FACE_PT:
                buckets["north"].append((lo, hi))
        elif abs(x0 - x1) <= _FACE_PT and abs(y1 - y0) > _FACE_PT:
            face = (x0 + x1) / 2.0
            lo, hi = sorted((y0, y1))
            if abs(face - extremes["east"]) <= _FACE_PT:
                buckets["east"].append((lo, hi))
            if abs(face - extremes["west"]) <= _FACE_PT:
                buckets["west"].append((lo, hi))
    faces: dict[str, tuple[float, float, float]] = {}
    for name, spans in buckets.items():
        merged = _merge_along_spans(spans)
        if len(merged) != 1:
            continue
        lo, hi = merged[0]
        faces[name] = (extremes[name], lo, hi)
    if len(faces) < 2:
        return None
    return faces


def _merge_along_spans(spans: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered = sorted(spans)
    if not ordered:
        return []
    merged = [ordered[0]]
    for lo, hi in ordered[1:]:
        prev_lo, prev_hi = merged[-1]
        if lo <= prev_hi + _FACE_PT:
            merged[-1] = (prev_lo, max(prev_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _bind_cardinal_axes(
    page: NativePage,
    *,
    south: tuple[float, float, float] | None = None,
    north: tuple[float, float, float] | None = None,
    east: tuple[float, float, float] | None = None,
    west: tuple[float, float, float] | None = None,
) -> tuple[HashBoundLength | None, HashBoundLength | None]:
    widths = []
    heights = []
    if south is not None:
        face, lo, hi = south
        widths.append(bind_wall_hash_length(
            page, horizontal_wall=True, face_perp=face, lo=lo, hi=hi, outward=1.0,
        ))
    if north is not None:
        face, lo, hi = north
        widths.append(bind_wall_hash_length(
            page, horizontal_wall=True, face_perp=face, lo=lo, hi=hi, outward=-1.0,
        ))
    if east is not None:
        face, lo, hi = east
        heights.append(bind_wall_hash_length(
            page, horizontal_wall=False, face_perp=face, lo=lo, hi=hi, outward=1.0,
        ))
    if west is not None:
        face, lo, hi = west
        heights.append(bind_wall_hash_length(
            page, horizontal_wall=False, face_perp=face, lo=lo, hi=hi, outward=-1.0,
        ))
    return _unique_length(widths), _unique_length(heights)


def _unique_length(hits: Sequence[HashBoundLength | None]) -> HashBoundLength | None:
    found = [item for item in hits if item is not None]
    if not found:
        return None
    if len({item.length_mm for item in found}) != 1:
        return None
    return found[0]
