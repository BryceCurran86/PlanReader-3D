"""Original-byte native font/glyph and clip authority census (read-only).

This module intentionally does not create a text-integrity receipt, glyph
authority, material definition, source occurrence, floor or customer quantity.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from math import isfinite

import fitz

from pb_pdf_text_integrity_authority import (
    _clip_model,
    _font_binding,
    _font_for_glyph_validation,
    _matching_trace_spans,
    _text_clip_reasons,
    classify_native_word_integrity,
)


def _bbox(value):
    try:
        box = tuple(float(x) for x in value)
    except (ValueError, TypeError):
        return None
    return box if len(box) == 4 and all(isfinite(v) for v in box) and (
        box[0] < box[2] and box[1] < box[3]
    ) else None


def _point_owned(point, box):
    try:
        x, y = float(point[0]), float(point[1])
    except (TypeError, ValueError, IndexError):
        return False
    return (
        isfinite(x) and isfinite(y)
        and box[0] - 0.001 <= x <= box[2] + 0.001
        and box[1] - 0.001 <= y <= box[3] + 0.001
    )


def _glyph_runs(spans, raw_text, bbox, page):
    """Keep all original exact source runs and no-fallback mapped glyph results."""
    runs = []
    for span in spans:
        chars = span.get("chars") or ()
        for offset in range(len(chars) - len(raw_text) + 1):
            candidate = chars[offset:offset + len(raw_text)]
            if any(
                type(char[0]) is not int or char[0] < 0 or char[0] > 0x10FFFF
                for char in candidate
            ):
                continue
            if "".join(chr(char[0]) for char in candidate) != raw_text:
                continue
            if not all(_point_owned(char[2], bbox) for char in candidate):
                continue
            font, reasons = _font_binding(page, span)
            font_view = _font_for_glyph_validation(page, font) if font else None
            mapped = []
            for char in candidate:
                actual_id = int(char[1])
                expected_id = None
                if font_view is not None and actual_id >= 0:
                    try:
                        expected_id = int(font_view.has_glyph(char[0], fallback=0))
                    except Exception:
                        expected_id = None
                mapped.append({
                    "unicode": char[0],
                    "trace_glyph_id": actual_id,
                    "font_expected_glyph_id": expected_id,
                    "independent_font_mapping_proven": (
                        expected_id is not None and expected_id > 0
                        and expected_id == actual_id
                    ),
                })
            xref = int(font[0]) if font is not None else None
            tounicode = None
            extracted = {"present": False, "extension": None, "bytes_count": 0}
            if xref is not None:
                try:
                    key, value = page.parent.xref_get_key(xref, "ToUnicode")
                    tounicode = {"kind": str(key), "value": str(value)}
                except Exception:
                    tounicode = {"kind": "unavailable", "value": ""}
                try:
                    font_data = page.parent.extract_font(xref)
                    blob = font_data[3] if len(font_data) > 3 else b""
                    extracted = {
                        "present": bool(blob),
                        "extension": str(font_data[1]) if len(font_data) > 1 else None,
                        "bytes_count": len(blob),
                    }
                except Exception:
                    pass
            runs.append({
                "sequence_number": span.get("seqno"),
                "font_name": str(span.get("font") or ""),
                "font_xref": xref,
                "font_subtype": str(font[2]) if font is not None else None,
                "font_encoding": str(font[5]) if font is not None and len(font) > 5 else None,
                "font_binding_reasons": list(reasons),
                "embedded_font": extracted,
                "tounicode": tounicode,
                "no_fallback_font_view_available": font_view is not None,
                "glyph_results": mapped,
                "all_glyph_ids_independently_verified": (
                    bool(mapped) and all(g["independent_font_mapping_proven"] for g in mapped)
                ),
            })
    return runs


def inspect_native_text_gates(
    source_bytes: bytes, *, expected_sha256: str, page_number: int, code: str,
) -> dict:
    """Return original source observations only; never promote words or quantities."""
    if type(source_bytes) is not bytes:
        raise TypeError("original source must be bytes")
    digest = sha256(source_bytes).hexdigest()
    if type(expected_sha256) is not str or digest != expected_sha256:
        raise ValueError("source SHA mismatch")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("canonical positive original page required")
    if type(code) is not str or not code or code.strip() != code:
        raise ValueError("exact original code required")

    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        if page_number > len(document):
            raise ValueError("source page out of bounds")
        page = document[page_number - 1]
        source_words = defaultdict(list)
        for item in page.get_text("words", flags=fitz.TEXTFLAGS_WORDS):
            box = _bbox(item[:4])
            if box is None or len(item) < 8:
                continue
            source_words[int(item[5])].append({
                "text": str(item[4]),
                "bbox": box,
                "source_address": [int(item[5]), int(item[6]), int(item[7])],
            })
        blocks = []
        for block_no, words in sorted(source_words.items()):
            if not any(w["text"] == code for w in words):
                continue
            details = []
            for w in sorted(words, key=lambda x: x["source_address"]):
                native_word = {"text": w["text"], "bbox": w["bbox"]}
                decision = classify_native_word_integrity(page, native_word)
                spans, _trace_text, trace_reasons = _matching_trace_spans(
                    page, native_word
                )
                clip = []
                for span in spans:
                    seq = span.get("seqno")
                    if type(seq) is int:
                        clip.extend(_text_clip_reasons(
                            page, w["bbox"], seq, native_word=native_word,
                        ))
                details.append({
                    **w,
                    "original_classifier_trusted": decision.trusted,
                    "original_decode_status": decision.decode_status,
                    "original_visibility_status": decision.visibility_status,
                    "original_decision_reasons": list(decision.reason_codes),
                    "matching_texttrace_span_count": len(spans),
                    "trace_match_reasons": list(trace_reasons),
                    "glyph_runs": _glyph_runs(spans, w["text"], w["bbox"], page),
                    "clip_reasons": sorted(set(clip)),
                    "font_or_clip_promotion_allowed": False,
                })
            blocks.append({"block_no": block_no, "source_words": details})
        model = _clip_model(page)
        clip = (
            {"model_available": False, "consistent": False,
             "clip_records": None, "path_records": None}
            if model is None
            else {"model_available": True,
                  "consistent": bool(model.consistent),
                  "clip_records": len(model.clips),
                  "path_records": len(model.paths)}
        )
    return {
        "source_sha256": digest,
        "source_page_number": page_number,
        "requested_material_code": code,
        "candidate_blocks": blocks,
        "candidate_block_count": len(blocks),
        "original_clip_model": clip,
        "read_only_source_evidence": True,
        "independent_raster_literal_proven": False,
        "material_definition_authenticated": False,
        "physical_floor_identity_authenticated": False,
        "commercial_quantity_published": False,
    }
