"""Producer-owned proof for physical wall classes with zero openings.

This authority closes a specific gap in the gross/net wall chain: a complete
physical wall may legitimately contain no opening, so it has no
OpeningHostFrameEvidence from which to derive a wall-local frame.

A positive ZeroOpeningWallFrameRecord is published only when all of the
following are re-proven from sealed authorities:

* the exact source page wall-candidate scope is complete;
* the selected wall is an unambiguous producer-owned equivalence representative;
* the page opening universe is complete;
* every opening in that complete universe resolves to a producer-owned physical
  opening and a sealed whole-wall host frame;
* none of those opening host frames intersects the selected physical-wall
  equivalence class; and
* every representation in the selected wall class agrees on one straight,
  source-derived path.

No caller wall geometry, opening list/count, completeness flag, length, area,
or "has no opening" assertion enters this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_frame_authority import (
    OpeningHostFrameAuthority,
    OpeningHostFrameSelector,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector


ZERO_OPENING_WALL_FRAME_SCHEMA_VERSION = "1.0.0"
ZERO_OPENING_WALL_FRAME_RESOLVED = "zero_opening_wall_frame_resolved"
ZERO_OPENING_WALL_FRAME_WALL_UNRESOLVED = "zero_opening_wall_frame_wall_unresolved"
ZERO_OPENING_WALL_FRAME_SCOPE_INCOMPLETE = "zero_opening_wall_frame_scope_incomplete"
ZERO_OPENING_WALL_FRAME_OPENING_UNIVERSE_INCOMPLETE = (
    "zero_opening_wall_frame_opening_universe_incomplete"
)
ZERO_OPENING_WALL_FRAME_OPENING_UNRESOLVED = (
    "zero_opening_wall_frame_opening_unresolved"
)
ZERO_OPENING_WALL_FRAME_HOST_FRAME_UNRESOLVED = (
    "zero_opening_wall_frame_host_frame_unresolved"
)
ZERO_OPENING_WALL_FRAME_HAS_OPENING = "zero_opening_wall_frame_has_opening"
ZERO_OPENING_WALL_FRAME_GEOMETRY_UNRESOLVED = (
    "zero_opening_wall_frame_geometry_unresolved"
)
ZERO_OPENING_WALL_FRAME_LINEAGE_MISMATCH = (
    "zero_opening_wall_frame_lineage_mismatch"
)
ZERO_OPENING_WALL_FRAME_RECORD_UNAVAILABLE = (
    "zero_opening_wall_frame_record_unavailable"
)

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]
_EPS = 1e-6


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class ZeroOpeningWallFrameSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.physical_wall_id,
        )


@dataclass(frozen=True)
class ZeroOpeningWallFrameRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    wall_candidate_viewport_id: str
    scale_viewport_id: str | None
    decision_scope_id: str
    physical_wall_id: str
    wall_local_frame_id: str
    member_wall_candidate_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    origin_pt: tuple[float, float]
    axis_unit: tuple[float, float]
    u0_pt: float
    u1_pt: float
    length_pt: float
    schema_version: str = ZERO_OPENING_WALL_FRAME_SCHEMA_VERSION


@dataclass(frozen=True)
class ZeroOpeningWallFrameResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: ZeroOpeningWallFrameRecord | None = None
    schema_version: str = ZERO_OPENING_WALL_FRAME_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> ZeroOpeningWallFrameResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    clean = tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason)))
    return ZeroOpeningWallFrameResult(
        status=status,
        reason_codes=clean or (ZERO_OPENING_WALL_FRAME_RECORD_UNAVAILABLE,),
        record=None,
    )


class ZeroOpeningWallFrameAuthority:
    """Read-only exact-selector authority over zero-opening wall frames."""

    def __init__(
        self,
        results: Mapping[_Key, ZeroOpeningWallFrameResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("ZeroOpeningWallFrameAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: ZeroOpeningWallFrameSelector,
    ) -> ZeroOpeningWallFrameResult:
        if type(selector) is not ZeroOpeningWallFrameSelector:
            raise TypeError("selector must be ZeroOpeningWallFrameSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                ZERO_OPENING_WALL_FRAME_RECORD_UNAVAILABLE,
            ),
        )


def combine_zero_opening_wall_frame_authorities(
    authorities: tuple[ZeroOpeningWallFrameAuthority, ...],
) -> ZeroOpeningWallFrameAuthority:
    """Combine only already-sealed zero-opening frame results.

    This helper cannot mint records. It exists so multi-page live composition
    can route exact page-local producer results into one downstream selector
    authority without accepting any caller-authored wall/frame truth.
    """
    merged: dict[_Key, ZeroOpeningWallFrameResult] = {}
    for authority in authorities:
        if type(authority) is not ZeroOpeningWallFrameAuthority:
            raise TypeError("all authorities must be producer-owned")
        for key, result in authority._results.items():
            prior = merged.get(key)
            if prior is not None and prior != result:
                raise RuntimeError("zero_opening_wall_frame_authority_conflict")
            merged[key] = result
    return ZeroOpeningWallFrameAuthority(merged, _seal=_AUTHORITY_SEAL)


class ZeroOpeningWallFrameProducer:
    """Trusted writer for source-derived wall frames with proven zero openings."""

    def __init__(
        self,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        opening_universe_completeness_authority: OpeningUniverseCompletenessAuthority,
        opening_host_frame_authority: OpeningHostFrameAuthority,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "ZeroOpeningWallFrameProducer must be obtained from from_authorities()"
            )
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned")
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError("physical_opening_authority must be producer-owned")
        if (
            type(opening_universe_completeness_authority)
            is not OpeningUniverseCompletenessAuthority
        ):
            raise TypeError(
                "opening_universe_completeness_authority must be producer-owned"
            )
        if type(opening_host_frame_authority) is not OpeningHostFrameAuthority:
            raise TypeError("opening_host_frame_authority must be producer-owned")
        self._walls = physical_wall_candidate_authority
        self._openings = physical_opening_authority
        self._opening_universe = opening_universe_completeness_authority
        self._host_frames = opening_host_frame_authority
        self._results: dict[_Key, ZeroOpeningWallFrameResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        opening_universe_completeness_authority: OpeningUniverseCompletenessAuthority,
        opening_host_frame_authority: OpeningHostFrameAuthority,
    ) -> "ZeroOpeningWallFrameProducer":
        return cls(
            physical_wall_candidate_authority=physical_wall_candidate_authority,
            physical_opening_authority=physical_opening_authority,
            opening_universe_completeness_authority=opening_universe_completeness_authority,
            opening_host_frame_authority=opening_host_frame_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> ZeroOpeningWallFrameAuthority:
        return ZeroOpeningWallFrameAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: ZeroOpeningWallFrameSelector,
        result: ZeroOpeningWallFrameResult,
    ) -> ZeroOpeningWallFrameResult:
        prior = self._results.get(selector.key)
        if prior is not None and prior != result:
            raise RuntimeError("zero_opening_wall_frame_producer_equivocation")
        self._results[selector.key] = result
        return result

    @staticmethod
    def _wall_class_members(scope, representative_id: str) -> tuple[str, ...] | None:
        equivalence = scope.equivalence
        if equivalence is None:
            return None
        if (
            representative_id not in tuple(equivalence.representative_wall_ids)
            or representative_id in tuple(equivalence.ambiguous_wall_ids)
            or representative_id in tuple(equivalence.abstained_wall_ids)
        ):
            return None
        for group in equivalence.equivalence_groups:
            if representative_id in group:
                return tuple(sorted(str(item) for item in group if str(item)))
        return (representative_id,)

    @staticmethod
    def _straight_path(
        paths: tuple[tuple[tuple[float, float], ...], ...],
    ) -> tuple[
        tuple[float, float],
        tuple[float, float],
        float,
    ] | None:
        if not paths or any(len(path) < 2 for path in paths):
            return None
        canonical = paths[0]
        if any(path != canonical for path in paths[1:]):
            return None

        start = (float(canonical[0][0]), float(canonical[0][1]))
        end = (float(canonical[-1][0]), float(canonical[-1][1]))
        if end < start:
            start, end = end, start
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length <= _EPS:
            return None

        # The current gross-wall representation is a straight wall-local
        # rectangle. Curved / kinked source paths remain unknown rather than
        # being flattened into a scalar length.
        for point in canonical[1:-1]:
            px = float(point[0]) - start[0]
            py = float(point[1]) - start[1]
            if abs(dx * py - dy * px) > _EPS * max(1.0, length):
                return None

        return start, (dx / length, dy / length), length

    def publish(
        self,
        selector: ZeroOpeningWallFrameSelector,
    ) -> ZeroOpeningWallFrameResult:
        if type(selector) is not ZeroOpeningWallFrameSelector:
            raise TypeError("selector must be ZeroOpeningWallFrameSelector")

        wall_scope = self._walls.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
            )
        )
        if (
            wall_scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not wall_scope.scope_complete
        ):
            return self._store(
                selector,
                _blocked(
                    wall_scope.status,
                    ZERO_OPENING_WALL_FRAME_SCOPE_INCOMPLETE,
                    *tuple(wall_scope.reason_codes),
                ),
            )
        if (
            wall_scope.document_id != selector.document_id
            or wall_scope.revision_id != selector.revision_id
            or wall_scope.source_sha256 != selector.source_sha256
            or wall_scope.snapshot_id != selector.snapshot_id
            or wall_scope.page_id != selector.page_id
            or wall_scope.decision_scope_id != selector.decision_scope_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    ZERO_OPENING_WALL_FRAME_LINEAGE_MISMATCH,
                ),
            )

        member_ids = self._wall_class_members(
            wall_scope,
            selector.physical_wall_id,
        )
        if not member_ids:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    ZERO_OPENING_WALL_FRAME_WALL_UNRESOLVED,
                ),
            )

        records_by_id = {
            record.wall_candidate_id: record for record in wall_scope.records
        }
        member_records = tuple(
            records_by_id.get(member_id) for member_id in member_ids
        )
        if any(record is None for record in member_records):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    ZERO_OPENING_WALL_FRAME_WALL_UNRESOLVED,
                ),
            )

        completeness = self._opening_universe.resolve(
            OpeningUniverseSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                decision_scope_id=selector.decision_scope_id,
            )
        )
        complete_record = completeness.record
        if (
            completeness.status is not EvidenceResolutionStatus.CORROBORATED
            or complete_record is None
            or not bool(completeness.decision_scope_complete)
            or tuple(complete_record.page_ids) != (selector.page_id,)
        ):
            return self._store(
                selector,
                _blocked(
                    completeness.status,
                    ZERO_OPENING_WALL_FRAME_OPENING_UNIVERSE_INCOMPLETE,
                    *tuple(completeness.reason_codes),
                ),
            )

        target_members = set(member_ids)
        for observation_id in complete_record.accounted_source_observation_ids:
            existence = self._openings.prove_existence(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            opening_record = existence.existence_record
            if (
                existence.status is not EvidenceResolutionStatus.CORROBORATED
                or opening_record is None
            ):
                return self._store(
                    selector,
                    _blocked(
                        existence.status,
                        ZERO_OPENING_WALL_FRAME_OPENING_UNRESOLVED,
                        *tuple(existence.reason_codes),
                    ),
                )
            if (
                opening_record.document_id != selector.document_id
                or opening_record.revision_id != selector.revision_id
                or opening_record.source_sha256 != selector.source_sha256
                or opening_record.snapshot_id != selector.snapshot_id
                or str(opening_record.page_id) != selector.page_id
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        ZERO_OPENING_WALL_FRAME_LINEAGE_MISMATCH,
                    ),
                )

            frame_result = self._host_frames.resolve(
                OpeningHostFrameSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                    opening_identity_id=opening_record.record_id,
                )
            )
            frame = frame_result.evidence
            if (
                frame_result.status is not EvidenceResolutionStatus.CORROBORATED
                or frame is None
            ):
                return self._store(
                    selector,
                    _blocked(
                        frame_result.status,
                        ZERO_OPENING_WALL_FRAME_HOST_FRAME_UNRESOLVED,
                        *tuple(frame_result.reason_codes),
                    ),
                )
            if target_members & set(frame.whole_wall_candidate_ids):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        ZERO_OPENING_WALL_FRAME_HAS_OPENING,
                    ),
                )

        member_records_typed = tuple(
            record for record in member_records if record is not None
        )
        viewport_ids = {
            str(record.wall_candidate.viewport_id)
            for record in member_records_typed
            if str(record.wall_candidate.viewport_id)
        }
        if len(viewport_ids) != 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    ZERO_OPENING_WALL_FRAME_GEOMETRY_UNRESOLVED,
                    "zero_opening_wall_viewport_unresolved",
                ),
            )
        viewport_id = next(iter(viewport_ids))

        paths = tuple(
            tuple(
                (float(point[0]), float(point[1]))
                for point in record.physical_identity.path_fingerprint or ()
            )
            for record in member_records_typed
        )
        frame_geometry = self._straight_path(paths)
        if frame_geometry is None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    ZERO_OPENING_WALL_FRAME_GEOMETRY_UNRESOLVED,
                ),
            )

        origin, axis, length_pt = frame_geometry
        source_observation_ids = tuple(
            sorted(
                {
                    str(source_id)
                    for record in member_records_typed
                    for source_id in record.physical_identity.source_primitive_ids
                    if str(source_id)
                }
            )
        )
        payload = {
            "schema_version": ZERO_OPENING_WALL_FRAME_SCHEMA_VERSION,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "wall_candidate_viewport_id": viewport_id,
            "scale_viewport_id": None,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "member_wall_candidate_ids": member_ids,
            "source_observation_ids": source_observation_ids,
            "origin_pt": origin,
            "axis_unit": axis,
            "u0_pt": 0.0,
            "u1_pt": round(length_pt, 12),
            "length_pt": round(length_pt, 12),
        }
        wall_local_frame_id = stable_contract_id(
            "zero_opening_wall_local_frame",
            payload,
            digest_chars=32,
        )
        record_payload = {
            **payload,
            "wall_local_frame_id": wall_local_frame_id,
        }
        record_id = stable_contract_id(
            "zero_opening_wall_frame",
            record_payload,
            digest_chars=32,
        )
        record = ZeroOpeningWallFrameRecord(
            record_id=record_id,
            wall_local_frame_id=wall_local_frame_id,
            **payload,
        )
        return self._store(
            selector,
            ZeroOpeningWallFrameResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(ZERO_OPENING_WALL_FRAME_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "ZERO_OPENING_WALL_FRAME_GEOMETRY_UNRESOLVED",
    "ZERO_OPENING_WALL_FRAME_HAS_OPENING",
    "ZERO_OPENING_WALL_FRAME_HOST_FRAME_UNRESOLVED",
    "ZERO_OPENING_WALL_FRAME_LINEAGE_MISMATCH",
    "ZERO_OPENING_WALL_FRAME_OPENING_UNIVERSE_INCOMPLETE",
    "ZERO_OPENING_WALL_FRAME_OPENING_UNRESOLVED",
    "ZERO_OPENING_WALL_FRAME_RECORD_UNAVAILABLE",
    "ZERO_OPENING_WALL_FRAME_RESOLVED",
    "ZERO_OPENING_WALL_FRAME_SCHEMA_VERSION",
    "ZERO_OPENING_WALL_FRAME_SCOPE_INCOMPLETE",
    "ZERO_OPENING_WALL_FRAME_WALL_UNRESOLVED",
    "combine_zero_opening_wall_frame_authorities",
    "ZeroOpeningWallFrameAuthority",
    "ZeroOpeningWallFrameProducer",
    "ZeroOpeningWallFrameRecord",
    "ZeroOpeningWallFrameResult",
    "ZeroOpeningWallFrameSelector",
]
