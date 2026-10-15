"""Original-only glyph ancestry remains diagnostic, never text authentication."""
from __future__ import annotations

from hashlib import sha256

import fitz
import pytest

from tools.diag_source_native_glyph_ancestry import inspect_original_glyphs


def _pdf(*, twice=False):
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.insert_text((72, 95), "FT3 PLAIN GLYPH", fontsize=14)
    if twice:
        page.insert_text((72, 210), "FT3 SECOND ROW", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_source_glyph_proof_lists_real_anchors_without_minting_material():
    data = _pdf()
    source_hash = sha256(data).hexdigest()
    result = inspect_original_glyphs(
        data, expected_sha256=source_hash, page_number=1, code="FT3"
    )
    assert result["source_sha256"] == source_hash
    assert result["candidate_block_count"] >= 1
    assert result["source_profile_comparison_only"] is True
    assert not result["independent_raster_literal_proven"]
    assert not result["material_definition_authenticated"]
    assert not result["source_finish_occurrence_authenticated"]
    assert not result["physical_floor_ownership_authenticated"]
    assert not result["commercial_quantity_published"]
    rows = [word for block in result["candidate_blocks"] for word in block["words"]]
    assert any(word["text"] == "FT3" for word in rows)
    assert all(len(word["native_source_address"]) == 3 for word in rows)
    assert all(word["independent_raster_literal_proven"] is False for word in rows)
    assert result == inspect_original_glyphs(
        data, expected_sha256=source_hash, page_number=1, code="FT3"
    )


def test_multiple_source_code_blocks_and_negative_inputs_fail_closed():
    data = _pdf(twice=True)
    digest = sha256(data).hexdigest()
    result = inspect_original_glyphs(data, expected_sha256=digest, page_number=1, code="FT3")
    assert sum(
        word["text"] == "FT3"
        for block in result["candidate_blocks"] for word in block["words"]
    ) == 2
    # Two independent marks are never reduced to the nearest or first.
    assert result["candidate_block_count"] >= 2
    empty = inspect_original_glyphs(data, expected_sha256=digest, page_number=1, code="ZZ9")
    assert empty["candidate_blocks"] == []
    assert empty["material_definition_authenticated"] is False
    with pytest.raises(ValueError, match="SHA"):
        inspect_original_glyphs(data, expected_sha256="0" * 64, page_number=1, code="FT3")
    for page in (0, 2, 1.0, True):
        with pytest.raises(ValueError):
            inspect_original_glyphs(data, expected_sha256=digest, page_number=page, code="FT3")
    for code in ("", "FT3 ", None):
        with pytest.raises(ValueError):
            inspect_original_glyphs(data, expected_sha256=digest, page_number=1, code=code)
    with pytest.raises(TypeError):
        inspect_original_glyphs(bytearray(data), expected_sha256=digest, page_number=1, code="FT3")
