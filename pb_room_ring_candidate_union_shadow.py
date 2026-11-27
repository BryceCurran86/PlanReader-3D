"""Report only (#4764 7227402524, C06): room-ring candidates of two builder settings, combined without choosing.

The layered builder run as usual and run with ``door_jamb_returns`` each find candidate rings; neither is safe alone
(the option gains one room and loses another). Identical rings agree. A ring only one run finds stays a candidate when
no different candidate ring overlaps it, so an open region in the other run never removes a room. Any overlap between
different candidate rings abstains every ring involved -- never by size, score or run. Each ring keeps the doorway
closures that bound it; a closure edge without source paths abstains its ring. Nothing is promoted or published and no
live path imports this.
"""
from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon

from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT
from pb_migration_contracts import EvidenceResolutionStatus

DEFAULT_RUN, ALTERNATIVE_RUN = "default", "door_jamb_returns"
REASON_AGREED = "both_runs_agree"
REASON_ONE_RUN = "one_run_only_without_overlap"
REASON_CONFLICT = "conflicting_room_candidates"
REASON_NO_PROVENANCE = "closure_without_source_provenance"
REASON_OWNERSHIP = "runs_not_from_the_same_source_page"
_CLOSURE = "layered_doorway_closure:"


def _key(ring: Any) -> tuple[tuple[float, float], ...]:
    return tuple(sorted((round(x, 3), round(y, 3)) for x, y in ring.polygon_pdf_pts))


def _overlapping(a: Polygon, b: Polygon) -> bool:
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds
    if ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0:
        return False
    return a.intersection(b).area > NOISE_PT * min(a.length, b.length)  # a shared edge is not an overlap


def union_room_ring_candidates(default_result: Any, alternative_result: Any) -> list[dict]:
    """One entry per distinct candidate ring of either run, with its status, runs and doorway closures."""
    runs = ((DEFAULT_RUN, default_result), (ALTERNATIVE_RUN, alternative_result))
    same_page = len({(ring.source_sha256, ring.page_index) for _name, result in runs for ring in result.rings}) <= 1
    entries: dict[tuple, dict] = {}
    for name, result in runs:
        closures = {closure.closure_id: closure for closure in result.closures}
        for ring in result.rings:
            if ring.status is not EvidenceResolutionStatus.CANDIDATE:
                continue
            entry = entries.setdefault(_key(ring), {"polygon_pdf_pts": tuple(ring.polygon_pdf_pts), "runs": [],
                                                    "record_ids": {}, "closures": {}, "unproven": False})
            entry["runs"].append(name)
            entry["record_ids"][name] = ring.record_id
            used = sorted({owner[len(_CLOSURE):] for owners in ring.edge_owner_ids for owner in owners
                           if owner.startswith(_CLOSURE)})
            entry["unproven"] |= any(i not in closures or not closures[i].native_path_indices for i in used)
            entry["closures"][name] = tuple((i, closures[i].kind, tuple(closures[i].native_path_indices))
                                            for i in used if i in closures)
    keys = sorted(entries)
    shapes = {key: Polygon(entries[key]["polygon_pdf_pts"]) for key in keys}
    conflicted = {key for position, key in enumerate(keys) for other in keys[position + 1:]
                  if _overlapping(shapes[key], shapes[other]) for key in (key, other)}
    found = []
    for key in keys:
        entry = entries[key]
        if not same_page:
            reason = REASON_OWNERSHIP
        elif key in conflicted:
            reason = REASON_CONFLICT
        elif entry["unproven"]:
            reason = REASON_NO_PROVENANCE
        else:
            reason = REASON_AGREED if len(set(entry["runs"])) == 2 else REASON_ONE_RUN
        found.append({
            "status": EvidenceResolutionStatus.CANDIDATE if reason in (REASON_AGREED, REASON_ONE_RUN)
            else EvidenceResolutionStatus.ABSTAINED,
            "reason": reason,
            "runs": tuple(sorted(set(entry["runs"]))),
            "record_ids": dict(sorted(entry["record_ids"].items())),
            "closures": dict(sorted(entry["closures"].items())),
            "polygon_pdf_pts": entry["polygon_pdf_pts"],
        })
    return found
