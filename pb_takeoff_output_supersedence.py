"""Fail-closed preservation of prior source-closed customer drafts.

A fresh production run may explicitly ABSTAIN/BLOCK/CONFLICT on a physical
quantity that was source-closed in the immediately prior run. Replacing every
PlanReader-owned row wholesale would erase that still-proven prior output.

This module preserves only prior unreviewed commercial projections whose exact
source SHA, semantic quantity and physical entity identities match a current
blocked claim. Source changes, disappeared objects, unmatched identities and
non-commercial legacy rows are never preserved.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import QuantityEvidence


@dataclass(frozen=True, order=True)
class BlockedCommercialClaimKey:
    source_sha256: str
    family: str
    semantic_key: str
    physical_entity_ids: tuple[str, ...]


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm_status(value: Any) -> str:
    return _clean(value).lower().replace("-", "_").replace(" ", "_")


def blocked_commercial_claim_key(
    quantity: QuantityEvidence,
    *,
    source_sha256: str,
) -> BlockedCommercialClaimKey | None:
    """Return an exact blocked-claim key, else None.

    This never turns an unavailable identity into a preservation entitlement.
    """
    if not isinstance(quantity, QuantityEvidence):
        raise TypeError("quantity must be QuantityEvidence")
    status = _norm_status(quantity.status)
    blocked = bool(
        quantity.abstained
        or quantity.blocking_reasons
        or status in {"blocked", "conflict", "abstained"}
        or "conflict" in status
    )
    if not blocked:
        return None

    sha = _clean(source_sha256).lower()
    entity_ids = tuple(sorted({_clean(v) for v in quantity.input_entity_ids if _clean(v)}))
    if not sha or not entity_ids:
        return None
    return BlockedCommercialClaimKey(
        source_sha256=sha,
        family=_clean(quantity.family),
        semantic_key=_clean(quantity.semantic_key),
        physical_entity_ids=entity_ids,
    )


def _commercial_projection_key_from_provenance(
    row: Mapping[str, Any],
) -> BlockedCommercialClaimKey | None:
    """Read exact source/physical identity from commercial projection provenance."""
    if not isinstance(row, Mapping):
        raise TypeError("row must be a mapping")

    notes = row.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        return None
    try:
        provenance = json.loads(notes)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(provenance, Mapping):
        return None
    if _clean(provenance.get("adapter")) != "commercial_takeoff":
        return None

    q = provenance.get("quantity")
    trace = provenance.get("source_trace")
    if not isinstance(q, Mapping) or not isinstance(trace, Mapping):
        return None
    if bool(q.get("abstained")):
        return None

    ids = tuple(
        sorted(
            {
                _clean(v)
                for v in (q.get("input_entity_ids") or ())
                if _clean(v)
            }
        )
    )
    sha = _clean(trace.get("source_sha256")).lower()
    family = _clean(q.get("family"))
    semantic_key = _clean(q.get("semantic_key"))
    if not sha or not family or not semantic_key or not ids:
        return None

    # The customer row must still describe the same sealed quantity.
    try:
        row_value = float(row.get("quantity"))
        provenance_value = float(q.get("value"))
    except (TypeError, ValueError, OverflowError):
        return None
    if row_value != provenance_value:
        return None

    return BlockedCommercialClaimKey(
        source_sha256=sha,
        family=family,
        semantic_key=semantic_key,
        physical_entity_ids=ids,
    )


def prior_commercial_projection_key(
    row: Mapping[str, Any],
) -> BlockedCommercialClaimKey | None:
    """Return exact provenance for an unreviewed commercial projection."""
    if _clean(row.get("quantity_status")).lower() != "to review":
        return None
    return _commercial_projection_key_from_provenance(row)


def prior_reviewed_commercial_projection_key(
    row: Mapping[str, Any],
) -> BlockedCommercialClaimKey | None:
    """Return exact provenance only for estimator-reviewed AI output."""
    key = _commercial_projection_key_from_provenance(row)
    if key is None:
        return None
    try:
        from pb_takeoff_authority_v164 import ai_takeoff_authority
        approved, _reason = ai_takeoff_authority(row)
    except Exception:
        return None
    return key if approved else None


def select_prior_commercial_rows_to_preserve(
    prior_rows: Iterable[Mapping[str, Any]],
    *,
    blocked_claim_keys: Iterable[BlockedCommercialClaimKey],
    replacement_rows: Iterable[Mapping[str, Any]] = (),
) -> tuple[Mapping[str, Any], ...]:
    """Return prior rows safe to carry forward across a blocked rerun.

    A current replacement with the same exact provenance key wins. A prior row
    is preserved only when a current blocked claim proves the same source and
    physical identity still exist.
    """
    blocked = set(blocked_claim_keys)
    replacement_keys = {
        key
        for row in replacement_rows
        if (key := prior_commercial_projection_key(row)) is not None
    }
    preserved: list[Mapping[str, Any]] = []
    seen: set[BlockedCommercialClaimKey] = set()
    for row in prior_rows:
        key = prior_commercial_projection_key(row)
        if key is None or key not in blocked or key in replacement_keys or key in seen:
            continue
        seen.add(key)
        preserved.append(row)
    return tuple(preserved)


def select_prior_reviewed_row_ids_to_retain(
    prior_rows: Iterable[Mapping[str, Any]],
    *,
    blocked_claim_keys: Iterable[BlockedCommercialClaimKey],
    replacement_rows: Iterable[Mapping[str, Any]] = (),
) -> tuple[int, ...]:
    """Keep reviewed AI rows in-place across an exact blocked rerun.

    Retaining the database row, rather than reserializing through the core
    21-field writer, preserves commercial-authority and AI-review columns.
    Duplicate reviewed rows for the same exact physical claim fail closed.
    """
    blocked = set(blocked_claim_keys)
    replacement_keys = {
        key
        for row in replacement_rows
        if (key := _commercial_projection_key_from_provenance(row)) is not None
    }
    retained: list[int] = []
    seen: set[BlockedCommercialClaimKey] = set()
    for row in prior_rows:
        key = prior_reviewed_commercial_projection_key(row)
        if key is None or key not in blocked or key in replacement_keys:
            continue
        if key in seen:
            raise ValueError(
                "duplicate reviewed commercial rows share one physical claim"
            )
        seen.add(key)
        raw_id = row.get("id")
        if isinstance(raw_id, bool):
            raise ValueError("reviewed commercial row id must be a positive integer")
        try:
            row_id = int(raw_id)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "reviewed commercial row id must be a positive integer"
            ) from exc
        if row_id <= 0:
            raise ValueError("reviewed commercial row id must be a positive integer")
        retained.append(row_id)
    return tuple(sorted(retained))


__all__ = [
    "BlockedCommercialClaimKey",
    "blocked_commercial_claim_key",
    "prior_commercial_projection_key",
    "prior_reviewed_commercial_projection_key",
    "select_prior_commercial_rows_to_preserve",
    "select_prior_reviewed_row_ids_to_retain",
]
