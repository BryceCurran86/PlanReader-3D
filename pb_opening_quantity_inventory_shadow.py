"""Shadow inventory: first-gate audit, signed-ID retention, duplicate rejection.

Mission items 1 / 23 / 24 (Cursor quantity-recovery batch A1).

This module does **not** publish measurements, counts, customer rows, or
benchmark scores. It consumes the existing GPT1 review queue shape produced by
``assess_gpt1_opening_candidates`` and adds:

- inventory completeness vs an explicit physical-opening ID set
- immutable retention of prior signed quantity identities
- fail-closed rejection of duplicate physical IDs or duplicate quantity IDs
- stale quantity rejection when the source root no longer matches

Reuse only. Do not invent door height, opening count, or filling kind.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates


_SIGNED_RETENTION_OK = "signed_quantity_identities_retained"
_DUPLICATE_PHYSICAL = "duplicate_physical_opening_identity"
_DUPLICATE_QUANTITY = "duplicate_signed_quantity_identity"
_STALE_QUANTITY = "stale_signed_quantity_source_root_mismatch"
_MISSING_PHYSICAL = "inventory_physical_opening_missing"
_UNEXPECTED_PHYSICAL = "inventory_unexpected_physical_opening"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _source_root_tuple(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _clean(row.get("document_id")),
        _clean(row.get("revision_id")),
        _clean(row.get("source_sha256")),
        _clean(row.get("snapshot_id")),
    )


def reject_duplicate_and_stale_quantity_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_source_root: Mapping[str, str],
) -> dict[str, Any]:
    """Fail closed on duplicate physical/quantity IDs or stale source roots."""
    required = ("document_id", "revision_id", "source_sha256", "snapshot_id")
    if any(not _clean(expected_source_root.get(k)) for k in required):
        raise ValueError("expected source root incomplete")
    expected = tuple(_clean(expected_source_root[k]) for k in required)

    physical_ids: list[str] = []
    quantity_ids: list[str] = []
    blockers: list[dict[str, str]] = []

    for row in rows:
        pid = _clean(row.get("physical_opening_id"))
        if not pid:
            raise ValueError("physical opening identity required")
        physical_ids.append(pid)
        root = _source_root_tuple(row)
        if any(not part for part in root):
            raise ValueError("row source root incomplete")
        if root != expected:
            blockers.append({
                "physical_opening_id": pid,
                "blocker": _STALE_QUANTITY,
            })
        qid = _clean(row.get("quantity_id"))
        if qid:
            quantity_ids.append(qid)

    physical_counts = Counter(physical_ids)
    quantity_counts = Counter(quantity_ids)
    for pid, count in sorted(physical_counts.items()):
        if count > 1:
            blockers.append({
                "physical_opening_id": pid,
                "blocker": _DUPLICATE_PHYSICAL,
            })
    for qid, count in sorted(quantity_counts.items()):
        if count > 1:
            blockers.append({
                "physical_opening_id": "",
                "signed_quantity_id": qid,
                "blocker": _DUPLICATE_QUANTITY,
            })

    blockers_sorted = sorted(
        blockers,
        key=lambda b: (b["blocker"], b.get("physical_opening_id", ""), b.get("signed_quantity_id", "")),
    )
    return {
        "status": (
            "INVENTORY_DUPLICATE_OR_STALE_BLOCKED"
            if blockers_sorted
            else "INVENTORY_IDENTITY_CLEAN"
        ),
        "blockers": blockers_sorted,
        "physical_opening_count": len(physical_ids),
        "signed_quantity_count": len(quantity_ids),
        "publication_allowed": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }


def retain_signed_quantity_identities(
    rows: Sequence[Mapping[str, Any]],
    *,
    required_signed_quantity_ids: Sequence[str],
) -> dict[str, Any]:
    """Prove every historically signed quantity ID is still present exactly once."""
    cleaned_required = [_clean(qid) for qid in required_signed_quantity_ids if _clean(qid)]
    required = tuple(sorted(set(cleaned_required)))
    if len(required) != len(cleaned_required):
        raise ValueError("required signed quantity identities must be unique")
    present = Counter(
        _clean(row.get("quantity_id"))
        for row in rows
        if _clean(row.get("quantity_id"))
    )
    missing = [qid for qid in required if present.get(qid, 0) == 0]
    duplicated = [qid for qid in required if present.get(qid, 0) > 1]
    retained = not missing and not duplicated
    return {
        "status": _SIGNED_RETENTION_OK if retained else "signed_quantity_identity_retention_failed",
        "required_signed_quantity_ids": list(required),
        "missing_signed_quantity_ids": missing,
        "duplicated_signed_quantity_ids": duplicated,
        "retained": retained,
        "publication_allowed": False,
        "shadow_only": True,
    }


def audit_opening_quantity_inventory(
    rows: list[dict],
    canonical: list[dict],
    f07: dict,
    *,
    source_root: dict,
    expected_physical_opening_ids: Sequence[str] | None = None,
    required_signed_quantity_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Full shadow inventory: first gates + signed retention + duplicate/stale checks."""
    identity_gate = reject_duplicate_and_stale_quantity_rows(
        rows, expected_source_root=source_root
    )
    if identity_gate["blockers"]:
        return {
            "status": "UNPUBLISHED_OPENING_INVENTORY_BLOCKED",
            "identity_gate": identity_gate,
            "gpt1_queue": None,
            "signed_retention": None,
            "inventory_completeness": None,
            "measurement_published": False,
            "customer_seal_granted": False,
            "opening_count_granted": False,
            "benchmark_score_granted": False,
            "shadow_only": True,
        }

    queue = assess_gpt1_opening_candidates(
        rows, canonical, f07, source_root=source_root
    )
    retention = retain_signed_quantity_identities(
        rows, required_signed_quantity_ids=required_signed_quantity_ids
    )

    completeness = None
    if expected_physical_opening_ids is not None:
        expected = {_clean(pid) for pid in expected_physical_opening_ids if _clean(pid)}
        observed = {_clean(row.get("physical_opening_id")) for row in rows}
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        completeness = {
            "status": (
                "INVENTORY_COMPLETE"
                if not missing and not unexpected
                else "INVENTORY_MISMATCH"
            ),
            "missing_physical_opening_ids": missing,
            "unexpected_physical_opening_ids": unexpected,
            "expected_count": len(expected),
            "observed_count": len(observed),
            "reasons": (
                ([_MISSING_PHYSICAL] if missing else [])
                + ([_UNEXPECTED_PHYSICAL] if unexpected else [])
            ),
        }

    return {
        "status": "UNPUBLISHED_OPENING_QUANTITY_INVENTORY_SHADOW",
        "identity_gate": identity_gate,
        "gpt1_queue": queue,
        "signed_retention": retention,
        "inventory_completeness": completeness,
        "first_gate_counts": queue["first_gate_counts"],
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
