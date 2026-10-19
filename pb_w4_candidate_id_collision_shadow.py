"""D5 — W4 candidate-ID collision shadow (GPT2 #3344 Task A precursor).

Detects when the same ``wall_candidate_id`` appears with distinct path
fingerprints or source primitive sets. Retains both records; never last-write
wins, nearest, or first.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def _clean(value: object) -> str:
    return str(value or "").strip()


def _fingerprint(record: Mapping[str, Any]) -> tuple[Any, ...]:
    path = record.get("canonical_path_fingerprint")
    if path is None:
        pts = record.get("centerline_pts") or ()
        path = tuple(tuple(float(x) for x in point) for point in pts)
    primitives = tuple(sorted(_clean(p) for p in (record.get("source_primitive_ids") or ()) if _clean(p)))
    return (path, primitives)


def build_w4_candidate_id_collision_shadow(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Report candidate-ID collisions without discarding either record."""
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise TypeError("wall record must be a mapping")
        wid = _clean(record.get("wall_candidate_id"))
        if not wid:
            raise ValueError("wall_candidate_id required")
        by_id[wid].append({
            "index": index,
            "wall_candidate_id": wid,
            "fingerprint": _fingerprint(record),
            "source_primitive_ids": list(
                sorted(_clean(p) for p in (record.get("source_primitive_ids") or ()) if _clean(p))
            ),
        })

    collisions = []
    for wid, rows in sorted(by_id.items()):
        if len(rows) < 2:
            continue
        fingerprints = {row["fingerprint"] for row in rows}
        if len(fingerprints) == 1:
            # Same ID, identical fingerprint — duplicate address, not distinct walls.
            kind = "duplicate_identical_wall_candidate_address"
        else:
            kind = "distinct_geometry_under_shared_wall_candidate_id"
        collisions.append({
            "wall_candidate_id": wid,
            "collision_kind": kind,
            "record_count": len(rows),
            "distinct_fingerprint_count": len(fingerprints),
            "records": rows,
            "merged_into_single_physical_wall": False,
            "last_write_wins_applied": False,
        })

    return {
        "status": "UNPUBLISHED_W4_CANDIDATE_ID_COLLISION_SHADOW",
        "collision_count": len(collisions),
        "collisions": collisions,
        "records_retained": True,
        "physical_equivalence_granted": False,
        "host_granted": False,
        "measurement_published": False,
        "shadow_only": True,
        "limitation": (
            "Diagnostic only. Shared wall_candidate_id with distinct fingerprints "
            "must retain both records until producer equivalence proves SAME or "
            "DISTINCT. Never resolve by insertion order."
        ),
    }
