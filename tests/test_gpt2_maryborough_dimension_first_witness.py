"""Source room dimension diagnostics never mint physical room quantities."""
import hashlib

import fitz
import pytest

from tools.diag_gpt2_maryborough_dimension_first_witness import (
    inspect_page,
    source_inventory,
)


def test_native_room_label_and_figured_token_remain_unowned_candidates() -> None:
    doc = fitz.open()
    page = doc.new_page(width=500, height=400)
    page.insert_text((40, 50), "FREEZER")
    page.insert_text((140, 80), "3570")
    page.insert_text((240, 80), "2026")
    result = inspect_page(page, 1, bind_vectors=False)
    assert any(
        row["candidate_label"] == "FREEZER"
        and row["status"] == "LABEL_CANDIDATE_ONLY"
        for row in result["source_room_label_candidates"]
    )
    assert result["candidate_count"] >= 1
    assert all(
        row["status"] == "UNOWNED_FIGURED_DIMENSION_CANDIDATE"
        for row in result["typed_native_dimension_candidates"]
    )
    assert not result["dimension_witness_bindings"]
    assert result["source_owned_room_area_granted"] is False
    assert result["cross_view_room_ownership_granted"] is False
    doc.close()


def test_wrong_source_sha_abstains_even_on_valid_pdf() -> None:
    doc = fitz.open()
    doc.new_page()
    payload = doc.tobytes()
    doc.close()
    with pytest.raises(ValueError, match="SOURCE_SHA_MISMATCH"):
        source_inventory(payload, expected_sha256="0" * 64)


def test_unauthorized_page_count_rejected_before_candidate_publication() -> None:
    doc = fitz.open()
    doc.new_page()
    payload = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError, match="SOURCE_PAGE_COUNT_MISMATCH"):
        source_inventory(payload, expected_sha256=sha)
