"""Read-only source geometry check for an overall dimension split by two parts.

This is not a source-visibility, glyph, frame, host, metric or quantity issuer.
It accepts untrusted caller-shaped source witnesses, so even a positive result
is only a structural candidate for the real source producer to re-prove.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_opening_tag_normalization import normalize_opening_tag


@dataclass(frozen=True)
class NativeAxisLine:
    source_id: str
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class NativeAxisWord:
    source_id: str
    text: str
    bbox: tuple[float, float, float, float]


def _axis(line: NativeAxisLine):
    if type(line) is not NativeAxisLine or not line.source_id:
        return None
    try:
        a, b = (tuple(float(v) for v in pt) for pt in (line.start, line.end))
    except (ValueError, TypeError):
        return None
    if len(a) != 2 or len(b) != 2 or not all(map(math.isfinite, a + b)):
        return None
    if a[0] == b[0] and a[1] != b[1]:
        return "y", a[0], min(a[1], b[1]), max(a[1], b[1])
    if a[1] == b[1] and a[0] != b[0]:
        return "x", a[1], min(a[0], b[0]), max(a[0], b[0])
    return None


def _word(word: NativeAxisWord, axis: str):
    if (type(word) is not NativeAxisWord or not word.source_id
            or type(word.text) is not str or not word.text
            or word.text != word.text.strip()):
        return None
    try:
        box = tuple(float(v) for v in word.bbox)
    except (ValueError, TypeError):
        return None
    if (len(box) != 4 or not all(map(math.isfinite, box))
            or box[0] >= box[2] or box[1] >= box[3]):
        return None
    return (((box[0] + box[2]) / 2 if axis == "x" else (box[1] + box[3]) / 2),
            ((box[1] + box[3]) / 2 if axis == "x" else (box[0] + box[2]) / 2),
            (box[3] - box[1] if axis == "x" else box[2] - box[0]))


def audit_source_split_figured_axis_shadow(
    *,
    overall_line: NativeAxisLine,
    part_lines: tuple[NativeAxisLine, ...],
    dimension_words: tuple[NativeAxisWord, ...],
    opening_mark_words: tuple[NativeAxisWord, ...],
) -> dict:
    """Require a two-part exact ink chain, additive figures and distinct marks.

    Source geometry/word provenance is *caller-shaped*, not authenticated here.
    A matching chain can guide an independently trusted source/physical review;
    it cannot bind an elevation to a plan opening or issue area/count/height.
    """
    base = {
        "status": "ABSTAINED", "reason": "source_split_figure_unproven",
        "source_native_glyph_trust_proven": False,
        "complete_source_rival_universe_proven": False,
        "plan_to_elevation_physical_identity_bound": False,
        "physical_host_or_frame_bound": False,
        "metric_quantity_granted": False,
        "customer_seal_granted": False,
        "benchmark_score_granted": False,
    }
    all_lines = (overall_line,) + tuple(part_lines)
    all_words = tuple(dimension_words) + tuple(opening_mark_words)
    if (len(part_lines) != 2 or len(dimension_words) != 3
            or len(opening_mark_words) != 2
            or any(type(v) is not str or not v or v != v.strip()
                   for v in [*(line.source_id for line in all_lines),
                             *(word.source_id for word in all_words)])
            or len({v.source_id for v in all_lines + all_words}) != len(all_lines + all_words)):
        return base
    geometry = [_axis(line) for line in all_lines]
    if any(item is None for item in geometry):
        return base
    axis, overall_coordinate, lo, hi = geometry[0]
    parts = sorted(geometry[1:], key=lambda item: item[2])
    if (any(item[0] != axis or item[1] != parts[0][1] for item in parts)
            or parts[0][1] == overall_coordinate
            or parts[0][2] != lo or parts[0][3] != parts[1][2]
            or parts[1][3] != hi):
        return base
    part_by_span = {tuple(geometry[i][2:]): all_lines[i]
                    for i in (1, 2)}
    spans = ((parts[0][2], parts[0][3]), (parts[1][2], parts[1][3]))
    if len(part_by_span) != 2:
        return base
    numbers = []
    for word in dimension_words:
        value = _word(word, axis)
        if value is None or not word.text.isascii() or not word.text.isdecimal():
            return base
        try:
            number = int(word.text)
        except (ValueError, OverflowError):
            return base
        if number <= 0:
            return base
        numbers.append((word, number, value))
    overall_candidates = [item for item in numbers
                          if abs(item[2][1] - overall_coordinate) <= item[2][2]
                          and lo < item[2][0] < hi]
    if len(overall_candidates) != 1:
        return base
    overall_word, overall_mm, _ = overall_candidates[0]
    remaining = [item for item in numbers if item[0].source_id != overall_word.source_id]
    grouped = []
    for lower, upper in spans:
        options = [item for item in remaining
                   if lower < item[2][0] < upper
                   and abs(item[2][1] - parts[0][1]) <= item[2][2]]
        marks = [word for word in opening_mark_words
                 if (v := _word(word, axis)) is not None and lower < v[0] < upper
                 and normalize_opening_tag(word.text) is not None]
        if len(options) != 1 or len(marks) != 1:
            return base
        grouped.append((options[0], marks[0]))
    if grouped[0][0][1] + grouped[1][0][1] != overall_mm:
        return base
    normalized = [normalize_opening_tag(mark.text) for _, mark in grouped]
    if (normalized[0].tag == normalized[1].tag
            or normalized[0].trade_type == normalized[1].trade_type):
        return base
    return {
        **base,
        "status": "CANDIDATE_SOURCE_SPLIT_FIGURE",
        "reason": "original_producer_reproof_required",
        "axis": axis,
        "overall_source_line_id": overall_line.source_id,
        "overall_word_id": overall_word.source_id,
        "overall_literal_mm_untrusted": overall_mm,
        "partitions": tuple({
            "span": span,
            "dimension_line_id": part_by_span[span].source_id,
            "dimension_word_id": pair[0][0].source_id,
            "dimension_literal_mm_untrusted": pair[0][1],
            "mark_word_id": pair[1].source_id,
            "normalized_mark_candidate": norm.tag,
            "kind_candidate": norm.trade_type,
        } for span, pair, norm in zip(spans, grouped, normalized)),
    }
