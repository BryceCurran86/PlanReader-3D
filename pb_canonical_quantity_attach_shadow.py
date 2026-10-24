"""Mission item 21 — attach validated quantities to canonical entities (shadow).

Requires matching source root + canonical entity ID. Does not publish.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _clean(value: object) -> str:
    return str(value or "").strip()


def attach_quantity_to_canonical_entity_shadow(
    *,
    quantity_id: str,
    canonical_entity_id: str,
    quantity_source_root: Mapping[str, str],
    entity_source_root: Mapping[str, str],
    quantity_authority_status: str | None,
) -> dict[str, Any]:
    qid = _clean(quantity_id)
    eid = _clean(canonical_entity_id)
    if not qid or not eid:
        raise ValueError("quantity and canonical entity identities required")
    keys = ("document_id", "revision_id", "source_sha256", "snapshot_id")
    qroot = tuple(_clean(quantity_source_root.get(k)) for k in keys)
    eroot = tuple(_clean(entity_source_root.get(k)) for k in keys)
    if any(not v for v in qroot + eroot):
        gate = "canonical_attach_source_root_incomplete"
        attached = False
    elif qroot != eroot:
        gate = "canonical_attach_source_root_mismatch"
        attached = False
    elif str(quantity_authority_status or "").strip().lower() not in {"firm", "corroborated"}:
        gate = "canonical_attach_quantity_not_authorised"
        attached = False
    else:
        gate = "canonical_entity_quantity_attach_review_only"
        attached = True
    return {
        "quantity_id": qid,
        "canonical_entity_id": eid,
        "attach_review_only": attached,
        "first_remaining_gate": gate,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
