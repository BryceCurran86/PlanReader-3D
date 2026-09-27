"""Producer-owned physical-opening -> authenticated floor-plan viewport authority.

This authority does not change the physical-opening existence proposition.
It adds only source-view ownership needed by viewport-scoped wall/opening work.

Positive path:
physical opening existence + SAME opening identity
-> replay every exact source support observation
-> exactly one producer-owned authenticated floor-plan wall viewport contains
   every support primitive endpoint
-> publish that viewport and its wall decision scope.

No caller geometry, nearest viewport, bbox-center-only ownership, confidence
ranking, project identity, benchmark value, host wall, deduction or quantity is
accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PhysicalOpeningAuthority,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
from pb_source_observation_authority import ObservationSelector


OPENING_VIEWPORT_ASSIGNMENT_SCHEMA_VERSION = "1.0.0"
OPENING_VIEWPORT_ASSIGNMENT_RESOLVED = "opening_viewport_assignment_resolved"
OPENING_VIEWPORT_ASSIGNMENT_UNAVAILABLE = "opening_viewport_assignment_unavailable"
OPENING_VIEWPORT_ASSIGNMENT_AMBIGUOUS = "opening_viewport_assignment_ambiguous"
OPENING_VIEWPORT_ASSIGNMENT_SOURCE_REPLAY_FAILED = (
    "opening_viewport_assignment_source_replay_failed"
)
OPENING_VIEWPORT_ASSIGNMENT_NO_FLOOR_PLAN = (
    "opening_viewport_assignment_no_authenticated_floor_plan"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()
_COORD_TOL = 1e-6


@dataclass(frozen=True)
class OpeningViewportAssignmentSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    opening_identity_id: str

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.opening_identity_id,
        )


@dataclass(frozen=True)
class OpeningViewportAssignmentRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    opening_identity_id: str
    viewport_id: str
    wall_decision_scope_id: str
    source_observation_ids: tuple[str, ...]
    wall_scope_complete: bool
    wall_scope_reason_codes: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = OPENING_VIEWPORT_ASSIGNMENT_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("OpeningViewportAssignmentRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive viewport assignment must be CORROBORATED")
        if not self.viewport_id or not self.wall_decision_scope_id:
            raise ValueError("viewport and wall scope are required")
        if not self.source_observation_ids:
            raise ValueError("source observation provenance is required")


@dataclass(frozen=True)
class OpeningViewportAssignmentResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[OpeningViewportAssignmentRecord] = None
    schema_version: str = OPENING_VIEWPORT_ASSIGNMENT_SCHEMA_VERSION


def _blocked(
    reason: str,
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
    extras: Sequence[str] = (),
) -> OpeningViewportAssignmentResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return OpeningViewportAssignmentResult(
        status=status,
        reason_codes=tuple(dict.fromkeys((reason, *tuple(extras)))),
        record=None,
    )


def _point_inside_bbox(
    point: tuple[float, float],
    bbox: Sequence[float],
) -> bool:
    x, y = float(point[0]), float(point[1])
    return (
        float(bbox[0]) - _COORD_TOL <= x <= float(bbox[2]) + _COORD_TOL
        and float(bbox[1]) - _COORD_TOL <= y <= float(bbox[3]) + _COORD_TOL
    )


def _geometry_inside_bbox(
    geometry: Sequence[float],
    bbox: Sequence[float],
) -> bool:
    if len(geometry) != 4 or len(bbox) != 4:
        return False
    try:
        x1, y1, x2, y2 = (float(value) for value in geometry)
    except (TypeError, ValueError):
        return False
    return _point_inside_bbox((x1, y1), bbox) and _point_inside_bbox(
        (x2, y2), bbox
    )


def _floor_plan_scopes_for_opening(
    *,
    wall_authority: PhysicalWallCandidateAuthority,
    opening,
    support_geometries: Sequence[Sequence[float]],
):
    matches = []
    for scope in wall_authority._scopes.values():
        if (
            scope.document_id != opening.document_id
            or scope.revision_id != opening.revision_id
            or scope.source_sha256 != opening.source_sha256
            or scope.snapshot_id != opening.snapshot_id
            or scope.page_id != opening.page_id
            or scope.status is not EvidenceResolutionStatus.CORROBORATED
            or str(getattr(scope, "scope_kind", "")) != "viewport"
            or str(getattr(scope, "viewport_view_type", "") or "") != "floor_plan"
            or not getattr(scope, "viewport_id", None)
            or getattr(scope, "viewport_bbox", None) is None
        ):
            continue
        bbox = scope.viewport_bbox
        if all(_geometry_inside_bbox(geometry, bbox) for geometry in support_geometries):
            matches.append(scope)
    return tuple(sorted(matches, key=lambda scope: str(scope.decision_scope_id)))


class OpeningViewportAssignmentAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, ...], OpeningViewportAssignmentResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningViewportAssignmentAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: OpeningViewportAssignmentSelector,
    ) -> OpeningViewportAssignmentResult:
        if type(selector) is not OpeningViewportAssignmentSelector:
            raise TypeError("selector must be OpeningViewportAssignmentSelector")
        return self._results.get(
            selector.key,
            _blocked(OPENING_VIEWPORT_ASSIGNMENT_UNAVAILABLE),
        )


class OpeningViewportAssignmentProducer:
    def __init__(
        self,
        physical_opening_authority: PhysicalOpeningAuthority,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        _seal=None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "OpeningViewportAssignmentProducer must be obtained "
                "from_authorities()"
            )
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError("physical_opening_authority must be producer-owned")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be producer-owned"
            )
        self._opening = physical_opening_authority
        self._walls = physical_wall_candidate_authority
        self._results: dict[
            tuple[str, ...], OpeningViewportAssignmentResult
        ] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_opening_authority: PhysicalOpeningAuthority,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "OpeningViewportAssignmentProducer":
        return cls(
            physical_opening_authority,
            physical_wall_candidate_authority,
            _seal=_PRODUCER_SEAL,
        )

    def publish(
        self,
        *,
        opening_left_selector: ObservationSelector,
        opening_right_selector: ObservationSelector,
    ) -> OpeningViewportAssignmentResult:
        if type(opening_left_selector) is not ObservationSelector:
            raise TypeError("opening_left_selector must be ObservationSelector")
        if type(opening_right_selector) is not ObservationSelector:
            raise TypeError("opening_right_selector must be ObservationSelector")

        left = self._opening.prove_existence(opening_left_selector)
        right = self._opening.prove_existence(opening_right_selector)
        identity = self._opening.compare_identity(
            opening_left_selector,
            opening_right_selector,
        )
        if (
            left.status is not EvidenceResolutionStatus.CORROBORATED
            or right.status is not EvidenceResolutionStatus.CORROBORATED
            or left.proposition != PHYSICAL_OPENING_EXISTS
            or right.proposition != PHYSICAL_OPENING_EXISTS
            or left.existence_record is None
            or right.existence_record is None
            or identity.status is not EvidenceResolutionStatus.CORROBORATED
            or identity.proven_same is not True
            or PHYSICAL_OPENING_IDENTITY_RESOLVED not in identity.reason_codes
            or left.existence_record.record_id != right.existence_record.record_id
        ):
            return _blocked(
                "authenticated_physical_opening_identity_required"
            )

        opening = left.existence_record
        visibility = self._opening.source_visibility_authority()
        support_geometries = []
        for observation_id in opening.source_observation_ids:
            resolved = visibility.resolve_visible(
                ObservationSelector(
                    document_id=opening.document_id,
                    revision_id=opening.revision_id,
                    source_sha256=opening.source_sha256,
                    snapshot_id=opening.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = resolved.observation
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
                or observation.document_id != opening.document_id
                or observation.revision_id != opening.revision_id
                or observation.source_sha256 != opening.source_sha256
                or observation.snapshot_id != opening.snapshot_id
                or observation.page_id != opening.page_id
                or len(tuple(observation.geometry or ())) != 4
            ):
                return _blocked(OPENING_VIEWPORT_ASSIGNMENT_SOURCE_REPLAY_FAILED)
            support_geometries.append(tuple(float(v) for v in observation.geometry))

        if not support_geometries:
            return _blocked(OPENING_VIEWPORT_ASSIGNMENT_SOURCE_REPLAY_FAILED)

        matches = _floor_plan_scopes_for_opening(
            wall_authority=self._walls,
            opening=opening,
            support_geometries=tuple(support_geometries),
        )
        if not matches:
            return _blocked(OPENING_VIEWPORT_ASSIGNMENT_NO_FLOOR_PLAN)
        if len(matches) != 1:
            return _blocked(
                OPENING_VIEWPORT_ASSIGNMENT_AMBIGUOUS,
                status=EvidenceResolutionStatus.CONFLICT,
            )
        scope = matches[0]

        payload = {
            "document_id": opening.document_id,
            "revision_id": opening.revision_id,
            "source_sha256": opening.source_sha256,
            "snapshot_id": opening.snapshot_id,
            "page_id": opening.page_id,
            "opening_identity_id": opening.record_id,
            "viewport_id": str(scope.viewport_id),
            "wall_decision_scope_id": scope.decision_scope_id,
            "source_observation_ids": tuple(sorted(opening.source_observation_ids)),
        }
        record = OpeningViewportAssignmentRecord(
            record_id=stable_contract_id(
                "opening_viewport_assignment",
                payload,
                digest_chars=32,
            ),
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            page_id=opening.page_id,
            opening_identity_id=opening.record_id,
            viewport_id=str(scope.viewport_id),
            wall_decision_scope_id=scope.decision_scope_id,
            source_observation_ids=tuple(sorted(opening.source_observation_ids)),
            wall_scope_complete=bool(scope.scope_complete),
            wall_scope_reason_codes=tuple(scope.reason_codes),
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_VIEWPORT_ASSIGNMENT_RESOLVED,),
            _seal=_RECORD_SEAL,
        )
        result = OpeningViewportAssignmentResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_VIEWPORT_ASSIGNMENT_RESOLVED,),
            record=record,
        )
        selector = OpeningViewportAssignmentSelector(
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            page_id=opening.page_id,
            opening_identity_id=opening.record_id,
        )
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            raise RuntimeError("opening viewport assignment producer equivocation")
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningViewportAssignmentAuthority:
        return OpeningViewportAssignmentAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )


__all__ = [
    "OPENING_VIEWPORT_ASSIGNMENT_AMBIGUOUS",
    "OPENING_VIEWPORT_ASSIGNMENT_NO_FLOOR_PLAN",
    "OPENING_VIEWPORT_ASSIGNMENT_RESOLVED",
    "OPENING_VIEWPORT_ASSIGNMENT_SCHEMA_VERSION",
    "OPENING_VIEWPORT_ASSIGNMENT_SOURCE_REPLAY_FAILED",
    "OPENING_VIEWPORT_ASSIGNMENT_UNAVAILABLE",
    "OpeningViewportAssignmentAuthority",
    "OpeningViewportAssignmentProducer",
    "OpeningViewportAssignmentRecord",
    "OpeningViewportAssignmentResult",
    "OpeningViewportAssignmentSelector",
]
