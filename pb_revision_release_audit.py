"""Fail-closed evidence inventory for original PlanReader revision releases."""
from dataclasses import dataclass
from typing import Mapping

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

def audit_revision_release(expected_head: str, receipts: Mapping) -> ReleaseAudit:
    """Inventory only: evidence strings are not independently authenticated."""
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
        if (not isinstance(receipt, Mapping)
            or receipt.get("head") != expected_head
            or receipt.get("passed") is not True
            or not isinstance(receipt.get("evidence"), str)
            or not receipt["evidence"].strip()):
            rejected.append(gate)
    return ReleaseAudit(not missing and not rejected, tuple(missing), tuple(rejected))
