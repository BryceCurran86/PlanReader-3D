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


PDF_TEXT_INTEGRITY_SCHEMA_VERSION = "1.1.0"
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
TEXT_LOW_CONTRAST_DEFAULT_PAGE = "text_low_contrast_default_page"
TEXT_OCCLUDED_BY_LATER_PAINT = "text_occluded_by_later_paint"
TEXT_CLIP_STATE_UNRESOLVED = "text_clip_state_unresolved"
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


def _matching_trace_span(
    page: object,
    word: Mapping[str, object],
) -> tuple[Optional[Mapping[str, object]], str, tuple[str, ...]]:
    raw_text = str(word.get("text") or "")
    bbox = word.get("bbox") or ()
    try:
        spans = page.get_texttrace() or []  # type: ignore[attr-defined]
    except Exception:
        return None, "", (TEXT_TRACE_UNAVAILABLE,)
    candidates: list[tuple[float, Mapping[str, object], str]] = []
    for span in spans:
        if not isinstance(span, Mapping):
            continue
        text = _trace_text(span)
        overlap = _intersection_ratio(bbox, span.get("bbox") or ())
        if overlap <= 0.0 or raw_text not in text:
            continue
        exact_bonus = 1.0 if text.strip() == raw_text else 0.0
        candidates.append((overlap + exact_bonus, span, text))
    if not candidates:
        return None, "", (TEXT_TRACE_UNAVAILABLE,)
    candidates.sort(key=lambda item: -item[0])
    best = candidates[0]
    if len(candidates) > 1 and abs(candidates[1][0] - best[0]) <= 1e-9:
        return None, "", (TEXT_TRACE_AMBIGUOUS,)
    return best[1], best[2], ()


def _near_white(span: Mapping[str, object]) -> bool:
    color = span.get("color")
    if not isinstance(color, (tuple, list)) or not color:
        return False
    try:
        values = [float(value) for value in color]
    except (TypeError, ValueError):
        return False
    return bool(values) and min(values) >= 0.97


def _page_has_unresolved_clip(page: object) -> bool:
    try:
        content = bytes(page.read_contents() or b"")  # type: ignore[attr-defined]
    except Exception:
        return True
    # Current producer has no per-text clipping receipt. If a text-containing
    # page uses clipping operators at all, stay conservative until that link is
    # independently proven.
    return re.search(rb"(?<!\S)W\*?(?!\S)", content) is not None


def _visibility_status(
    page: object,
    word: Mapping[str, object],
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
    if str(span.get("layer") or "").strip():
        reasons.append(TEXT_OPTIONAL_CONTENT_UNRESOLVED)
    if _near_white(span):
        reasons.append(TEXT_LOW_CONTRAST_DEFAULT_PAGE)
    if _page_has_unresolved_clip(page):
        reasons.append(TEXT_CLIP_STATE_UNRESOLVED)

    try:
        seqno = int(span.get("seqno"))
    except (TypeError, ValueError):
        seqno = None
    try:
        bboxlog = page.get_bboxlog() or []  # type: ignore[attr-defined]
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
        word_bbox = word.get("bbox") or ()
        for item in bboxlog[seqno + 1 :]:
            try:
                paint_kind, paint_bbox = str(item[0]), item[1]
            except (IndexError, TypeError):
                continue
            if paint_kind not in {"fill-path", "fill-image", "fill-shade", "fill-text"}:
                continue
            if _intersection_ratio(word_bbox, paint_bbox) >= 0.65:
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
    block positive text authority rather than being guessed through.
    """

    raw_text = str(word.get("text") or "")
    reasons: list[str] = []
    span, trace_text, trace_reasons = _matching_trace_span(page, word)
    reasons.extend(trace_reasons)
    if span is None:
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

    decode_status, decode_reasons, font_xref, font_subtype, font_name = _decode_status(
        page, span, raw_text
    )
    reasons.extend(decode_reasons)
    visibility_status, visibility_reasons, seqno = _visibility_status(page, word, span)
    reasons.extend(visibility_reasons)
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
        sequence_number=seqno,
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
