"""Mission item 6 — signed opening dedupe without re-keying historical IDs.

Prevents a new physical opening from adopting an existing signed quantity ID
or silently aliasing a previously sealed physical identity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _clean(value: object) -> str:
    return str(value or "").strip()


def assess_signed_opening_dedupe_shadow(
    *,
    candidate_physical_opening_id: str,
    candidate_quantity_id: str | None,
    sealed_physical_opening_ids: Sequence[str],
    sealed_quantity_ids: Sequence[str],
    alias_claims: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    candidate = _clean(candidate_physical_opening_id)
    if not candidate:
        raise ValueError("candidate physical opening identity required")
    sealed_phys = {_clean(i) for i in sealed_physical_opening_ids if _clean(i)}
    sealed_qty = {_clean(i) for i in sealed_quantity_ids if _clean(i)}
    qid = _clean(candidate_quantity_id) or None

    blockers: list[str] = []
    if candidate in sealed_phys:
        blockers.append("candidate_reuses_sealed_physical_opening_id")
    if qid and qid in sealed_qty:
        blockers.append("candidate_reuses_sealed_quantity_id")
    for claim in alias_claims:
        if not isinstance(claim, Mapping):
            raise TypeError("alias claim must be a mapping")
        left = _clean(claim.get("physical_opening_id"))
        right = _clean(claim.get("alias_of_physical_opening_id"))
        if left == candidate and right in sealed_phys and left != right:
            blockers.append("candidate_aliases_sealed_physical_opening")
        if left in sealed_phys and right == candidate and left != right:
            blockers.append("sealed_physical_opening_aliased_to_candidate")

    return {
        "candidate_physical_opening_id": candidate,
        "candidate_quantity_id": qid,
        "blockers": sorted(set(blockers)),
        "first_remaining_gate": (
            "signed_opening_dedupe_blocked" if blockers else "signed_opening_dedupe_clear_review_only"
        ),
        "rekey_allowed": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
