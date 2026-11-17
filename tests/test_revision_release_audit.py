import pytest
from pb_revision_release_audit import REQUIRED_GATES, audit_revision_release

HEAD = "a" * 40

def valid_receipts():
    return {gate: {"head": HEAD, "passed": True, "evidence": "test receipt"} for gate in REQUIRED_GATES}

def trusted(gate, head, receipt):
    return head == HEAD and gate in REQUIRED_GATES and receipt["evidence"] == "test receipt"

def test_positive_with_independent_verifier():
    assert audit_revision_release(HEAD, valid_receipts(), verify_receipt=trusted).ready

def test_unverified_claims_never_authorize_release():
    result = audit_revision_release(HEAD, valid_receipts())
    assert not result.ready
    assert set(result.rejected) == set(REQUIRED_GATES)

def test_missing_gates():
    receipts = valid_receipts()
    del receipts["production_auth_provider"]
    assert audit_revision_release(HEAD, receipts, verify_receipt=trusted).missing == ("production_auth_provider",)

def test_stale_head_and_non_boolean_pass():
    receipts = valid_receipts()
    receipts["python314_exact_head"]["head"] = "b" * 40
    receipts["unified_head_shared_lock"]["passed"] = 1
    assert set(audit_revision_release(HEAD, receipts, verify_receipt=trusted).rejected) == {
        "python314_exact_head", "unified_head_shared_lock"}

def test_blank_evidence_and_bad_sha():
    receipts = valid_receipts()
    receipts["security_source_checks"]["evidence"] = " "
    assert "security_source_checks" in audit_revision_release(HEAD, receipts, verify_receipt=trusted).rejected
    with pytest.raises(ValueError):
        audit_revision_release("main", receipts)

def test_verifier_exception_and_non_boolean_result_fail_closed():
    def raises(gate, head, receipt):
        raise RuntimeError("provider unavailable")
    assert not audit_revision_release(HEAD, valid_receipts(), verify_receipt=raises).ready
    assert not audit_revision_release(HEAD, valid_receipts(), verify_receipt=lambda *_: 1).ready
