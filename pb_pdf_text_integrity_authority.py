"""Producer-owned PDF text decoding and render-eligibility authority.

This module is deliberately upstream of semantic consumers. It answers only:
"is this producer-owned native PDF word safe to expose as trusted visible
text?" It does not decide whether text is a dimension, bind text to an
opening, or unlock any commercial quantity.

Instances of :class:`PdfTextIntegrityAuthority` are minted by the trusted
``SourceVisibilityProducer`` composition root. Ordinary callers provide only
``ObservationSelector`` values.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import (
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    ObservationSelector,
    SourceObservationAuthority,
)


PDF_TEXT_INTEGRITY_SCHEMA_VERSION = "1.2.0"
TRUSTED_PDF_TEXT = "trusted_pdf_text"
TEXT_INTEGRITY_RECEIPT_UNAVAILABLE = "text_integrity_receipt_unavailable"
TEXT_INTEGRITY_RECEIPT_MISMATCH = "text_integrity_receipt_mismatch"
TEXT_TRACE_UNAVAILABLE = "text_trace_unavailable"
TEXT_TRACE_AMBIGUOUS = "text_trace_ambiguous"
TEXT_FONT_BINDING_AMBIGUOUS = "text_font_binding_ambiguous"
TEXT_TYPE3_FONT_UNTRUSTED = "text_type3_font_untrusted"
TEXT_RENDER_MODE_UNTRUSTED = "text_render_mode_untrusted"
TEXT_OPACITY_UNTRUSTED = "text_opacity_untrusted"
TEXT_OPTIONAL_CONTENT_UNRESOLVED = "text_optional_content_unresolved"
TEXT_OPTIONAL_CONTENT_OFF = "text_optional_content_off"
TEXT_LOW_CONTRAST_DEFAULT_PAGE = "text_low_contrast_default_page"
TEXT_OCCLUDED_BY_LATER_PAINT = "text_occluded_by_later_paint"
TEXT_CLIP_STATE_UNRESOLVED = "text_clip_state_unresolved"
TEXT_CLIPPED_BY_CLIP_REGION = "text_clipped_by_clip_region"
TEXT_UNICODE_UNTRUSTED = "text_unicode_untrusted"
TEXT_DECODE_MISMATCH = "text_decode_mismatch"
TEXT_TOUNICODE_MALFORMED = "text_tounicode_malformed"
TEXT_TOUNICODE_OR_KNOWN_ENCODING_REQUIRED = "text_tounicode_or_known_encoding_required"
TEXT_STANDARD_ENCODING_NON_ASCII_UNTRUSTED = "text_standard_encoding_non_ascii_untrusted"
TEXT_GLYPH_UNICODE_MISMATCH = "text_glyph_unicode_mismatch"
TEXT_GLYPH_MAPPING_UNVERIFIED = "text_glyph_mapping_unverified"

# Imported by SourceVisibilityProducer only. This is a structural construction
# seal, consistent with the existing visibility authority pattern; it is not a
# security boundary against equal-privilege Python code.
_PDF_TEXT_AUTHORITY_SEAL = object()

_BASE14_SIMPLE_FONTS = {
    "courier",
    "courier-bold",
    "courier-oblique",
    "courier-boldoblique",
    "helvetica",
    "helvetica-bold",
    "helvetica-oblique",
    "helvetica-boldoblique",
    "times-roman",
    "times-bold",
    "times-italic",
    "times-bolditalic",
}
_KNOWN_SIMPLE_ENCODINGS = {"", "WinAnsiEncoding", "StandardEncoding", "MacRomanEncoding"}
_CMAP_ALLOWED_WORDS = {
    "begincmap",
    "endcmap",
    "def",
    "dict",
    "begin",
    "end",
    "begincodespacerange",
    "endcodespacerange",
    "beginbfchar",
    "endbfchar",
    "beginbfrange",
    "endbfrange",
    "begincidchar",
    "endcidchar",
    "begincidrange",
    "endcidrange",
    "findresource",
    "currentdict",
    "defineresource",
    "pop",
    "usecmap",
    "cmapname",
}


@dataclass(frozen=True)
class NativeTextIntegrityDecision:
    trusted: bool
    raw_text: str
    decode_status: str
    visibility_status: str
    reason_codes: tuple[str, ...]
    font_xref: Optional[int] = None
    font_subtype: str = ""
    font_name: str = ""
    sequence_number: Optional[int] = None
    trace_sequence_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class PdfTextIntegrityReceipt:
    receipt_id: str
    parent_observation_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    source_partition_id: str
    raw_text: str
    geometry: tuple[float, ...]
    trusted: bool
    decode_status: str
    visibility_status: str
    reason_codes: tuple[str, ...]
    font_xref: Optional[int] = None
    font_subtype: str = ""
    font_name: str = ""
    sequence_number: Optional[int] = None
    trace_sequence_numbers: tuple[int, ...] = ()
    block_no: Optional[int] = None
    line_no: Optional[int] = None
    word_no: Optional[int] = None
    schema_version: str = PDF_TEXT_INTEGRITY_SCHEMA_VERSION


@dataclass(frozen=True)
class PdfTextIntegrityResult:
    status: EvidenceResolutionStatus
    proposition: Optional[str]
    trusted_text: Optional[str]
    reason_codes: tuple[str, ...]
    receipt: Optional[PdfTextIntegrityReceipt] = None
    physical_opening_existence: str = PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _rect_tuple(value: Sequence[object]) -> tuple[float, float, float, float]:
    if len(value) < 4:
        raise ValueError("text geometry requires four bbox coordinates")
    out = tuple(float(value[index]) for index in range(4))
    if not all(math.isfinite(v) for v in out):
        raise ValueError("text geometry must be finite")
    return out  # type: ignore[return-value]


def _intersection_ratio(
    subject: Sequence[object], other: Sequence[object]
) -> float:
    try:
        ax0, ay0, ax1, ay1 = _rect_tuple(subject)
        bx0, by0, bx1, by1 = _rect_tuple(other)
    except (TypeError, ValueError):
        return 0.0
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    area = max(1e-9, abs(ax1 - ax0) * abs(ay1 - ay0))
    return inter / area


def _trace_text(span: Mapping[str, object]) -> str:
    chars = span.get("chars") or ()
    text: list[str] = []
    for char in chars:  # type: ignore[assignment]
        try:
            text.append(chr(int(char[0])))  # type: ignore[index]
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
    return "".join(text)


def _unicode_is_untrusted(text: str) -> bool:
    for char in str(text):
        codepoint = ord(char)
        category = unicodedata.category(char)
        if codepoint == 0xFFFD:
            return True
        if category in {"Cs", "Co"}:
            return True
        if category == "Cc" and char not in "\t\r\n":
            return True
    return False


def _normalise_font_name(value: object) -> str:
    name = str(value or "").strip().lstrip("/")
    if "+" in name:
        prefix, rest = name.split("+", 1)
        if len(prefix) == 6 and prefix.isalnum():
            name = rest
    return name.lower()


def _known_standard_simple_font(font: Sequence[object], raw_text: str) -> bool:
    if len(font) < 6:
        return False
    subtype = str(font[2] or "")
    base_font = _normalise_font_name(font[3])
    encoding = str(font[5] or "")
    if subtype != "Type1" or base_font not in _BASE14_SIMPLE_FONTS:
        return False
    if encoding not in _KNOWN_SIMPLE_ENCODINGS:
        return False
    # Without a ToUnicode map, keep the safe exception deliberately narrow:
    # printable ASCII in the standard Base14 encodings only.
    return all(0x20 <= ord(char) <= 0x7E for char in str(raw_text))


def _valid_tounicode_cmap(stream: bytes | bytearray | memoryview | None) -> bool:
    if not stream:
        return False
    try:
        text = bytes(stream).decode("latin1")
    except UnicodeDecodeError:
        return False
    lower = text.lower()
    required = (
        "begincmap",
        "endcmap",
        "/cmaptype",
        "begincodespacerange",
        "endcodespacerange",
    )
    if not all(token in lower for token in required):
        return False
    if not ("beginbfchar" in lower or "beginbfrange" in lower):
        return False

    block_specs = (
        (
            "beginbfchar",
            "endbfchar",
            r"<[0-9A-Fa-f]+>\s+<[0-9A-Fa-f]+>",
        ),
        (
            "beginbfrange",
            "endbfrange",
            r"<[0-9A-Fa-f]+>\s+<[0-9A-Fa-f]+>\s+(?:<[0-9A-Fa-f]+>|\[)",
        ),
    )
    for begin, end, mapping_pattern in block_specs:
        pattern = rf"(\d+)\s+{begin}\b(.*?){end}\b"
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            expected = int(match.group(1))
            found = len(re.findall(mapping_pattern, match.group(2)))
            if found != expected:
                return False

    # Fail closed on unknown bare CMap operators. Names, hex strings, literal
    # strings and numeric operands are removed before checking operators.
    #
    # The only stack operator admitted beyond the allow-list is ``dup``, and
    # only in the exact structural idiom ``<integer> dict dup begin`` (the
    # standard way a CMap opens its /CIDSystemInfo dictionary: allocate a
    # dictionary, duplicate the reference so it can be both opened and later
    # stored by ``def``). It is consumed here, before operator scrubbing, so a
    # ``dup`` anywhere else -- or any other stack operator such as ``exch`` --
    # still leaves an unknown operator and fails the validator.
    text = re.sub(
        r"(?<![\w/.+-])\d+\s+dict\s+dup\s+begin\b",
        "dict begin",
        text,
        flags=re.IGNORECASE,
    )
    scrubbed = re.sub(r"%[^\r\n]*", " ", text)
    scrubbed = re.sub(r"\([^)]*\)", " ", scrubbed)
    scrubbed = re.sub(r"<[0-9A-Fa-f\s]*>", " ", scrubbed)
    scrubbed = re.sub(r"/[A-Za-z0-9_.+-]+", " ", scrubbed)
    scrubbed = re.sub(r"\b\d+\b", " ", scrubbed)
    scrubbed = (
        scrubbed.replace("<<", " ")
        .replace(">>", " ")
        .replace("[", " ")
        .replace("]", " ")
    )
    operators = {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", scrubbed)
    }
    return not (operators - _CMAP_ALLOWED_WORDS)


def _font_binding(page: object, span: Mapping[str, object]) -> tuple[Optional[Sequence[object]], tuple[str, ...]]:
    try:
        fonts = page.get_fonts(full=True) or []  # type: ignore[attr-defined]
    except Exception:
        return None, (TEXT_FONT_BINDING_AMBIGUOUS,)
    target = _normalise_font_name(span.get("font"))
    matches: dict[int, Sequence[object]] = {}
    for font in fonts:
        try:
            xref = int(font[0])
            aliases = {_normalise_font_name(font[3]), _normalise_font_name(font[4])}
        except (IndexError, TypeError, ValueError):
            continue
        if target and target in aliases:
            matches[xref] = font
    if len(matches) != 1:
        return None, (TEXT_FONT_BINDING_AMBIGUOUS,)
    return next(iter(matches.values())), ()


def _font_for_glyph_validation(page: object, font: Sequence[object]):
    """Return a no-fallback font view suitable for glyph-id verification.

    ``get_texttrace()`` exposes both decoded Unicode and the actual glyph id.
    A structurally valid ToUnicode CMap is therefore insufficient by itself:
    the decoded code point must also resolve to the glyph that was rendered.
    If the font cannot be reconstructed independently, callers must fail closed.
    """

    try:
        xref = int(font[0])
    except (IndexError, TypeError, ValueError):
        return None

    try:
        extracted = page.parent.extract_font(xref)  # type: ignore[attr-defined]
        font_buffer = extracted[3] if len(extracted) >= 4 else b""
    except Exception:
        font_buffer = b""
    if font_buffer:
        try:
            return fitz.Font(fontbuffer=font_buffer)
        except Exception:
            return None

    try:
        base_font = str(font[3] or "")
    except (IndexError, TypeError):
        return None
    if _normalise_font_name(base_font) not in _BASE14_SIMPLE_FONTS:
        return None
    try:
        return fitz.Font(fontname=base_font)
    except Exception:
        return None


def _glyph_unicode_consistency_reasons(
    page: object,
    span: Mapping[str, object],
    font: Sequence[object],
) -> tuple[str, ...]:
    """Verify trace Unicode against the glyph ids actually rendered.

    PyMuPDF text traces expose each character as ``(unicode, glyph_id, ...)``.
    The glyph id is font dependent and remains independent of a malicious or
    incorrect ToUnicode remapping.  Compare it with the no-fallback glyph for
    the decoded Unicode.  Unknown mappings abstain rather than guessing.
    """

    font_view = _font_for_glyph_validation(page, font)
    if font_view is None:
        return (TEXT_GLYPH_MAPPING_UNVERIFIED,)

    chars = span.get("chars") or ()
    checked = 0
    for char in chars:  # type: ignore[assignment]
        try:
            unicode_codepoint = int(char[0])  # type: ignore[index]
            actual_glyph_id = int(char[1])  # type: ignore[index]
        except (IndexError, TypeError, ValueError):
            return (TEXT_GLYPH_MAPPING_UNVERIFIED,)

        # PyMuPDF uses -1 for continuation components of some ligatures.  The
        # leading component still carries the real glyph and is checked.
        if actual_glyph_id < 0:
            continue
        try:
            expected_glyph_id = int(
                font_view.has_glyph(unicode_codepoint, fallback=0)
            )
        except Exception:
            return (TEXT_GLYPH_MAPPING_UNVERIFIED,)
        if expected_glyph_id <= 0:
            return (TEXT_GLYPH_MAPPING_UNVERIFIED,)
        checked += 1
        if actual_glyph_id != expected_glyph_id:
            return (TEXT_GLYPH_UNICODE_MISMATCH,)

    if checked == 0:
        return (TEXT_GLYPH_MAPPING_UNVERIFIED,)
    return ()


def _decode_status(
    page: object,
    span: Mapping[str, object],
    raw_text: str,
) -> tuple[str, tuple[str, ...], Optional[int], str, str]:
    font, reasons = _font_binding(page, span)
    if font is None:
        return "unresolved", reasons, None, "", ""
    xref = int(font[0])
    subtype = str(font[2] or "")
    base_font = str(font[3] or "")
    if subtype == "Type3":
        return (
            "blocked_type3",
            (TEXT_TYPE3_FONT_UNTRUSTED,),
            xref,
            subtype,
            base_font,
        )
    try:
        kind, value = page.parent.xref_get_key(xref, "ToUnicode")  # type: ignore[attr-defined]
    except Exception:
        kind, value = "null", "null"
    if kind == "xref":
        try:
            cmap_xref = int(str(value).split()[0])
            cmap = page.parent.xref_stream(cmap_xref)  # type: ignore[attr-defined]
        except Exception:
            cmap = None
        if not _valid_tounicode_cmap(cmap):
            return (
                "malformed_tounicode",
                (TEXT_TOUNICODE_MALFORMED,),
                xref,
                subtype,
                base_font,
            )
        glyph_reasons = _glyph_unicode_consistency_reasons(page, span, font)
        if glyph_reasons:
            decode_status = (
                "tounicode_glyph_mismatch"
                if TEXT_GLYPH_UNICODE_MISMATCH in glyph_reasons
                else "tounicode_glyph_unverified"
            )
            return decode_status, glyph_reasons, xref, subtype, base_font
        return "validated_tounicode", (), xref, subtype, base_font
    if _known_standard_simple_font(font, raw_text):
        return "known_standard_encoding", (), xref, subtype, base_font
    if len(font) >= 6 and str(font[2] or "") == "Type1" and _normalise_font_name(font[3]) in _BASE14_SIMPLE_FONTS:
        return (
            "standard_encoding_non_ascii_untrusted",
            (TEXT_STANDARD_ENCODING_NON_ASCII_UNTRUSTED,),
            xref,
            subtype,
            base_font,
        )
    return (
        "unresolved_encoding",
        (TEXT_TOUNICODE_OR_KNOWN_ENCODING_REQUIRED,),
        xref,
        subtype,
        base_font,
    )


_PAGE_CACHE_ATTR = "_pb_text_integrity_page_cache"


def _page_cache(page: object) -> dict:
    """Per-page memo of read-only PDF state (never shared across pages)."""
    cache = getattr(page, _PAGE_CACHE_ATTR, None)
    if cache is None:
        cache = {}
        try:
            setattr(page, _PAGE_CACHE_ATTR, cache)
        except Exception:
            return {}
    return cache


def _texttrace_spans(page: object) -> Optional[list]:
    cache = _page_cache(page)
    if "texttrace" not in cache:
        try:
            cache["texttrace"] = list(page.get_texttrace() or [])  # type: ignore[attr-defined]
        except Exception:
            cache["texttrace"] = None
    return cache["texttrace"]


def _span_seqno(span: Mapping[str, object]) -> Optional[int]:
    try:
        return int(span.get("seqno"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _trace_chars(span: Mapping[str, object]) -> list[tuple[str, tuple[float, float, float, float]]]:
    out: list[tuple[str, tuple[float, float, float, float]]] = []
    for char in span.get("chars") or ():  # type: ignore[assignment]
        try:
            glyph_text = chr(int(char[0]))  # type: ignore[index]
            char_bbox = _rect_tuple(char[3])  # type: ignore[index]
        except (IndexError, TypeError, ValueError, OverflowError):
            return []
        out.append((glyph_text, char_bbox))
    return out


def _owned_span_chain(
    spans: Sequence[Mapping[str, object]],
    raw_text: str,
    bbox: Sequence[object],
) -> tuple[Optional[tuple[Mapping[str, object], ...]], tuple[str, ...]]:
    """Prove that a native word is one contiguous character run across spans.

    Used only when no single trace span contains the word (the producer split
    it across text-showing operations, or a word begins/ends mid-span).
    Ownership is a structural proof, not a geometric preference:

    * the word's characters are a contiguous run of trace characters drawn by
      spans with consecutive sequence numbers, so nothing else was painted
      between them;
    * the run's text is exactly the word, and every matched character's own
      box lies inside the word's box (the string match is tied to geometry);
    * exactly one such run exists in the whole trace, and no other trace
      character substantially overlaps the word box (otherwise the word could
      be a blend of separate paints).

    Anything else abstains; the nearest or best-overlapping span is never
    chosen. Every span contributing a character is returned so that each one
    is verified independently.
    """

    involved = [
        span
        for span in spans
        if isinstance(span, Mapping)
        and _span_seqno(span) is not None
        and _intersection_ratio(bbox, span.get("bbox") or ()) > 0.0
    ]
    involved.sort(key=lambda span: _span_seqno(span))  # type: ignore[arg-type]

    runs: list[list[Mapping[str, object]]] = []
    for span in involved:
        if runs and _span_seqno(span) == _span_seqno(runs[-1][-1]) + 1:  # type: ignore[operator]
            runs[-1].append(span)
        else:
            runs.append([span])

    hits: list[tuple[Mapping[str, object], ...]] = []
    matched_char_ids: set[tuple[int, int]] = set()
    for run in runs:
        flat: list[tuple[str, tuple[float, float, float, float], int, int]] = []
        for span_index, span in enumerate(run):
            chars = _trace_chars(span)
            for char_index, (glyph_text, char_bbox) in enumerate(chars):
                flat.append((glyph_text, char_bbox, span_index, char_index))
        text = "".join(item[0] for item in flat)
        width = len(raw_text)
        position = text.find(raw_text)
        while position != -1 and width:
            window = flat[position : position + width]
            if all(_intersection_ratio(item[1], bbox) >= 0.99 for item in window):
                ordered_indices = sorted({item[2] for item in window})
                hits.append(tuple(run[index] for index in ordered_indices))
                for item in window:
                    matched_char_ids.add((id(run[item[2]]), item[3]))
            position = text.find(raw_text, position + 1)
    if not hits:
        return None, (TEXT_TRACE_UNAVAILABLE,)
    if len(hits) > 1:
        return None, (TEXT_TRACE_AMBIGUOUS,)

    for span in spans:
        if not isinstance(span, Mapping):
            continue
        for char_index, (_glyph, char_bbox) in enumerate(_trace_chars(span)):
            if (id(span), char_index) in matched_char_ids:
                continue
            if _intersection_ratio(char_bbox, bbox) >= 0.5:
                return None, (TEXT_TRACE_AMBIGUOUS,)
    return hits[0], ()


def _matching_trace_spans(
    page: object,
    word: Mapping[str, object],
) -> tuple[tuple[Mapping[str, object], ...], str, tuple[str, ...]]:
    raw_text = str(word.get("text") or "")
    bbox = word.get("bbox") or ()
    spans = _texttrace_spans(page)
    if spans is None:
        return (), "", (TEXT_TRACE_UNAVAILABLE,)
    candidates: list[tuple[Mapping[str, object], str]] = []
    for span in spans:
        if not isinstance(span, Mapping):
            continue
        text = _trace_text(span)
        overlap = _intersection_ratio(bbox, span.get("bbox") or ())
        if overlap <= 0.0 or raw_text not in text:
            continue
        candidates.append((span, text))
    if len(candidates) == 1:
        return (candidates[0][0],), candidates[0][1], ()
    if len(candidates) > 1:
        # Multiple source trace spans can each explain the same native word.
        # Do not rank by overlap, exact-text bonus, geometry, sequence number,
        # or any other preference: ownership is ambiguous unless unique.
        return (), "", (TEXT_TRACE_AMBIGUOUS,)

    chain, reasons = _owned_span_chain(spans, raw_text, bbox)
    if chain is None:
        return (), "", reasons
    return chain, "".join(_trace_text(span) for span in chain), ()


def _near_white(span: Mapping[str, object]) -> bool:
    color = span.get("color")
    if not isinstance(color, (tuple, list)) or not color:
        return False
    try:
        values = [float(value) for value in color]
    except (TypeError, ValueError):
        return False
    return bool(values) and min(values) >= 0.97


# ---------------------------------------------------------------------------
# Per-text clip ownership
# ---------------------------------------------------------------------------
#
# The former rule vetoed every text on any page containing a ``W`` operator.
# Extended drawings expose the clip stack (each clip's exact ``scissor`` and
# nesting ``level``) and every painted path's ``seqno``/``level``; text spans
# share the same sequence counter. That is enough to prove, for a given text,
# which clips *may* apply and which *must* apply -- but only where the PDF's
# own structure proves it:
#
# * the clips that may be active at a text are those on the stack at the path
#   painted immediately before it, those on the stack at the path painted
#   immediately after it, and any clip pushed between those two paths;
# * when both neighbours sit at the same level with no clip pushed between
#   them the stack is provably unchanged, so the text's active clips are
#   exactly that stack;
# * a text is proven unclipped only if EVERY clip that may apply is an exact
#   axis-aligned rectangle that contains the text. A clip that does not
#   contain the text, but is only possibly active, is unresolved (not assumed
#   inactive); one that is provably active and does not contain it clips the
#   text; a non-rectangular clip is never treated as its bounding box.
#
# Anything the model cannot reconcile (level bookkeeping mismatch, rotated
# pages, clips reported without extended drawings) fails closed.

_CLIP_TOLERANCE_PT = 0.5


@dataclass(frozen=True)
class _ClipRecord:
    scissor: tuple[float, float, float, float]
    exact_rectangle: bool


@dataclass(frozen=True)
class _ClipModel:
    consistent: bool
    clips: tuple[_ClipRecord, ...]
    # (seqno, level, clip ids on the stack, position in the extended-drawing list)
    paths: tuple[tuple[int, int, tuple[int, ...], int], ...]
    # (position in the extended-drawing list, clip id)
    pushes: tuple[tuple[int, int], ...]


def _points_are_axis_aligned_rectangle(points: Sequence[tuple[float, float]]) -> bool:
    unique = {(round(x, 4), round(y, 4)) for x, y in points}
    if len(unique) != 4:
        return False
    xs = {x for x, _y in unique}
    ys = {y for _x, y in unique}
    return len(xs) == 2 and len(ys) == 2


def _clip_is_exact_rectangle(entry: Mapping[str, object], scissor: fitz.Rect) -> bool:
    items = entry.get("items") or []
    if not items or scissor.is_empty:
        return False
    if len(items) == 1:
        item = items[0]
        kind = item[0]
        if kind == "re":
            return True
        if kind == "qu":
            quad = item[1]
            try:
                corners = [quad.ul, quad.ur, quad.lr, quad.ll]
                area = 0.0
                for index in range(4):
                    x0, y0 = corners[index]
                    x1, y1 = corners[(index + 1) % 4]
                    area += x0 * y1 - x1 * y0
                area = abs(area) / 2.0
            except Exception:
                return False
            return abs(area - scissor.width * scissor.height) <= 1e-6 * max(1.0, area)
        return False
    if len(items) == 4 and all(item[0] == "l" for item in items):
        points: list[tuple[float, float]] = []
        for item in items:
            for point in (item[1], item[2]):
                points.append((float(point.x), float(point.y)))
        for item in items:
            p0, p1 = item[1], item[2]
            if abs(float(p0.x) - float(p1.x)) > 1e-4 and abs(float(p0.y) - float(p1.y)) > 1e-4:
                return False
        return _points_are_axis_aligned_rectangle(points)
    return False


def _build_clip_model(page: object) -> Optional[_ClipModel]:
    try:
        drawings = page.get_drawings(extended=True) or []  # type: ignore[attr-defined]
    except Exception:
        return None
    clips: list[_ClipRecord] = []
    pushes: list[tuple[int, int]] = []
    paths: list[tuple[int, int, tuple[int, ...], int]] = []
    stack: list[int] = []
    consistent = True
    for position, entry in enumerate(drawings):
        kind = entry.get("type")
        if kind == "clip":
            try:
                level = int(entry.get("level"))
                scissor = fitz.Rect(entry.get("scissor"))
            except (TypeError, ValueError):
                consistent = False
                continue
            if level < 0 or level > len(stack):
                consistent = False
                continue
            del stack[level:]
            clip_id = len(clips)
            clips.append(
                _ClipRecord(
                    scissor=(float(scissor.x0), float(scissor.y0), float(scissor.x1), float(scissor.y1)),
                    exact_rectangle=_clip_is_exact_rectangle(entry, scissor),
                )
            )
            stack.append(clip_id)
            pushes.append((position, clip_id))
            continue
        seqno = entry.get("seqno")
        if seqno is None:
            continue
        try:
            level = int(entry.get("level"))
            seq = int(seqno)
        except (TypeError, ValueError):
            consistent = False
            continue
        # Pops are not reported as entries: a painted path's ``level`` is the
        # authoritative number of clips active at that path, so a lower level
        # than the tracked stack means the innermost clips were popped. A
        # higher level would mean an unreported push and cannot be reconciled.
        if level > len(stack):
            consistent = False
        else:
            del stack[level:]
        paths.append((seq, level, tuple(stack), position))
    paths.sort(key=lambda item: item[0])
    return _ClipModel(
        consistent=consistent,
        clips=tuple(clips),
        paths=tuple(paths),
        pushes=tuple(pushes),
    )


def _clip_model(page: object) -> Optional[_ClipModel]:
    cache = _page_cache(page)
    if "clip_model" not in cache:
        cache["clip_model"] = _build_clip_model(page)
    return cache["clip_model"]


def _page_content_has_clip_operator(page: object) -> Optional[bool]:
    try:
        content = bytes(page.read_contents() or b"")  # type: ignore[attr-defined]
    except Exception:
        return None
    return re.search(rb"(?<!\S)W\*?(?!\S)", content) is not None


def _rect_contains(
    outer: Sequence[float], inner: Sequence[float], tolerance: float = _CLIP_TOLERANCE_PT
) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _text_clip_reasons(
    page: object,
    subject_bbox: Sequence[object],
    seqno: Optional[int],
) -> tuple[str, ...]:
    model = _clip_model(page)
    has_clip_operator = _page_content_has_clip_operator(page)
    if model is None or has_clip_operator is None:
        return (TEXT_CLIP_STATE_UNRESOLVED,)
    if not model.clips:
        # No clip reported by the extended device. A clip operator in the page
        # content that the device did not surface is unexplained: fail closed.
        return (TEXT_CLIP_STATE_UNRESOLVED,) if has_clip_operator else ()
    if not model.consistent or seqno is None:
        return (TEXT_CLIP_STATE_UNRESOLVED,)
    try:
        if int(getattr(page, "rotation", 0) or 0) != 0:
            return (TEXT_CLIP_STATE_UNRESOLVED,)
        bbox = _rect_tuple(subject_bbox)
    except (TypeError, ValueError):
        return (TEXT_CLIP_STATE_UNRESOLVED,)

    before = None
    after = None
    for path in model.paths:
        if path[0] < seqno:
            before = path
        elif path[0] > seqno:
            after = path
            break
    lo_position = before[3] if before is not None else -1
    hi_position = after[3] if after is not None else None
    stack_before = set(before[2]) if before is not None else set()
    stack_after = set(after[2]) if after is not None else None
    between = {
        clip_id
        for position, clip_id in model.pushes
        if position > lo_position and (hi_position is None or position < hi_position)
    }

    if before is not None and after is not None and not between and before[1] == after[1]:
        if before[2] != after[2]:
            return (TEXT_CLIP_STATE_UNRESOLVED,)
        may_apply = set(before[2])
        must_apply = set(before[2])
    else:
        may_apply = stack_before | between | (stack_after or set())
        must_apply = (stack_before & stack_after) if stack_after is not None else set()

    reasons: list[str] = []
    for clip_id in sorted(may_apply):
        clip = model.clips[clip_id]
        contained = _rect_contains(clip.scissor, bbox)
        if contained and clip.exact_rectangle:
            continue
        if not contained and clip_id in must_apply:
            reasons.append(TEXT_CLIPPED_BY_CLIP_REGION)
        else:
            reasons.append(TEXT_CLIP_STATE_UNRESOLVED)
    return _ordered_unique(reasons)


# ---------------------------------------------------------------------------
# Optional content (layer) visibility
# ---------------------------------------------------------------------------
#
# A trace span's ``layer`` is only a name. Positive authority needs proof that
# the optional-content group is ON in the default viewing configuration:
# a registered OCG, resolved BaseState/ON/OFF arrays and no /AS auto-state.
# (PyMuPDF's ``get_ocgs()['on']`` is deliberately NOT used as a cross-check: it
# ignores /OFF and BaseState, so it is a name/intent source only. MuPDF's own
# behaviour is the independent reading -- text in a hidden layer never reaches
# ``get_texttrace()`` at all.) Because
# the marked-content ancestry of a given text is not recovered, the proof is
# also required for every optional-content object the page can reference: an
# OFF (or unresolvable) group anywhere on the page could be an ancestor, so
# none of the page's layered text is vouched for in that case.

_OC_MAX_DEPTH = 8
_REF_PATTERN = re.compile(r"(\d+)\s+\d+\s+R")


def _extract_value(obj_text: str, key: str) -> Optional[str]:
    """Return the raw value following ``/key`` in a PDF dictionary text."""
    match = re.search(rf"/{re.escape(key)}(?![A-Za-z0-9_.+-])\s*", obj_text)
    if match is None:
        return None
    rest = obj_text[match.end():]
    if rest.startswith("<<"):
        depth = 0
        index = 0
        while index < len(rest) - 1:
            pair = rest[index : index + 2]
            if pair == "<<":
                depth += 1
                index += 2
                continue
            if pair == ">>":
                depth -= 1
                index += 2
                if depth == 0:
                    return rest[:index]
                continue
            index += 1
        return None
    if rest.startswith("["):
        end = rest.find("]")
        return rest[: end + 1] if end >= 0 else None
    ref = re.match(r"\d+\s+\d+\s+R", rest)
    if ref:
        return ref.group(0)
    name = re.match(r"/[^\s/<>\[\]()]+", rest)
    if name:
        return name.group(0)
    return None


def _resolve_dict_text(doc: object, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    ref = re.fullmatch(r"(\d+)\s+\d+\s+R", value.strip())
    if ref:
        try:
            return str(doc.xref_object(int(ref.group(1)), compressed=False))  # type: ignore[attr-defined]
        except Exception:
            return None
    return value


def _refs_in(text: Optional[str]) -> list[int]:
    return [int(m.group(1)) for m in _REF_PATTERN.finditer(text or "")]


@dataclass(frozen=True)
class _OcgConfig:
    resolvable: bool
    base_state: str
    on_xrefs: frozenset[int]
    off_xrefs: frozenset[int]
    has_auto_state: bool
    names: Mapping[int, str]
    intents: Mapping[int, tuple[str, ...]]

    def is_on(self, xref: int) -> Optional[bool]:
        if not self.resolvable or self.has_auto_state:
            return None
        if xref not in self.names:
            return None
        if self.intents.get(xref):
            return None
        if self.base_state == "ON":
            state = xref not in self.off_xrefs
        elif self.base_state == "OFF":
            state = xref in self.on_xrefs
        else:
            return None
        return state


def _load_ocg_config(doc: object) -> _OcgConfig:
    unresolved = _OcgConfig(False, "", frozenset(), frozenset(), False, {}, {})
    try:
        catalog = doc.xref_object(doc.pdf_catalog(), compressed=False)  # type: ignore[attr-defined]
    except Exception:
        return unresolved
    props = _resolve_dict_text(doc, _extract_value(catalog, "OCProperties"))
    if props is None:
        return unresolved
    default = _resolve_dict_text(doc, _extract_value(props, "D"))
    if default is None:
        return unresolved
    base_match = re.search(r"/BaseState\s*/(\w+)", default)
    base_state = base_match.group(1).upper() if base_match else "ON"
    on_xrefs = frozenset(_refs_in(_extract_value(default, "ON")))
    off_xrefs = frozenset(_refs_in(_extract_value(default, "OFF")))
    has_auto_state = re.search(r"/AS(?![A-Za-z0-9_.+-])", default) is not None
    registered = set(_refs_in(_extract_value(props, "OCGs")))
    try:
        reader = doc.get_ocgs() or {}  # type: ignore[attr-defined]
    except Exception:
        return unresolved
    names: dict[int, str] = {}
    intents: dict[int, tuple[str, ...]] = {}
    for xref, info in reader.items():
        if int(xref) not in registered:
            continue
        names[int(xref)] = str(info.get("name", ""))
        intents[int(xref)] = tuple(str(v) for v in (info.get("intent") or ()))
    return _OcgConfig(
        resolvable=True,
        base_state=base_state,
        on_xrefs=on_xrefs,
        off_xrefs=off_xrefs,
        has_auto_state=has_auto_state,
        names=names,
        intents=intents,
    )


def _doc_cache(doc: object) -> dict:
    cache = getattr(doc, "_pb_text_integrity_doc_cache", None)
    if cache is None:
        cache = {}
        try:
            setattr(doc, "_pb_text_integrity_doc_cache", cache)
        except Exception:
            return {}
    return cache


def _ocg_config(doc: object) -> _OcgConfig:
    cache = _doc_cache(doc)
    if "ocg_config" not in cache:
        cache["ocg_config"] = _load_ocg_config(doc)
    return cache["ocg_config"]


def _walk_resources(
    doc: object,
    resources_text: Optional[str],
    found: set[int],
    problems: list[str],
    visited: set[int],
    depth: int,
) -> None:
    if resources_text is None:
        return
    if depth > _OC_MAX_DEPTH:
        problems.append("depth")
        return
    properties = _resolve_dict_text(doc, _extract_value(resources_text, "Properties"))
    if properties is not None:
        if "<<" in properties[2:]:
            problems.append("inline_property")
        for ref in _refs_in(properties):
            found.add(ref)
    xobjects = _resolve_dict_text(doc, _extract_value(resources_text, "XObject"))
    if xobjects is None:
        return
    for xref in _refs_in(xobjects):
        if xref in visited:
            continue
        visited.add(xref)
        try:
            obj = str(doc.xref_object(xref, compressed=False))  # type: ignore[attr-defined]
        except Exception:
            problems.append("xobject")
            continue
        oc_value = _extract_value(obj, "OC")
        if oc_value is not None:
            found.update(_refs_in(oc_value))
        if re.search(r"/Subtype\s*/Form\b", obj):
            _walk_resources(
                doc,
                _resolve_dict_text(doc, _extract_value(obj, "Resources")),
                found,
                problems,
                visited,
                depth + 1,
            )


def _page_resources_text(doc: object, page: object) -> Optional[str]:
    try:
        xref = int(page.xref)  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return None
    for _hop in range(_OC_MAX_DEPTH):
        try:
            obj = str(doc.xref_object(xref, compressed=False))  # type: ignore[attr-defined]
        except Exception:
            return None
        value = _extract_value(obj, "Resources")
        if value is not None:
            return _resolve_dict_text(doc, value)
        refs = _refs_in(_extract_value(obj, "Parent"))
        if not refs:
            return None
        xref = refs[0]
    return None


def _page_optional_content_objects(page: object) -> tuple[frozenset[int], bool]:
    """Every optional-content object the page can reference, and a problem flag."""
    doc = page.parent  # type: ignore[attr-defined]
    cache = _page_cache(page)
    if "oc_objects" in cache:
        return cache["oc_objects"]
    found: set[int] = set()
    problems: list[str] = []
    resources = _page_resources_text(doc, page)
    if resources is None:
        problems.append("resources")
    else:
        _walk_resources(doc, resources, found, problems, set(), 0)
    result = (frozenset(found), bool(problems))
    cache["oc_objects"] = result
    return result


def _optional_content_reasons(page: object, span: Mapping[str, object]) -> tuple[str, ...]:
    layer = str(span.get("layer") or "")
    if not layer.strip():
        return ()
    try:
        doc = page.parent  # type: ignore[attr-defined]
        config = _ocg_config(doc)
        page_objects, problem = _page_optional_content_objects(page)
    except Exception:
        return (TEXT_OPTIONAL_CONTENT_UNRESOLVED,)
    if not config.resolvable or problem:
        return (TEXT_OPTIONAL_CONTENT_UNRESOLVED,)

    named = [xref for xref, name in config.names.items() if name == layer]
    if not named:
        named = [xref for xref, name in config.names.items() if name.strip() == layer.strip()]
    if not named:
        return (TEXT_OPTIONAL_CONTENT_UNRESOLVED,)
    states = [config.is_on(xref) for xref in named]
    if any(state is None for state in states):
        return (TEXT_OPTIONAL_CONTENT_UNRESOLVED,)
    if all(state is False for state in states):
        return (TEXT_OPTIONAL_CONTENT_OFF,)
    if not all(states):
        return (TEXT_OPTIONAL_CONTENT_UNRESOLVED,)

    for xref in page_objects:
        if config.is_on(xref) is not True:
            # OFF, unregistered, an OCMD, or otherwise unresolvable: it may be
            # an ancestor of this text's marked content, so it is not proven.
            return (TEXT_OPTIONAL_CONTENT_UNRESOLVED,)
    return ()


def _cached_bboxlog(page: object) -> list:
    cache = _page_cache(page)
    if "bboxlog" not in cache:
        cache["bboxlog"] = list(page.get_bboxlog() or [])  # type: ignore[attr-defined]
    return cache["bboxlog"]


def _visibility_status(
    page: object,
    subject_bbox: Sequence[object],
    span: Mapping[str, object],
) -> tuple[str, tuple[str, ...], Optional[int]]:
    reasons: list[str] = []
    try:
        render_mode = int(span.get("type", 0) or 0)
    except (TypeError, ValueError):
        render_mode = 99
    if render_mode > 1:
        reasons.append(TEXT_RENDER_MODE_UNTRUSTED)
    try:
        opacity = float(span.get("opacity", 1.0))
    except (TypeError, ValueError):
        opacity = 0.0
    if not math.isfinite(opacity) or opacity < 0.95:
        reasons.append(TEXT_OPACITY_UNTRUSTED)
    reasons.extend(_optional_content_reasons(page, span))
    if _near_white(span):
        reasons.append(TEXT_LOW_CONTRAST_DEFAULT_PAGE)

    try:
        seqno = int(span.get("seqno"))
    except (TypeError, ValueError):
        seqno = None
    reasons.extend(_text_clip_reasons(page, span.get("bbox") or subject_bbox, seqno))
    try:
        bboxlog = _cached_bboxlog(page)
    except Exception:
        bboxlog = []
        reasons.append(TEXT_TRACE_UNAVAILABLE)
    if seqno is None or not (0 <= seqno < len(bboxlog)):
        reasons.append(TEXT_TRACE_UNAVAILABLE)
    else:
        current_kind = str(bboxlog[seqno][0])
        if current_kind == "ignore-text":
            reasons.append(TEXT_RENDER_MODE_UNTRUSTED)
        elif current_kind not in {"fill-text", "stroke-text"}:
            reasons.append(TEXT_TRACE_UNAVAILABLE)
        for item in bboxlog[seqno + 1 :]:
            try:
                paint_kind, paint_bbox = str(item[0]), item[1]
            except (IndexError, TypeError):
                continue
            if paint_kind not in {"fill-path", "fill-image", "fill-shade", "fill-text"}:
                continue
            if _intersection_ratio(subject_bbox, paint_bbox) >= 0.65:
                reasons.append(TEXT_OCCLUDED_BY_LATER_PAINT)
                break

    unique = _ordered_unique(reasons)
    return ("proven_visible" if not unique else "unresolved_or_blocked"), unique, seqno


def classify_native_word_integrity(
    page: object,
    word: Mapping[str, object],
) -> NativeTextIntegrityDecision:
    """Classify one raw native word using producer-owned PDF state.

    The classifier is intentionally conservative. Unknown font binding,
    clipping, optional-content state, suspicious Unicode, or later paint all
    block positive text authority rather than being guessed through. A word
    split across consecutive whole trace spans is trusted only if every owned
    span independently passes every check.
    """

    raw_text = str(word.get("text") or "")
    reasons: list[str] = []
    spans, trace_text, trace_reasons = _matching_trace_spans(page, word)
    reasons.extend(trace_reasons)
    if not spans:
        return NativeTextIntegrityDecision(
            trusted=False,
            raw_text=raw_text,
            decode_status="unresolved",
            visibility_status="unresolved_or_blocked",
            reason_codes=_ordered_unique(reasons or (TEXT_TRACE_UNAVAILABLE,)),
        )

    if _unicode_is_untrusted(raw_text) or _unicode_is_untrusted(trace_text):
        reasons.append(TEXT_UNICODE_UNTRUSTED)
    if raw_text not in trace_text:
        reasons.append(TEXT_DECODE_MISMATCH)

    chain = len(spans) > 1
    word_bbox = word.get("bbox") or ()
    first_decode = ""
    blocked_decode: Optional[str] = None
    font_xref: Optional[int] = None
    font_subtype = ""
    font_name = ""
    visibility_status = "proven_visible"
    sequence_numbers: list[int] = []
    first_seqno: Optional[int] = None
    for index, span in enumerate(spans):
        span_text = _trace_text(span) if chain else raw_text
        span_decode, decode_reasons, xref, subtype, base_font = _decode_status(page, span, span_text)
        reasons.extend(decode_reasons)
        subject = (span.get("bbox") or word_bbox) if chain else word_bbox
        _span_visibility, visibility_reasons, seqno = _visibility_status(page, subject, span)
        reasons.extend(visibility_reasons)
        if index == 0:
            first_decode, font_xref, font_subtype, font_name = span_decode, xref, subtype, base_font
            first_seqno = seqno
        if decode_reasons and blocked_decode is None:
            blocked_decode = span_decode
        if visibility_reasons:
            visibility_status = "unresolved_or_blocked"
        if seqno is not None:
            sequence_numbers.append(seqno)
    decode_status = blocked_decode or first_decode
    unique = _ordered_unique(reasons)
    return NativeTextIntegrityDecision(
        trusted=not unique,
        raw_text=raw_text,
        decode_status=decode_status,
        visibility_status=visibility_status,
        reason_codes=unique,
        font_xref=font_xref,
        font_subtype=font_subtype,
        font_name=font_name,
        sequence_number=first_seqno,
        trace_sequence_numbers=tuple(sequence_numbers) if chain else (),
    )


def build_pdf_text_integrity_receipt(
    *,
    parent_observation_id: str,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    page_id: str,
    source_partition_id: str,
    geometry: Sequence[object],
    decision: NativeTextIntegrityDecision,
    block_no: Optional[int] = None,
    line_no: Optional[int] = None,
    word_no: Optional[int] = None,
) -> PdfTextIntegrityReceipt:
    bbox = _rect_tuple(geometry)
    payload = {
        "parent_observation_id": parent_observation_id,
        "document_id": document_id,
        "revision_id": revision_id,
        "source_sha256": source_sha256,
        "page_id": page_id,
        "source_partition_id": source_partition_id,
        "raw_text": decision.raw_text,
        "geometry": bbox,
        "trusted": decision.trusted,
        "decode_status": decision.decode_status,
        "visibility_status": decision.visibility_status,
        "reason_codes": decision.reason_codes,
        "font_xref": decision.font_xref,
        "font_subtype": decision.font_subtype,
        "font_name": decision.font_name,
        "sequence_number": decision.sequence_number,
        "trace_sequence_numbers": tuple(decision.trace_sequence_numbers),
        "block_no": None if block_no is None else int(block_no),
        "line_no": None if line_no is None else int(line_no),
        "word_no": None if word_no is None else int(word_no),
    }
    receipt_id = stable_contract_id("pdf_text_integrity", payload, digest_chars=32)
    return PdfTextIntegrityReceipt(receipt_id=receipt_id, **payload)


class PdfTextIntegrityAuthority:
    """Read-only trusted-text resolver minted by SourceVisibilityProducer."""

    def __init__(
        self,
        source_authority: SourceObservationAuthority,
        receipts: Mapping[tuple[str, str], PdfTextIntegrityReceipt],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PDF_TEXT_AUTHORITY_SEAL:
            raise TypeError(
                "PdfTextIntegrityAuthority must be obtained from "
                "SourceVisibilityProducer.text_integrity_authority()"
            )
        self._source_authority = source_authority
        self._receipts = receipts

    def resolve_text(self, selector: ObservationSelector) -> PdfTextIntegrityResult:
        receipt = self._receipts.get((selector.snapshot_id, selector.observation_id))
        if receipt is None:
            return PdfTextIntegrityResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                trusted_text=None,
                reason_codes=(TEXT_INTEGRITY_RECEIPT_UNAVAILABLE,),
            )

        source_result = self._source_authority.resolve(selector)
        observation = source_result.observation
        if observation is None or source_result.status != EvidenceResolutionStatus.CORROBORATED:
            return PdfTextIntegrityResult(
                status=source_result.status,
                proposition=None,
                trusted_text=None,
                reason_codes=tuple(source_result.reason_codes),
                receipt=receipt,
            )

        if (
            observation.observation_kind != "native_pdf_word"
            or observation.origin_kind != "native"
            or observation.viewport_id is not None
            or observation.observation_id != receipt.parent_observation_id
            or observation.document_id != receipt.document_id
            or observation.revision_id != receipt.revision_id
            or observation.source_sha256 != receipt.source_sha256
            or observation.page_id != receipt.page_id
            or observation.source_partition_id != receipt.source_partition_id
            or observation.raw_text != receipt.raw_text
            or tuple(observation.geometry) != tuple(receipt.geometry)
        ):
            return PdfTextIntegrityResult(
                status=EvidenceResolutionStatus.CONFLICT,
                proposition=None,
                trusted_text=None,
                reason_codes=(TEXT_INTEGRITY_RECEIPT_MISMATCH,),
                receipt=receipt,
            )

        if not receipt.trusted:
            return PdfTextIntegrityResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                trusted_text=None,
                reason_codes=receipt.reason_codes,
                receipt=receipt,
            )

        return PdfTextIntegrityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=TRUSTED_PDF_TEXT,
            trusted_text=receipt.raw_text,
            reason_codes=("producer_owned_pdf_text_integrity_resolved",),
            receipt=receipt,
        )


__all__ = [
    "PDF_TEXT_INTEGRITY_SCHEMA_VERSION",
    "TRUSTED_PDF_TEXT",
    "TEXT_CLIPPED_BY_CLIP_REGION",
    "TEXT_CLIP_STATE_UNRESOLVED",
    "TEXT_DECODE_MISMATCH",
    "TEXT_FONT_BINDING_AMBIGUOUS",
    "TEXT_GLYPH_MAPPING_UNVERIFIED",
    "TEXT_GLYPH_UNICODE_MISMATCH",
    "TEXT_INTEGRITY_RECEIPT_MISMATCH",
    "TEXT_INTEGRITY_RECEIPT_UNAVAILABLE",
    "TEXT_LOW_CONTRAST_DEFAULT_PAGE",
    "TEXT_OCCLUDED_BY_LATER_PAINT",
    "TEXT_OPACITY_UNTRUSTED",
    "TEXT_OPTIONAL_CONTENT_OFF",
    "TEXT_OPTIONAL_CONTENT_UNRESOLVED",
    "TEXT_RENDER_MODE_UNTRUSTED",
    "TEXT_STANDARD_ENCODING_NON_ASCII_UNTRUSTED",
    "TEXT_TOUNICODE_MALFORMED",
    "TEXT_TOUNICODE_OR_KNOWN_ENCODING_REQUIRED",
    "TEXT_TRACE_AMBIGUOUS",
    "TEXT_TRACE_UNAVAILABLE",
    "TEXT_TYPE3_FONT_UNTRUSTED",
    "TEXT_UNICODE_UNTRUSTED",
    "NativeTextIntegrityDecision",
    "PdfTextIntegrityAuthority",
    "PdfTextIntegrityReceipt",
    "PdfTextIntegrityResult",
    "build_pdf_text_integrity_receipt",
    "classify_native_word_integrity",
]
