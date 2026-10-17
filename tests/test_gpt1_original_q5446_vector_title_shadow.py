"""SHA-pinned original Q5446 raster-vector title evidence only."""
from pathlib import Path
import pytest
from tools.diag_gpt1_original_q5446_vector_title_shadow import (
    SHA, source_title_candidates, title_from_ocr_text,
)


def test_ocr_title_requires_source_view_field_and_no_competing_title():
    assert title_from_ocr_text(
        "View:\nGROUND FLOOR PLAN ;\nCustomer:", "GROUND FLOOR PLAN"
    ) == "GROUND FLOOR PLAN"
    assert title_from_ocr_text(
        "View: FIRST FLOOR PLAN", "FIRST FLOOR PLAN"
    ) == "FIRST FLOOR PLAN"
    assert title_from_ocr_text("GROUND FLOOR PLAN", "GROUND FLOOR PLAN") is None
    assert title_from_ocr_text(
        "View: GROUND FLOOR PLAN FIRST FLOOR PLAN", "GROUND FLOOR PLAN"
    ) is None
    assert title_from_ocr_text(
        "View: GROUND FLOOR PLAN GROUND FLOOR PLAN", "GROUND FLOOR PLAN"
    ) is None


def test_unauthenticated_pdf_cannot_claim_original_sheet_title():
    with pytest.raises(ValueError, match="SHA-verified"):
        source_title_candidates(b"%PDF-synthetic")


def test_original_vector_source_positive_but_no_producer_role_promotion():
    source = Path("documents/sources/Q5446_Standard_Plans_V1_20220320.pdf")
    if not source.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: no original proof")
    from hashlib import sha256
    pdf = source.read_bytes()
    assert sha256(pdf).hexdigest() == SHA
    result = source_title_candidates(pdf)
    assert [r["original_title_candidate"] for r in result["title_candidate_rows"]] == [
        "GROUND FLOOR PLAN", "FIRST FLOOR PLAN"
    ]
    assert [r["native_drawings_on_page"] for r in result["title_candidate_rows"]] == [
        16159, 13170
    ]
    assert all(not r["producer_positive_floor_plan_role"]
               for r in result["title_candidate_rows"])
    assert result["topology_eligible_pages"] is None
    assert not result["source_authored_page_role_issued"]
    assert result["full_20k_cap_preserved"]
    with pytest.raises(ValueError, match="SHA-verified"):
        source_title_candidates(pdf + b"altered")
