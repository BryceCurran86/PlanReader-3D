"""Original text discovery must preserve trust and never grant filling roles."""

from hashlib import sha256

import fitz

from tools.diag_gptmax_original_opening_role_text import original_role_text_audit


def source_pdf():
    pdf = fitz.open()
    page = pdf.new_page(width=500, height=300)
    page.insert_text((30, 40), "2142 BIFOLD")
    page.insert_text((30, 90), "DOOR WINDOW")
    page.insert_text((30, 150), "BIFOLD", render_mode=3)
    payload = pdf.tobytes()
    pdf.close()
    return payload


def test_original_native_blocks_keep_visible_positive_and_hidden_negative_without_role():
    payload = source_pdf()
    original_hash = sha256(payload).hexdigest()
    report = original_role_text_audit(payload, ("BIFOLD", "DOOR", "WINDOW"))
    texts = [r["text_result"] for r in report["original_native_text_blocks"]]
    assert any(r["trusted_text"] == "BIFOLD" for r in texts)
    assert any(
        r["receipt"]["raw_text"] == "BIFOLD" and r["trusted_text"] is None
        for r in texts
    )
    assert {r["trusted_text"] for r in texts if r["trusted_text"]} >= {
        "DOOR",
        "WINDOW",
        "2142",
    }
    assert not report["filling_role_granted"]
    assert not report["physical_identity_transfer_granted"]
    assert not report["quantity_granted"] and not report["count_granted"]
    assert sha256(payload).hexdigest() == original_hash == report["source_sha256"]
    snapshot = report["original_published_snapshot"]["snapshot"]["snapshot_id"]
    assert all(
        r["selector"]["snapshot_id"] == snapshot
        for r in report["original_native_text_blocks"]
    )
    replay = original_role_text_audit(payload, ("WINDOW", "BIFOLD", "DOOR", "DOOR"))
    assert report == replay


def test_empty_query_result_is_a_bounded_search_not_nonexistence_or_role_proof():
    report = original_role_text_audit(source_pdf(), ("UNMENTIONED",))
    assert report["original_native_word_count"] > 0
    assert not report["original_native_text_blocks"]
    assert not report["filling_role_granted"] and not report["quantity_granted"]
