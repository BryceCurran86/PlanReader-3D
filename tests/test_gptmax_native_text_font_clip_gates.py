"""Exact native glyph/font and clipping inspect-only security regression."""
from hashlib import sha256

import fitz
import pytest

from tools.diag_native_text_font_clip_gates import inspect_native_text_gates


def _pdf(*, second=False, change_font=False):
    doc = fitz.open()
    page = doc.new_page(width=600, height=430)
    page.insert_text((72, 95), "FT3 FLOOR TILE - TEST", fontsize=12)
    if second:
        page.insert_text((72, 205), "FT3 ANOTHER FINISH", fontsize=12)
    if change_font:
        page.insert_text((72, 312), "FT4 OTHER", fontsize=12, fontname="cour")
    raw = doc.tobytes()
    doc.close()
    return raw


def test_exact_original_font_clip_diagnostic_never_grants_authority():
    data = _pdf()
    sha = sha256(data).hexdigest()
    result = inspect_native_text_gates(
        data, expected_sha256=sha, page_number=1, code="FT3",
    )
    assert result["source_sha256"] == sha
    assert result["candidate_block_count"] >= 1
    assert result["original_clip_model"]["model_available"] in (True, False)
    rows = [w for b in result["candidate_blocks"] for w in b["source_words"]]
    assert any(w["text"] == "FT3" for w in rows)
    assert all(len(w["source_address"]) == 3 for w in rows)
    assert all(w["font_or_clip_promotion_allowed"] is False for w in rows)
    assert result["read_only_source_evidence"] is True
    assert result["independent_raster_literal_proven"] is False
    assert result["material_definition_authenticated"] is False
    assert result["physical_floor_identity_authenticated"] is False
    assert result["commercial_quantity_published"] is False
    assert result == inspect_native_text_gates(
        data, expected_sha256=sha, page_number=1, code="FT3",
    )


def test_competing_origins_no_fuzzy_cross_font_and_source_fails_closed():
    data = _pdf(second=True, change_font=True)
    sha = sha256(data).hexdigest()
    result = inspect_native_text_gates(
        data, expected_sha256=sha, page_number=1, code="FT3",
    )
    assert sum(
        w["text"] == "FT3"
        for block in result["candidate_blocks"] for w in block["source_words"]
    ) == 2
    assert result["candidate_block_count"] >= 2
    assert inspect_native_text_gates(
        data, expected_sha256=sha, page_number=1, code="MISSING",
    )["candidate_blocks"] == []
    with pytest.raises(ValueError, match="SHA"):
        inspect_native_text_gates(
            data, expected_sha256="f" * 64, page_number=1, code="FT3",
        )
    for page in (0, 2, 1.0, True):
        with pytest.raises(ValueError):
            inspect_native_text_gates(
                data, expected_sha256=sha, page_number=page, code="FT3",
            )
    for code in ("", " FT3", None):
        with pytest.raises(ValueError):
            inspect_native_text_gates(
                data, expected_sha256=sha, page_number=1, code=code,
            )
    with pytest.raises(TypeError):
        inspect_native_text_gates(
            bytearray(data), expected_sha256=sha, page_number=1, code="FT3",
        )
