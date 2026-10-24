"""Production and diagnostic source CMap/GID readers are exactly one implementation."""
from pathlib import Path
import hashlib

import fitz
import pytest

import pb_pdf_source_symbol_font_authority as source
import tools.diag_pdf_symbol_byte_glyph_shadow as diagnostic

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_production_and_diagnostic_share_exact_source_readers():
    assert source._unique_source_tounicode is diagnostic._unique_source_tounicode
    assert source._source_truetype_symbol_subtables is diagnostic._source_truetype_symbol_subtables


def test_original_ft3_source_bytes_and_embedded_gids_same_positive_proof():
    pytest.importorskip("fontTools")
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[10]
        owned=[font for font in page.get_fonts(full=True)
               if str(font[3]).split("+")[-1]=="ISOCPEUR"]
        assert len(owned)==1
        xref=int(owned[0][0])
        unicode_map,status=source._unique_source_tounicode(doc,xref)
        assert status=="parsed_one_byte_bfrange_candidates"
        assert unicode_map[0x10]==70 # FT3: F
        assert unicode_map[0x18]==84 # FT3: T
        assert unicode_map[0x07]==51 # FT3: 3
        embedded=doc.extract_font(xref)
        gids,status=source._source_truetype_symbol_subtables(embedded[3])
        assert status=="unique_symbol_gid_candidates"
        assert (gids[0x10],gids[0x18],gids[0x07])==(39,53,20)
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def test_missing_embedded_font_and_unknown_font_mapping_abstain():
    assert source._source_truetype_symbol_subtables(b"")==(
        {},"embedded_font_program_unavailable"
    )
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as doc:
        invalid,status=source._unique_source_tounicode(doc,9999999)
        assert not invalid
        assert status in ("source_tounicode_unavailable","source_tounicode_missing")


def test_exact_parser_does_not_use_unicode_fallback_or_invent_source_count():
    assert source._source_truetype_symbol_subtables(b"\x00\x00\x00\x00")[0]=={}
    # This source parser alone cannot construct an authenticated material,
    # quantity, building-wall identity, ceiling area or SourceObservation.
    assert not hasattr(source,"publish_material_definition")
    assert not hasattr(source,"publish_floor_finish_quantity")
