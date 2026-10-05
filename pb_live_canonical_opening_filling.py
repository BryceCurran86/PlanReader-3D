"""Canonical door/window filling identities from authenticated physical openings.

This projection does not discover an opening, classify a kind, or create a
quantity. It consumes only LiveCanonicalOpeningObject values whose upstream
opening-kind authority already resolved door/window without conflict.

The installed filling is a different physical/canonical proposition from the
wall void that hosts it. The filling identity is therefore derived from the
producer-owned physical opening identity plus the authenticated kind, while
source/evidence lineage remains metadata rather than physical identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


LIVE_CANONICAL_OPENING_FILLING_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_OPENING_FILLING_RESOLVED = "live_canonical_opening_filling_resolved"
LIVE_CANONICAL_OPENING_FILLING_PARTIAL = "live_canonical_opening_filling_partial"
LIVE_CANONICAL_OPENING_FILLING_UNAVAILABLE = "live_canonical_opening_filling_unavailable"
LIVE_CANONICAL_OPENING_FILLING_CONFLICT = "live_canonical_opening_filling_conflict"


@dataclass(frozen=True)
class LiveCanonicalOpeningFillingObject:
    canonical_filling_id: str
    physical_filling_id: str
    physical_opening_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    filling_kind: str
    type_mark: Optional[str]
    host_wall_id: Optional[str]
    evidence_ids: tuple[str, ...]
    opening_geometry_complete: bool
    geometry_complete: bool = False
    metric_geometry_complete: bool = False
    commercial_quantity_authority: bool = False
    schema_version: str = LIVE_CANONICAL_OPENING_FILLING_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_filling_id": self.canonical_filling_id,
            "physical_filling_id": self.physical_filling_id,
            "physical_opening_id": self.physical_opening_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "filling_kind": self.filling_kind,
            "type_mark": self.type_mark,
            "host_wall_id": self.host_wall_id,
            "evidence_ids": list(self.evidence_ids),
            "opening_geometry_complete": self.opening_geometry_complete,
            "geometry_complete": self.geometry_complete,
            "metric_geometry_complete": self.metric_geometry_complete,
            "commercial_quantity_authority": self.commercial_quantity_authority,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LiveCanonicalDoorObject(LiveCanonicalOpeningFillingObject):
    pass


@dataclass(frozen=True)
class LiveCanonicalWindowObject(LiveCanonicalOpeningFillingObject):
    pass


@dataclass(frozen=True)
class LiveCanonicalOpeningFillingProjection:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    doors: tuple[LiveCanonicalDoorObject, ...]
    windows: tuple[LiveCanonicalWindowObject, ...]
    unresolved_opening_ids: tuple[str, ...] = ()
    schema_version: str = LIVE_CANONICAL_OPENING_FILLING_SCHEMA_VERSION


def _clean(value: object) -> str:
    return str(value or "").strip()


def _filling_from_opening(
    opening: LiveCanonicalOpeningObject,
) -> LiveCanonicalOpeningFillingObject | None:
    if type(opening) is not LiveCanonicalOpeningObject:
        raise TypeError("openings must contain LiveCanonicalOpeningObject values")

    kind = _clean(opening.opening_kind).lower()
    if kind not in {"door", "window"}:
        return None

    physical_opening_id = _clean(opening.physical_opening_id)
    lineage = (
        _clean(opening.document_id),
        _clean(opening.revision_id),
        _clean(opening.source_sha256),
        _clean(opening.snapshot_id),
        _clean(opening.page_id),
    )
    if (
        not physical_opening_id
        or not all(lineage)
        or not opening.evidence_ids
    ):
        return None

    physical_filling_id = stable_contract_id(
        "physical_opening_filling",
        {
            "physical_opening_id": physical_opening_id,
            "filling_kind": kind,
        },
        digest_chars=32,
    )
    cls = LiveCanonicalDoorObject if kind == "door" else LiveCanonicalWindowObject
    return cls(
        canonical_filling_id=physical_filling_id,
        physical_filling_id=physical_filling_id,
        physical_opening_id=physical_opening_id,
        document_id=lineage[0],
        revision_id=lineage[1],
        source_sha256=lineage[2],
        snapshot_id=lineage[3],
        page_id=lineage[4],
        viewport_id=opening.viewport_id,
        filling_kind=kind,
        type_mark=opening.type_mark,
        host_wall_id=opening.host_wall_id,
        evidence_ids=tuple(opening.evidence_ids),
        opening_geometry_complete=bool(opening.geometry_complete),
    )


def project_live_canonical_opening_fillings(
    openings: Sequence[LiveCanonicalOpeningObject],
) -> LiveCanonicalOpeningFillingProjection:
    by_id: dict[str, LiveCanonicalOpeningFillingObject] = {}
    unresolved: list[str] = []

    for opening in openings:
        filling = _filling_from_opening(opening)
        if filling is None:
            if type(opening) is not LiveCanonicalOpeningObject:
                raise TypeError("openings must contain LiveCanonicalOpeningObject values")
            unresolved.append(_clean(opening.physical_opening_id) or _clean(opening.canonical_opening_id))
            continue
        prior = by_id.get(filling.physical_filling_id)
        if prior is not None and prior != filling:
            return LiveCanonicalOpeningFillingProjection(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(LIVE_CANONICAL_OPENING_FILLING_CONFLICT,),
                doors=(),
                windows=(),
                unresolved_opening_ids=tuple(sorted(set(unresolved))),
            )
        by_id[filling.physical_filling_id] = filling

    doors = tuple(
        sorted(
            (item for item in by_id.values() if type(item) is LiveCanonicalDoorObject),
            key=lambda item: item.physical_filling_id,
        )
    )
    windows = tuple(
        sorted(
            (item for item in by_id.values() if type(item) is LiveCanonicalWindowObject),
            key=lambda item: item.physical_filling_id,
        )
    )
    unresolved_ids = tuple(sorted(set(value for value in unresolved if value)))

    if doors or windows:
        return LiveCanonicalOpeningFillingProjection(
            status=(
                EvidenceResolutionStatus.CANDIDATE
                if unresolved_ids
                else EvidenceResolutionStatus.CORROBORATED
            ),
            reason_codes=(
                (LIVE_CANONICAL_OPENING_FILLING_PARTIAL,)
                if unresolved_ids
                else (LIVE_CANONICAL_OPENING_FILLING_RESOLVED,)
            ),
            doors=doors,
            windows=windows,
            unresolved_opening_ids=unresolved_ids,
        )

    return LiveCanonicalOpeningFillingProjection(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(LIVE_CANONICAL_OPENING_FILLING_UNAVAILABLE,),
        doors=(),
        windows=(),
        unresolved_opening_ids=unresolved_ids,
    )


__all__ = [
    "LIVE_CANONICAL_OPENING_FILLING_CONFLICT",
    "LIVE_CANONICAL_OPENING_FILLING_PARTIAL",
    "LIVE_CANONICAL_OPENING_FILLING_RESOLVED",
    "LIVE_CANONICAL_OPENING_FILLING_SCHEMA_VERSION",
    "LIVE_CANONICAL_OPENING_FILLING_UNAVAILABLE",
    "LiveCanonicalDoorObject",
    "LiveCanonicalOpeningFillingObject",
    "LiveCanonicalOpeningFillingProjection",
    "LiveCanonicalWindowObject",
    "project_live_canonical_opening_fillings",
]
