"""Read-only symbol-font source byte -> Unicode -> embedded GID audit.

A PDF may encode a symbol TrueType font with private-use Unicode F000+code,
while its ToUnicode CMap reports normal character meanings. A raw
font.has_glyph(ToUnicode_unicode, fallback=0) check does not validate that
mapping. This source diagnostic tests the distinct *byte/CMap/TTF* chain, but
it NEVER grants native text truth, visual glyph ink/clip ownership, OCR trust,
material definitions, physical floor correspondence or quantities.

Works on actual PDF source bytes, not guessed labels or world knowledge. The
optional fontTools dependency is imported only by this diagnostic.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import re

import fitz


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
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return {}, "fonttools_unavailable"
    if not isinstance(program,bytes) or not program:
        return {}, "embedded_font_program_unavailable"
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


def audit_pdf_embedded_symbol_source(
    source_bytes: bytes, *, expected_sha256: str, page_number: int,
    native_word_addresses: tuple[tuple[int,int,int],...],
):
    if type(source_bytes) is not bytes:
        raise TypeError("source bytes required")
    digest=sha256(source_bytes).hexdigest()
    if type(expected_sha256) is not str or digest!=expected_sha256:
        raise ValueError("original_source_sha_mismatch")
    if type(page_number) is not int or page_number<1:
        raise ValueError("source page number required")
    if not native_word_addresses or any(
        type(a) is not tuple or len(a)!=3 or any(type(v) is not int or v<0 for v in a)
        for a in native_word_addresses
    ):
        raise ValueError("explicit native source word addresses required")
    with fitz.open(stream=source_bytes,filetype="pdf") as doc:
        if page_number>len(doc):
            raise ValueError("source page out of range")
        page=doc[page_number-1]
        source_words={
            (int(w[5]),int(w[6]),int(w[7])):w
            for w in page.get_text("words",flags=fitz.TEXTFLAGS_WORDS)
            if len(w)>=8
        }
        traces=tuple(page.get_texttrace())
        font_by_name={}
        for row in page.get_fonts(full=True):
            if len(row)>=4:
                font_by_name.setdefault(str(row[3]).split("+")[-1],set()).add(int(row[0]))
        inventory={}
        rows=[]
        for address in native_word_addresses:
            word=source_words.get(address)
            if word is None:
                rows.append({"original_source_address":list(address),
                             "first_gate":"native_word_unavailable",
                             "text_verified_or_trusted":False})
                continue
            bbox=fitz.Rect(word[:4])
            literal=str(word[4])
            candidates=[]
            for trace in traces:
                chars=trace.get("chars",())
                if not chars or len(chars)<len(literal):
                    continue
                font_name=str(trace.get("font") or "")
                names=font_by_name.get(font_name,set())
                if len(names)!=1:
                    continue
                xref=next(iter(names))
                if xref not in inventory:
                    tounicode,unireason=_unique_source_tounicode(doc,xref)
                    embedded=doc.extract_font(xref)
                    raw=embedded[3] if len(embedded)>=4 else b""
                    symbols,ttfreason=_source_truetype_symbol_subtables(raw)
                    inventory[xref]={
                        "source_font_xref":xref,
                        "font_program_sha256":sha256(raw).hexdigest() if raw else None,
                        "pdf_tounicode":tounicode,
                        "symbol_byte_glyph_ids":symbols,
                        "tounicode_source_status":unireason,
                        "font_symbol_source_status":ttfreason,
                    }
                fonts=inventory[xref]
                for offset in range(len(chars)-len(literal)+1):
                    group=chars[offset:offset+len(literal)]
                    try:
                        if "".join(chr(int(c[0])) for c in group)!=literal:
                            continue
                    except (ValueError,TypeError,OverflowError):
                        continue
                    if not all(
                        fitz.Rect(c[3]).intersects(bbox)
                        for c in group
                    ):
                        continue
                    glyph_rows=[]
                    for c in group:
                        unicode_cp,glyph_id=int(c[0]),int(c[1])
                        exact_codes=[
                            byte for byte,reported_cp in fonts["pdf_tounicode"].items()
                            if reported_cp==unicode_cp
                        ]
                        agreements=[
                            {"original_pdf_character_byte":code,
                             "true_type_symbol_gid":fonts["symbol_byte_glyph_ids"].get(code)}
                            for code in exact_codes
                        ]
                        is_unique=(len(agreements)==1 and
                                   agreements[0]["true_type_symbol_gid"]==glyph_id
                                   and glyph_id>0)
                        glyph_rows.append({
                            "renderer_unicode_codepoint":unicode_cp,
                            "renderer_embedded_font_glyph_id":glyph_id,
                            "all_original_pdf_code_candidates":agreements,
                            "unique_pdf_code_to_font_glyph_candidate_agrees":is_unique,
                            "native_visual_or_clip_proof":False,
                        })
                    candidates.append({
                        "original_trace_sequence":trace.get("seqno"),
                        "source_font_xref":xref,
                        "source_word_bbox_pdf_pts":list(word[:4]),
                        "glyph_rows":glyph_rows,
                        "all_code_mapping_candidates_agree":
                            bool(glyph_rows) and all(x["unique_pdf_code_to_font_glyph_candidate_agrees"]
                                                     for x in glyph_rows),
                        "proves_text_or_material":False,
                    })
            rows.append({
                "original_source_address":list(address),
                "native_literal_word":literal,
                "all_competing_native_trace_word_candidates":candidates,
                "native_text_integrity_trusted_by_this_audit":False,
                "source_clip_and_ink_proven":False,
                "material_semantic_definition_granted":False,
            })
    return {
        "source_sha256":digest,
        "source_pdf_page":page_number,
        "source_word_candidates":rows,
        "source_font_inventory_status":[{
            "xref":i["source_font_xref"],
            "font_program_sha256":i["font_program_sha256"],
            "tounicode_source_status":i["tounicode_source_status"],
            "font_symbol_source_status":i["font_symbol_source_status"],
        } for i in inventory.values()],
        "read_only_diagnostic":True,
        "new_trusted_native_words":0,
        "new_material_definition":0,
        "new_physical_room_correspondence":0,
        "new_customer_quantities":0,
        "uses_frozen_benchmark_truth":False,
    }
