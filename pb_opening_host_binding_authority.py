"""Producer-owned authenticated physical-opening -> host-wall binding authority V3.

This module proves one narrow proposition only: an already source-authenticated
physical opening instance is bound to exactly one host wall band derived from the
complete sealed physical-wall-candidate scope for the same exact source/page.

Host binding consumes the producer-owned physical-wall equivalence result. A
candidate identity is only an address for one wall representation; it is never
promoted into physical-wall sameness or distinctness. Competing representations
for the same geometric host role may collapse only when upstream equivalence
proves SAME_PHYSICAL_WALL. DISTINCT_PHYSICAL_WALLS remain separate. An
AMBIGUOUS_PHYSICAL_EQUIVALENCE affecting a possible host representation blocks
the host proposition rather than being resolved by geometry, confidence,
nearest, first, or lexical choice.

It does not prove opening dimensions, physical void, deductions, wall role,
wall height, wall thickness, net wall area, FIRM/commercial publication or
JobHub data. Ordinary callers never supply walls, candidate lists, completeness
booleans, radii, confidence, raw opening spans, host ids, equivalence claims or
geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateSelector,
)
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationRecord
from pb_source_visibility_authority import SourceVisibilityAuthority
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT


OPENING_HOST_BINDING_SCHEMA_VERSION = "3.2.0"
OPENING_HOST_UNIVERSE_RESOLVED = "opening_host_wall_universe_resolved"
OPENING_HOST_BINDING_RESOLVED = "opening_host_binding_resolved"
OPENING_HOST_BINDING_UNAVAILABLE = "opening_host_binding_unavailable"
HOST_EQUIVALENCE_AMBIGUOUS = "ambiguous_physical_wall_equivalence_for_host"
HOST_EQUIVALENCE_UNAVAILABLE = "physical_wall_equivalence_required_for_host"
HOST_BAND_CENTER_MISMATCH = "authenticated_host_wall_band_not_centered_on_opening"

_UNIVERSE_PRODUCER_SEAL = object()
_UNIVERSE_AUTHORITY_SEAL = object()
_BINDING_PRODUCER_SEAL = object()
_BINDING_AUTHORITY_SEAL = object()
_COORD_TOL = 1e-6
_PARALLEL_TOL = math.sin(math.radians(5.0))
Point = tuple[float, float]


@dataclass(frozen=True)
class OpeningHostWallUniverseSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "page_id", "decision_scope_id",
        ):
            _require_nonempty(getattr(self, name), name)


@dataclass(frozen=True)
class OpeningHostWallUniverseResult:
    status: EvidenceResolutionStatus
    scope_complete: bool
    records: tuple[PhysicalWallCandidateRecord, ...]
    source_observation_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    reason_codes: tuple[str, ...]
    equivalence: Optional[PhysicalWallEquivalenceResolution] = None
    proposition: Optional[str] = None
    schema_version: str = OPENING_HOST_BINDING_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningHostBindingSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "page_id", "decision_scope_id", "opening_identity_id",
        ):
            _require_nonempty(getattr(self, name), name)


@dataclass(frozen=True)
class OpeningHostBindingRecord:
    """One opening-scoped host binding, not a global physical-wall identity."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str
    host_wall_id: str
    member_wall_candidate_ids: tuple[str, ...]
    member_candidate_identity_ids: tuple[str, ...]
    member_equivalence_groups: tuple[tuple[str, ...], ...]
    source_observation_ids: tuple[str, ...]
    schema_version: str = OPENING_HOST_BINDING_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningHostBindingResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[OpeningHostBindingRecord] = None
    schema_version: str = OPENING_HOST_BINDING_SCHEMA_VERSION

    @property
    def host_wall_id(self) -> Optional[str]:
        return self.record.host_wall_id if self.record is not None else None


@dataclass(frozen=True)
class _OpeningGeometry:
    origin: Point
    axis: Point
    normal: Point
    length: float
    thickness: float


@dataclass(frozen=True)
class _RoleCandidate:
    offset: float
    record: PhysicalWallCandidateRecord
    candidate_group: tuple[str, ...]


@dataclass(frozen=True)
class _FaceBreak:
    left: _RoleCandidate
    right: _RoleCandidate
    offset: float


@dataclass(frozen=True)
class _HostBand:
    member_ids: tuple[str, ...]
    member_candidate_identity_ids: tuple[str, ...]
    member_equivalence_groups: tuple[tuple[str, ...], ...]
    center_offset: float


@dataclass(frozen=True)
class _HostBandResolution:
    status: EvidenceResolutionStatus
    bands: tuple[_HostBand, ...]
    reason_codes: tuple[str, ...] = ()


_BindingKey = tuple[str, str, str, str, str, str, str]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _blocked_universe(
    selector: OpeningHostWallUniverseSelector,
    *reasons: str,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
) -> OpeningHostWallUniverseResult:
    return OpeningHostWallUniverseResult(
        status=status,
        scope_complete=False,
        records=(),
        source_observation_ids=(),
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
        reason_codes=tuple(dict.fromkeys(reasons or ("host_wall_universe_unavailable",))),
        equivalence=None,
    )


def _blocked_binding(
    *reasons: str,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
) -> OpeningHostBindingResult:
    return OpeningHostBindingResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(reasons or (OPENING_HOST_BINDING_UNAVAILABLE,))),
        record=None,
    )


class OpeningHostWallUniverseProducer:
    """Sealed bridge from complete physical-wall candidate authority."""

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _UNIVERSE_PRODUCER_SEAL:
            raise TypeError(
                "OpeningHostWallUniverseProducer must be obtained from "
                "from_physical_wall_candidate_authority()"
            )
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned")
        self._wall_authority = physical_wall_candidate_authority

    @classmethod
    def from_physical_wall_candidate_authority(
        cls,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "OpeningHostWallUniverseProducer":
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned")
        return cls(
            physical_wall_candidate_authority,
            _seal=_UNIVERSE_PRODUCER_SEAL,
        )

    def authority(self) -> "OpeningHostWallUniverseAuthority":
        return OpeningHostWallUniverseAuthority(
            self._wall_authority,
            _seal=_UNIVERSE_AUTHORITY_SEAL,
        )


class OpeningHostWallUniverseAuthority:
    """Selector-only complete host-wall universe reader."""

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _UNIVERSE_AUTHORITY_SEAL:
            raise TypeError("OpeningHostWallUniverseAuthority is producer-owned")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned")
        self._wall_authority = physical_wall_candidate_authority

    def resolve_scope(
        self,
        selector: OpeningHostWallUniverseSelector,
    ) -> OpeningHostWallUniverseResult:
        if not isinstance(selector, OpeningHostWallUniverseSelector):
            raise TypeError("selector must be OpeningHostWallUniverseSelector")
        wall_result = self._wall_authority.resolve_scope(
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
            wall_result.status is not EvidenceResolutionStatus.CORROBORATED
            or wall_result.scope_complete is not True
            or not tuple(wall_result.records)
        ):
            status = (
                EvidenceResolutionStatus.CONFLICT
                if wall_result.status is EvidenceResolutionStatus.CONFLICT
                else EvidenceResolutionStatus.ABSTAINED
            )
            return _blocked_universe(
                selector,
                "physical_wall_candidate_scope_unavailable",
                *tuple(wall_result.reason_codes),
                status=status,
            )
        if wall_result.equivalence is None:
            return _blocked_universe(selector, HOST_EQUIVALENCE_UNAVAILABLE)
        return OpeningHostWallUniverseResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            scope_complete=True,
            records=tuple(wall_result.records),
            source_observation_ids=tuple(wall_result.source_observation_ids),
            document_id=wall_result.document_id,
            revision_id=wall_result.revision_id,
            source_sha256=wall_result.source_sha256,
            snapshot_id=wall_result.snapshot_id,
            page_id=wall_result.page_id,
            decision_scope_id=wall_result.decision_scope_id,
            reason_codes=(OPENING_HOST_UNIVERSE_RESOLVED,),
            equivalence=wall_result.equivalence,
            proposition=OPENING_HOST_UNIVERSE_RESOLVED,
        )


class OpeningHostBindingProducer:
    """Trusted writer that re-proves opening identity and unique host geometry."""

    def __init__(
        self,
        physical_opening_authority: PhysicalOpeningAuthority,
        host_wall_universe_authority: OpeningHostWallUniverseAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _BINDING_PRODUCER_SEAL:
            raise TypeError("OpeningHostBindingProducer must be obtained from from_authorities()")
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError("physical_opening_authority must be producer-owned")
        if type(physical_opening_authority.source_visibility_authority()) is not SourceVisibilityAuthority:
            raise TypeError(
                "physical_opening_authority must be backed by producer-owned SourceVisibilityAuthority"
            )
        if type(host_wall_universe_authority) is not OpeningHostWallUniverseAuthority:
            raise TypeError("host_wall_universe_authority must be producer-owned")
        self._opening = physical_opening_authority
        self._universe = host_wall_universe_authority
        self._results: dict[_BindingKey, OpeningHostBindingResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_opening_authority: PhysicalOpeningAuthority,
        host_wall_universe_authority: OpeningHostWallUniverseAuthority,
    ) -> "OpeningHostBindingProducer":
        return cls(
            physical_opening_authority,
            host_wall_universe_authority,
            _seal=_BINDING_PRODUCER_SEAL,
        )

    def publish(
        self,
        *,
        opening_left_selector: ObservationSelector,
        opening_right_selector: ObservationSelector,
        host_universe_selector: OpeningHostWallUniverseSelector,
    ) -> OpeningHostBindingResult:
        if not isinstance(opening_left_selector, ObservationSelector):
            raise TypeError("opening_left_selector must be ObservationSelector")
        if not isinstance(opening_right_selector, ObservationSelector):
            raise TypeError("opening_right_selector must be ObservationSelector")
        if not isinstance(host_universe_selector, OpeningHostWallUniverseSelector):
            raise TypeError("host_universe_selector must be OpeningHostWallUniverseSelector")

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
            return _blocked_binding("authenticated_physical_opening_identity_required")

        opening = left.existence_record
        if not _selector_matches_opening(host_universe_selector, opening):
            return _blocked_binding("opening_host_scope_mismatch")

        universe = self._universe.resolve_scope(host_universe_selector)
        if (
            universe.status is not EvidenceResolutionStatus.CORROBORATED
            or universe.scope_complete is not True
            or universe.equivalence is None
        ):
            status = (
                EvidenceResolutionStatus.CONFLICT
                if universe.status is EvidenceResolutionStatus.CONFLICT
                else EvidenceResolutionStatus.ABSTAINED
            )
            return _blocked_binding(
                "complete_authenticated_host_wall_universe_required",
                *universe.reason_codes,
                status=status,
            )

        lineage_resolution = _resolve_generic_gap_lineage_host(
            self._opening,
            opening,
            universe.records,
            universe.equivalence,
        )
        if lineage_resolution is not None:
            band_resolution = lineage_resolution
        else:
            geometry = _opening_geometry(self._opening, opening)
            if geometry is None:
                return _blocked_binding("authenticated_opening_geometry_unavailable")
            band_resolution = _resolve_host_bands(
                universe.records,
                geometry,
                universe.equivalence,
            )
        if band_resolution.status is not EvidenceResolutionStatus.CORROBORATED:
            return _blocked_binding(
                *band_resolution.reason_codes,
                status=band_resolution.status,
            )
        bands = band_resolution.bands
        if not bands:
            return _blocked_binding("no_authenticated_host_wall_band")
        if len(bands) != 1:
            return _blocked_binding(
                "multiple_authenticated_host_wall_bands",
                status=EvidenceResolutionStatus.CONFLICT,
            )

        band = bands[0]
        # This identifier is scoped to this exact opening/host proof. It is not
        # a standalone physical-wall identity and never substitutes for the
        # upstream SAME/DISTINCT/AMBIGUOUS equivalence proposition.
        host_wall_id = stable_contract_id(
            "opening_host_binding_group",
            {
                "document_id": opening.document_id,
                "revision_id": opening.revision_id,
                "source_sha256": opening.source_sha256,
                "snapshot_id": opening.snapshot_id,
                "page_id": opening.page_id,
                "opening_identity_id": opening.record_id,
                "member_wall_candidate_ids": band.member_ids,
                "member_candidate_identity_ids": band.member_candidate_identity_ids,
                "member_equivalence_groups": band.member_equivalence_groups,
            },
            digest_chars=32,
        )
        payload = {
            "document_id": opening.document_id,
            "revision_id": opening.revision_id,
            "source_sha256": opening.source_sha256,
            "snapshot_id": opening.snapshot_id,
            "page_id": opening.page_id,
            "decision_scope_id": host_universe_selector.decision_scope_id,
            "opening_identity_id": opening.record_id,
            "host_wall_id": host_wall_id,
            "member_wall_candidate_ids": band.member_ids,
            "member_candidate_identity_ids": band.member_candidate_identity_ids,
            "member_equivalence_groups": band.member_equivalence_groups,
            "source_observation_ids": universe.source_observation_ids,
        }
        record = OpeningHostBindingRecord(
            record_id=stable_contract_id("opening_host_binding_v3", payload, digest_chars=32),
            document_id=opening.document_id,
            revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id,
            page_id=opening.page_id,
            decision_scope_id=host_universe_selector.decision_scope_id,
            opening_identity_id=opening.record_id,
            host_wall_id=host_wall_id,
            member_wall_candidate_ids=band.member_ids,
            member_candidate_identity_ids=band.member_candidate_identity_ids,
            member_equivalence_groups=band.member_equivalence_groups,
            source_observation_ids=tuple(universe.source_observation_ids),
        )
        result = OpeningHostBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_HOST_BINDING_RESOLVED,),
            record=record,
        )
        key = _binding_key(
            opening.document_id,
            opening.revision_id,
            opening.source_sha256,
            opening.snapshot_id,
            opening.page_id,
            host_universe_selector.decision_scope_id,
            opening.record_id,
        )
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("opening host-binding producer equivocation")
        self._results[key] = result
        return result

    def authority(self) -> "OpeningHostBindingAuthority":
        return OpeningHostBindingAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_BINDING_AUTHORITY_SEAL,
        )


class OpeningHostBindingAuthority:
    """Sealed selector-only positive binding lookup."""

    def __init__(
        self,
        results: Mapping[_BindingKey, OpeningHostBindingResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _BINDING_AUTHORITY_SEAL:
            raise TypeError("OpeningHostBindingAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningHostBindingSelector) -> OpeningHostBindingResult:
        if not isinstance(selector, OpeningHostBindingSelector):
            raise TypeError("selector must be OpeningHostBindingSelector")
        result = self._results.get(
            _binding_key(
                selector.document_id,
                selector.revision_id,
                selector.source_sha256,
                selector.snapshot_id,
                selector.page_id,
                selector.decision_scope_id,
                selector.opening_identity_id,
            )
        )
        return result if result is not None else _blocked_binding("host_binding_record_unavailable")


def _binding_key(
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    decision_scope_id: str,
    opening_identity_id: str,
) -> _BindingKey:
    return (
        str(document_id), str(revision_id), str(source_sha256), str(snapshot_id),
        str(page_id), str(decision_scope_id), str(opening_identity_id),
    )


def _selector_matches_opening(
    selector: OpeningHostWallUniverseSelector,
    opening: PhysicalOpeningExistenceRecord,
) -> bool:
    return (
        selector.document_id == opening.document_id
        and selector.revision_id == opening.revision_id
        and selector.source_sha256 == opening.source_sha256
        and selector.snapshot_id == opening.snapshot_id
        and selector.page_id == opening.page_id
    )


def _line(record: SourceObservationRecord) -> Optional[tuple[float, float, float, float]]:
    if len(record.geometry) != 4:
        return None
    try:
        values = tuple(float(value) for value in record.geometry)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    if math.hypot(values[2] - values[0], values[3] - values[1]) <= _COORD_TOL:
        return None
    return values  # type: ignore[return-value]


def _canonical_unit(line: Sequence[float]) -> Optional[Point]:
    dx, dy = float(line[2]) - float(line[0]), float(line[3]) - float(line[1])
    length = math.hypot(dx, dy)
    if length <= _COORD_TOL:
        return None
    ux, uy = dx / length, dy / length
    if ux < -_COORD_TOL or (abs(ux) <= _COORD_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    return (ux, uy)


def _cross(left: Point, right: Point) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _project(point: Point, origin: Point, axis: Point) -> float:
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


def _endpoints(line: Sequence[float]) -> tuple[Point, Point]:
    return ((float(line[0]), float(line[1])), (float(line[2]), float(line[3])))


def _parallel(left: Sequence[float], right: Sequence[float]) -> bool:
    lu, ru = _canonical_unit(left), _canonical_unit(right)
    return lu is not None and ru is not None and abs(_cross(lu, ru)) <= _COORD_TOL


def _collinear(left: Sequence[float], right: Sequence[float]) -> bool:
    if not _parallel(left, right):
        return False
    axis = _canonical_unit(left)
    assert axis is not None
    first = _endpoints(left)[0]
    other = _endpoints(right)[0]
    return abs(_cross(axis, (other[0] - first[0], other[1] - first[1]))) <= _COORD_TOL


def _scalar_interval(line: Sequence[float], axis: Point) -> tuple[float, float]:
    values = [point[0] * axis[0] + point[1] * axis[1] for point in _endpoints(line)]
    return (min(values), max(values))


def _point_at_scalar(line: Sequence[float], axis: Point, target: float) -> Optional[Point]:
    for point in _endpoints(line):
        value = point[0] * axis[0] + point[1] * axis[1]
        if abs(value - target) <= _COORD_TOL:
            return point
    return None


def _point_close(left: Point, right: Point, *, tolerance: float = _COORD_TOL) -> bool:
    return (
        abs(float(left[0]) - float(right[0])) <= tolerance
        and abs(float(left[1]) - float(right[1])) <= tolerance
    )


def _window_jamb_pair_geometry(
    records: Sequence[SourceObservationRecord],
) -> Optional[_OpeningGeometry]:
    """Recover two-face opening geometry from an authenticated gap + two jambs.

    The GAP_CORROBORATED_WINDOW_JAMB_PAIR producer path contributes exactly
    two collinear wall-continuation segments and two source-drawn jamb
    segments. This helper accepts only the topology already proven by that
    pattern: one unique positive gap, one jamb attached to each gap endpoint,
    parallel jambs, and matching opposite endpoints. It never infers geometry
    from proximity, labels, dimensions, or expected widths.
    """

    if len(records) != 4:
        return None
    lines = tuple(_line(record) for record in records)
    if any(line is None for line in lines):
        return None
    concrete = tuple(line for line in lines if line is not None)

    gap_candidates: list[
        tuple[int, int, Point, Point, Point]
    ] = []
    for first_index, first in enumerate(concrete):
        for second_index in range(first_index + 1, len(concrete)):
            second = concrete[second_index]
            if not _collinear(first, second):
                continue
            axis = _canonical_unit(first)
            if axis is None:
                continue
            first_iv = _scalar_interval(first, axis)
            second_iv = _scalar_interval(second, axis)
            if first_iv[0] <= second_iv[0]:
                left, left_iv, right, right_iv = first, first_iv, second, second_iv
            else:
                left, left_iv, right, right_iv = second, second_iv, first, first_iv
            if right_iv[0] - left_iv[1] <= _COORD_TOL:
                continue
            start = _point_at_scalar(left, axis, left_iv[1])
            end = _point_at_scalar(right, axis, right_iv[0])
            if start is None or end is None:
                continue
            gap_candidates.append(
                (first_index, second_index, axis, start, end)
            )

    if len(gap_candidates) != 1:
        return None
    first_index, second_index, axis, start, end = gap_candidates[0]
    jamb_indexes = tuple(
        index
        for index in range(len(concrete))
        if index not in {first_index, second_index}
    )
    if len(jamb_indexes) != 2:
        return None

    gap_length = math.hypot(end[0] - start[0], end[1] - start[1])
    if gap_length <= _COORD_TOL:
        return None
    normal = (-axis[1], axis[0])

    attached: dict[str, tuple[Point, Point]] = {}
    for index in jamb_indexes:
        jamb = concrete[index]
        jamb_axis = _canonical_unit(jamb)
        if jamb_axis is None or abs(jamb_axis[0] * axis[0] + jamb_axis[1] * axis[1]) > _PARALLEL_TOL:
            return None
        jamb_points = _endpoints(jamb)
        matches: list[tuple[str, Point, Point]] = []
        for name, gap_point in (("start", start), ("end", end)):
            for endpoint_index, endpoint in enumerate(jamb_points):
                if _point_close(endpoint, gap_point):
                    matches.append(
                        (name, gap_point, jamb_points[1 - endpoint_index])
                    )
        if len(matches) != 1:
            return None
        name, gap_point, opposite = matches[0]
        if name in attached:
            return None
        attached[name] = (gap_point, opposite)

    if set(attached) != {"start", "end"}:
        return None
    start_face, start_opposite = attached["start"]
    end_face, end_opposite = attached["end"]

    start_offset = (
        (start_opposite[0] - start_face[0]) * normal[0]
        + (start_opposite[1] - start_face[1]) * normal[1]
    )
    end_offset = (
        (end_opposite[0] - end_face[0]) * normal[0]
        + (end_opposite[1] - end_face[1]) * normal[1]
    )
    if (
        abs(start_offset) <= _COORD_TOL
        or abs(end_offset) <= _COORD_TOL
        or start_offset * end_offset <= 0.0
    ):
        return None
    thickness = (abs(start_offset) + abs(end_offset)) / 2.0
    thickness_tol = max(_COORD_TOL, thickness * 0.05)
    if abs(abs(start_offset) - abs(end_offset)) > thickness_tol:
        return None

    opposite_axis = (
        end_opposite[0] - start_opposite[0],
        end_opposite[1] - start_opposite[1],
    )
    opposite_length = math.hypot(*opposite_axis)
    if opposite_length <= _COORD_TOL:
        return None
    opposite_unit = (
        opposite_axis[0] / opposite_length,
        opposite_axis[1] / opposite_length,
    )
    if abs(_cross(axis, opposite_unit)) > _PARALLEL_TOL:
        return None
    if abs(opposite_length - gap_length) > max(_COORD_TOL, gap_length * 0.02):
        return None

    origin = (
        (start_face[0] + start_opposite[0]) / 2.0,
        (start_face[1] + start_opposite[1]) / 2.0,
    )
    end_mid = (
        (end_face[0] + end_opposite[0]) / 2.0,
        (end_face[1] + end_opposite[1]) / 2.0,
    )
    direction = (end_mid[0] - origin[0], end_mid[1] - origin[1])
    length = math.hypot(*direction)
    if length <= _COORD_TOL:
        return None
    resolved_axis = (direction[0] / length, direction[1] / length)
    resolved_normal = (-resolved_axis[1], resolved_axis[0])
    return _OpeningGeometry(
        origin=origin,
        axis=resolved_axis,
        normal=resolved_normal,
        length=length,
        thickness=thickness,
    )



GENERIC_GAP_HOST_PATTERNS = frozenset(
    {
        GAP_CORROBORATED_DOOR_JAMB_LEAF,
        GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    }
)
HOST_GAP_LINEAGE_UNAVAILABLE = "opening_gap_wall_lineage_unavailable"
HOST_GAP_LINEAGE_UNMAPPED = "opening_gap_wall_lineage_unmapped"
HOST_GAP_LINEAGE_AMBIGUOUS = "opening_gap_wall_lineage_ambiguous"


def _raw_source_primitive_id(record: SourceObservationRecord) -> Optional[str]:
    """Return the exact producer source primitive referenced by a visible line."""
    ref = str(getattr(record, "source_primitive_ref", "") or "")
    prefix = "visible:"
    if not ref.startswith(prefix):
        return None
    raw_id = ref[len(prefix):].strip()
    return raw_id or None


def _unique_gap_source_records(
    records: Sequence[SourceObservationRecord],
) -> Optional[tuple[SourceObservationRecord, SourceObservationRecord]]:
    """Find exactly one positive collinear interruption among source records."""
    candidates: list[tuple[SourceObservationRecord, SourceObservationRecord]] = []
    for index, first_record in enumerate(records):
        first = _line(first_record)
        if first is None:
            return None
        for second_record in records[index + 1:]:
            second = _line(second_record)
            if second is None or not _collinear(first, second):
                continue
            axis = _canonical_unit(first)
            if axis is None:
                continue
            first_iv = _scalar_interval(first, axis)
            second_iv = _scalar_interval(second, axis)
            if first_iv[0] <= second_iv[0]:
                left_iv, right_iv = first_iv, second_iv
            else:
                left_iv, right_iv = second_iv, first_iv
            if right_iv[0] - left_iv[1] > _COORD_TOL:
                candidates.append((first_record, second_record))
    if len(candidates) != 1:
        return None
    return candidates[0]


def _resolve_gap_lineage_host_from_records(
    opening_records: Sequence[SourceObservationRecord],
    wall_records: Sequence[PhysicalWallCandidateRecord],
    equivalence: PhysicalWallEquivalenceResolution,
) -> _HostBandResolution:
    """Bind a generic gap opening to wall candidates by immutable source lineage.

    The G17 generic door/window patterns have already proved that two visible
    source wall primitives form the interrupted wall run.  This resolver does
    not use nearest-wall geometry.  It maps those exact primitives through W4
    lineage, requires one unambiguous upstream equivalence group per side, and
    retains both structural roles in the opening-scoped host group.
    """

    gap_pair = _unique_gap_source_records(opening_records)
    if gap_pair is None:
        return _HostBandResolution(
            EvidenceResolutionStatus.ABSTAINED,
            (),
            (HOST_GAP_LINEAGE_UNAVAILABLE,),
        )
    raw_ids = tuple(_raw_source_primitive_id(record) for record in gap_pair)
    if any(raw_id is None for raw_id in raw_ids):
        return _HostBandResolution(
            EvidenceResolutionStatus.ABSTAINED,
            (),
            (HOST_GAP_LINEAGE_UNAVAILABLE,),
        )
    left_raw, right_raw = raw_ids  # type: ignore[misc]
    if left_raw == right_raw:
        return _HostBandResolution(
            EvidenceResolutionStatus.ABSTAINED,
            (),
            (HOST_GAP_LINEAGE_UNAVAILABLE,),
        )

    ambiguous_ids = set(equivalence.ambiguous_wall_ids)
    group_lookup = _equivalence_group_lookup(equivalence)
    role_members: list[_RoleCandidate] = []
    for raw_id in (left_raw, right_raw):
        owners = tuple(
            record
            for record in wall_records
            if record.physical_identity.usable
            and raw_id in set(record.physical_identity.source_primitive_ids)
        )
        if not owners:
            return _HostBandResolution(
                EvidenceResolutionStatus.ABSTAINED,
                (),
                (HOST_GAP_LINEAGE_UNMAPPED,),
            )
        if any(record.wall_candidate_id in ambiguous_ids for record in owners):
            return _HostBandResolution(
                EvidenceResolutionStatus.CONFLICT,
                (),
                (HOST_GAP_LINEAGE_AMBIGUOUS, HOST_EQUIVALENCE_AMBIGUOUS),
            )

        by_group: dict[tuple[str, ...], list[PhysicalWallCandidateRecord]] = {}
        for record in owners:
            group = _equivalence_group_for(
                equivalence,
                record.wall_candidate_id,
                group_lookup=group_lookup,
            )
            by_group.setdefault(group, []).append(record)
        if len(by_group) != 1:
            return _HostBandResolution(
                EvidenceResolutionStatus.CONFLICT,
                (),
                (HOST_GAP_LINEAGE_AMBIGUOUS,),
            )
        group, members = next(iter(by_group.items()))
        chosen = sorted(members, key=lambda record: record.wall_candidate_id)[0]
        role_members.append(
            _RoleCandidate(
                offset=0.0,
                record=chosen,
                candidate_group=group,
            )
        )

    member_ids = tuple(
        sorted({member.record.wall_candidate_id for member in role_members})
    )
    identity_ids = tuple(
        sorted(
            {
                str(member.record.physical_identity.candidate_identity_id)
                for member in role_members
                if member.record.physical_identity.candidate_identity_id
            }
        )
    )
    if not member_ids or not identity_ids:
        return _HostBandResolution(
            EvidenceResolutionStatus.ABSTAINED,
            (),
            (HOST_GAP_LINEAGE_UNMAPPED,),
        )
    groups = tuple(
        sorted({tuple(sorted(member.candidate_group)) for member in role_members})
    )
    return _HostBandResolution(
        EvidenceResolutionStatus.CORROBORATED,
        (
            _HostBand(
                member_ids=member_ids,
                member_candidate_identity_ids=identity_ids,
                member_equivalence_groups=groups,
                center_offset=0.0,
            ),
        ),
        (),
    )


def _resolve_generic_gap_lineage_host(
    authority: PhysicalOpeningAuthority,
    opening: PhysicalOpeningExistenceRecord,
    wall_records: Sequence[PhysicalWallCandidateRecord],
    equivalence: PhysicalWallEquivalenceResolution,
) -> Optional[_HostBandResolution]:
    if opening.structural_pattern not in GENERIC_GAP_HOST_PATTERNS:
        return None
    visibility = authority.source_visibility_authority()
    if type(visibility) is not SourceVisibilityAuthority:
        return _HostBandResolution(
            EvidenceResolutionStatus.ABSTAINED,
            (),
            (HOST_GAP_LINEAGE_UNAVAILABLE,),
        )
    observations: list[SourceObservationRecord] = []
    for observation_id in opening.source_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.observation is None
        ):
            return _HostBandResolution(
                EvidenceResolutionStatus.ABSTAINED,
                (),
                (HOST_GAP_LINEAGE_UNAVAILABLE,),
            )
        observations.append(result.observation)
    return _resolve_gap_lineage_host_from_records(
        observations,
        wall_records,
        equivalence,
    )


def _opening_geometry(
    authority: PhysicalOpeningAuthority,
    opening: PhysicalOpeningExistenceRecord,
) -> Optional[_OpeningGeometry]:
    if opening.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION:
        bbox = opening.aperture_bbox_pt
        if bbox is None or len(bbox) != 4:
            return None
        try:
            x0, y0, x1, y1 = (float(value) for value in bbox)
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
            return None
        width = x1 - x0
        height = y1 - y0
        if width <= _COORD_TOL or height <= _COORD_TOL:
            return None

        # G17 proves framed raster openings only when the aperture span is at
        # least twice the local wall thickness. Recheck that invariant here so
        # the sealed bbox can recover orientation without nearest-wall or
        # caller-supplied geometry.
        if width > height + _COORD_TOL:
            if width + _COORD_TOL < 2.0 * height:
                return None
            return _OpeningGeometry(
                origin=(x0, (y0 + y1) / 2.0),
                axis=(1.0, 0.0),
                normal=(0.0, 1.0),
                length=width,
                thickness=height,
            )
        if height > width + _COORD_TOL:
            if height + _COORD_TOL < 2.0 * width:
                return None
            return _OpeningGeometry(
                origin=((x0 + x1) / 2.0, y0),
                axis=(0.0, 1.0),
                normal=(-1.0, 0.0),
                length=height,
                thickness=width,
            )
        return None

    visibility = authority.source_visibility_authority()
    if type(visibility) is not SourceVisibilityAuthority:
        return None
    records: list[SourceObservationRecord] = []
    for observation_id in opening.source_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=opening.document_id,
                revision_id=opening.revision_id,
                source_sha256=opening.source_sha256,
                snapshot_id=opening.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.observation is None
        ):
            return None
        records.append(result.observation)
    if opening.structural_pattern == GAP_CORROBORATED_WINDOW_JAMB_PAIR:
        return _window_jamb_pair_geometry(records)
    if len(records) != 6:
        return None

    breaks: list[tuple[Point, Point, Point]] = []
    for index, first_record in enumerate(records):
        first = _line(first_record)
        if first is None:
            return None
        for second_record in records[index + 1 :]:
            second = _line(second_record)
            if second is None or not _collinear(first, second):
                continue
            axis = _canonical_unit(first)
            assert axis is not None
            first_iv = _scalar_interval(first, axis)
            second_iv = _scalar_interval(second, axis)
            if first_iv[0] <= second_iv[0]:
                left, left_iv, right, right_iv = first, first_iv, second, second_iv
            else:
                left, left_iv, right, right_iv = second, second_iv, first, first_iv
            if right_iv[0] - left_iv[1] <= _COORD_TOL:
                continue
            start = _point_at_scalar(left, axis, left_iv[1])
            end = _point_at_scalar(right, axis, right_iv[0])
            if start is not None and end is not None:
                breaks.append((axis, start, end))

    candidates: list[_OpeningGeometry] = []
    for index, (axis, start_a, end_a) in enumerate(breaks):
        for axis_b, start_b, end_b in breaks[index + 1 :]:
            if abs(abs(axis[0] * axis_b[0] + axis[1] * axis_b[1]) - 1.0) > _COORD_TOL:
                continue
            a0 = start_a[0] * axis[0] + start_a[1] * axis[1]
            a1 = end_a[0] * axis[0] + end_a[1] * axis[1]
            b0 = start_b[0] * axis[0] + start_b[1] * axis[1]
            b1 = end_b[0] * axis[0] + end_b[1] * axis[1]
            if abs(a0 - b0) > _COORD_TOL or abs(a1 - b1) > _COORD_TOL:
                continue
            normal = (-axis[1], axis[0])
            thickness = abs(
                (start_b[0] - start_a[0]) * normal[0]
                + (start_b[1] - start_a[1]) * normal[1]
            )
            if thickness <= _COORD_TOL:
                continue
            start_mid = (
                (start_a[0] + start_b[0]) / 2.0,
                (start_a[1] + start_b[1]) / 2.0,
            )
            end_mid = (
                (end_a[0] + end_b[0]) / 2.0,
                (end_a[1] + end_b[1]) / 2.0,
            )
            length = math.hypot(end_mid[0] - start_mid[0], end_mid[1] - start_mid[1])
            if length <= _COORD_TOL:
                continue
            candidates.append(
                _OpeningGeometry(
                    origin=start_mid,
                    axis=axis,
                    normal=normal,
                    length=length,
                    thickness=thickness,
                )
            )
    if len(candidates) != 1:
        return None
    return candidates[0]


def _candidate_axis_data(
    record: PhysicalWallCandidateRecord,
    opening: _OpeningGeometry,
) -> Optional[tuple[float, float, float]]:
    wall = record.wall_candidate
    if wall.is_curved or len(wall.centerline_pts) < 2:
        return None
    if "non_simple_chain_topology_fallback_ordering" in wall.reason_codes:
        return None
    points = tuple((float(x), float(y)) for x, y in wall.centerline_pts)
    if any(not (math.isfinite(x) and math.isfinite(y)) for x, y in points):
        return None
    line = (points[0][0], points[0][1], points[-1][0], points[-1][1])
    unit = _canonical_unit(line)
    if unit is None or abs(_cross(unit, opening.axis)) > _PARALLEL_TOL:
        return None
    for start, end in zip(points, points[1:]):
        segment_unit = _canonical_unit((start[0], start[1], end[0], end[1]))
        if segment_unit is None or abs(_cross(segment_unit, opening.axis)) > _PARALLEL_TOL:
            return None
    along = tuple(_project(point, opening.origin, opening.axis) for point in points)
    offsets = tuple(_project(point, opening.origin, opening.normal) for point in points)
    if max(offsets) - min(offsets) > DEFAULT_GAP_SNAP_TOLERANCE_PT:
        return None
    return (min(along), max(along), sum(offsets) / len(offsets))


def _pair_lookup(
    equivalence: PhysicalWallEquivalenceResolution,
) -> dict[tuple[str, str], PhysicalEquivalenceClass]:
    result: dict[tuple[str, str], PhysicalEquivalenceClass] = {}
    for left, right, raw in equivalence.pair_classifications:
        key = tuple(sorted((str(left), str(right))))
        try:
            result[key] = PhysicalEquivalenceClass(raw)
        except ValueError:
            continue
    return result


def _equivalence_group_lookup(
    equivalence: PhysicalWallEquivalenceResolution,
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for group in equivalence.equivalence_groups:
        normalized = tuple(sorted(str(member) for member in group))
        for member in normalized:
            result.setdefault(member, normalized)
    return result


def _equivalence_group_for(
    equivalence: PhysicalWallEquivalenceResolution,
    wall_id: str,
    *,
    group_lookup: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> tuple[str, ...]:
    if group_lookup is not None:
        return group_lookup.get(wall_id, (wall_id,))
    for group in equivalence.equivalence_groups:
        if wall_id in group:
            return tuple(sorted(str(member) for member in group))
    return (wall_id,)


def _clusters_by_offset(
    candidates: Sequence[tuple[float, PhysicalWallCandidateRecord]],
    axis_tol: float,
) -> tuple[tuple[tuple[float, PhysicalWallCandidateRecord], ...], ...]:
    ordered = sorted(candidates, key=lambda item: (item[0], item[1].wall_candidate_id))
    clusters: list[list[tuple[float, PhysicalWallCandidateRecord]]] = []
    for item in ordered:
        if not clusters or abs(item[0] - clusters[-1][0][0]) > axis_tol:
            clusters.append([item])
        else:
            clusters[-1].append(item)
    return tuple(tuple(cluster) for cluster in clusters)


def _normalize_role_candidates(
    candidates: Sequence[tuple[float, PhysicalWallCandidateRecord]],
    equivalence: PhysicalWallEquivalenceResolution,
    axis_tol: float,
    *,
    pair_lookup: Optional[Mapping[tuple[str, str], PhysicalEquivalenceClass]] = None,
    group_lookup: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> tuple[EvidenceResolutionStatus, tuple[_RoleCandidate, ...], tuple[str, ...]]:
    """Normalize alternatives competing for one geometric host role.

    A producer-owned SAME group may legitimately span *different* structural
    roles (for example the two authenticated faces of one physical wall band).
    The global group therefore travels with each role member; it is not a
    command to delete every non-global representative from host geometry.

    Within one offset cluster, pairwise upstream equivalence still controls
    authority: AMBIGUOUS blocks, DISTINCT stays separate, and only members of
    the same positively proven SAME group may be reduced to one deterministic
    local representation. Geometry never establishes sameness by itself.
    """
    pair_lookup = _pair_lookup(equivalence) if pair_lookup is None else pair_lookup
    group_lookup = (
        _equivalence_group_lookup(equivalence)
        if group_lookup is None
        else group_lookup
    )
    normalized: list[_RoleCandidate] = []

    for cluster in _clusters_by_offset(candidates, axis_tol):
        if len(cluster) > 1:
            for index, (_left_offset, left) in enumerate(cluster):
                for _right_offset, right in cluster[index + 1 :]:
                    key = tuple(sorted((left.wall_candidate_id, right.wall_candidate_id)))
                    classification = pair_lookup.get(key)
                    if classification is None:
                        return (
                            EvidenceResolutionStatus.ABSTAINED,
                            (),
                            (HOST_EQUIVALENCE_UNAVAILABLE,),
                        )
                    if classification is PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE:
                        return (
                            EvidenceResolutionStatus.CONFLICT,
                            (),
                            (HOST_EQUIVALENCE_AMBIGUOUS,),
                        )

        by_group: dict[tuple[str, ...], list[tuple[float, PhysicalWallCandidateRecord]]] = {}
        for offset, record in cluster:
            group = _equivalence_group_for(
                equivalence,
                record.wall_candidate_id,
                group_lookup=group_lookup,
            )
            by_group.setdefault(group, []).append((offset, record))

        for group, members in sorted(by_group.items()):
            # If a SAME group spans other structural roles, only the member(s)
            # present in this local role cluster are eligible for its geometry.
            # When several proven-SAME representations compete in the same role,
            # choose a deterministic local representation only after that SAME
            # proof exists; this is not an identity heuristic.
            offset, record = sorted(
                members,
                key=lambda item: (item[0], item[1].wall_candidate_id),
            )[0]
            normalized.append(
                _RoleCandidate(offset=offset, record=record, candidate_group=group)
            )

    normalized.sort(key=lambda item: (item.offset, item.record.wall_candidate_id))
    return EvidenceResolutionStatus.CORROBORATED, tuple(normalized), ()


def _resolve_host_bands(
    records: Sequence[PhysicalWallCandidateRecord],
    opening: _OpeningGeometry,
    equivalence: PhysicalWallEquivalenceResolution,
) -> _HostBandResolution:
    left_raw: list[tuple[float, PhysicalWallCandidateRecord]] = []
    right_raw: list[tuple[float, PhysicalWallCandidateRecord]] = []
    edge_tol = max(0.5, min(2.0, opening.length * 0.02))

    for record in records:
        data = _candidate_axis_data(record, opening)
        if data is None:
            continue
        along_min, along_max, offset = data
        if along_min < -edge_tol and abs(along_max) <= edge_tol:
            left_raw.append((offset, record))
        if along_max > opening.length + edge_tol and abs(along_min - opening.length) <= edge_tol:
            right_raw.append((offset, record))

    pair_lookup = _pair_lookup(equivalence)
    group_lookup = _equivalence_group_lookup(equivalence)

    relevant_wall_ids = {
        record.wall_candidate_id for _offset, record in (*left_raw, *right_raw)
    }
    ambiguous_relevant_ids = relevant_wall_ids & set(equivalence.ambiguous_wall_ids)
    if ambiguous_relevant_ids:
        explained_ambiguous_wall_ids = {
            wall_id
            for pair, classification in pair_lookup.items()
            if classification
            is PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
            for wall_id in pair
        }
        if not ambiguous_relevant_ids <= explained_ambiguous_wall_ids:
            return _HostBandResolution(
                EvidenceResolutionStatus.CONFLICT,
                (),
                (HOST_EQUIVALENCE_AMBIGUOUS,),
            )

    axis_tol = max(0.5, opening.thickness * 0.05)
    left_status, left_candidates, left_reasons = _normalize_role_candidates(
        left_raw,
        equivalence,
        axis_tol,
        pair_lookup=pair_lookup,
        group_lookup=group_lookup,
    )
    if left_status is not EvidenceResolutionStatus.CORROBORATED:
        return _HostBandResolution(left_status, (), left_reasons)
    right_status, right_candidates, right_reasons = _normalize_role_candidates(
        right_raw,
        equivalence,
        axis_tol,
        pair_lookup=pair_lookup,
        group_lookup=group_lookup,
    )
    if right_status is not EvidenceResolutionStatus.CORROBORATED:
        return _HostBandResolution(right_status, (), right_reasons)

    face_breaks: list[_FaceBreak] = []
    for left in left_candidates:
        matches = [right for right in right_candidates if abs(right.offset - left.offset) <= axis_tol]
        for right in matches:
            face_breaks.append(_FaceBreak(left=left, right=right, offset=left.offset))

    bands: list[_HostBand] = []
    thickness_tol = max(0.75, opening.thickness * 0.15)
    proximity_limit = max(24.0, opening.thickness * 3.0)
    for index, first in enumerate(face_breaks):
        for second in face_breaks[index + 1 :]:
            separation = abs(second.offset - first.offset)
            if abs(separation - opening.thickness) > thickness_tol:
                continue
            center_offset = (first.offset + second.offset) / 2.0
            if abs(center_offset) > proximity_limit:
                continue

            role_members = (first.left, first.right, second.left, second.right)
            member_ids = tuple(sorted(member.record.wall_candidate_id for member in role_members))
            if len(set(member_ids)) != 4:
                continue

            candidate_identity_ids: list[str] = []
            groups: list[tuple[str, ...]] = []
            valid = True
            for member in role_members:
                identity = member.record.physical_identity
                if not identity.usable or not identity.candidate_identity_id:
                    valid = False
                    break
                candidate_identity_ids.append(str(identity.candidate_identity_id))
                groups.append(tuple(sorted(member.candidate_group)))
            if not valid:
                continue

            bands.append(
                _HostBand(
                    member_ids=member_ids,
                    member_candidate_identity_ids=tuple(sorted(candidate_identity_ids)),
                    member_equivalence_groups=tuple(sorted(set(groups))),
                    center_offset=center_offset,
                )
            )

    unique: dict[
        tuple[tuple[str, ...], tuple[tuple[str, ...], ...]], _HostBand
    ] = {}
    for band in bands:
        key = (band.member_ids, band.member_equivalence_groups)
        unique.setdefault(key, band)
    resolved = tuple(sorted(unique.values(), key=lambda item: (item.member_ids, item.member_equivalence_groups)))
    if len(resolved) == 1:
        center_tol = max(DEFAULT_GAP_SNAP_TOLERANCE_PT, thickness_tol)
        if abs(resolved[0].center_offset) > center_tol:
            return _HostBandResolution(
                EvidenceResolutionStatus.ABSTAINED,
                (),
                (HOST_BAND_CENTER_MISMATCH,),
            )
    return _HostBandResolution(EvidenceResolutionStatus.CORROBORATED, resolved, ())


def _host_bands(
    records: Sequence[PhysicalWallCandidateRecord],
    opening: _OpeningGeometry,
    equivalence: PhysicalWallEquivalenceResolution,
) -> tuple[_HostBand, ...]:
    """Compatibility facade for focused tests; authority uses _resolve_host_bands."""
    result = _resolve_host_bands(records, opening, equivalence)
    return result.bands if result.status is EvidenceResolutionStatus.CORROBORATED else ()


__all__ = [
    "OPENING_HOST_BINDING_SCHEMA_VERSION",
    "OpeningHostBindingAuthority",
    "OpeningHostBindingProducer",
    "OpeningHostBindingRecord",
    "OpeningHostBindingResult",
    "OpeningHostBindingSelector",
    "OpeningHostWallUniverseAuthority",
    "OpeningHostWallUniverseProducer",
    "OpeningHostWallUniverseResult",
    "OpeningHostWallUniverseSelector",
]
