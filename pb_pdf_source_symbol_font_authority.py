"""Source-authoritative one-byte PDF ToUnicode and embedded symbol-font tables.

Production module shared by the PDF native text classifier and the standalone
diagnostic. Original source bytes and embedded font GID maps only; no Unicode
fallback, OCR, material, physical wall or customer quantity authorization.
All parse failure modes abstain. Optional fontTools dependency fail-closes.
"""
from __future__ import annotations

from io import BytesIO
import re

_SIMPLE_BFRANGE = re.compile(
    rb"^<([0-9A-Fa-f]{2})><([0-9A-Fa-f]{2})><([0-9A-Fa-f]{4,6})>$",
    re.MULTILINE,
)


def _unique_source_tounicode(doc, font_xref: int):
    """Only the explicitly declared one-byte, nonconflicting bfrange map."""
    try:
        key, ref = doc.xref_get_key(font_xref, "ToUnicode")
        if key != "xref":
            return {}, "source_tounicode_missing"
        raw = doc.xref_stream(int(str(ref).split()[0]))
    except Exception:
        return {}, "source_tounicode_unavailable"
    if not isinstance(raw, bytes) or b"<00><ff>" not in raw:
        return {}, "not_full_one_byte_codespace"
    result = {}
    for row in raw.splitlines():
        candidate = _SIMPLE_BFRANGE.fullmatch(row.strip())
        if not candidate:
            continue
        start, end, unicode_first = (
            int(candidate.group(i),16) for i in range(1,4)
        )
        if end < start or end > 255 or unicode_first+end-start > 0x10FFFF:
            return {}, "invalid_bfrange"
        for byte in range(start,end+1):
            codepoint=unicode_first+byte-start
            if byte in result and result[byte] != codepoint:
                return {}, "conflicting_pdf_unicode"
            result[byte]=codepoint
    if not result:
        return {}, "tounicode_not_supported_by_shadow"
    # This parser is intentionally limited to fully simple source map tables.
    # Unknown operators or additional differently shaped mapping tables make
    # the candidate universe incomplete, so refuse positive candidate proof.
    bfrange_rows=re.findall(rb"(?m)^\s*<[^>\r\n]*>\s*<[^>\r\n]*>\s*<[^>\r\n]*>\s*$",raw)
    if len(bfrange_rows)!=len(tuple(_SIMPLE_BFRANGE.finditer(raw))):
        return {}, "unhandled_tounicode_rival_rows"
    if b"beginbfchar" in raw:
        return {}, "unhandled_tounicode_bfchar"
    return result, "parsed_one_byte_bfrange_candidates"


def _source_truetype_symbol_subtables(program: bytes):
    """Keep all genuinely encoded table candidates; reject conflicting GIDs."""
    if not isinstance(program,bytes) or not program:
        return {}, "embedded_font_program_unavailable"
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return {}, "fonttools_unavailable"
    try:
        font=TTFont(BytesIO(program),recalcBBoxes=False,lazy=False)
        try:
            tables=[
                table for table in font["cmap"].tables
                if (int(table.platformID),int(table.platEncID)) in ((1,0),(3,0))
            ]
            if not tables or not any((t.platformID,t.platEncID)==(3,0) for t in tables):
                return {}, "symbol_cmap_missing"
            candidates={}
            for table in tables:
                for code,glyph in table.cmap.items():
                    if not isinstance(code,int):
                        continue
                    original_byte=code-0xF000 if table.platformID==3 else code
                    if original_byte<0 or original_byte>255:
                        continue
                    gid=int(font.getGlyphID(glyph))
                    if gid<=0:
                        continue
                    candidates.setdefault(original_byte,set()).add(gid)
            if any(len(v)!=1 for v in candidates.values()):
                return {}, "conflicting_symbol_font_subtables"
            return {byte:next(iter(ids)) for byte,ids in candidates.items()}, "unique_symbol_gid_candidates"
        finally:
            font.close()
    except Exception:
        return {}, "embedded_symbol_font_parse_unavailable"
