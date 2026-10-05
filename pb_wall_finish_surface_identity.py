"""Stable physical identity for source-owned wall-finish surfaces.

Identity is physical wall + physical face + trade scope within one source
document. Revision, snapshot, material wording and detector version are semantic
state and must not churn the physical surface identity.
"""
from __future__ import annotations

from pb_migration_contracts import stable_contract_id


def physical_wall_finish_surface_id(
    *,
    document_id: str,
    physical_wall_id: str,
    physical_face_id: str,
    trade_scope_id: str,
) -> str:
    values = {
        "document_id": str(document_id or "").strip(),
        "physical_wall_id": str(physical_wall_id or "").strip(),
        "physical_face_id": str(physical_face_id or "").strip(),
        "trade_scope_id": str(trade_scope_id or "").strip(),
    }
    missing = tuple(name for name, value in values.items() if not value)
    if missing:
        raise ValueError(
            "wall-finish surface identity requires " + ", ".join(missing)
        )
    return stable_contract_id(
        "physical_wall_finish_surface",
        values,
        digest_chars=32,
    )


__all__ = ["physical_wall_finish_surface_id"]
