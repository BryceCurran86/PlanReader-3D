"""G17 physical-opening existence and local instance identity authority.

A positive existence result is available only from producer-proven visible
native PDF geometry. Caller-published structural semantic labels remain useful
for fail-closed diagnostics, but cannot self-certify a physical opening.

Physical-opening identity is deliberately local to one authenticated source
scope. It is resolved only by independently re-proving G17 existence for both
selectors and comparing the producer-owned existence records. Dimensions,
host binding, universe completeness, physical voids, deductions and commercial
publication remain separate downstream authorities.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationAuthority,
    SourceObservationAuthorityResult,
    SourceObservationRecord,
)
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    VISIBILITY_RECEIPT_UNAVAILABLE,
    SourceVisibilityAuthority,
)


PHYSICAL_OPENING_EXISTS = "physical_opening_exists"
PHYSICAL_OPENING_EXISTENCE_UNRESOLVED = "physical_opening_existence_unresolved"
PHYSICAL_OPENING_IDENTITY_UNRESOLVED = "physical_opening_identity_unresolved"
PHYSICAL_OPENING_IDENTITIES_DISTINCT = "physical_opening_identities_distinct"
PHYSICAL_OPENING_IDENTITY_SCOPE_MISMATCH = "physical_opening_identity_scope_mismatch"
PHYSICAL_OPENING_IDENTITY_EXISTENCE_REQUIRED = "physical_opening_identity_existence_required"
PHYSICAL_OPENING_IDENTITY_RESOLVED = "physical_opening_identity_resolved"

AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE = (
    "authoritative_physical_opening_semantics_unavailable"
)
AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE = (
    "authoritative_physical_opening_identity_unavailable"
)
MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY = (
    "independent source-native physical opening instance semantic producer"
)

JAMB_BOUNDED_TWO_FACE_INTERRUPTION = "jamb_bounded_two_face_interruption"
WALL_FACE_INTERRUPTION_KIND = "wall_face_interruption"
OPENING_JAMB_BOUNDARY_KIND = "opening_jamb_boundary"
WEAK_PHYSICAL_OPENING_CANDIDATE_KINDS = frozenset(
    {"opening_swing_arc", "wall_gap_candidate"}
)

STRUCTURAL_OPENING_CANDIDATE = "structural_opening_candidate"
STRUCTURAL_OPENING_EXISTENCE_RESOLVED = "structural_opening_existence_resolved"
AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES = "ambiguous_physical_opening_candidates"
INSUFFICIENT_INDEPENDENT_SOURCE_LINEAGE = "insufficient_independent_source_lineage"
INVALID_STRUCTURAL_GEOMETRY = "invalid_structural_geometry"
SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE = "snapshot_observation_integrity_failure"
VISIBLE_WALL_CONTINUATION_REQUIRED = "visible_wall_continuation_required"
VISIBLE_SOURCE_AUTHORITY_REQUIRED = "visible_source_authority_required"

# Numeric equality only. These are not proximity/search radii and cannot create
# candidate membership between otherwise unrelated primitives.
_COORD_EQ_ABS_TOL = 1e-6
_PARALLEL_REL_TOL = 1e-9


@dataclass(frozen=True)
class CandidateSemanticOpening:
    """Producer-snapshot-owned candidate, not yet a broader opening identity."""

    candidate_id: str
    source_observation_ids: tuple[str, ...]
    source_lineage_root_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    structural_pattern: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PhysicalOpeningExistenceRecord:
    """Narrow resolved proposition: one local physical opening exists."""

    record_id: str
    source_observation_ids: tuple[str, ...]
    source_lineage_root_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    semantic_class: str
    status: EvidenceResolutionStatus
    proposition: str
    structural_pattern: str
    diagnostic_confidence: float
    blocking_reasons: tuple[str, ...]
    structural_reason_codes: tuple[str, ...]
    producer_method: str
    producer_version: str
    producer_generation: int


@dataclass(frozen=True)
class PhysicalOpeningExistenceResult:
    """Fail-closed result for the physical-opening existence proposition."""

    status: EvidenceResolutionStatus
    proposition: Optional[str]
    physical_opening_existence: str
    reason_codes: tuple[str, ...]
    source_observation: Optional[SourceObservationAuthorityResult] = None
    candidate: Optional[CandidateSemanticOpening] = None
    existence_record: Optional[PhysicalOpeningExistenceRecord] = None
    missing_upstream_capability: Optional[str] = None


@dataclass(frozen=True)
class PhysicalOpeningIdentityResult:
    """Fail-closed result for whether two observations denote one opening."""

    status: EvidenceResolutionStatus
    physical_opening_identity: str
    proven_same: bool
    reason_codes: tuple[str, ...]
    left_source_observation: Optional[SourceObservationAuthorityResult] = None
    right_source_observation: Optional[SourceObservationAuthorityResult] = None
    missing_upstream_capability: Optional[str] = None


@dataclass(frozen=True)
class _FaceBreak:
    first: SourceObservationRecord
    second: SourceObservationRecord
    gap_start: float
    gap_end: float
    start_point: tuple[float, float]
    end_point: tuple[float, float]
    direction: tuple[float, float]


def _dedupe_reason_codes(*groups: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for group in groups:
        for reason in group:
            clean = str(reason or "").strip()
            if clean and clean not in result:
                result.append(clean)
    return tuple(result)


def _source_failure_status(*results: SourceObservationAuthorityResult) -> EvidenceResolutionStatus:
    if any(result.status is EvidenceResolutionStatus.CONFLICT for result in results):
        return EvidenceResolutionStatus.CONFLICT
    return EvidenceResolutionStatus.ABSTAINED


def _line_geometry(record: SourceObservationRecord) -> Optional[tuple[float, float, float, float]]:
    if len(record.geometry) != 4:
        return None
    values = tuple(float(value) for value in record.geometry)
    if not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = values
    if math.hypot(x2 - x1, y2 - y1) <= _COORD_EQ_ABS_TOL:
        return None
    return (x1, y1, x2, y2)


def _point_close(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return (
        abs(left[0] - right[0]) <= _COORD_EQ_ABS_TOL
        and abs(left[1] - right[1]) <= _COORD_EQ_ABS_TOL
    )


def _segment_matches(
    record: SourceObservationRecord,
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    line = _line_geometry(record)
    if line is None:
        return False
    start = (line[0], line[1])
    end = (line[2], line[3])
    return (
        _point_close(start, first) and _point_close(end, second)
    ) or (
        _point_close(start, second) and _point_close(end, first)
    )


def _parallel(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    ldx, ldy = left[2] - left[0], left[3] - left[1]
    rdx, rdy = right[2] - right[0], right[3] - right[1]
    llen = math.hypot(ldx, ldy)
    rlen = math.hypot(rdx, rdy)
    if llen <= _COORD_EQ_ABS_TOL or rlen <= _COORD_EQ_ABS_TOL:
        return False
    return abs(ldx * rdy - ldy * rdx) <= _PARALLEL_REL_TOL * llen * rlen


def _canonical_direction(line: tuple[float, float, float, float]) -> tuple[float, float]:
    dx, dy = line[2] - line[0], line[3] - line[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    if ux < -_COORD_EQ_ABS_TOL or (
        abs(ux) <= _COORD_EQ_ABS_TOL and uy < 0.0
    ):
        ux, uy = -ux, -uy
    return (ux, uy)


def _projection(point: tuple[float, float], direction: tuple[float, float]) -> float:
    return point[0] * direction[0] + point[1] * direction[1]


def _cross(left: tuple[float, float], right: tuple[float, float]) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _collinear(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    if not _parallel(left, right):
        return False
    direction = _canonical_direction(left)
    delta = (right[0] - left[0], right[1] - left[1])
    return abs(_cross(direction, delta)) <= _COORD_EQ_ABS_TOL


def _endpoint_at_projection(
    line: tuple[float, float, float, float],
    direction: tuple[float, float],
    target: float,
) -> Optional[tuple[float, float]]:
    first = (line[0], line[1])
    second = (line[2], line[3])
    if abs(_projection(first, direction) - target) <= _COORD_EQ_ABS_TOL:
        return first
    if abs(_projection(second, direction) - target) <= _COORD_EQ_ABS_TOL:
        return second
    return None


def _face_break(
    first: SourceObservationRecord,
    second: SourceObservationRecord,
) -> Optional[_FaceBreak]:
    first_line = _line_geometry(first)
    second_line = _line_geometry(second)
    if first_line is None or second_line is None or not _collinear(first_line, second_line):
        return None
    direction = _canonical_direction(first_line)
    first_values = sorted(
        (_projection((first_line[0], first_line[1]), direction),
         _projection((first_line[2], first_line[3]), direction))
    )
    second_values = sorted(
        (_projection((second_line[0], second_line[1]), direction),
         _projection((second_line[2], second_line[3]), direction))
    )
    if first_values[0] <= second_values[0]:
        left_record, left_line, left_values = first, first_line, first_values
        right_record, right_line, right_values = second, second_line, second_values
    else:
        left_record, left_line, left_values = second, second_line, second_values
        right_record, right_line, right_values = first, first_line, first_values
    gap_start = left_values[1]
    gap_end = right_values[0]
    if gap_end - gap_start <= _COORD_EQ_ABS_TOL:
        return None
    start_point = _endpoint_at_projection(left_line, direction, gap_start)
    end_point = _endpoint_at_projection(right_line, direction, gap_end)
    if start_point is None or end_point is None:
        return None
    return _FaceBreak(
        first=left_record,
        second=right_record,
        gap_start=gap_start,
        gap_end=gap_end,
        start_point=start_point,
        end_point=end_point,
        direction=direction,
    )


def _same_gap(left: _FaceBreak, right: _FaceBreak) -> bool:
    if abs(left.gap_start - right.gap_start) > _COORD_EQ_ABS_TOL:
        return False
    if abs(left.gap_end - right.gap_end) > _COORD_EQ_ABS_TOL:
        return False
    dot = left.direction[0] * right.direction[0] + left.direction[1] * right.direction[1]
    return abs(abs(dot) - 1.0) <= _PARALLEL_REL_TOL


def _distinct_parallel_axes(left: _FaceBreak, right: _FaceBreak) -> bool:
    delta = (
        right.start_point[0] - left.start_point[0],
        right.start_point[1] - left.start_point[1],
    )
    return abs(_cross(left.direction, delta)) > _COORD_EQ_ABS_TOL


def _canonical_line(record: SourceObservationRecord) -> tuple[tuple[float, float], tuple[float, float]]:
    line = _line_geometry(record)
    if line is None:
        return ((0.0, 0.0), (0.0, 0.0))
    first = (round(line[0], 6), round(line[1], 6))
    second = (round(line[2], 6), round(line[3], 6))
    return tuple(sorted((first, second)))  # type: ignore[return-value]


class PhysicalOpeningAuthority:
    """Read-only authority over source-proven opening existence and local identity."""

    def __init__(
        self,
        source_observation_authority: SourceObservationAuthority | SourceVisibilityAuthority,
    ) -> None:
        if type(source_observation_authority) is SourceObservationAuthority:
            self._source_observation_authority: Optional[SourceObservationAuthority] = (
                source_observation_authority
            )
            self._source_visibility_authority: Optional[SourceVisibilityAuthority] = None
        elif type(source_observation_authority) is SourceVisibilityAuthority:
            self._source_observation_authority = None
            self._source_visibility_authority = source_observation_authority
        else:
            raise TypeError(
                "source_observation_authority must be the concrete producer-owned "
                "SourceObservationAuthority or SourceVisibilityAuthority reader"
            )

    def source_visibility_authority(self) -> Optional[SourceVisibilityAuthority]:
        """Return the producer-owned visibility reader when this authority is visibility-backed.

        Raw diagnostic mode deliberately returns ``None``. Downstream authorities
        that require source-visible geometry can therefore fail closed without
        reaching through this class's private storage.
        """
        return self._source_visibility_authority

    @staticmethod
    def capabilities() -> dict[str, bool]:
        return {
            "physical_opening_existence": True,
            "physical_opening_identity": True,
            "opening_universe_complete": False,
            "opening_dimensions": False,
            "host_identity": False,
            "host_binding": False,
            "physical_void": False,
            "net_wall_area": False,
        }

    def _raw_snapshot_records(
        self,
        seed: SourceObservationAuthorityResult,
    ) -> tuple[tuple[SourceObservationRecord, ...], tuple[SourceObservationAuthorityResult, ...]]:
        source = self._source_observation_authority
        if source is None or seed.snapshot is None or seed.source_revision is None:
            return (), ()
        records: list[SourceObservationRecord] = []
        failures: list[SourceObservationAuthorityResult] = []
        for observation_id in seed.snapshot.observation_ids:
            result = source.resolve(
                ObservationSelector(
                    document_id=seed.snapshot.document_id,
                    revision_id=seed.snapshot.revision_id,
                    source_sha256=seed.snapshot.source_sha256,
                    snapshot_id=seed.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if result.status is EvidenceResolutionStatus.CORROBORATED and result.observation:
                records.append(result.observation)
            else:
                failures.append(result)
        return tuple(records), tuple(failures)

    def _visible_snapshot_records(
        self,
        seed: SourceObservationAuthorityResult,
    ) -> tuple[tuple[SourceObservationRecord, ...], tuple[SourceObservationAuthorityResult, ...]]:
        visibility = self._source_visibility_authority
        if visibility is None or seed.snapshot is None or seed.source_revision is None:
            return (), ()
        records: list[SourceObservationRecord] = []
        failures: list[SourceObservationAuthorityResult] = []
        for observation_id in seed.snapshot.observation_ids:
            result = visibility.resolve_visible(
                ObservationSelector(
                    document_id=seed.snapshot.document_id,
                    revision_id=seed.snapshot.revision_id,
                    source_sha256=seed.snapshot.source_sha256,
                    snapshot_id=seed.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if result.status is EvidenceResolutionStatus.CORROBORATED and result.observation:
                records.append(result.observation)
            elif result.status is EvidenceResolutionStatus.CONFLICT:
                failures.append(result)
            elif VISIBILITY_RECEIPT_UNAVAILABLE not in result.reason_codes:
                failures.append(result)
        return tuple(records), tuple(failures)

    @staticmethod
    def _raw_structural_candidates(
        seed: SourceObservationRecord,
        records: tuple[SourceObservationRecord, ...],
    ) -> tuple[CandidateSemanticOpening, ...]:
        scoped = tuple(
            record
            for record in records
            if record.document_id == seed.document_id
            and record.revision_id == seed.revision_id
            and record.source_sha256 == seed.source_sha256
            and record.snapshot_id == seed.snapshot_id
            and record.page_id == seed.page_id
            and record.viewport_id == seed.viewport_id
        )
        faces = tuple(
            record for record in scoped
            if record.observation_kind == WALL_FACE_INTERRUPTION_KIND
            and _line_geometry(record) is not None
        )
        jambs = tuple(
            record for record in scoped
            if record.observation_kind == OPENING_JAMB_BOUNDARY_KIND
            and _line_geometry(record) is not None
        )
        discovered: dict[tuple[object, ...], tuple[set[str], set[str]]] = {}
        for index, first_face in enumerate(faces):
            first_line = _line_geometry(first_face)
            if first_line is None:
                continue
            for second_face in faces[index + 1:]:
                second_line = _line_geometry(second_face)
                if second_line is None or not _parallel(first_line, second_line):
                    continue
                orientations = (
                    ((first_line[0], first_line[1]), (second_line[0], second_line[1]),
                     (first_line[2], first_line[3]), (second_line[2], second_line[3])),
                    ((first_line[0], first_line[1]), (second_line[2], second_line[3]),
                     (first_line[2], first_line[3]), (second_line[0], second_line[1])),
                )
                for first_a, first_b, second_a, second_b in orientations:
                    left_jambs = tuple(j for j in jambs if _segment_matches(j, first_a, first_b))
                    right_jambs = tuple(j for j in jambs if _segment_matches(j, second_a, second_b))
                    for left_jamb in left_jambs:
                        for right_jamb in right_jambs:
                            support = (first_face, second_face, left_jamb, right_jamb)
                            if len({item.observation_id for item in support}) != 4:
                                continue
                            geometry_key = tuple(sorted(_canonical_line(item) for item in support))
                            roots = {
                                parent
                                for item in support
                                for parent in item.derivation_parent_ids
                            }
                            key = (seed.document_id, seed.revision_id, seed.source_sha256,
                                   seed.snapshot_id, seed.page_id, seed.viewport_id, geometry_key)
                            if key in discovered:
                                discovered[key][0].update(item.observation_id for item in support)
                                discovered[key][1].update(roots)
                            else:
                                discovered[key] = (
                                    {item.observation_id for item in support}, set(roots)
                                )
        result: list[CandidateSemanticOpening] = []
        for key in sorted(discovered, key=repr):
            observation_ids, root_ids = discovered[key]
            payload = {
                "document_id": seed.document_id,
                "revision_id": seed.revision_id,
                "source_sha256": seed.source_sha256,
                "snapshot_id": seed.snapshot_id,
                "page_id": seed.page_id,
                "viewport_id": seed.viewport_id,
                "structural_pattern": JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
                "source_observation_ids": tuple(sorted(observation_ids)),
                "source_lineage_root_ids": tuple(sorted(root_ids)),
            }
            result.append(CandidateSemanticOpening(
                candidate_id=stable_contract_id("physical_opening_candidate", payload, digest_chars=32),
                source_observation_ids=tuple(sorted(observation_ids)),
                source_lineage_root_ids=tuple(sorted(root_ids)),
                document_id=seed.document_id,
                revision_id=seed.revision_id,
                source_sha256=seed.source_sha256,
                snapshot_id=seed.snapshot_id,
                page_id=seed.page_id,
                viewport_id=seed.viewport_id,
                structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
                status=EvidenceResolutionStatus.CANDIDATE,
                reason_codes=(STRUCTURAL_OPENING_CANDIDATE, VISIBLE_SOURCE_AUTHORITY_REQUIRED),
            ))
        return tuple(result)

    @staticmethod
    def _visible_structural_candidates(
        seed: SourceObservationRecord,
        records: tuple[SourceObservationRecord, ...],
    ) -> tuple[CandidateSemanticOpening, ...]:
        scoped = tuple(
            record
            for record in records
            if record.observation_kind in {
                NATIVE_PDF_VISIBLE_SEGMENT,
                RASTER_PDF_VISIBLE_SEGMENT,
            }
            and record.document_id == seed.document_id
            and record.revision_id == seed.revision_id
            and record.source_sha256 == seed.source_sha256
            and record.snapshot_id == seed.snapshot_id
            and record.page_id == seed.page_id
            and record.viewport_id is None
            and _line_geometry(record) is not None
        )
        breaks: list[_FaceBreak] = []
        for index, first in enumerate(scoped):
            for second in scoped[index + 1:]:
                found = _face_break(first, second)
                if found is not None:
                    breaks.append(found)

        discovered: dict[tuple[object, ...], tuple[SourceObservationRecord, ...]] = {}
        for index, first_break in enumerate(breaks):
            for second_break in breaks[index + 1:]:
                if not _same_gap(first_break, second_break):
                    continue
                if not _distinct_parallel_axes(first_break, second_break):
                    continue
                left_jambs = tuple(
                    record for record in scoped
                    if _segment_matches(record, first_break.start_point, second_break.start_point)
                )
                right_jambs = tuple(
                    record for record in scoped
                    if _segment_matches(record, first_break.end_point, second_break.end_point)
                )
                for left_jamb in left_jambs:
                    for right_jamb in right_jambs:
                        support = (
                            first_break.first, first_break.second,
                            second_break.first, second_break.second,
                            left_jamb, right_jamb,
                        )
                        if len({item.observation_id for item in support}) != 6:
                            continue
                        parent_ids: list[str] = []
                        lineage_ok = True
                        for item in support:
                            if len(item.derivation_parent_ids) != 1:
                                lineage_ok = False
                                break
                            parent_ids.append(item.derivation_parent_ids[0])
                        if not lineage_ok or len(set(parent_ids)) != 6:
                            continue
                        geometry_key = tuple(sorted(_canonical_line(item) for item in support))
                        key = (
                            seed.document_id, seed.revision_id, seed.source_sha256,
                            seed.snapshot_id, seed.page_id, geometry_key,
                        )
                        discovered[key] = support

        candidates: list[CandidateSemanticOpening] = []
        for key in sorted(discovered, key=repr):
            support = discovered[key]
            observation_ids = tuple(sorted(item.observation_id for item in support))
            root_ids = tuple(sorted(item.derivation_parent_ids[0] for item in support))
            payload = {
                "document_id": seed.document_id,
                "revision_id": seed.revision_id,
                "source_sha256": seed.source_sha256,
                "snapshot_id": seed.snapshot_id,
                "page_id": seed.page_id,
                "viewport_id": None,
                "structural_pattern": JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
                "source_observation_ids": observation_ids,
                "source_lineage_root_ids": root_ids,
            }
            candidates.append(CandidateSemanticOpening(
                candidate_id=stable_contract_id("physical_opening_candidate", payload, digest_chars=32),
                source_observation_ids=observation_ids,
                source_lineage_root_ids=root_ids,
                document_id=seed.document_id,
                revision_id=seed.revision_id,
                source_sha256=seed.source_sha256,
                snapshot_id=seed.snapshot_id,
                page_id=seed.page_id,
                viewport_id=None,
                structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
                status=EvidenceResolutionStatus.CANDIDATE,
                reason_codes=(JAMB_BOUNDED_TWO_FACE_INTERRUPTION, VISIBLE_WALL_CONTINUATION_REQUIRED),
            ))
        return tuple(candidates)

    @staticmethod
    def _single_raw_candidate(
        observation: SourceObservationRecord,
    ) -> CandidateSemanticOpening:
        roots = tuple(sorted(observation.derivation_parent_ids))
        payload = {
            "document_id": observation.document_id,
            "revision_id": observation.revision_id,
            "source_sha256": observation.source_sha256,
            "snapshot_id": observation.snapshot_id,
            "page_id": observation.page_id,
            "viewport_id": observation.viewport_id,
            "source_observation_ids": (observation.observation_id,),
            "source_lineage_root_ids": roots,
            "structural_pattern": STRUCTURAL_OPENING_CANDIDATE,
        }
        reasons = (STRUCTURAL_OPENING_CANDIDATE, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        if observation.observation_kind in {WALL_FACE_INTERRUPTION_KIND, OPENING_JAMB_BOUNDARY_KIND} \
                and _line_geometry(observation) is None:
            reasons = _dedupe_reason_codes(reasons, (INVALID_STRUCTURAL_GEOMETRY,))
        return CandidateSemanticOpening(
            candidate_id=stable_contract_id("physical_opening_candidate", payload, digest_chars=32),
            source_observation_ids=(observation.observation_id,),
            source_lineage_root_ids=roots,
            document_id=observation.document_id,
            revision_id=observation.revision_id,
            source_sha256=observation.source_sha256,
            snapshot_id=observation.snapshot_id,
            page_id=observation.page_id,
            viewport_id=observation.viewport_id,
            structural_pattern=STRUCTURAL_OPENING_CANDIDATE,
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=reasons,
        )

    def prove_existence(self, selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")

        if self._source_visibility_authority is None:
            source = self._source_observation_authority
            assert source is not None
            source_result = source.resolve(selector)
            if source_result.status is not EvidenceResolutionStatus.CORROBORATED or source_result.observation is None:
                return PhysicalOpeningExistenceResult(
                    status=_source_failure_status(source_result), proposition=None,
                    physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                    reason_codes=_dedupe_reason_codes(source_result.reason_codes),
                    source_observation=source_result,
                    missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
                )
            records, failures = self._raw_snapshot_records(source_result)
            if failures:
                return PhysicalOpeningExistenceResult(
                    status=_source_failure_status(*failures), proposition=None,
                    physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                    reason_codes=_dedupe_reason_codes(
                        (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,),
                        *tuple(result.reason_codes for result in failures),
                    ), source_observation=source_result,
                )
            observation = source_result.observation
            candidates = self._raw_structural_candidates(observation, records)
            containing = tuple(
                candidate for candidate in candidates
                if observation.observation_id in candidate.source_observation_ids
            )
            if len(containing) > 1:
                return PhysicalOpeningExistenceResult(
                    status=EvidenceResolutionStatus.CONFLICT, proposition=None,
                    physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                    reason_codes=(AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,),
                    source_observation=source_result,
                )
            if observation.observation_kind in {
                WALL_FACE_INTERRUPTION_KIND, OPENING_JAMB_BOUNDARY_KIND,
                *WEAK_PHYSICAL_OPENING_CANDIDATE_KINDS,
            }:
                candidate = containing[0] if containing else self._single_raw_candidate(observation)
                return PhysicalOpeningExistenceResult(
                    status=EvidenceResolutionStatus.CANDIDATE, proposition=None,
                    physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                    reason_codes=candidate.reason_codes,
                    source_observation=source_result, candidate=candidate,
                    missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
                )
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED, proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        visibility = self._source_visibility_authority
        source_result = visibility.resolve_visible(selector)
        if source_result.status is not EvidenceResolutionStatus.CORROBORATED or source_result.observation is None:
            return PhysicalOpeningExistenceResult(
                status=_source_failure_status(source_result), proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=_dedupe_reason_codes(source_result.reason_codes),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )
        records, failures = self._visible_snapshot_records(source_result)
        if failures:
            return PhysicalOpeningExistenceResult(
                status=_source_failure_status(*failures), proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=_dedupe_reason_codes(
                    (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,),
                    *tuple(result.reason_codes for result in failures),
                ), source_observation=source_result,
            )
        observation = source_result.observation
        candidates = self._visible_structural_candidates(observation, records)
        containing = tuple(
            candidate for candidate in candidates
            if observation.observation_id in candidate.source_observation_ids
        )
        if len(containing) > 1:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CONFLICT, proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=(AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,),
                source_observation=source_result,
            )
        if len(containing) != 1 or source_result.snapshot is None:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED, proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=(VISIBLE_WALL_CONTINUATION_REQUIRED,),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        candidate = containing[0]
        record_payload = {
            "document_id": candidate.document_id,
            "revision_id": candidate.revision_id,
            "source_sha256": candidate.source_sha256,
            "snapshot_id": candidate.snapshot_id,
            "page_id": candidate.page_id,
            "viewport_id": candidate.viewport_id,
            "semantic_class": "opening",
            "structural_pattern": candidate.structural_pattern,
            "source_observation_ids": candidate.source_observation_ids,
            "source_lineage_root_ids": candidate.source_lineage_root_ids,
        }
        existence = PhysicalOpeningExistenceRecord(
            record_id=stable_contract_id("physical_opening_existence", record_payload, digest_chars=32),
            source_observation_ids=candidate.source_observation_ids,
            source_lineage_root_ids=candidate.source_lineage_root_ids,
            document_id=candidate.document_id,
            revision_id=candidate.revision_id,
            source_sha256=candidate.source_sha256,
            snapshot_id=candidate.snapshot_id,
            page_id=candidate.page_id,
            viewport_id=None,
            semantic_class="opening",
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            structural_pattern=candidate.structural_pattern,
            diagnostic_confidence=1.0,
            blocking_reasons=(),
            structural_reason_codes=(STRUCTURAL_OPENING_EXISTENCE_RESOLVED,),
            producer_method=source_result.snapshot.producer_method,
            producer_version=source_result.snapshot.producer_version,
            producer_generation=source_result.snapshot.producer_generation,
        )
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence=PHYSICAL_OPENING_EXISTS,
            reason_codes=(STRUCTURAL_OPENING_EXISTENCE_RESOLVED,),
            source_observation=source_result,
            candidate=candidate,
            existence_record=existence,
        )

    @staticmethod
    def _identity_scope(record: PhysicalOpeningExistenceRecord) -> tuple[str, str, str, str, str]:
        return (
            record.document_id,
            record.revision_id,
            record.source_sha256,
            record.snapshot_id,
            record.page_id,
        )

    def compare_identity(
        self,
        left_selector: ObservationSelector,
        right_selector: ObservationSelector,
    ) -> PhysicalOpeningIdentityResult:
        """Compare two selectors using independently re-proven G17 existence only."""
        if not isinstance(left_selector, ObservationSelector):
            raise TypeError("left_selector must be ObservationSelector")
        if not isinstance(right_selector, ObservationSelector):
            raise TypeError("right_selector must be ObservationSelector")

        left_existence = self.prove_existence(left_selector)
        right_existence = self.prove_existence(right_selector)
        left_source = left_existence.source_observation
        right_source = right_existence.source_observation

        if (
            left_existence.status is not EvidenceResolutionStatus.CORROBORATED
            or right_existence.status is not EvidenceResolutionStatus.CORROBORATED
            or left_existence.existence_record is None
            or right_existence.existence_record is None
            or left_existence.proposition != PHYSICAL_OPENING_EXISTS
            or right_existence.proposition != PHYSICAL_OPENING_EXISTS
        ):
            status = (
                EvidenceResolutionStatus.CONFLICT
                if (
                    left_existence.status is EvidenceResolutionStatus.CONFLICT
                    or right_existence.status is EvidenceResolutionStatus.CONFLICT
                )
                else EvidenceResolutionStatus.ABSTAINED
            )
            return PhysicalOpeningIdentityResult(
                status=status,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
                proven_same=False,
                reason_codes=_dedupe_reason_codes(
                    (PHYSICAL_OPENING_IDENTITY_EXISTENCE_REQUIRED,),
                    left_existence.reason_codes,
                    right_existence.reason_codes,
                ),
                left_source_observation=left_source,
                right_source_observation=right_source,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        left_record = left_existence.existence_record
        right_record = right_existence.existence_record
        if self._identity_scope(left_record) != self._identity_scope(right_record):
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
                proven_same=False,
                reason_codes=(PHYSICAL_OPENING_IDENTITY_SCOPE_MISMATCH,),
                left_source_observation=left_source,
                right_source_observation=right_source,
                missing_upstream_capability=(
                    "independent cross-scope physical opening equivalence authority"
                ),
            )

        if left_record.record_id == right_record.record_id:
            return PhysicalOpeningIdentityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                physical_opening_identity=left_record.record_id,
                proven_same=True,
                reason_codes=(PHYSICAL_OPENING_IDENTITY_RESOLVED,),
                left_source_observation=left_source,
                right_source_observation=right_source,
            )

        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
            proven_same=False,
            reason_codes=(PHYSICAL_OPENING_IDENTITY_RESOLVED,),
            left_source_observation=left_source,
            right_source_observation=right_source,
        )


__all__ = [
    "AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES",
    "AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE",
    "AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE",
    "CandidateSemanticOpening",
    "INSUFFICIENT_INDEPENDENT_SOURCE_LINEAGE",
    "INVALID_STRUCTURAL_GEOMETRY",
    "JAMB_BOUNDED_TWO_FACE_INTERRUPTION",
    "MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY",
    "OPENING_JAMB_BOUNDARY_KIND",
    "PHYSICAL_OPENING_EXISTS",
    "PHYSICAL_OPENING_EXISTENCE_UNRESOLVED",
    "PHYSICAL_OPENING_IDENTITIES_DISTINCT",
    "PHYSICAL_OPENING_IDENTITY_EXISTENCE_REQUIRED",
    "PHYSICAL_OPENING_IDENTITY_RESOLVED",
    "PHYSICAL_OPENING_IDENTITY_SCOPE_MISMATCH",
    "PHYSICAL_OPENING_IDENTITY_UNRESOLVED",
    "PhysicalOpeningAuthority",
    "PhysicalOpeningExistenceRecord",
    "PhysicalOpeningExistenceResult",
    "PhysicalOpeningIdentityResult",
    "SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE",
    "STRUCTURAL_OPENING_CANDIDATE",
    "STRUCTURAL_OPENING_EXISTENCE_RESOLVED",
    "VISIBLE_SOURCE_AUTHORITY_REQUIRED",
    "VISIBLE_WALL_CONTINUATION_REQUIRED",
    "WALL_FACE_INTERRUPTION_KIND",
    "WEAK_PHYSICAL_OPENING_CANDIDATE_KINDS",
]
