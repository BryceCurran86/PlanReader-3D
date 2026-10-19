"""Mission item 27 — trade quantity readiness without inventing scopes.

Painting, plastering, tiling, concreting, carpentry, plumbing, electrical
abstain until trade-specific evidence IDs exist. No default rates or areas.
"""
from __future__ import annotations

from typing import Any, Sequence

_SUPPORTED_TRADES = frozenset({
    "painting",
    "plastering",
    "tiling",
    "concreting",
    "carpentry",
    "plumbing",
    "electrical",
})


def assess_trade_quantity_evidence_readiness_shadow(
    *,
    trade: str,
    evidence_ids: Sequence[str] = (),
    quantity_authority_status: str | None = None,
) -> dict[str, Any]:
    name = str(trade or "").strip().lower()
    if name not in _SUPPORTED_TRADES:
        raise ValueError(f"unsupported trade {trade!r}")
    evidence = tuple(str(e).strip() for e in evidence_ids if str(e).strip())
    auth = str(quantity_authority_status or "").strip().lower()
    if not evidence:
        gate = f"{name}_evidence_unavailable"
    elif auth not in {"firm", "corroborated"}:
        gate = f"{name}_quantity_authority_unproven"
    else:
        gate = f"{name}_quantity_review_only"
    return {
        "trade": name,
        "evidence_ids": list(evidence),
        "first_remaining_gate": gate,
        "default_rate_or_area_invented": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
