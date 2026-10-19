"""Mission item 22 — enforce source lineage required fields on quantity rows.

Document, SHA, revision, snapshot, viewport/decision scope must be present.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_REQUIRED = (
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
)


def enforce_source_lineage_required_fields_shadow(
    rows: Sequence[Mapping[str, Any]],
    *,
    require_decision_scope: bool = True,
) -> dict[str, Any]:
    required = list(_REQUIRED)
    if require_decision_scope:
        required.append("decision_scope_id")
    blockers = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError("lineage row must be a mapping")
        missing = [field for field in required if not str(row.get(field) or "").strip()]
        if missing:
            blockers.append({
                "index": index,
                "quantity_id": row.get("quantity_id"),
                "physical_object_id": row.get("physical_object_id"),
                "missing_fields": missing,
            })
    return {
        "status": (
            "SOURCE_LINEAGE_INCOMPLETE"
            if blockers
            else "SOURCE_LINEAGE_FIELDS_PRESENT_REVIEW_ONLY"
        ),
        "blockers": blockers,
        "publication_allowed": False,
        "measurement_published": False,
        "shadow_only": True,
    }
