import pytest
from tools.diag_gpt2_page9_original_rcp_firstgate import audit

def test_wrong_source_sha_must_fail_before_viewport_detection():
    with pytest.raises(ValueError,match="source_sha_mismatch"):
        audit(b"unrelated source bytes")

def test_source_page_universe_must_be_31(monkeypatch):
    from tools import diag_gpt2_page9_original_rcp_firstgate as module
    import hashlib
    monkeypatch.setattr(module, "SOURCE_SHA", hashlib.sha256(b"test").hexdigest())
    import fitz
    doc = fitz.open()
    doc.new_page()
    payload = doc.tobytes()
    doc.close()
    monkeypatch.setattr(module, "SOURCE_SHA", hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError, match="source_page_universe_mismatch"):
        audit(payload)
