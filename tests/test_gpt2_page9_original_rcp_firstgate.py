import pytest
from tools.diag_gpt2_page9_original_rcp_firstgate import audit

def test_wrong_source_sha_must_fail_before_viewport_detection():
    with pytest.raises(ValueError,match="source_sha_mismatch"):
        audit(b"unrelated source bytes")
