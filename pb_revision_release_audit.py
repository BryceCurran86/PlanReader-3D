"""Fail-closed evidence inventory for original PlanReader revision releases.

A receipt is a claim until an independent trusted verifier checks it.
"""
from dataclasses import dataclass
from typing import Callable, Mapping

REQUIRED_GATES = (
    "python313_exact_head", "python314_exact_head", "security_source_checks",
    "production_auth_provider", "tenant_and_csrf_isolation",
    "unified_head_shared_lock", "cross_process_contention",
    "source_sha_pinned_replay", "original_customer_retention",
    "revision_pdf_immutability",
)

@dataclass(frozen=True)
class ReleaseAudit:
    ready: bool
    missing: tuple[str, ...]
    rejected: tuple[str, ...]

def audit_revision_release(
    expected_head: str,
    receipts: Mapping,
    *,
    verify_receipt: Callable[[str, str, Mapping], bool] | None = None,
) -> ReleaseAudit:
    """Require a trusted independent verifier for every supplied gate.

    The caller must resolve CI run identity, private-source evidence and host
    attestations independently. User-controlled strings are never proof.
    """
    if not isinstance(expected_head, str) or len(expected_head) != 40 or any(
        ch not in "0123456789abcdef" for ch in expected_head
    ):
        raise ValueError("expected_head must be a lowercase full git SHA")
    if not isinstance(receipts, Mapping):
        raise TypeError("receipts must be a mapping")
    missing, rejected = [], []
    for gate in REQUIRED_GATES:
        if gate not in receipts:
            missing.append(gate)
            continue
        receipt = receipts[gate]
        structurally_valid = (
            isinstance(receipt, Mapping)
            and receipt.get("head") == expected_head
            and receipt.get("passed") is True
            and isinstance(receipt.get("evidence"), str)
            and bool(receipt["evidence"].strip())
        )
        if not structurally_valid or verify_receipt is None:
            rejected.append(gate)
            continue
        try:
            verified = verify_receipt(gate, expected_head, receipt) is True
        except Exception:
            verified = False
        if not verified:
            rejected.append(gate)
    return ReleaseAudit(not missing and not rejected, tuple(missing), tuple(rejected))
