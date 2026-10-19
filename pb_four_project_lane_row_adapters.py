"""Adapt lane-owned first-gate receipts into four-project report rows.

Project keys are report labels only — never prediction inputs.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

LOT16_PROJECT_KEY = "au_qld_lot16_power"
MARYBOROUGH_PROJECT_KEY = "au_qld_maryborough_service_station"


def lot16_handoff_to_four_project_rows(
    opening_decisions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in opening_decisions:
        oid = str(decision.get("physical_opening_id") or "").strip()
        gate = str(decision.get("first_remaining_gate") or "").strip()
        sha = str(decision.get("source_sha256") or "").strip()
        snap = str(decision.get("snapshot_id") or "").strip()
        if not oid or not gate or not sha or not snap:
            raise ValueError("incomplete Lot16 handoff decision row")
        rows.append({
            "project_key": LOT16_PROJECT_KEY,
            "physical_object_id": oid,
            "first_remaining_gate": gate,
            "source_sha256": sha,
            "snapshot_id": snap,
            "decision_scope_id": (
                str(decision.get("source_decision_scope_id") or "").strip() or None
            ),
            "prior_signed_quantity_id": (
                str(decision.get("prior_signed_quantity_id") or "").strip() or None
            ),
        })
    return rows


def maryborough_room_scopes_to_four_project_rows(
    scope_first_failures: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
) -> list[dict[str, Any]]:
    sha = str(source_sha256 or "").strip()
    if not sha:
        raise ValueError("Maryborough source SHA required")
    rows: list[dict[str, Any]] = []
    for scope in scope_first_failures:
        scope_id = str(scope.get("decision_scope_id") or "").strip()
        gate = str(scope.get("first_unproved_authority") or "").strip()
        snap = str(scope.get("snapshot_id") or "").strip()
        if not scope_id or not gate or not snap:
            raise ValueError("incomplete Maryborough room first-gate scope")
        if str(scope.get("source_sha256") or "").strip() not in ("", sha):
            raise ValueError("Maryborough scope source SHA mismatch")
        rows.append({
            "project_key": MARYBOROUGH_PROJECT_KEY,
            "physical_object_id": scope_id,
            "first_remaining_gate": gate,
            "source_sha256": sha,
            "snapshot_id": snap,
            "decision_scope_id": scope_id,
            "prior_signed_quantity_id": None,
        })
    return rows
