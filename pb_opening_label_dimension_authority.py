"""Source-owned opening-label dimension authority.

Architectural floor plans often label an already-drawn physical opening with a
compact size callout such as 1200 - 1810 ASW or 870 CS instead of a detached
dimension chain or schedule row. This module binds those printed callouts only
to an independently proven physical opening.

It never creates an opening from text, chooses nearest text/opening, infers
width-versus-height order from a two-number callout, uses drawing scale to
manufacture figured dimensions, or reads benchmark truth/project identity.

Two-number callouts publish an order-invariant area. Axis-specific width and
height remain unresolved here until a separate authority proves the source
ordering convention.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningExistenceRecord,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationRecord
from pb_source_visibility_authority import SourceVisibilityProducer


OPENING_LABEL_DIMENSION_SCHEMA_VERSION = "1.0.0"
OPENING_LABEL_DIMENSION_RESOLVED = "opening_label_dimension_resolved"
OPENING_LABEL_DIMENSION_UNAVAILABLE = "opening_label_dimension_unavailable"
OPENING_LABEL_DIMENSION_GEOMETRY_UNAVAILABLE = "opening_label_dimension_geometry_unavailable"
OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE = "opening_label_dimension_text_unavailable"
OPENING_LABEL_DIMENSION_AMBIGUOUS = "opening_label_dimension_ambiguous"
OPENING_LABEL_DIMENSION_SEMANTIC_CONFLICT = "opening_label_dimension_semantic_conflict"
OPENING_LABEL_DIMENSION_SOURCE_SCOPE_UNAVAILABLE = "opening_label_dimension_source_scope_unavailable"

_MIN_OPENING_DIMENSION_MM = 400.0
_MAX_OPENING_DIMENSION_MM = 6000.0
_COORD_TOL = 1e-6

_PAIR_RE = re.compile(
    r"^\s*(?P<a>\d{1,2}[,.]\d{3}|\d{3,4}|\d{1,2})\s*"
    r"(?:[-–—xX×])\s*"
    r"(?P<b>\d{1,2}[,.]\d{3}|\d{3,4}|\d{1,2})"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(
    r"^\s*(?P<a>\d{1,2}[,.]\d{3}|\d{3,4})(?P<tail>.*)$",
    re.IGNORECASE,
)
_WINDOW_TOKEN_RE = re.compile(
    r"\b(?:ASW|AAW|ADH|ADHW|ASHW|AFW|ALW|WINDOWS?)\b",
    re.IGNORECASE,
)
_DOOR_TOKEN_RE = re.compile(
    r"\b(?:ASD|ASSD|VSD|CS)\b|\b(?:PANEL\s+LIFT\s+)?DOORS?\b",
    re.IGNORECASE,
)
_OPENING_MODIFIER_TOKEN_RE = re.compile(
    r"\b(?:ASW|AAW|ADH|ADHW|ASHW|AFW|ALW|ASD|ASSD|VSD|CS|OBS|"
    r"PANEL|LIFT|DOOR|WINDOW)\b",
    re.IGNORECASE,
)
_ALLOWED_TAIL_RE = re.compile(
    r"^(?:\s*[-–—]?\s*)"
    r"(?:(?:ASW|AAW|ADH|ADHW|ASHW|AFW|ALW|ASD|ASSD|VSD|CS|OBS|"
    r"PANEL|LIFT|DOOR)\b[\s-]*)*$",
    re.IGNORECASE,
)
_ALLOWED_SINGLE_TAIL_RE = re.compile(
    r"^\s*(?:(?:ASW|AAW|ADH|ADHW|ASHW|AFW|ALW|ASD|ASSD|VSD|CS|OBS|"
    r"PANEL|LIFT|DOOR)\b\s*)*$",
    re.IGNORECASE,
)
_FRAGMENT_EXCLUSION_TOKEN_RE = re.compile(
    r"^(?:CLEAR|NICHE|SCALE)$",
    re.IGNORECASE,
)
_FRAGMENT_CONTINUATION_TOKEN_RE = re.compile(
    r"^(?:[-–—xX×])$",
)

_Key = tuple[str, str, str, str, str]


@dataclass(frozen=True)
class ParsedOpeningLabel:
    """Syntax-only opening-label parse; semantics resolve after ownership."""

    raw_text: str
    dimension_tokens: tuple[str, ...]
    dimension_values_mm: tuple[float, ...]
    suffix_text: str
    semantic_kind: Optional[str]
    compact_hundreds_used: bool

    @property
    def dimension_count(self) -> int:
        return len(self.dimension_tokens)

    @property
    def area_m2(self) -> Optional[float]:
        if len(self.dimension_values_mm) != 2:
            return None
        return (
            float(self.dimension_values_mm[0])
            * float(self.dimension_values_mm[1])
            / 1_000_000.0
        )


@dataclass(frozen=True)
class OpeningLabelDimensionEvidence:
    evidence_id: str
    opening_record_id: str
    page_id: str
    viewport_id: Optional[str]
    source_text_observation_ids: tuple[str, ...]
    raw_text: str
    dimension_values_mm: tuple[float, ...]
    semantic_kind: Optional[str]
    area_m2: Optional[float]
    axis_order_resolved: bool = False
    basis: str = "figured_opening_label"
    schema_version: str = OPENING_LABEL_DIMENSION_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningLabelDimensionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: Optional[OpeningLabelDimensionEvidence] = None
    schema_version: str = OPENING_LABEL_DIMENSION_SCHEMA_VERSION


@dataclass(frozen=True)
class _GapSpan:
    axis: tuple[float, float]
    normal: tuple[float, float]
    along_min: float
    along_max: float
    cross_center: float
    cross_spread: float


@dataclass(frozen=True)
class _TrustedTextLine:
    observation_ids: tuple[str, ...]
    text: str
    bbox: tuple[float, float, float, float]


def _blocked(status: EvidenceResolutionStatus, *reasons: str) -> OpeningLabelDimensionResult:
    return OpeningLabelDimensionResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(reason for reason in reasons if reason))
        or (OPENING_LABEL_DIMENSION_UNAVAILABLE,),
    )


def _semantic_kind_evidence(text: str) -> tuple[Optional[str], bool]:
    """Resolve suffix semantics only after authenticated opening ownership."""
    has_window = _WINDOW_TOKEN_RE.search(text or "") is not None
    has_door = _DOOR_TOKEN_RE.search(text or "") is not None
    if has_window and has_door:
        return None, True
    if has_window:
        return "window", False
    if has_door:
        return "door", False
    return None, False


def _semantic_kind(text: str) -> Optional[str]:
    kind, conflict = _semantic_kind_evidence(text)
    return None if conflict else kind


def _dimension_token_mm(raw: str, *, compact_allowed: bool) -> Optional[tuple[float, bool]]:
    cleaned = str(raw or "").replace(",", "").replace(".", "").strip()
    if not cleaned.isdigit():
        return None
    compact = len(cleaned) <= 2
    value = float(int(cleaned))
    if compact:
        if not compact_allowed:
            return None
        value *= 100.0
    if not (_MIN_OPENING_DIMENSION_MM <= value <= _MAX_OPENING_DIMENSION_MM):
        return None
    return value, compact


def _normalised_suffix(text: str) -> str:
    return " ".join(str(text or "").split())


def parse_opening_label_dimensions(text: str) -> Optional[ParsedOpeningLabel]:
    """Parse syntax only; never infer door/window kind or physical ownership."""
    raw = " ".join(str(text or "").split())
    if not raw:
        return None

    pair = _PAIR_RE.fullmatch(raw)
    if pair is not None:
        tail = str(pair.group("tail") or "")
        if tail.strip() and _ALLOWED_TAIL_RE.fullmatch(tail) is None:
            return None
        compact_allowed = _OPENING_MODIFIER_TOKEN_RE.search(tail) is not None
        first = _dimension_token_mm(pair.group("a"), compact_allowed=compact_allowed)
        second = _dimension_token_mm(pair.group("b"), compact_allowed=compact_allowed)
        if first is None or second is None:
            return None
        return ParsedOpeningLabel(
            raw_text=raw,
            dimension_tokens=(str(pair.group("a")), str(pair.group("b"))),
            dimension_values_mm=(first[0], second[0]),
            suffix_text=_normalised_suffix(tail),
            semantic_kind=None,
            compact_hundreds_used=bool(first[1] or second[1]),
        )

    single = _SINGLE_RE.fullmatch(raw)
    if single is None:
        return None
    tail = str(single.group("tail") or "")
    if tail.strip() and _ALLOWED_SINGLE_TAIL_RE.fullmatch(tail) is None:
        return None
    value = _dimension_token_mm(single.group("a"), compact_allowed=False)
    if value is None:
        return None
    return ParsedOpeningLabel(
        raw_text=raw,
        dimension_tokens=(str(single.group("a")),),
        dimension_values_mm=(value[0],),
        suffix_text=_normalised_suffix(tail),
        semantic_kind=None,
        compact_hundreds_used=False,
    )

def _line(record: SourceObservationRecord) -> Optional[tuple[float, float, float, float]]:
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


def _unit(line: Sequence[float]) -> Optional[tuple[float, float]]:
    dx = float(line[2]) - float(line[0])
    dy = float(line[3]) - float(line[1])
    length = math.hypot(dx, dy)
    if length <= _COORD_TOL:
        return None
    ux, uy = dx / length, dy / length
    if ux < -_COORD_TOL or (abs(ux) <= _COORD_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    return (ux, uy)


def _cross(left: tuple[float, float], right: tuple[float, float]) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _dot(point: tuple[float, float], axis: tuple[float, float]) -> float:
    return point[0] * axis[0] + point[1] * axis[1]


def _endpoints(line: Sequence[float]) -> tuple[tuple[float, float], tuple[float, float]]:
    return ((float(line[0]), float(line[1])), (float(line[2]), float(line[3])))


def _collinear(left: Sequence[float], right: Sequence[float]) -> bool:
    left_axis = _unit(left)
    right_axis = _unit(right)
    if left_axis is None or right_axis is None:
        return False
    if abs(_cross(left_axis, right_axis)) > _COORD_TOL:
        return False
    origin = _endpoints(left)[0]
    other = _endpoints(right)[0]
    return abs(
        _cross(left_axis, (other[0] - origin[0], other[1] - origin[1]))
    ) <= _COORD_TOL


def _gap_span(records: Sequence[SourceObservationRecord]) -> Optional[_GapSpan]:
    lines = tuple(
        (record, geometry)
        for record in records
        if (geometry := _line(record)) is not None
    )
    if len(lines) != len(records):
        return None

    candidates: list[tuple[tuple[float, float], float, float, float]] = []
    for index, (_first_record, first) in enumerate(lines):
        for _second_record, second in lines[index + 1:]:
            if not _collinear(first, second):
                continue
            axis = _unit(first)
            if axis is None:
                continue
            normal = (-axis[1], axis[0])
            first_values = sorted(_dot(point, axis) for point in _endpoints(first))
            second_values = sorted(_dot(point, axis) for point in _endpoints(second))
            if first_values[0] <= second_values[0]:
                left, right = first_values, second_values
            else:
                left, right = second_values, first_values
            gap_start, gap_end = left[1], right[0]
            if gap_end - gap_start <= _COORD_TOL:
                continue
            cross_value = sum(
                _dot(point, normal)
                for point in (*_endpoints(first), *_endpoints(second))
            ) / 4.0
            candidates.append((axis, gap_start, gap_end, cross_value))

    if not candidates:
        return None

    groups: list[list[tuple[tuple[float, float], float, float, float]]] = []
    for candidate in candidates:
        axis, start, end, _ = candidate
        matching_group = None
        for group in groups:
            g_axis, g_start, g_end, _ = group[0]
            if (
                abs(abs(g_axis[0] * axis[0] + g_axis[1] * axis[1]) - 1.0)
                <= _COORD_TOL
                and abs(g_start - start) <= _COORD_TOL
                and abs(g_end - end) <= _COORD_TOL
            ):
                matching_group = group
                break
        if matching_group is None:
            groups.append([candidate])
        else:
            matching_group.append(candidate)

    if len(groups) != 1:
        return None
    group = groups[0]
    axis, start, end, _ = group[0]
    # _unit already canonicalizes direction, so every matching group uses the
    # same projection sign.
    normal = (-axis[1], axis[0])
    cross_values = tuple(item[3] for item in group)
    return _GapSpan(
        axis=axis,
        normal=normal,
        along_min=min(start, end),
        along_max=max(start, end),
        cross_center=sum(cross_values) / len(cross_values),
        cross_spread=max(cross_values) - min(cross_values),
    )


def _bbox_union(values: Sequence[Sequence[float]]) -> Optional[tuple[float, float, float, float]]:
    if not values:
        return None
    try:
        boxes = [tuple(float(value) for value in item[:4]) for item in values]
    except (TypeError, ValueError):
        return None
    if any(len(box) != 4 or not all(math.isfinite(value) for value in box) for box in boxes):
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _adjacent_exclusion_token(
    rows: Sequence[tuple[int, str, str, tuple[float, ...]]],
    *,
    start: int,
    end: int,
) -> bool:
    """Reject a partial parse when a nearby source token changes its meaning."""

    def _is_close(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
        lx0, ly0, lx1, ly1 = (float(v) for v in left[:4])
        rx0, ry0, rx1, ry1 = (float(v) for v in right[:4])
        horizontal_gap = max(0.0, max(lx0, rx0) - min(lx1, rx1))
        vertical_overlap = max(0.0, min(ly1, ry1) - max(ly0, ry0))
        min_height = max(
            _COORD_TOL,
            min(abs(ly1 - ly0), abs(ry1 - ry0)),
        )
        return (
            vertical_overlap >= 0.5 * min_height
            and horizontal_gap <= 1.5 * min_height
        )

    if start > 0:
        token = str(rows[start - 1][2] or "").strip()
        if (
            (
                _FRAGMENT_EXCLUSION_TOKEN_RE.fullmatch(token) is not None
                or _FRAGMENT_CONTINUATION_TOKEN_RE.fullmatch(token) is not None
            )
            and _is_close(rows[start - 1][3], rows[start][3])
        ):
            return True
    if end < len(rows):
        token = str(rows[end][2] or "").strip()
        if (
            (
                _FRAGMENT_EXCLUSION_TOKEN_RE.fullmatch(token) is not None
                or _FRAGMENT_CONTINUATION_TOKEN_RE.fullmatch(token) is not None
            )
            and _is_close(rows[end - 1][3], rows[end][3])
        ):
            return True
    return False


def _select_fragment_candidates(
    candidates: Sequence[tuple[tuple[int, int], int, int, _TrustedTextLine]],
) -> tuple[_TrustedTextLine, ...]:
    """Resolve overlap components by syntax rank; preserve equal-rank ties."""
    pending = sorted(
        candidates,
        key=lambda item: (item[1], item[2], item[3].observation_ids, item[3].text),
    )
    components: list[list[tuple[tuple[int, int], int, int, _TrustedTextLine]]] = []
    for candidate in pending:
        _rank, start, end, _fragment = candidate
        touched: list[int] = []
        for index, component in enumerate(components):
            if any(
                start < other_end and other_start < end
                for _r, other_start, other_end, _f in component
            ):
                touched.append(index)
        if not touched:
            components.append([candidate])
            continue
        merged = [candidate]
        for index in reversed(touched):
            merged.extend(components.pop(index))
        components.append(merged)

    winners: list[tuple[int, int, _TrustedTextLine]] = []
    for component in components:
        best_rank = max(item[0] for item in component)
        seen: set[tuple[int, int, tuple[str, ...], str]] = set()
        for rank, start, end, fragment in sorted(
            component,
            key=lambda item: (item[1], item[2], item[3].observation_ids, item[3].text),
        ):
            if rank != best_rank:
                continue
            key = (start, end, fragment.observation_ids, fragment.text)
            if key in seen:
                continue
            seen.add(key)
            winners.append((start, end, fragment))

    return tuple(
        fragment
        for _start, _end, fragment in sorted(
            winners,
            key=lambda item: (item[0], item[1], item[2].observation_ids, item[2].text),
        )
    )


def _parseable_opening_label_fragments(
    rows: Sequence[tuple[int, str, str, tuple[float, ...]]],
) -> tuple[_TrustedTextLine, ...]:
    """Split one native text line using deterministic syntax evidence only."""
    ordered = sorted(rows, key=lambda item: (item[0], item[1]))
    if not ordered:
        return ()

    candidates: list[tuple[tuple[int, int], int, int, _TrustedTextLine]] = []
    max_words = 7
    for start in range(len(ordered)):
        for end in range(start + 1, min(len(ordered), start + max_words) + 1):
            subset = ordered[start:end]
            text_value = " ".join(row[2] for row in subset)
            parsed = parse_opening_label_dimensions(text_value)
            if parsed is None:
                continue
            if _adjacent_exclusion_token(ordered, start=start, end=end):
                continue
            bbox = _bbox_union([row[3] for row in subset])
            if bbox is None:
                continue
            rank = (parsed.dimension_count, end - start)
            candidates.append(
                (rank, start, end, _TrustedTextLine(
                    observation_ids=tuple(row[1] for row in subset),
                    text=text_value,
                    bbox=bbox,
                ))
            )
    return _select_fragment_candidates(candidates)

def _bbox_overlap_fraction(
    first_min: float,
    first_max: float,
    second_min: float,
    second_max: float,
) -> float:
    overlap = max(0.0, min(first_max, second_max) - max(first_min, second_min))
    denominator = min(first_max - first_min, second_max - second_min)
    if denominator <= _COORD_TOL:
        return 0.0
    return overlap / denominator


def _line_stitchable(
    first: _TrustedTextLine,
    second: _TrustedTextLine,
) -> bool:
    """Return True only for source lines that are geometrically contiguous."""
    ax0, ay0, ax1, ay1 = first.bbox
    bx0, by0, bx1, by1 = second.bbox
    a_width, a_height = ax1 - ax0, ay1 - ay0
    b_width, b_height = bx1 - bx0, by1 - by0
    if min(a_width, a_height, b_width, b_height) <= _COORD_TOL:
        return False

    x_overlap = _bbox_overlap_fraction(ax0, ax1, bx0, bx1)
    y_overlap = _bbox_overlap_fraction(ay0, ay1, by0, by1)
    vertical_gap = max(0.0, max(ay0, by0) - min(ay1, by1))
    horizontal_gap = max(0.0, max(ax0, bx0) - min(ax1, bx1))

    stacked = (
        x_overlap >= 0.65
        and vertical_gap <= 0.75 * max(a_height, b_height)
    )
    side_by_side = (
        y_overlap >= 0.65
        and horizontal_gap <= 0.75 * max(a_width, b_width)
    )
    return stacked or side_by_side


def _stitched_opening_label_fragment(
    first: _TrustedTextLine,
    second: _TrustedTextLine,
) -> Optional[_TrustedTextLine]:
    """Join contiguous native lines only for one unique syntax parse."""
    if not _line_stitchable(first, second):
        return None
    bbox = _bbox_union((first.bbox, second.bbox))
    if bbox is None:
        return None

    possibilities: dict[tuple[tuple[str, ...], str], tuple[str, tuple[str, ...]]] = {}
    for left, right in ((first, second), (second, first)):
        combined = f"{left.text} {right.text}"
        parsed = parse_opening_label_dimensions(combined)
        if parsed is None:
            continue
        signature = (
            tuple(token.lower() for token in parsed.dimension_tokens),
            parsed.suffix_text.lower(),
        )
        possibilities.setdefault(
            signature,
            (combined, (*left.observation_ids, *right.observation_ids)),
        )
    if len(possibilities) != 1:
        return None
    combined, observation_ids = next(iter(possibilities.values()))
    return _TrustedTextLine(
        observation_ids=tuple(dict.fromkeys(observation_ids)),
        text=combined,
        bbox=bbox,
    )

def _prefer_richer_label_fragments(
    fragments: Sequence[_TrustedTextLine],
) -> tuple[_TrustedTextLine, ...]:
    """Suppress only strictly weaker provenance-contained syntax parses."""
    parsed_rows: list[tuple[_TrustedTextLine, ParsedOpeningLabel]] = []
    for fragment in fragments:
        parsed = parse_opening_label_dimensions(fragment.text)
        if parsed is not None:
            parsed_rows.append((fragment, parsed))

    kept: list[_TrustedTextLine] = []
    for fragment, parsed in parsed_rows:
        own_ids = set(fragment.observation_ids)
        dominated = False
        for other, other_parsed in parsed_rows:
            if other is fragment:
                continue
            other_ids = set(other.observation_ids)
            if not own_ids < other_ids:
                continue
            if other_parsed.dimension_count > parsed.dimension_count:
                dominated = True
                break
            if (
                other_parsed.dimension_count == parsed.dimension_count
                and tuple(token.lower() for token in other_parsed.dimension_tokens)
                == tuple(token.lower() for token in parsed.dimension_tokens)
                and len(other.observation_ids) > len(fragment.observation_ids)
            ):
                dominated = True
                break
        if not dominated:
            kept.append(fragment)
    return tuple(kept)

def _trusted_text_lines(
    source: SourceVisibilityProducer,
    opening: PhysicalOpeningExistenceRecord,
) -> tuple[_TrustedTextLine, ...]:
    published = source.published_snapshot_for_revision(opening.revision_id)
    if published is None or published.snapshot.snapshot_id != opening.snapshot_id:
        return ()
    integrity = source.text_integrity_authority()
    grouped: dict[
        tuple[object, ...],
        list[tuple[int, str, str, tuple[float, ...]]],
    ] = {}
    for observation_id in published.text_observation_ids:
        resolved = integrity.resolve_text(
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
            or resolved.trusted_text is None
            or resolved.receipt is None
            or str(resolved.receipt.page_id) != str(opening.page_id)
        ):
            continue
        receipt = resolved.receipt
        if receipt.block_no is not None and receipt.line_no is not None:
            key = ("native-line", int(receipt.block_no), int(receipt.line_no))
            order = int(receipt.word_no or 0)
        else:
            key = ("observation", observation_id)
            order = 0
        grouped.setdefault(key, []).append(
            (
                order,
                observation_id,
                resolved.trusted_text,
                tuple(float(value) for value in receipt.geometry),
            )
        )

    raw_lines: list[_TrustedTextLine] = []
    fragments: list[_TrustedTextLine] = []
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda item: (item[0], item[1]))
        bbox = _bbox_union([row[3] for row in ordered])
        if bbox is None:
            continue
        raw_lines.append(
            _TrustedTextLine(
                observation_ids=tuple(row[1] for row in ordered),
                text=" ".join(row[2] for row in ordered),
                bbox=bbox,
            )
        )
        fragments.extend(
            _parseable_opening_label_fragments(ordered)
        )

    # Some CAD exports wrap one callout over two immediately adjacent native
    # lines. Add only syntax-valid, geometry-contiguous two-line claims.
    for index, first in enumerate(raw_lines):
        for second in raw_lines[index + 1:]:
            stitched = _stitched_opening_label_fragment(first, second)
            if stitched is not None:
                fragments.append(stitched)

    fragments = list(
        _prefer_richer_label_fragments(fragments)
    )
    return tuple(
        sorted(
            fragments,
            key=lambda item: (
                item.bbox[1],
                item.bbox[0],
                item.bbox[3],
                item.bbox[2],
                item.observation_ids,
            ),
        )
    )


def _label_matches_gap(label: _TrustedTextLine, gap: _GapSpan) -> bool:
    x0, y0, x1, y1 = label.bbox
    center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    along = _dot(center, gap.axis)
    if along < gap.along_min - _COORD_TOL or along > gap.along_max + _COORD_TOL:
        return False

    cross = _dot(center, gap.normal)
    glyph_height = max(_COORD_TOL, min(abs(x1 - x0), abs(y1 - y0)))
    cross_allowance = max(3.0 * glyph_height, 2.0 * gap.cross_spread)
    return abs(cross - gap.cross_center) <= cross_allowance + _COORD_TOL


def _structural_kind(pattern: str) -> Optional[str]:
    if pattern == GAP_CORROBORATED_DOOR_JAMB_LEAF:
        return "door"
    if pattern == GAP_CORROBORATED_WINDOW_JAMB_PAIR:
        return "window"
    return None


_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()


class OpeningLabelDimensionProducer:
    def __init__(self, source: SourceVisibilityProducer, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "OpeningLabelDimensionProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be producer-owned")
        self._source = source
        self._physical = source.physical_opening_authority()
        self._results: dict[_Key, OpeningLabelDimensionResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source: SourceVisibilityProducer,
    ) -> "OpeningLabelDimensionProducer":
        return cls(source, _seal=_PRODUCER_SEAL)

    def publish_scope(self, selector: ObservationSelector) -> OpeningLabelDimensionResult:
        if type(selector) is not ObservationSelector:
            raise TypeError("selector must be ObservationSelector")
        physical = self._physical.prove_existence(selector)
        opening = physical.existence_record
        if (
            physical.status is not EvidenceResolutionStatus.CORROBORATED
            or physical.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
        ):
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_LABEL_DIMENSION_SOURCE_SCOPE_UNAVAILABLE,
            )

        key = (
            opening.document_id,
            opening.revision_id,
            opening.source_sha256,
            opening.snapshot_id,
            opening.record_id,
        )
        prior = self._results.get(key)
        if prior is not None:
            return prior

        visibility = self._source.authority()
        source_records: list[SourceObservationRecord] = []
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
                        OPENING_LABEL_DIMENSION_SOURCE_SCOPE_UNAVAILABLE,
                    ),
                )
            source_records.append(resolved.observation)

        gap = _gap_span(source_records)
        if gap is None:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    OPENING_LABEL_DIMENSION_GEOMETRY_UNAVAILABLE,
                ),
            )

        structural_kind = _structural_kind(opening.structural_pattern)
        candidates: dict[
            tuple[str, tuple[float, ...], Optional[str], tuple[float, float, float, float]],
            tuple[_TrustedTextLine, ParsedOpeningLabel, Optional[str]],
        ] = {}
        for line in _trusted_text_lines(self._source, opening):
            parsed = parse_opening_label_dimensions(line.text)
            if parsed is None or not _label_matches_gap(line, gap):
                continue
            suffix_kind, suffix_conflict = _semantic_kind_evidence(parsed.suffix_text)
            if suffix_conflict or (
                structural_kind is not None
                and suffix_kind is not None
                and structural_kind != suffix_kind
            ):
                return self._store(
                    key,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        OPENING_LABEL_DIMENSION_SEMANTIC_CONFLICT,
                    ),
                )
            semantic_kind = structural_kind or suffix_kind
            signature = (
                parsed.raw_text.lower(),
                parsed.dimension_values_mm,
                semantic_kind,
                tuple(round(value, 4) for value in line.bbox),
            )
            candidates.setdefault(signature, (line, parsed, semantic_kind))
        if not candidates:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE,
                ),
            )
        if len(candidates) != 1:
            return self._store(
                key,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    OPENING_LABEL_DIMENSION_AMBIGUOUS,
                ),
            )

        line, parsed, semantic_kind = next(iter(candidates.values()))
        payload = {
            "schema_version": OPENING_LABEL_DIMENSION_SCHEMA_VERSION,
            "opening_record_id": opening.record_id,
            "page_id": opening.page_id,
            "viewport_id": opening.viewport_id,
            "source_text_observation_ids": tuple(sorted(line.observation_ids)),
            "raw_text": parsed.raw_text,
            "dimension_values_mm": parsed.dimension_values_mm,
            "semantic_kind": semantic_kind,
        }
        evidence = OpeningLabelDimensionEvidence(
            evidence_id=stable_contract_id(
                "opening_label_dimension",
                payload,
                digest_chars=32,
            ),
            opening_record_id=opening.record_id,
            page_id=opening.page_id,
            viewport_id=opening.viewport_id,
            source_text_observation_ids=tuple(sorted(line.observation_ids)),
            raw_text=parsed.raw_text,
            dimension_values_mm=parsed.dimension_values_mm,
            semantic_kind=semantic_kind,
            area_m2=parsed.area_m2,
        )
        return self._store(
            key,
            OpeningLabelDimensionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(OPENING_LABEL_DIMENSION_RESOLVED,),
                evidence=evidence,
            ),
        )

    def _store(self, key: _Key, result: OpeningLabelDimensionResult) -> OpeningLabelDimensionResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("opening-label dimension producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> "OpeningLabelDimensionAuthority":
        return OpeningLabelDimensionAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )


class OpeningLabelDimensionAuthority:
    def __init__(
        self,
        results: Mapping[_Key, OpeningLabelDimensionResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningLabelDimensionAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, opening: PhysicalOpeningExistenceRecord) -> OpeningLabelDimensionResult:
        if type(opening) is not PhysicalOpeningExistenceRecord:
            raise TypeError("opening must be PhysicalOpeningExistenceRecord")
        key = (
            opening.document_id,
            opening.revision_id,
            opening.source_sha256,
            opening.snapshot_id,
            opening.record_id,
        )
        return self._results.get(
            key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_LABEL_DIMENSION_UNAVAILABLE,
            ),
        )


__all__ = [
    "OPENING_LABEL_DIMENSION_AMBIGUOUS",
    "OPENING_LABEL_DIMENSION_GEOMETRY_UNAVAILABLE",
    "OPENING_LABEL_DIMENSION_RESOLVED",
    "OPENING_LABEL_DIMENSION_SCHEMA_VERSION",
    "OPENING_LABEL_DIMENSION_SEMANTIC_CONFLICT",
    "OPENING_LABEL_DIMENSION_SOURCE_SCOPE_UNAVAILABLE",
    "OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE",
    "OPENING_LABEL_DIMENSION_UNAVAILABLE",
    "OpeningLabelDimensionAuthority",
    "OpeningLabelDimensionEvidence",
    "OpeningLabelDimensionProducer",
    "OpeningLabelDimensionResult",
    "ParsedOpeningLabel",
    "parse_opening_label_dimensions",
]
