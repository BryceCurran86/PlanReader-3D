"""Exact original embedded TrueType Unicode cmap census; no text authority.

Optional fontTools is used ONLY for this read-only diagnostic. The source PDF
ToUnicode CMap is not used as an embedded-font Unicode mapping. No selected
mapping can grant a source character, material, room or quantity.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from typing import Any

import fitz

from tools.diag_native_text_font_clip_gates import inspect_native_text_gates


def _original_ttf_unicode_cmaps(font_bytes: bytes) -> dict[str, Any]:
    """All original Unicode subtables, keeping conflicting glyph identities."""
    if type(font_bytes) is not bytes or not font_bytes:
        return {"status": "font_program_unavailable", "subtables": ()}
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return {"status": "fonttools_unavailable", "subtables": ()}
    try:
        font = TTFont(BytesIO(font_bytes), recalcBBoxes=False, lazy=False)
        try:
            if "cmap" not in font:
                return {"status": "no_cmap", "subtables": ()}
            subtables = []
            for subtable in font["cmap"].tables:
                if not subtable.isUnicode():
                    continue
                rows = []
                for codepoint, glyph_name in sorted(subtable.cmap.items()):
                    if type(codepoint) is not int or not 0 <= codepoint <= 0x10FFFF:
                        continue
                    try:
                        gid = int(font.getGlyphID(glyph_name))
                    except (TypeError, ValueError, KeyError):
                        continue
                    rows.append((codepoint, gid, str(glyph_name)))
                subtables.append({
                    "platform_id": int(subtable.platformID),
                    "encoding_id": int(subtable.platEncID),
                    "entries": tuple(rows),
                })
            return {
                "status": "parsed" if subtables else "no_unicode_cmap",
                "subtables": tuple(subtables),
            }
        finally:
            font.close()
    except Exception:
        # An invalid / unsupported font is not a reason to replace its cmap
        # with a decoder default or the PDF's ToUnicode declaration.
        return {"status": "font_parse_unavailable", "subtables": ()}


def _all_glyph_candidates(inventory: dict[str, Any], codepoint: int) -> list[dict]:
    """Do not choose a candidate when two genuine Unicode cmap tables differ."""
    return [
        {
            "platform_id": t["platform_id"],
            "encoding_id": t["encoding_id"],
            "glyph_id": gid,
            "glyph_name": name,
        }
        for t in inventory.get("subtables", ())
        for unicode_value, gid, name in t["entries"]
        if unicode_value == codepoint
    ]


def _read_source_font_program(doc: fitz.Document, xref: int):
    try:
        extracted = doc.extract_font(xref)
        font_bytes = extracted[3] if len(extracted) >= 4 else b""
    except Exception:
        font_bytes = b""
    if not isinstance(font_bytes, bytes):
        font_bytes = b""
    return font_bytes


def inspect_original_embedded_cmap(
    source_bytes: bytes, *, expected_sha256: str, page_number: int, code: str
) -> dict:
    if type(source_bytes) is not bytes:
        raise TypeError("original source bytes required")
    digest = sha256(source_bytes).hexdigest()
    if type(expected_sha256) is not str or digest != expected_sha256:
        raise ValueError("original source SHA mismatch")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("original page number required")
    if type(code) is not str or not code or code.strip() != code:
        raise ValueError("exact source code required")

    baseline = inspect_native_text_gates(
        source_bytes, expected_sha256=expected_sha256,
        page_number=page_number, code=code,
    )
    source_fonts: dict[int, dict] = {}
    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        for block in baseline["candidate_blocks"]:
            for word in block["source_words"]:
                for run in word["glyph_runs"]:
                    xref = run["font_xref"]
                    if type(xref) is not int or xref <= 0 or xref in source_fonts:
                        continue
                    font_bytes = _read_source_font_program(doc, xref)
                    source_fonts[xref] = {
                        "xref": xref,
                        "font_program_sha256": sha256(font_bytes).hexdigest()
                            if font_bytes else None,
                        "font_program_length": len(font_bytes),
                        "unicode_cmap": _original_ttf_unicode_cmaps(font_bytes),
                    }
    blocks = []
    for block in baseline["candidate_blocks"]:
        rows = []
        for word in block["source_words"]:
            mapped_runs = []
            for run in word["glyph_runs"]:
                xref = run["font_xref"]
                inventory = source_fonts.get(xref, {}).get("unicode_cmap", {})
                glyph_results = []
                for glyph in run["glyph_results"]:
                    candidates = _all_glyph_candidates(inventory, glyph["unicode"])
                    unique = {candidate["glyph_id"] for candidate in candidates}
                    glyph_results.append({
                        **glyph,
                        "font_unicode_cmap_candidates": candidates,
                        "unique_font_unicode_gid": next(iter(unique))
                            if len(unique) == 1 else None,
                        "unicode_cmap_trace_id_consistent": (
                            len(unique) == 1
                            and next(iter(unique)) == glyph["trace_glyph_id"]
                            and glyph["trace_glyph_id"] > 0
                        ),
                        "visual_ink_or_clip_authority_granted": False,
                    })
                mapped_runs.append({
                    "font_xref": xref,
                    "original_trace_sequence": run["sequence_number"],
                    "font_unicode_cmap_status": inventory.get("status", "unavailable"),
                    "glyph_results": glyph_results,
                })
            rows.append({
                "source_address": word["source_address"],
                "text": word["text"],
                "ordinary_integrity_reasons": word["original_decision_reasons"],
                "runs": mapped_runs,
                "trusted_text_granted": False,
            })
        blocks.append({"block_no": block["block_no"], "source_words": rows})
    return {
        "source_sha256": digest,
        "page_number": page_number,
        "exact_requested_code": code,
        "candidate_blocks": blocks,
        "source_fonts": [source_fonts[k] for k in sorted(source_fonts)],
        "original_source_word_count": sum(len(b["source_words"]) for b in blocks),
        "native_font_metadata_only": True,
        "independent_raster_literal_proven": False,
        "source_material_definition_authenticated": False,
        "physical_room_and_floor_identity_granted": False,
        "commercial_quantity_published": False,
    }
