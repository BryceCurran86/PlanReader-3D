"""Original embedded font CMap is only evidence, never visible-text authority."""
from hashlib import sha256

import fitz
import pytest

from tools.diag_embedded_cmap_glyph_shadow import (
    _all_glyph_candidates,
    inspect_original_embedded_cmap,
)


def _pdf(*, competing=False):
    document = fitz.open()
    page = document.new_page(width=600, height=450)
    page.insert_text((72, 95), "FT3 OLD TILE", fontsize=12)
    if competing:
        page.insert_text((72, 240), "FT3 OTHER TILE", fontsize=12)
    raw = document.tobytes()
    document.close()
    return raw


def test_all_embedded_unicode_cmap_candidates_survive_even_conflict():
    inventory = {
        "status": "parsed",
        "subtables": (
            {"platform_id": 3, "encoding_id": 1,
             "entries": ((65, 14, "A"), (8216, 100, "quoteleft"))},
            {"platform_id": 0, "encoding_id": 3,
             "entries": ((65, 14, "A"), (8216, 200, "uni2018"))},
        ),
    }
    assert {c["glyph_id"] for c in _all_glyph_candidates(inventory, 8216)} == {100, 200}
    assert len(_all_glyph_candidates(inventory, 65)) == 2
    assert _all_glyph_candidates(inventory, 8217) == []


def test_original_cmap_report_rejects_commercial_grants_and_foreign_source():
    data = _pdf(competing=True)
    digest = sha256(data).hexdigest()
    report = inspect_original_embedded_cmap(
        data, expected_sha256=digest, page_number=1, code="FT3",
    )
    rows = [w for b in report["candidate_blocks"] for w in b["source_words"]]
    assert sum(w["text"] == "FT3" for w in rows) == 2
    assert report["original_source_word_count"] == len(rows)
    assert report["native_font_metadata_only"] is True
    assert report["source_sha256"] == digest
    assert not report["independent_raster_literal_proven"]
    assert not report["source_material_definition_authenticated"]
    assert not report["physical_room_and_floor_identity_granted"]
    assert not report["commercial_quantity_published"]
    assert all(not w["trusted_text_granted"] for w in rows)
    assert all(
        not g["visual_ink_or_clip_authority_granted"]
        for w in rows for run in w["runs"] for g in run["glyph_results"]
    )
    assert report == inspect_original_embedded_cmap(
        data, expected_sha256=digest, page_number=1, code="FT3",
    )
    with pytest.raises(ValueError, match="SHA"):
        inspect_original_embedded_cmap(
            data, expected_sha256="0" * 64, page_number=1, code="FT3",
        )
    for page in (0, 2, 1.0, True):
        with pytest.raises(ValueError):
            inspect_original_embedded_cmap(
                data, expected_sha256=digest, page_number=page, code="FT3",
            )
    for code in ("", "FT3 ", None):
        with pytest.raises(ValueError):
            inspect_original_embedded_cmap(
                data, expected_sha256=digest, page_number=1, code=code,
            )
    with pytest.raises(TypeError):
        inspect_original_embedded_cmap(
            bytearray(data), expected_sha256=digest, page_number=1, code="FT3",
        )
