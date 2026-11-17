import pytest
from pb_revision_release_audit import REQUIRED_GATES, audit_revision_release

HEAD = "a" * 40

def valid_receipts():
    return {gate: {"head": HEAD, "passed": True, "evidence": "test receipt"} for gate in REQUIRED_GATES}

def test_positive():
    assert audit_revision_release(HEAD, valid_receipts()).ready

def test_missing_gates():
    receipts = valid_receipts()
    del receipts["production_auth_provider"]
    assert audit_revision_release(HEAD, receipts).missing == ("production_auth_provider",)

def test_stale_head_and_non_boolean_pass():
    receipts = valid_receipts()
    receipts["python314_exact_head"]["head"] = "b" * 40
    receipts["unified_head_shared_lock"]["passed"] = 1
    assert set(audit_revision_release(HEAD, receipts).rejected) == {
        "python314_exact_head", "unified_head_shared_lock"}

def test_blank_evidence_and_bad_sha():
    receipts = valid_receipts()
    receipts["security_source_checks"]["evidence"] = " "
    assert "security_source_checks" in audit_revision_release(HEAD, receipts).rejected
    with pytest.raises(ValueError):
        audit_revision_release("main", receipts)
