"""Mission item 25 — source-closed sealing readiness (never self-seals).

A genuinely new quantity may enter seal review only when lineage, authority,
dedupe, and retention of prior signed IDs all pass. This module does not call
GPT3 sealers or mutate customer rows.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def assess_source_closed_seal_readiness_shadow(
    *,
    quantity_id: str,
    authority_status: str | None,
    source_lineage_complete: bool,
    dedupe_clear: bool,
    prior_signed_ids_retained: bool,
    owner_promotion_approved: bool,
) -> dict[str, Any]:
    qid = str(quantity_id or "").strip()
    if not qid:
        raise ValueError("quantity identity required")
    auth = str(authority_status or "").strip().lower()
    if not source_lineage_complete:
        gate = "seal_blocked_incomplete_source_lineage"
    elif not dedupe_clear:
        gate = "seal_blocked_dedupe_conflict"
    elif not prior_signed_ids_retained:
        gate = "seal_blocked_prior_signed_identity_loss"
    elif auth not in {"firm", "corroborated"}:
        gate = "seal_blocked_quantity_not_authorised"
    elif not owner_promotion_approved:
        gate = "seal_blocked_owner_promotion_required"
    else:
        gate = "source_closed_seal_review_only"
    return {
        "quantity_id": qid,
        "first_remaining_gate": gate,
        "seal_activated": False,
        "customer_rows_mutated": False,
        "measurement_published": False,
        "shadow_only": True,
    }
