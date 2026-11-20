"""Original source decode identity survives the exact same native cache."""
import hashlib
import fitz
import pytest
from tools.check_original_native_decode_parity import (
    NativeDecodeParityError, check_original_native_decode_parity,
)

def _pdf():
    d = fitz.open()
    page = d.new_page()
    page.draw_rect(fitz.Rect(10, 10, 150, 120), color=(0, 0, 0), width=2)
    page.insert_text((20, 30), "Window 1200x1810")
    result = d.tobytes()
    d.close()
    return result

def test_source_cold_warm_proofs_are_identical_and_noncommercial():
    pdf = _pdf()
    r = check_original_native_decode_parity(
        pdf, expected_sha256=hashlib.sha256(pdf).hexdigest(), page_number=1,
    )
    assert r["observation_count"] > 0
    assert r["status"] == "SOURCE_NATIVE_DECODE_IDENTITY_PARITY_VERIFIED"
    assert r["benchmark_scored"] is False
    assert r["commercial_quantity_authorized"] is False

@pytest.mark.parametrize("sha,page", [
    ("a" * 64, 1), ("b" * 60, 1), ("a" * 64, True), ("a" * 64, 0),
])
def test_wrong_original_sha_or_page_rejected(sha, page):
    with pytest.raises(NativeDecodeParityError):
        check_original_native_decode_parity(_pdf(), expected_sha256=sha, page_number=page)

def test_original_page_must_exist():
    pdf = _pdf()
    with pytest.raises(NativeDecodeParityError, match="page_unavailable"):
        check_original_native_decode_parity(
            pdf, expected_sha256=hashlib.sha256(pdf).hexdigest(), page_number=2,
        )

def test_nonpdf_must_not_claim_native_parity():
    source = b"not a pdf"
    with pytest.raises(NativeDecodeParityError, match="unreadable"):
        check_original_native_decode_parity(
            source, expected_sha256=hashlib.sha256(source).hexdigest(), page_number=1,
        )
