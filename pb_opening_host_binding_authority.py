"""Producer-owned opening -> physical host-wall binding authority.

This module establishes exactly one proposition: a previously identified opening
record is structurally bound to exactly one physical wall within an exact,
producer-owned decision scope.

It does *not* establish opening existence/identity, opening dimensions, physical
void, deduction area, net wall area, FIRM/commercial publication, or JobHub
publication.  Ordinary consumers query by lineage/scope selector only.  They do
not supply walls, geometry, host ids, fingerprints, counts, radii, or completeness
claims to the read boundary.

The trusted writer deliberately reuses the existing #323 wall identity and
physical-equivalence stack.  Geometry is evaluated in the opening's local axis so
angled/rotated hosts are not reduced to horizontal/vertical special cases.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from pb_hosted_opening_geometry import HostedOpeningSpan
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_identity import (
    PhysicalWallIdentity,
    resolve_physical_wall_equivalence,
    resolve_physical_wall_identity,
)
from pb_wall_room_topology_contracts import WallCandidate


OPENING_HOST_BINDING_SCHEMA_VERSION = "1.0.0"
_AUTHORITY_SEAL = object()
Point = tuple[float, float]
_RecordKey = tuple[str, str, str, str, str, str]


@dataclass(frozen=True)
class OpeningHostBindingSelector:
    """Read-only lookup selector; intentionally contains no host proof inputs."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
            "opening_record_id",
        ):
            _require_nonempty(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class OpeningHostBindingRecord:
    """Immutable producer-owned positive host-binding record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    decision_scope_id: str
    opening_record_id: str
    host_wall_id: str
    physical_wall_identity_id: str
    path_fingerprint: tuple[Point, ...]
    source_primitive_ids: tuple[str, ...]
    relevant_physical_wall_ids: tuple[str, ...]
    relevant_universe_fingerprint: str
    schema_version: str = OPENING_HOST_BINDING_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningHostBindingResult:
    """Resolution result at the selector-only consumer boundary."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[OpeningHostBindingRecord] = None
    schema_version: str = OPENING_HOST_BINDING_SCHEMA_VERSION

    @property
    def host_wall_id(self) -> Optional[str]:
        return self.record.host_wall_id if self.record is not None else None


@dataclass(frozen=True)
class _HostGeometry:
    wall_id: str
    relevant: bool
    contains_opening: bool
    path_fingerprint: tuple[Point, ...]


class OpeningHostBindingAuthority:
    """Sealed read-only host-binding lookup surface."""

    def __init__(
        self,
        results: Mapping[_RecordKey, OpeningHostBindingResult],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("OpeningHostBindingAuthority is producer-owned")
        self._results = results

    def resolve(self, selector: OpeningHostBindingSelector) -> OpeningHostBindingResult:
        if not isinstance(selector, OpeningHostBindingSelector):
            raise TypeError("selector must be OpeningHostBindingSelector")
        key = _record_key(
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.decision_scope_id,
            selector.opening_record_id,
        )
        result = self._results.get(key)
        if result is not None:
            return result
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "host_binding_record_unavailable",
        )


class OpeningHostBindingProducer:
    """Trusted writer for exact-scope opening host-binding decisions."""

    def __init__(self) -> None:
        self._results: dict[_RecordKey, OpeningHostBindingResult] = {}

    def publish_scope(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        viewport_id: Optional[str],
        decision_scope_id: str,
        opening_record_id: str,
        opening_span: HostedOpeningSpan,
        walls: Sequence[WallCandidate],
        edges_by_id: Mapping[str, Mapping[str, Any]],
        source_complete: bool,
        host_universe_complete: bool,
        traversal_truncated: bool,
    ) -> OpeningHostBindingResult:
        """Resolve and publish one exact producer-owned host decision scope.

        The boolean coverage inputs are writer-side state.  They are intentionally
        absent from ``OpeningHostBindingSelector`` and therefore cannot be echoed
        back by ordinary query callers as proof.
        """

        for field_name, value in (
            ("document_id", document_id),
            ("revision_id", revision_id),
            ("source_sha256", source_sha256),
            ("snapshot_id", snapshot_id),
            ("page_id", page_id),
            ("decision_scope_id", decision_scope_id),
            ("opening_record_id", opening_record_id),
        ):
            _require_nonempty(value, field_name)
        if not isinstance(opening_span, HostedOpeningSpan):
            raise TypeError("opening_span must be HostedOpeningSpan")

        key = _record_key(
            document_id,
            revision_id,
            source_sha256,
            snapshot_id,
            decision_scope_id,
            opening_record_id,
        )

        if source_complete is not True:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "source_enumeration_incomplete",
            ))
        if host_universe_complete is not True:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "host_universe_incomplete",
            ))
        if traversal_truncated:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "host_universe_traversal_truncated",
            ))
        # A local viewport/crop is not proof that all competing physical walls in
        # the decision scope were enumerated.  Start conservatively at page scope.
        if viewport_id is not None:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "viewport_limited_host_scope",
            ))

        frame = _opening_frame(opening_span)
        if frame is None:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "opening_host_axis_unavailable",
            ))

        ordered_walls = tuple(sorted(tuple(walls), key=lambda wall: wall.candidate_id))
        if not ordered_walls:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "host_universe_empty",
            ))

        geometries: dict[str, _HostGeometry] = {}
        relevant: list[WallCandidate] = []
        for wall in ordered_walls:
            geometry = _classify_wall_against_opening(wall, opening_span, frame)
            if geometry is None:
                # Curved/degenerate/unclassifiable wall geometry may still be a
                # competing host, so do not silently discard it from a complete
                # host universe.
                return self._store(key, _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    "host_wall_geometry_unresolved",
                ))
            geometries[wall.candidate_id] = geometry
            if geometry.relevant:
                relevant.append(wall)

        if not relevant:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "no_structurally_relevant_host_wall",
            ))
        if not any(geometries[wall.candidate_id].contains_opening for wall in relevant):
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "no_wall_contains_opening_span",
            ))

        identities: list[PhysicalWallIdentity] = []
        identity_by_wall_id: dict[str, PhysicalWallIdentity] = {}
        walls_by_id = {wall.candidate_id: wall for wall in relevant}
        for wall in relevant:
            identity = resolve_physical_wall_identity(
                wall=wall,
                edges_by_id=edges_by_id,
            )
            identities.append(identity)
            identity_by_wall_id[wall.candidate_id] = identity
            if not identity.usable:
                return self._store(key, _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    "physical_host_wall_identity_unavailable",
                    *identity.blocking_reasons,
                ))

        equivalence = resolve_physical_wall_equivalence(
            tuple(identities),
            walls_by_id=walls_by_id,
        )
        if equivalence.ambiguous_wall_ids or equivalence.abstained_wall_ids:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.CONFLICT,
                "physical_host_wall_equivalence_ambiguous",
            ))
        if len(equivalence.representative_wall_ids) != 1:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.CONFLICT,
                "multiple_physical_host_walls_remain",
            ))

        host_wall_id = equivalence.representative_wall_ids[0]
        host_geometry = geometries.get(host_wall_id)
        host_identity = identity_by_wall_id.get(host_wall_id)
        if host_geometry is None or host_identity is None or not host_geometry.contains_opening:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "physical_host_representative_does_not_contain_opening",
            ))
        if host_identity.candidate_identity_id is None or host_identity.path_fingerprint is None:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                "physical_host_identity_incomplete",
            ))

        semantic_members = tuple(
            sorted(
                (
                    identity.wall_candidate_id,
                    str(identity.candidate_identity_id or ""),
                    tuple(identity.path_fingerprint or ()),
                    tuple(sorted(identity.source_primitive_ids)),
                )
                for identity in identities
            )
        )
        relevant_universe_fingerprint = stable_contract_id(
            "opening_host_universe",
            {
                "members": semantic_members,
            },
        )
        record_payload = {
            "schema_version": OPENING_HOST_BINDING_SCHEMA_VERSION,
            "document_id": document_id,
            "revision_id": revision_id,
            "source_sha256": source_sha256,
            "snapshot_id": snapshot_id,
            "page_id": page_id,
            "viewport_id": viewport_id,
            "decision_scope_id": decision_scope_id,
            "opening_record_id": opening_record_id,
            "host_wall_id": host_wall_id,
            "physical_wall_identity_id": host_identity.candidate_identity_id,
            "path_fingerprint": tuple(host_identity.path_fingerprint),
            "source_primitive_ids": tuple(sorted(host_identity.source_primitive_ids)),
            "relevant_physical_wall_ids": tuple(equivalence.representative_wall_ids),
            "relevant_universe_fingerprint": relevant_universe_fingerprint,
        }
        record = OpeningHostBindingRecord(
            record_id=stable_contract_id("opening_host_binding", record_payload),
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_id=page_id,
            viewport_id=viewport_id,
            decision_scope_id=decision_scope_id,
            opening_record_id=opening_record_id,
            host_wall_id=host_wall_id,
            physical_wall_identity_id=host_identity.candidate_identity_id,
            path_fingerprint=tuple(host_identity.path_fingerprint),
            source_primitive_ids=tuple(sorted(host_identity.source_primitive_ids)),
            relevant_physical_wall_ids=tuple(equivalence.representative_wall_ids),
            relevant_universe_fingerprint=relevant_universe_fingerprint,
        )
        return self._store(
            key,
            OpeningHostBindingResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("unique_physical_host_wall_bound",),
                record=record,
            ),
        )

    def authority(self) -> OpeningHostBindingAuthority:
        return OpeningHostBindingAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        key: _RecordKey,
        result: OpeningHostBindingResult,
    ) -> OpeningHostBindingResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("opening host-binding producer equivocation")
        self._results[key] = result
        return result


def _record_key(
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    opening_record_id: str,
) -> _RecordKey:
    return (
        str(document_id),
        str(revision_id),
        str(source_sha256),
        str(snapshot_id),
        str(decision_scope_id),
        str(opening_record_id),
    )


def _blocked(
    status: EvidenceResolutionStatus,
    *reason_codes: str,
) -> OpeningHostBindingResult:
    cleaned = tuple(dict.fromkeys(str(code) for code in reason_codes if str(code)))
    return OpeningHostBindingResult(
        status=status,
        reason_codes=cleaned or ("host_binding_unavailable",),
        record=None,
    )


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _opening_frame(
    span: HostedOpeningSpan,
) -> Optional[tuple[Point, Point, float]]:
    try:
        start = (float(span.jamb_start[0]), float(span.jamb_start[1]))
        end = (float(span.jamb_end[0]), float(span.jamb_end[1]))
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= 1e-6:
        return None
    unit = (dx / length, dy / length)
    normal = (-unit[1], unit[0])
    return unit, normal, length


def _project(point: Point, origin: Point, axis: Point) -> float:
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


def _classify_wall_against_opening(
    wall: WallCandidate,
    span: HostedOpeningSpan,
    frame: tuple[Point, Point, float],
) -> Optional[_HostGeometry]:
    if wall.is_curved or len(wall.centerline_pts) < 2:
        return None
    try:
        points = tuple((float(x), float(y)) for x, y in wall.centerline_pts)
    except (TypeError, ValueError):
        return None
    if any(not (math.isfinite(x) and math.isfinite(y)) for x, y in points):
        return None

    first, last = points[0], points[-1]
    wall_dx = last[0] - first[0]
    wall_dy = last[1] - first[1]
    wall_length = math.hypot(wall_dx, wall_dy)
    if wall_length <= 1e-6:
        return None
    wall_unit = (wall_dx / wall_length, wall_dy / wall_length)

    opening_axis, opening_normal, opening_length = frame
    # Direction is unsigned: a wall traversed in reverse is the same path.
    cross = abs(wall_unit[0] * opening_axis[1] - wall_unit[1] * opening_axis[0])
    parallel_limit = math.sin(math.radians(5.0))
    if cross > parallel_limit:
        return _HostGeometry(
            wall_id=wall.candidate_id,
            relevant=False,
            contains_opening=False,
            path_fingerprint=(),
        )

    origin = (float(span.jamb_start[0]), float(span.jamb_start[1]))
    along = tuple(_project(point, origin, opening_axis) for point in points)
    across = tuple(abs(_project(point, origin, opening_normal)) for point in points)

    raw_thickness = getattr(span, "wall_thickness_pt", None)
    try:
        thickness = abs(float(raw_thickness)) if raw_thickness is not None else 0.0
    except (TypeError, ValueError):
        thickness = 0.0
    cross_tolerance = max(6.0, thickness * 0.75)
    if max(across) > cross_tolerance:
        return _HostGeometry(
            wall_id=wall.candidate_id,
            relevant=False,
            contains_opening=False,
            path_fingerprint=(),
        )

    along_min = min(along)
    along_max = max(along)
    along_tolerance = max(1.0, min(4.0, opening_length * 0.02))
    relevant = (
        along_max >= -along_tolerance
        and along_min <= opening_length + along_tolerance
    )
    contains = (
        relevant
        and along_min <= along_tolerance
        and along_max >= opening_length - along_tolerance
    )
    return _HostGeometry(
        wall_id=wall.candidate_id,
        relevant=relevant,
        contains_opening=contains,
        path_fingerprint=(),
    )


__all__ = [
    "OPENING_HOST_BINDING_SCHEMA_VERSION",
    "OpeningHostBindingAuthority",
    "OpeningHostBindingProducer",
    "OpeningHostBindingRecord",
    "OpeningHostBindingResult",
    "OpeningHostBindingSelector",
]
