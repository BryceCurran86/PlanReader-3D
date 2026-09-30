"""Shadow-only source-content proof of rectangular text clip ownership.

This module handles the narrow case where PyMuPDF's extended drawing device
does not surface a clipping path that is nevertheless explicit in the PDF
content stream.

The shadow never trusts text. It proves only that one raw text-show operation
is owned by one exact rectangular clipping region and whether that rectangle
contains the native word bbox. Raw text bytes are never decoded or matched.

Binding is fail-closed:
* source bytes must match the producer-owned revision SHA-256;
* the target native word must have a unique trace span or an exact structural
  fill/stroke trace pair;
* every raw text-show operation on the page must map one-to-one, in source
  order, to the logical texttrace groups by render mode;
* the target raw operation must have exactly one active, source-owned,
  axis-aligned rectangular clip;
* non-identity CTM changes, non-rectangular clips, malformed q/Q state,
  XObject invocation, inline images, or operation/trace count mismatch
  abstain.

No live authority consumes this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_fill_stroke_equivalence_shadow import (
    FILL_STROKE_SHADOW_VISIBILITY_BLOCKED,
    classify_fill_stroke_text_pair_shadow,
)
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_TRACE_AMBIGUOUS,
    _matching_trace_spans,
    _rect_contains,
)
from pb_source_observation_authority import (
    OBSERVATION_UNAVAILABLE,
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    ObservationSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


PDF_TEXT_SOURCE_CLIP_OWNERSHIP_SHADOW_SCHEMA_VERSION = "1.0.0"
PDF_TEXT_SOURCE_RECTANGULAR_CLIP_CONTAINS_WORD = (
    "pdf_text_source_rectangular_clip_contains_word"
)
PDF_TEXT_SOURCE_RECTANGULAR_CLIP_EXCLUDES_WORD = (
    "pdf_text_source_rectangular_clip_excludes_word"
)

SOURCE_CLIP_SHADOW_RESOLVED_CONTAINS = (
    "source_text_clip_shadow_resolved_contains"
)
SOURCE_CLIP_SHADOW_RESOLVED_EXCLUDES = (
    "source_text_clip_shadow_resolved_excludes"
)
SOURCE_CLIP_SHADOW_NOT_APPLICABLE = (
    "source_text_clip_shadow_not_applicable"
)
SOURCE_CLIP_SHADOW_PAGE_UNAVAILABLE = (
    "source_text_clip_shadow_page_unavailable"
)
SOURCE_CLIP_SHADOW_CONTENT_UNSUPPORTED = (
    "source_text_clip_shadow_content_unsupported"
)
SOURCE_CLIP_SHADOW_TRACE_OPERATION_MISMATCH = (
    "source_text_clip_shadow_trace_operation_mismatch"
)
SOURCE_CLIP_SHADOW_TARGET_TRACE_UNRESOLVED = (
    "source_text_clip_shadow_target_trace_unresolved"
)
SOURCE_CLIP_SHADOW_ACTIVE_CLIP_UNRESOLVED = (
    "source_text_clip_shadow_active_clip_unresolved"
)

_ORIGIN_TOLERANCE_PT = 0.02

# PDF content operators relevant to ordinary page streams. Unknown operators
# fail the lexical operation parser rather than being guessed.
_OPERATORS = frozenset(
    {
        "q", "Q", "cm",
        "w", "J", "j", "M", "d", "ri", "i", "gs",
        "m", "l", "c", "v", "y", "h", "re",
        "S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n",
        "W", "W*",
        "BT", "ET", "Tc", "Tw", "Tz", "TL", "Tf", "Tr", "Ts",
        "Td", "TD", "Tm", "T*", "Tj", "TJ", "'", '"',
        "d0", "d1",
        "CS", "cs", "SC", "SCN", "sc", "scn",
        "G", "g", "RG", "rg", "K", "k", "sh",
        "Do", "BI", "ID", "EI",
        "MP", "DP", "BMC", "BDC", "EMC", "BX", "EX",
    }
)
_SHOW_OPERATORS = frozenset({"Tj", "TJ", "'", '"'})
_PATH_BUILDERS = frozenset({"m", "l", "c", "v", "y", "h", "re"})
_PATH_ENDERS = frozenset(
    {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"}
)
_WHITESPACE = b"\x00\x09\x0a\x0c\x0d\x20"
_DELIMITERS = b"()<>[]{}/%"


@dataclass(frozen=True)
class _LexToken:
    kind: str
    value: object
    start: int
    end: int


@dataclass(frozen=True)
class _Operation:
    name: str
    operands: tuple[_LexToken, ...]
    start: int
    end: int


@dataclass(frozen=True)
class _RawTextShow:
    ordinal: int
    render_mode: int
    clip_rect_pdf: Optional[tuple[float, float, float, float]]
    clip_known: bool
    active_clip_count: int
    operation_start: int


@dataclass(frozen=True)
class _TraceGroup:
    sequence_numbers: tuple[int, ...]
    render_modes: tuple[int, ...]
    first_origin: tuple[float, float]


@dataclass(frozen=True)
class SourceContentTextClipShadowResult:
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    reason_codes: tuple[str, ...]
    proof_id: Optional[str]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    observation_id: str
    raw_text: str
    bbox: tuple[float, float, float, float]
    sequence_numbers: tuple[int, ...] = ()
    raw_text_show_ordinal: Optional[int] = None
    render_mode: Optional[int] = None
    clip_rect_pdf: Optional[tuple[float, float, float, float]] = None
    clip_rect_page: Optional[tuple[float, float, float, float]] = None
    live_text_reason_codes: tuple[str, ...] = ()
    schema_version: str = PDF_TEXT_SOURCE_CLIP_OWNERSHIP_SHADOW_SCHEMA_VERSION


def _skip_ws_comments(data: bytes, index: int) -> int:
    size = len(data)
    while index < size:
        if data[index] in _WHITESPACE:
            index += 1
            continue
        if data[index] == ord("%"):
            index += 1
            while index < size and data[index] not in (10, 13):
                index += 1
            continue
        break
    return index


def _scan_literal_string(data: bytes, index: int) -> Optional[int]:
    depth = 1
    cursor = index + 1
    size = len(data)
    while cursor < size:
        char = data[cursor]
        if char == ord("\\"):
            cursor += 1
            if cursor >= size:
                return None
            if data[cursor] == 13 and cursor + 1 < size and data[cursor + 1] == 10:
                cursor += 2
            else:
                cursor += 1
            continue
        if char == ord("("):
            depth += 1
        elif char == ord(")"):
            depth -= 1
            if depth == 0:
                return cursor + 1
        cursor += 1
    return None


def _scan_hex_string(data: bytes, index: int) -> Optional[int]:
    cursor = index + 1
    while cursor < len(data):
        if data[cursor] == ord(">"):
            return cursor + 1
        cursor += 1
    return None


def _scan_name(data: bytes, index: int) -> int:
    cursor = index + 1
    while (
        cursor < len(data)
        and data[cursor] not in _WHITESPACE
        and data[cursor] not in _DELIMITERS
    ):
        cursor += 1
    return cursor


def _scan_composite(
    data: bytes,
    index: int,
    *,
    array: bool,
) -> Optional[int]:
    opener = ord("[") if array else None
    closer = ord("]") if array else None
    cursor = index + (1 if array else 2)
    depth = 1
    while cursor < len(data):
        cursor = _skip_ws_comments(data, cursor)
        if cursor >= len(data):
            return None
        if data[cursor] == ord("("):
            end = _scan_literal_string(data, cursor)
            if end is None:
                return None
            cursor = end
            continue
        if data[cursor] == ord("<") and (
            cursor + 1 >= len(data) or data[cursor + 1] != ord("<")
        ):
            end = _scan_hex_string(data, cursor)
            if end is None:
                return None
            cursor = end
            continue
        if array:
            if data[cursor] == opener:
                depth += 1
                cursor += 1
                continue
            if data[cursor] == closer:
                depth -= 1
                cursor += 1
                if depth == 0:
                    return cursor
                continue
        else:
            if data[cursor:cursor + 2] == b"<<":
                depth += 1
                cursor += 2
                continue
            if data[cursor:cursor + 2] == b">>":
                depth -= 1
                cursor += 2
                if depth == 0:
                    return cursor
                continue
        cursor += 1
    return None


def _lex_content(data: bytes) -> Optional[tuple[_LexToken, ...]]:
    tokens: list[_LexToken] = []
    index = 0
    size = len(data)
    while True:
        index = _skip_ws_comments(data, index)
        if index >= size:
            break
        start = index
        char = data[index]
        if char == ord("("):
            end = _scan_literal_string(data, index)
            if end is None:
                return None
            tokens.append(_LexToken("object", data[index:end], start, end))
            index = end
            continue
        if char == ord("["):
            end = _scan_composite(data, index, array=True)
            if end is None:
                return None
            tokens.append(_LexToken("object", data[index:end], start, end))
            index = end
            continue
        if data[index:index + 2] == b"<<":
            end = _scan_composite(data, index, array=False)
            if end is None:
                return None
            tokens.append(_LexToken("object", data[index:end], start, end))
            index = end
            continue
        if char == ord("<"):
            end = _scan_hex_string(data, index)
            if end is None:
                return None
            tokens.append(_LexToken("object", data[index:end], start, end))
            index = end
            continue
        if char == ord("/"):
            end = _scan_name(data, index)
            tokens.append(
                _LexToken(
                    "object",
                    data[index:end].decode("latin1"),
                    start,
                    end,
                )
            )
            index = end
            continue
        if char in (ord("]"), ord(">")):
            return None

        cursor = index
        while (
            cursor < size
            and data[cursor] not in _WHITESPACE
            and data[cursor] not in _DELIMITERS
        ):
            cursor += 1
        if cursor == index:
            return None
        raw = data[index:cursor]
        text = raw.decode("latin1")
        try:
            value = float(text)
        except ValueError:
            tokens.append(_LexToken("word", text, start, cursor))
        else:
            if not math.isfinite(value):
                return None
            tokens.append(_LexToken("number", value, start, cursor))
        index = cursor
    return tuple(tokens)


def _operations(data: bytes) -> Optional[tuple[_Operation, ...]]:
    tokens = _lex_content(data)
    if tokens is None:
        return None
    operands: list[_LexToken] = []
    operations: list[_Operation] = []
    for token in tokens:
        if token.kind != "word":
            operands.append(token)
            continue
        name = str(token.value)
        if name not in _OPERATORS:
            return None
        if name in {"BI", "ID", "EI"}:
            return None
        start = operands[0].start if operands else token.start
        operations.append(
            _Operation(
                name=name,
                operands=tuple(operands),
                start=start,
                end=token.end,
            )
        )
        operands.clear()
    if operands:
        return None
    return tuple(operations)


def _numbers(operation: _Operation, count: int) -> Optional[tuple[float, ...]]:
    if len(operation.operands) != count:
        return None
    values: list[float] = []
    for token in operation.operands:
        if token.kind != "number":
            return None
        values.append(float(token.value))
    return tuple(values)


def _normalise_rect(
    x: float,
    y: float,
    width: float,
    height: float,
) -> Optional[tuple[float, float, float, float]]:
    if not all(math.isfinite(v) for v in (x, y, width, height)):
        return None
    x2 = x + width
    y2 = y + height
    x0, x1 = sorted((x, x2))
    y0, y1 = sorted((y, y2))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _intersect_rects(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> Optional[tuple[float, float, float, float]]:
    x0 = max(first[0], second[0])
    y0 = max(first[1], second[1])
    x1 = min(first[2], second[2])
    y1 = min(first[3], second[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


@dataclass
class _GraphicsState:
    clip_rect: Optional[tuple[float, float, float, float]] = None
    clip_count: int = 0
    clip_known: bool = True
    ctm_identity: bool = True

    def clone(self) -> "_GraphicsState":
        return _GraphicsState(
            clip_rect=self.clip_rect,
            clip_count=self.clip_count,
            clip_known=self.clip_known,
            ctm_identity=self.ctm_identity,
        )


def _raw_text_shows(data: bytes) -> Optional[tuple[_RawTextShow, ...]]:
    operations = _operations(data)
    if operations is None:
        return None

    graphics = _GraphicsState()
    stack: list[_GraphicsState] = []
    path_rect: Optional[tuple[float, float, float, float]] = None
    path_exact = True
    pending_clip = False
    pending_clip_exact = False
    render_mode = 0
    in_text = False
    shows: list[_RawTextShow] = []

    def clear_path_and_commit() -> None:
        nonlocal path_rect, path_exact, pending_clip, pending_clip_exact
        if pending_clip:
            if (
                not pending_clip_exact
                or path_rect is None
                or not graphics.ctm_identity
            ):
                graphics.clip_known = False
            elif graphics.clip_known:
                if graphics.clip_rect is None:
                    graphics.clip_rect = path_rect
                else:
                    intersected = _intersect_rects(
                        graphics.clip_rect,
                        path_rect,
                    )
                    if intersected is None:
                        graphics.clip_known = False
                    else:
                        graphics.clip_rect = intersected
                graphics.clip_count += 1
        path_rect = None
        path_exact = True
        pending_clip = False
        pending_clip_exact = False

    for operation in operations:
        name = operation.name

        if name == "q":
            if operation.operands:
                return None
            stack.append(graphics.clone())
            continue
        if name == "Q":
            if operation.operands or not stack:
                return None
            graphics = stack.pop()
            path_rect = None
            path_exact = True
            pending_clip = False
            pending_clip_exact = False
            continue
        if name == "cm":
            values = _numbers(operation, 6)
            if values is None:
                return None
            if any(
                abs(value - expected) > 1e-12
                for value, expected in zip(
                    values,
                    (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                )
            ):
                graphics.ctm_identity = False
            continue
        if name == "Do":
            return None

        if name in _PATH_BUILDERS:
            if name == "re":
                values = _numbers(operation, 4)
                rect = None if values is None else _normalise_rect(*values)
                if (
                    rect is None
                    or path_rect is not None
                    or not path_exact
                ):
                    path_exact = False
                    path_rect = None
                else:
                    path_rect = rect
            else:
                path_exact = False
                path_rect = None
            continue
        if name in {"W", "W*"}:
            if operation.operands:
                return None
            pending_clip = True
            pending_clip_exact = path_exact and path_rect is not None
            continue
        if name in _PATH_ENDERS:
            clear_path_and_commit()
            continue

        if name == "BT":
            if operation.operands or in_text:
                return None
            in_text = True
            continue
        if name == "ET":
            if operation.operands or not in_text:
                return None
            in_text = False
            continue
        if name == "Tr":
            values = _numbers(operation, 1)
            if values is None or not float(values[0]).is_integer():
                return None
            render_mode = int(values[0])
            if render_mode not in (0, 1, 2):
                return None
            continue
        if name in _SHOW_OPERATORS:
            if not in_text:
                return None
            shows.append(
                _RawTextShow(
                    ordinal=len(shows),
                    render_mode=render_mode,
                    clip_rect_pdf=graphics.clip_rect,
                    clip_known=(
                        graphics.clip_known
                        and graphics.ctm_identity
                    ),
                    active_clip_count=graphics.clip_count,
                    operation_start=operation.start,
                )
            )
            continue

    if stack or in_text or pending_clip:
        return None
    return tuple(shows)


def _point_tuple(value: object) -> Optional[tuple[float, float]]:
    try:
        if hasattr(value, "x") and hasattr(value, "y"):
            x = float(value.x)  # type: ignore[attr-defined]
            y = float(value.y)  # type: ignore[attr-defined]
        else:
            x = float(value[0])  # type: ignore[index]
            y = float(value[1])  # type: ignore[index]
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x, y


def _span_signature(span: Mapping[str, object]) -> Optional[tuple[object, ...]]:
    try:
        bbox = tuple(round(float(v), 9) for v in span.get("bbox") or ())
        chars = tuple(span.get("chars") or ())
        font = str(span.get("font") or "")
        size = round(float(span.get("size")), 9)
        opacity = round(float(span.get("opacity", 1.0)), 9)
        layer = str(span.get("layer") or "")
    except (TypeError, ValueError):
        return None
    if len(bbox) != 4 or not chars:
        return None
    char_rows = []
    for char in chars:
        try:
            origin = _point_tuple(char[2])
            cbbox = tuple(round(float(v), 9) for v in char[3])
            row = (
                int(char[0]),
                int(char[1]),
                origin,
                cbbox,
            )
        except (TypeError, ValueError, IndexError):
            return None
        if origin is None or len(cbbox) != 4:
            return None
        char_rows.append(row)
    return bbox, tuple(char_rows), font, size, opacity, layer


def _trace_groups(page: object) -> Optional[tuple[_TraceGroup, ...]]:
    try:
        spans = [
            span
            for span in (page.get_texttrace() or ())  # type: ignore[attr-defined]
            if isinstance(span, Mapping)
        ]
    except Exception:
        return None
    try:
        spans.sort(key=lambda span: int(span.get("seqno")))
    except (TypeError, ValueError):
        return None

    groups: list[_TraceGroup] = []
    index = 0
    while index < len(spans):
        first = spans[index]
        try:
            first_seq = int(first.get("seqno"))
            first_mode = int(first.get("type"))
        except (TypeError, ValueError):
            return None
        if first_mode not in (0, 1):
            return None
        first_chars = tuple(first.get("chars") or ())
        if not first_chars:
            return None
        first_origin = _point_tuple(first_chars[0][2])
        if first_origin is None:
            return None

        if (
            first_mode == 0
            and index + 1 < len(spans)
        ):
            second = spans[index + 1]
            try:
                second_seq = int(second.get("seqno"))
                second_mode = int(second.get("type"))
            except (TypeError, ValueError):
                return None
            if (
                second_seq == first_seq + 1
                and second_mode == 1
                and _span_signature(first) is not None
                and _span_signature(first) == _span_signature(second)
            ):
                groups.append(
                    _TraceGroup(
                        sequence_numbers=(first_seq, second_seq),
                        render_modes=(0, 1),
                        first_origin=first_origin,
                    )
                )
                index += 2
                continue

        groups.append(
            _TraceGroup(
                sequence_numbers=(first_seq,),
                render_modes=(first_mode,),
                first_origin=first_origin,
            )
        )
        index += 1
    return tuple(groups)


def _bind_operations_to_traces(
    page: object,
) -> Optional[tuple[tuple[_RawTextShow, _TraceGroup], ...]]:
    try:
        content = bytes(page.read_contents() or b"")  # type: ignore[attr-defined]
    except Exception:
        return None
    shows = _raw_text_shows(content)
    groups = _trace_groups(page)
    if shows is None or groups is None or len(shows) != len(groups):
        return None

    bound: list[tuple[_RawTextShow, _TraceGroup]] = []
    for show, group in zip(shows, groups):
        expected = (
            (0,)
            if show.render_mode == 0
            else (1,)
            if show.render_mode == 1
            else (0, 1)
        )
        if group.render_modes != expected:
            return None
        bound.append((show, group))
    return tuple(bound)


def _target_sequence_numbers(
    page: object,
    word: Mapping[str, object],
) -> tuple[int, ...]:
    pair = classify_fill_stroke_text_pair_shadow(page, word)
    if (
        len(pair.sequence_numbers) == 2
        and (
            pair.equivalent
            or FILL_STROKE_SHADOW_VISIBILITY_BLOCKED
            in pair.reason_codes
        )
    ):
        return pair.sequence_numbers

    spans, _text, reasons = _matching_trace_spans(page, word)
    if reasons or len(spans) != 1:
        return ()
    try:
        return (int(spans[0].get("seqno")),)
    except (TypeError, ValueError):
        return ()


def _page_rect_from_pdf_rect(
    page: object,
    rect: tuple[float, float, float, float],
) -> Optional[tuple[float, float, float, float]]:
    try:
        matrix = page.transformation_matrix  # type: ignore[attr-defined]
        points = [
            fitz.Point(rect[0], rect[1]) * matrix,
            fitz.Point(rect[2], rect[1]) * matrix,
            fitz.Point(rect[2], rect[3]) * matrix,
            fitz.Point(rect[0], rect[3]) * matrix,
        ]
    except Exception:
        return None
    xs = [float(point.x) for point in points]
    ys = [float(point.y) for point in points]
    if not all(math.isfinite(v) for v in (*xs, *ys)):
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_tuple(value: Sequence[object]) -> tuple[float, float, float, float]:
    if len(value) < 4:
        raise ValueError("bbox requires four coordinates")
    result = tuple(float(value[index]) for index in range(4))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("bbox must be finite")
    return result  # type: ignore[return-value]


def _blocked(
    *,
    selector: ObservationSelector,
    published,
    status: EvidenceResolutionStatus,
    reason_codes: Sequence[str],
    receipt=None,
) -> SourceContentTextClipShadowResult:
    revision = getattr(published, "revision", None)
    return SourceContentTextClipShadowResult(
        status=status,
        proposition=None,
        reason_codes=tuple(dict.fromkeys(str(code) for code in reason_codes)),
        proof_id=None,
        document_id=(
            str(selector.document_id)
            if revision is None
            else str(revision.document_id)
        ),
        revision_id=str(selector.revision_id),
        source_sha256=str(selector.source_sha256),
        snapshot_id=str(selector.snapshot_id),
        page_id=(
            ""
            if receipt is None
            else str(getattr(receipt, "page_id", "") or "")
        ),
        observation_id=str(selector.observation_id),
        raw_text=(
            ""
            if receipt is None
            else str(getattr(receipt, "raw_text", "") or "")
        ),
        bbox=(
            (0.0, 0.0, 0.0, 0.0)
            if receipt is None
            else _bbox_tuple(getattr(receipt, "geometry", ()))
        ),
        live_text_reason_codes=(
            ()
            if receipt is None
            else tuple(getattr(receipt, "reason_codes", ()) or ())
        ),
    )


def resolve_source_content_text_clip_shadow(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    selector: ObservationSelector,
    source_bytes: bytes,
) -> SourceContentTextClipShadowResult:
    """Resolve one native word's exact source-content rectangular clip."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be producer-owned "
            "SourceVisibilityProducer"
        )
    if type(selector) is not ObservationSelector:
        raise TypeError("selector must be ObservationSelector")
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be immutable bytes")

    published = source_visibility_producer.published_snapshot_for_revision(
        selector.revision_id
    )
    if published is None:
        return _blocked(
            selector=selector,
            published=None,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(OBSERVATION_UNAVAILABLE,),
        )
    if (
        selector.document_id != published.revision.document_id
        or selector.revision_id != published.revision.revision_id
        or selector.source_sha256 != published.revision.source_sha256
        or selector.snapshot_id != published.snapshot.snapshot_id
    ):
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SNAPSHOT_MISMATCH,),
        )
    if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(SOURCE_HASH_MISMATCH,),
        )

    live = source_visibility_producer.text_integrity_authority().resolve_text(
        selector
    )
    receipt = live.receipt
    if receipt is None:
        return _blocked(
            selector=selector,
            published=published,
            status=live.status,
            reason_codes=live.reason_codes or (OBSERVATION_UNAVAILABLE,),
        )
    if TEXT_CLIP_STATE_UNRESOLVED not in tuple(live.reason_codes):
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_CLIP_SHADOW_NOT_APPLICABLE,),
            receipt=receipt,
        )

    try:
        page_index = int(receipt.page_id) - 1
    except (TypeError, ValueError):
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_CLIP_SHADOW_PAGE_UNAVAILABLE,),
            receipt=receipt,
        )

    try:
        pdf = fitz.open(stream=source_bytes, filetype="pdf")
    except Exception:
        return _blocked(
            selector=selector,
            published=published,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_CLIP_SHADOW_PAGE_UNAVAILABLE,),
            receipt=receipt,
        )

    try:
        if page_index < 0 or page_index >= int(pdf.page_count):
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_CLIP_SHADOW_PAGE_UNAVAILABLE,),
                receipt=receipt,
            )
        page = pdf.load_page(page_index)
        word = {
            "text": receipt.raw_text,
            "bbox": tuple(receipt.geometry),
        }
        target_sequences = _target_sequence_numbers(page, word)
        if not target_sequences:
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_CLIP_SHADOW_TARGET_TRACE_UNRESOLVED,),
                receipt=receipt,
            )
        bindings = _bind_operations_to_traces(page)
        if bindings is None:
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_CLIP_SHADOW_TRACE_OPERATION_MISMATCH,),
                receipt=receipt,
            )
        matches = [
            (show, group)
            for show, group in bindings
            if group.sequence_numbers == target_sequences
        ]
        if len(matches) != 1:
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_CLIP_SHADOW_TRACE_OPERATION_MISMATCH,),
                receipt=receipt,
            )
        show, group = matches[0]
        if (
            not show.clip_known
            or show.clip_rect_pdf is None
            or show.active_clip_count != 1
        ):
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_CLIP_SHADOW_ACTIVE_CLIP_UNRESOLVED,),
                receipt=receipt,
            )
        clip_page = _page_rect_from_pdf_rect(page, show.clip_rect_pdf)
        if clip_page is None:
            return _blocked(
                selector=selector,
                published=published,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_CLIP_SHADOW_ACTIVE_CLIP_UNRESOLVED,),
                receipt=receipt,
            )
        bbox = _bbox_tuple(receipt.geometry)
        contains = _rect_contains(clip_page, bbox)
    finally:
        pdf.close()

    proposition = (
        PDF_TEXT_SOURCE_RECTANGULAR_CLIP_CONTAINS_WORD
        if contains
        else PDF_TEXT_SOURCE_RECTANGULAR_CLIP_EXCLUDES_WORD
    )
    reason = (
        SOURCE_CLIP_SHADOW_RESOLVED_CONTAINS
        if contains
        else SOURCE_CLIP_SHADOW_RESOLVED_EXCLUDES
    )
    payload = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": receipt.page_id,
        "observation_id": selector.observation_id,
        "bbox": bbox,
        "sequence_numbers": group.sequence_numbers,
        "raw_text_show_ordinal": show.ordinal,
        "render_mode": show.render_mode,
        "clip_rect_pdf": show.clip_rect_pdf,
        "clip_rect_page": clip_page,
        "proposition": proposition,
    }
    proof_id = stable_contract_id(
        "pdf_text_source_clip_ownership_shadow_v1",
        payload,
        digest_chars=32,
    )
    return SourceContentTextClipShadowResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=proposition,
        reason_codes=(reason,),
        proof_id=proof_id,
        document_id=str(published.revision.document_id),
        revision_id=str(published.revision.revision_id),
        source_sha256=str(published.revision.source_sha256),
        snapshot_id=str(published.snapshot.snapshot_id),
        page_id=str(receipt.page_id),
        observation_id=str(selector.observation_id),
        raw_text=str(receipt.raw_text),
        bbox=bbox,
        sequence_numbers=group.sequence_numbers,
        raw_text_show_ordinal=show.ordinal,
        render_mode=show.render_mode,
        clip_rect_pdf=show.clip_rect_pdf,
        clip_rect_page=clip_page,
        live_text_reason_codes=tuple(live.reason_codes),
    )


__all__ = [
    "PDF_TEXT_SOURCE_CLIP_OWNERSHIP_SHADOW_SCHEMA_VERSION",
    "PDF_TEXT_SOURCE_RECTANGULAR_CLIP_CONTAINS_WORD",
    "PDF_TEXT_SOURCE_RECTANGULAR_CLIP_EXCLUDES_WORD",
    "SOURCE_CLIP_SHADOW_RESOLVED_CONTAINS",
    "SOURCE_CLIP_SHADOW_RESOLVED_EXCLUDES",
    "SOURCE_CLIP_SHADOW_NOT_APPLICABLE",
    "SOURCE_CLIP_SHADOW_PAGE_UNAVAILABLE",
    "SOURCE_CLIP_SHADOW_CONTENT_UNSUPPORTED",
    "SOURCE_CLIP_SHADOW_TRACE_OPERATION_MISMATCH",
    "SOURCE_CLIP_SHADOW_TARGET_TRACE_UNRESOLVED",
    "SOURCE_CLIP_SHADOW_ACTIVE_CLIP_UNRESOLVED",
    "SourceContentTextClipShadowResult",
    "resolve_source_content_text_clip_shadow",
]
