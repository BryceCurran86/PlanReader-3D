"""Coverage records for the 3D audit render (shadow / read-only).

The audit render must show every object PlanReader interpreted together with
whether it is accounted for by a take-off row.  This module owns only the
*interface* the renderer consumes: one frozen ``AuditObjectRecord`` per object
plus a ``CoverageRecordProvider`` protocol.  A coverage registry (when one lands
on main) plugs in by implementing the protocol; nothing here is a competing
coverage authority.

``DefaultCoverageProvider`` is the fail-closed stand-in used when no registry
exists.  It can only ever *lower* trust relative to the inputs it is given:

* an object is ``ACCOUNTED`` only when the caller supplies at least one
  take-off link and every supplied link is complete;
* an object with no take-off link is ``UNACCOUNTED``;
* an object the authority modules deliberately refuse (typed refusal reason on
  the object) or that cannot be placed at all is ``ABSTAINED``;
* partial links or unresolved attributes downgrade to ``PARTIAL``.

It never reads or changes ``takeoff_eligible`` / ``deduction_authority`` and it
never fabricates a take-off row id.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple


class CoverageState(str, Enum):
    ACCOUNTED = "ACCOUNTED"
    PARTIAL = "PARTIAL"
    UNACCOUNTED = "UNACCOUNTED"
    ABSTAINED = "ABSTAINED"


# Opening ``physical_state`` values (see pb_bim_viewer) where an authority
# module deliberately refuses to place / deduct the opening.
REFUSED_PHYSICAL_STATES = frozenset(
    {"wrong_host", "wrong_level", "invalid_geometry", "conflict_overlap", "evidence_only"}
)

REASON_NO_TAKEOFF_LINK = "no_takeoff_link"
REASON_PARTIAL_TAKEOFF_LINK = "partial_takeoff_link"
REASON_NOT_DRAWABLE = "not_drawable"


@dataclass(frozen=True)
class TakeoffLink:
    """A link from a model object to one take-off row."""

    row_id: str
    complete: bool = True


@dataclass(frozen=True)
class AuditObjectRecord:
    object_id: str
    object_type: str
    coverage_state: CoverageState
    reason_code: Optional[str] = None
    source_pages: Tuple[int, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    takeoff_row_ids: Tuple[str, ...] = ()
    geometry_basis: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "coverage_state": self.coverage_state.value,
            "reason_code": self.reason_code,
            "source_pages": list(self.source_pages),
            "provenance": copy.deepcopy(dict(self.provenance)),
            "takeoff_row_ids": list(self.takeoff_row_ids),
            "geometry_basis": self.geometry_basis,
        }


class CoverageRecordProvider(Protocol):
    def record_for(self, obj: Mapping[str, Any]) -> AuditObjectRecord:
        """Return the coverage record for one scene object (see pb_audit_render)."""


def _source_pages(obj: Mapping[str, Any]) -> Tuple[int, ...]:
    prov = obj.get("provenance") or {}
    pages: List[int] = []
    page = prov.get("page_number")
    if isinstance(page, int) and page > 0:
        pages.append(page)
    for extra in obj.get("source_pages") or ():
        if isinstance(extra, int) and extra > 0 and extra not in pages:
            pages.append(extra)
    return tuple(sorted(pages))


class DefaultCoverageProvider:
    """Fail-closed stand-in used until a coverage registry exists."""

    def __init__(self, takeoff_links: Optional[Mapping[str, Sequence[TakeoffLink]]] = None):
        self._links: Dict[str, Tuple[TakeoffLink, ...]] = {
            str(k): tuple(v) for k, v in (takeoff_links or {}).items()
        }

    def record_for(self, obj: Mapping[str, Any]) -> AuditObjectRecord:
        oid = str(obj.get("id"))
        links = self._links.get(oid, ())
        state, reason = self._classify(obj, links)
        return AuditObjectRecord(
            object_id=oid,
            object_type=str(obj.get("type") or "UNKNOWN"),
            coverage_state=state,
            reason_code=reason,
            source_pages=_source_pages(obj),
            provenance=copy.deepcopy(dict(obj.get("provenance") or {})),
            takeoff_row_ids=tuple(link.row_id for link in links),
            geometry_basis=str((obj.get("geometry") or {}).get("basis") or "none"),
        )

    @staticmethod
    def _classify(
        obj: Mapping[str, Any], links: Sequence[TakeoffLink]
    ) -> Tuple[CoverageState, Optional[str]]:
        refusal = obj.get("refusal_reason")
        if refusal:
            return CoverageState.ABSTAINED, str(refusal)
        if str(obj.get("physical_state") or "") in REFUSED_PHYSICAL_STATES:
            return CoverageState.ABSTAINED, str(obj.get("physical_state"))
        if not links:
            return CoverageState.UNACCOUNTED, REASON_NO_TAKEOFF_LINK
        if not all(link.complete for link in links):
            return CoverageState.PARTIAL, REASON_PARTIAL_TAKEOFF_LINK
        unresolved = obj.get("unresolved_attributes") or ()
        if unresolved:
            return CoverageState.PARTIAL, "unresolved:" + ",".join(sorted(map(str, unresolved)))
        return CoverageState.ACCOUNTED, None


def summarise_records(records: Iterable[AuditObjectRecord]) -> Dict[str, Dict[str, int]]:
    """Counts by object type and coverage state (deterministic key order)."""
    out: Dict[str, Dict[str, int]] = {}
    for rec in records:
        by_state = out.setdefault(rec.object_type, {s.value: 0 for s in CoverageState})
        by_state[rec.coverage_state.value] += 1
    return {k: out[k] for k in sorted(out)}
