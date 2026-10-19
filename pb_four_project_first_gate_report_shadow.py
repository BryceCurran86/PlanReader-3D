"""Shadow harness: per-object first-failing-authority reports (mission 28).

Aggregates lane-supplied first-gate rows for the four frozen Full Plan V2
projects. Does not run the evaluator, read gold quantities, or invent gates.
Project labels are report keys only — never prediction inputs.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


_REQUIRED_ROW_FIELDS = (
    "project_key",
    "physical_object_id",
    "first_remaining_gate",
    "source_sha256",
    "snapshot_id",
)


def build_four_project_first_gate_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    required_project_keys: Sequence[str],
) -> dict[str, Any]:
    """Stable per-object first-gate ledger with completeness over project keys."""
    required = tuple(dict.fromkeys(str(k).strip() for k in required_project_keys if str(k).strip()))
    if not required:
        raise ValueError("required project keys needed")

    normalised: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for field in _REQUIRED_ROW_FIELDS:
            if not str(row.get(field) or "").strip():
                raise ValueError(f"missing {field}")
        key = (str(row["project_key"]).strip(), str(row["physical_object_id"]).strip())
        if key in seen:
            raise ValueError("duplicate project/object first-gate row")
        seen.add(key)
        normalised.append({
            "project_key": key[0],
            "physical_object_id": key[1],
            "first_remaining_gate": str(row["first_remaining_gate"]).strip(),
            "source_sha256": str(row["source_sha256"]).strip(),
            "snapshot_id": str(row["snapshot_id"]).strip(),
            "decision_scope_id": str(row.get("decision_scope_id") or "").strip() or None,
            "prior_signed_quantity_id": str(row.get("prior_signed_quantity_id") or "").strip() or None,
            "measurement_published": False,
            "benchmark_matched": None,
        })

    by_project: dict[str, list[dict[str, Any]]] = {k: [] for k in required}
    unexpected_projects: list[str] = []
    for row in normalised:
        if row["project_key"] not in by_project:
            unexpected_projects.append(row["project_key"])
            continue
        by_project[row["project_key"]].append(row)

    for project_key in by_project:
        by_project[project_key] = sorted(
            by_project[project_key], key=lambda r: r["physical_object_id"]
        )

    gate_counts = {
        project_key: dict(sorted(Counter(
            r["first_remaining_gate"] for r in project_rows
        ).items()))
        for project_key, project_rows in by_project.items()
    }
    missing_projects = [k for k in required if not by_project[k]]

    return {
        "status": "UNPUBLISHED_FOUR_PROJECT_FIRST_GATE_SHADOW",
        "required_project_keys": list(required),
        "missing_project_keys": missing_projects,
        "unexpected_project_keys": sorted(set(unexpected_projects)),
        "objects_by_project": by_project,
        "first_gate_counts_by_project": gate_counts,
        "total_object_rows": len(normalised),
        "evaluator_invoked": False,
        "gold_values_consumed": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
