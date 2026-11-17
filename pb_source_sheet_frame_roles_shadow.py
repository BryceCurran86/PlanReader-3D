"""Source-native sheet-frame/title-grid exclusion, strictly noncommercial.

Four unlayered unfilled thin native lines must close ONE broad source sheet
border with exact corner contact, and original printed DRAWING, REVISION and
SCALE text must be just beyond its bottom edge. No page-coordinate crop, layer
guess, project ID, threshold snap, wall synthesis, FIRM or quantity promotion.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

_NOISE_PT = 0.05
_MIN_COVERAGE = 0.65


def _point(value: Any) -> tuple[float, float]:
    if hasattr(value, "x") and hasattr(value, "y"):
        return float(value.x), float(value.y)
    return float(value[0]), float(value[1])


def _native_unlayered_rule(
    index: int, row: Mapping[str, Any] | object,
) -> tuple[int, str, float, float, float, float] | None:
    if not isinstance(row, Mapping):
        return None
    if str(row.get("layer") or "").strip() or row.get("fill") is not None:
        return None
    if row.get("type") not in ("s", None):
        return None
    items = row.get("items") or ()
    if len(items) != 1 or items[0][0] != "l":
        return None
    try:
        x0, y0 = _point(items[0][1])
        x1, y1 = _point(items[0][2])
        width = float(row.get("width"))
        color = row.get("color")
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1, width)):
            return None
        if not (0 < width <= 1.0):
            return None
        if color is not None and (
            len(color) != 3 or any(
                type(v) not in (int, float) or not math.isfinite(v)
                or abs(v) > 0.08 for v in color
            )
        ):
            return None
        dashes = "".join(str(row.get("dashes") or "").split())
        if dashes not in ("", "[]0"):
            return None
        if abs(y0 - y1) <= _NOISE_PT and abs(x0 - x1) > _NOISE_PT:
            return index, "h", min(x0, x1), y0, max(x0, x1), y0
        if abs(x0 - x1) <= _NOISE_PT and abs(y0 - y1) > _NOISE_PT:
            return index, "v", x0, min(y0, y1), x0, max(y0, y1)
    except (ValueError, TypeError, IndexError, OverflowError):
        return None
    return None


def _title_words(words: Sequence[Mapping[str, Any] | Sequence[Any]]):
    rows = []
    for word in words:
        try:
            if isinstance(word, Mapping):
                raw = word.get("text")
                r = word.get("bbox_pdf_pts") or word.get("bbox")
            else:
                raw, r = word[4], word[:4]
            x0, y0, x1, y1 = (float(v) for v in r)
            if not all(map(math.isfinite, (x0, y0, x1, y1))):
                continue
            token = "".join(c for c in str(raw).upper() if c.isalpha())
            if token in {"DRAWING", "REVISION", "SCALE"}:
                rows.append((token, x0, y0, x1, y1))
        except (ValueError, TypeError, IndexError, KeyError):
            continue
    return tuple(rows)


def source_sheet_frame_nonwall_path_ids(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> frozenset[int]:
    """Return only original native rule IDs supporting a unique title-bearing sheet.

    Empty on missing labels, ambiguous frames, nonexact corners or absent
    original path geometry. Proof is negative wall-role evidence, never
    geometry or authentication of the building.
    """
    if not drawings or not source_words or len(drawings) > 20_000:
        return frozenset()
    lines = [
        row for idx, raw in enumerate(drawings)
        if (row := _native_unlayered_rule(idx, raw)) is not None
    ]
    if len(lines) < 4:
        return frozenset()
    xs = [q for _, _, x0, _, x1, _ in lines for q in (x0, x1)]
    ys = [q for _, _, _, y0, _, y1 in lines for q in (y0, y1)]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    if dx <= 0 or dy <= 0:
        return frozenset()
    h = sorted(
        (r for r in lines if r[1] == "h" and r[4] - r[2] >= _MIN_COVERAGE * dx),
        key=lambda r: (-(r[4] - r[2]), r[0]),
    )[:32]
    v = sorted(
        (r for r in lines if r[1] == "v" and r[5] - r[3] >= _MIN_COVERAGE * dy),
        key=lambda r: (-(r[5] - r[3]), r[0]),
    )[:32]
    titles = _title_words(source_words)
    if not h or len(v) < 2 or len(titles) < 3:
        return frozenset()
    discovered: dict[tuple[float, ...], tuple[set[int], tuple[float, ...]]] = {}
    for i, left in enumerate(v):
        for right in v[i + 1:]:
            lx, rx = sorted((left[2], right[2]))
            top, bottom = left[3], left[5]
            if rx - lx < _MIN_COVERAGE * dx or bottom - top < _MIN_COVERAGE * dy:
                continue
            if abs(left[3] - right[3]) > _NOISE_PT or abs(left[5] - right[5]) > _NOISE_PT:
                continue
            horizontal = [
                r for r in h
                if abs(r[2] - lx) <= _NOISE_PT and abs(r[4] - rx) <= _NOISE_PT
                and (abs(r[3] - top) <= _NOISE_PT or abs(r[3] - bottom) <= _NOISE_PT)
            ]
            upper = [r for r in horizontal if abs(r[3] - top) <= _NOISE_PT]
            lower = [r for r in horizontal if abs(r[3] - bottom) <= _NOISE_PT]
            if len(upper) != 1 or len(lower) != 1:
                continue
            footer_limit = bottom + 0.16 * (bottom - top)
            title_hits = {
                token for token, x0, y0, x1, y1 in titles
                if lx - _NOISE_PT <= x0 <= x1 <= rx + _NOISE_PT
                and bottom - _NOISE_PT <= y0 <= y1 <= footer_limit
            }
            if not {"DRAWING", "REVISION", "SCALE"} <= title_hits:
                continue
            key = tuple(round(k, 4) for k in (lx, top, rx, bottom))
            ids = {left[0], right[0], upper[0][0], lower[0][0]}
            # Two distinct source-native frame candidates at identical
            # geometry are still competing original owners; do not let
            # a dict overwrite silently elect either one.
            if key in discovered:
                return frozenset()
            discovered[key] = (ids, (lx, top, rx, bottom, footer_limit))
    if len(discovered) != 1:
        return frozenset()
    ids, (lx, top, rx, bottom, footer_limit) = next(iter(discovered.values()))
    # Native title grid underneath the verified main drawing frame. Each
    # grid rule is source-only line ink, never a wall. A title word by itself
    # does NOT prove an unrelated off-page path belongs to this grid.
    for idx, axis, x0, y0, x1, y1 in lines:
        if (
            lx - _NOISE_PT <= x0 <= x1 <= rx + _NOISE_PT
            and bottom - _NOISE_PT <= y0 <= y1 <= footer_limit
        ):
            ids.add(idx)
    return frozenset(ids)
