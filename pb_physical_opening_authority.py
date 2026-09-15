"""G17 phase-2 physical-opening semantic authority boundary.

Phase 1 proves immutable producer-owned source observations exist and are bound
to exact PDF bytes.  Phase 2 remains deliberately narrower than opening
identity, dimensions, host binding, universe completeness, physical voids or
commercial deductions.

A positive physical-opening-existence result is available only for one reviewed
structural pattern: a producer-backed jamb-bounded interruption of two wall
faces.  Candidate membership is rediscovered from the producer-owned snapshot;
callers cannot supply candidate sets, corroboration flags, confidence thresholds
or semantic labels.  Every structural support must trace to independent native
source roots.  Weaker evidence remains candidate/blocked and identity remains
fail-closed.
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


PHYSICAL_OPENING_EXISTS = "physical_opening_exists"
PHYSICAL_OPENING_EXISTENCE_UNRESOLVED = "physical_opening_existence_unresolved"
PHYSICAL_OPENING_IDENTITY_UNRESOLVED = "physical_opening_identity_unresolved"

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

# This tolerance is only for deterministic equality of already-produced source
# coordinates.  It is not a proximity/search radius and cannot create candidate
# membership between otherwise unrelated primitives.
_COORD_EQ_ABS_TOL = 1e-6
_PARALLEL_REL_TOL = 1e-9


@dataclass(frozen=True)
class CandidateSemanticOpening:
    """Producer-snapshot-owned candidate, not yet a physical-opening fact."""

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
    values = tuple(float(v) for v in record.geometry)
    if not all(math.isfinite(v) for v in values):
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
    cross = abs(ldx * rdy - ldy * rdx)
    return cross <= _PARALLEL_REL_TOL * llen * rlen


def _canonical_line(line: tuple[float, float, float, float]) -> tuple[tuple[float, float], tuple[float, float]]:
    first = (round(line[0], 6), round(line[1], 6))
    second = (round(line[2], 6), round(line[3], 6))
    return tuple(sorted((first, second)))  # type: ignore[return-value]


class PhysicalOpeningAuthority:
    """Read-only Phase-2 consumer over the concrete Phase-1 authority reader."""

    def __init__(self, source_observation_authority: SourceObservationAuthority) -> None:
        if type(source_observation_authority) is not SourceObservationAuthority:
            raise TypeError(
                "source_observation_authority must be the concrete producer-owned "
                "SourceObservationAuthority reader"
            )
        self._source_observation_authority = source_observation_authority

    @staticmethod
    def capabilities() -> dict[str, bool]:
        """Declare propositions this Phase-2 slice can establish."""

        return {
            "physical_opening_existence": True,
            "physical_opening_identity": False,
            "opening_universe_complete": False,
            "opening_dimensions": False,
            "host_identity": False,
            "host_binding": False,
            "physical_void": False,
            "net_wall_area": False,
        }

    def _snapshot_records(
        self,
        seed: SourceObservationAuthorityResult,
    ) -> tuple[tuple[SourceObservationRecord, ...], tuple[SourceObservationAuthorityResult, ...]]:
        if seed.snapshot is None or seed.source_revision is None:
            return (), ()
        records: list[SourceObservationRecord] = []
        failures: list[SourceObservationAuthorityResult] = []
        for observation_id in seed.snapshot.observation_ids:
            selector = ObservationSelector(
                document_id=seed.snapshot.document_id,
                revision_id=seed.snapshot.revision_id,
                source_sha256=seed.snapshot.source_sha256,
                snapshot_id=seed.snapshot.snapshot_id,
                observation_id=observation_id,
            )
            result = self._source_observation_authority.resolve(selector)
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.observation is None
            ):
                failures.append(result)
            else:
                records.append(result.observation)
        return tuple(records), tuple(failures)

    @staticmethod
    def _lineage_roots(
        record: SourceObservationRecord,
        records_by_id: dict[str, SourceObservationRecord],
        memo: dict[str, Optional[frozenset[str]]],
        visiting: Optional[set[str]] = None,
    ) -> Optional[frozenset[str]]:
        cached = memo.get(record.observation_id)
        if cached is not None or record.observation_id in memo:
            return cached
        active = set() if visiting is None else set(visiting)
        if record.observation_id in active:
            memo[record.observation_id] = None
            return None
        active.add(record.observation_id)
        if not record.derivation_parent_ids:
            if record.origin_kind != "native":
                memo[record.observation_id] = None
                return None
            roots = frozenset((record.observation_id,))
            memo[record.observation_id] = roots
            return roots
        roots_set: set[str] = set()
        for parent_id in record.derivation_parent_ids:
            parent = records_by_id.get(parent_id)
            if parent is None:
                memo[record.observation_id] = None
                return None
            parent_roots = PhysicalOpeningAuthority._lineage_roots(
                parent, records_by_id, memo, active
            )
            if not parent_roots:
                memo[record.observation_id] = None
                return None
            roots_set.update(parent_roots)
        roots = frozenset(roots_set)
        memo[record.observation_id] = roots
        return roots

    @staticmethod
    def _independent_roots(root_sets: tuple[frozenset[str], ...]) -> bool:
        if any(not roots for roots in root_sets):
            return False
        for index, left in enumerate(root_sets):
            for right in root_sets[index + 1 :]:
                if left.intersection(right):
                    return False
        return True

    def _discover_structural_candidates(
        self,
        *,
        seed_observation: SourceObservationRecord,
        records: tuple[SourceObservationRecord, ...],
    ) -> tuple[CandidateSemanticOpening, ...]:
        scoped = tuple(
            record
            for record in records
            if record.document_id == seed_observation.document_id
            and record.revision_id == seed_observation.revision_id
            and record.source_sha256 == seed_observation.source_sha256
            and record.snapshot_id == seed_observation.snapshot_id
            and record.page_id == seed_observation.page_id
            and record.viewport_id == seed_observation.viewport_id
        )
        records_by_id = {record.observation_id: record for record in records}
        lineage_memo: dict[str, Optional[frozenset[str]]] = {}
        faces = tuple(
            record
            for record in scoped
            if record.observation_kind == WALL_FACE_INTERRUPTION_KIND
            and _line_geometry(record) is not None
        )
        jambs = tuple(
            record
            for record in scoped
            if record.observation_kind == OPENING_JAMB_BOUNDARY_KIND
            and _line_geometry(record) is not None
        )

        # Equivalent duplicated detector observations are collapsed by immutable
        # source-root support plus exact structural geometry, not by confidence.
        discovered: dict[
            tuple[object, ...],
            tuple[set[str], set[str], tuple[str, ...]],
        ] = {}
        for face_index, first_face in enumerate(faces):
            first_line = _line_geometry(first_face)
            if first_line is None:
                continue
            for second_face in faces[face_index + 1 :]:
                second_line = _line_geometry(second_face)
                if second_line is None or not _parallel(first_line, second_line):
                    continue
                orientations = (
                    (
                        (first_line[0], first_line[1]),
                        (second_line[0], second_line[1]),
                        (first_line[2], first_line[3]),
                        (second_line[2], second_line[3]),
                    ),
                    (
                        (first_line[0], first_line[1]),
                        (second_line[2], second_line[3]),
                        (first_line[2], first_line[3]),
                        (second_line[0], second_line[1]),
                    ),
                )
                for first_a, first_b, second_a, second_b in orientations:
                    first_jambs = tuple(
                        jamb for jamb in jambs if _segment_matches(jamb, first_a, first_b)
                    )
                    second_jambs = tuple(
                        jamb for jamb in jambs if _segment_matches(jamb, second_a, second_b)
                    )
                    for first_jamb in first_jambs:
                        for second_jamb in second_jambs:
                            support = (first_face, second_face, first_jamb, second_jamb)
                            if len({item.observation_id for item in support}) != 4:
                                continue
                            root_sets: list[frozenset[str]] = []
                            invalid_lineage = False
                            for item in support:
                                roots = self._lineage_roots(item, records_by_id, lineage_memo)
                                if not roots:
                                    invalid_lineage = True
                                    break
                                root_sets.append(roots)
                            if invalid_lineage or not self._independent_roots(tuple(root_sets)):
                                continue
                            all_roots = tuple(sorted(set().union(*root_sets)))
                            geometry_key = tuple(
                                sorted(
                                    (
                                        _canonical_line(first_line),
                                        _canonical_line(second_line),
                                        _canonical_line(_line_geometry(first_jamb)),  # type: ignore[arg-type]
                                        _canonical_line(_line_geometry(second_jamb)),  # type: ignore[arg-type]
                                    )
                                )
                            )
                            key = (
                                seed_observation.document_id,
                                seed_observation.revision_id,
                                seed_observation.source_sha256,
                                seed_observation.snapshot_id,
                                seed_observation.page_id,
                                seed_observation.viewport_id,
                                all_roots,
                                geometry_key,
                            )
                            obs_ids = {item.observation_id for item in support}
                            if key in discovered:
                                existing_obs, existing_roots, reasons = discovered[key]
                                existing_obs.update(obs_ids)
                                existing_roots.update(all_roots)
                                discovered[key] = (existing_obs, existing_roots, reasons)
                            else:
                                discovered[key] = (
                                    obs_ids,
                                    set(all_roots),
                                    (JAMB_BOUNDED_TWO_FACE_INTERRUPTION,),
                                )

        candidates: list[CandidateSemanticOpening] = []
        for key in sorted(discovered, key=repr):
            observation_ids, root_ids, reasons = discovered[key]
            payload = {
                "document_id": seed_observation.document_id,
                "revision_id": seed_observation.revision_id,
                "source_sha256": seed_observation.source_sha256,
                "snapshot_id": seed_observation.snapshot_id,
                "page_id": seed_observation.page_id,
                "viewport_id": seed_observation.viewport_id,
                "structural_pattern": JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
                "source_observation_ids": tuple(sorted(observation_ids)),
                "source_lineage_root_ids": tuple(sorted(root_ids)),
            }
            candidates.append(
                CandidateSemanticOpening(
                    candidate_id=stable_contract_id(
                        "physical_opening_candidate", payload, digest_chars=32
                    ),
                    source_observation_ids=tuple(sorted(observation_ids)),
                    source_lineage_root_ids=tuple(sorted(root_ids)),
                    document_id=seed_observation.document_id,
                    revision_id=seed_observation.revision_id,
                    source_sha256=seed_observation.source_sha256,
                    snapshot_id=seed_observation.snapshot_id,
                    page_id=seed_observation.page_id,
                    viewport_id=seed_observation.viewport_id,
                    structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
                    status=EvidenceResolutionStatus.CANDIDATE,
                    reason_codes=reasons,
                )
            )
        return tuple(candidates)

    def _single_observation_candidate(
        self,
        observation: SourceObservationRecord,
        records: tuple[SourceObservationRecord, ...],
    ) -> CandidateSemanticOpening:
        records_by_id = {record.observation_id: record for record in records}
        roots = self._lineage_roots(observation, records_by_id, {}) or frozenset()
        payload = {
            "document_id": observation.document_id,
            "revision_id": observation.revision_id,
            "source_sha256": observation.source_sha256,
            "snapshot_id": observation.snapshot_id,
            "page_id": observation.page_id,
            "viewport_id": observation.viewport_id,
            "source_observation_ids": (observation.observation_id,),
            "source_lineage_root_ids": tuple(sorted(roots)),
            "structural_pattern": STRUCTURAL_OPENING_CANDIDATE,
        }
        reasons = (STRUCTURAL_OPENING_CANDIDATE,)
        if not roots:
            reasons = _dedupe_reason_codes(reasons, (INSUFFICIENT_INDEPENDENT_SOURCE_LINEAGE,))
        if observation.observation_kind in {
            WALL_FACE_INTERRUPTION_KIND,
            OPENING_JAMB_BOUNDARY_KIND,
        } and _line_geometry(observation) is None:
            reasons = _dedupe_reason_codes(reasons, (INVALID_STRUCTURAL_GEOMETRY,))
        return CandidateSemanticOpening(
            candidate_id=stable_contract_id(
                "physical_opening_candidate", payload, digest_chars=32
            ),
            source_observation_ids=(observation.observation_id,),
            source_lineage_root_ids=tuple(sorted(roots)),
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
        """Resolve one local physical opening only from independent structural roots."""

        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")

        source_result = self._source_observation_authority.resolve(selector)
        if (
            source_result.status is not EvidenceResolutionStatus.CORROBORATED
            or source_result.observation is None
        ):
            return PhysicalOpeningExistenceResult(
                status=_source_failure_status(source_result),
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=_dedupe_reason_codes(source_result.reason_codes),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        records, failures = self._snapshot_records(source_result)
        if failures:
            return PhysicalOpeningExistenceResult(
                status=_source_failure_status(*failures),
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=_dedupe_reason_codes(
                    (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,),
                    *tuple(result.reason_codes for result in failures),
                ),
                source_observation=source_result,
            )

        observation = source_result.observation
        candidates = self._discover_structural_candidates(
            seed_observation=observation,
            records=records,
        )
        containing = tuple(
            candidate
            for candidate in candidates
            if observation.observation_id in candidate.source_observation_ids
        )
        if len(containing) > 1:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CONFLICT,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=(AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,),
                source_observation=source_result,
            )
        if len(containing) == 1 and source_result.snapshot is not None:
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
                record_id=stable_contract_id(
                    "physical_opening_existence", record_payload, digest_chars=32
                ),
                source_observation_ids=candidate.source_observation_ids,
                source_lineage_root_ids=candidate.source_lineage_root_ids,
                document_id=candidate.document_id,
                revision_id=candidate.revision_id,
                source_sha256=candidate.source_sha256,
                snapshot_id=candidate.snapshot_id,
                page_id=candidate.page_id,
                viewport_id=candidate.viewport_id,
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

        if observation.observation_kind in {
            WALL_FACE_INTERRUPTION_KIND,
            OPENING_JAMB_BOUNDARY_KIND,
            *WEAK_PHYSICAL_OPENING_CANDIDATE_KINDS,
        }:
            candidate = self._single_observation_candidate(observation, records)
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CANDIDATE,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=candidate.reason_codes,
                source_observation=source_result,
                candidate=candidate,
            )

        # Tags, text, schedules, generic rectangles, CV/heuristic labels and other
        # observations remain necessary-at-most provenance; none is a structural
        # physical-opening existence proposition on its own.
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
            source_observation=source_result,
            missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
        )

    def compare_identity(
        self,
        left_selector: ObservationSelector,
        right_selector: ObservationSelector,
    ) -> PhysicalOpeningIdentityResult:
        """Never infer physical identity from observation equality or similarity."""

        if not isinstance(left_selector, ObservationSelector):
            raise TypeError("left_selector must be ObservationSelector")
        if not isinstance(right_selector, ObservationSelector):
            raise TypeError("right_selector must be ObservationSelector")

        left = self._source_observation_authority.resolve(left_selector)
        right = self._source_observation_authority.resolve(right_selector)
        if (
            left.status is not EvidenceResolutionStatus.CORROBORATED
            or right.status is not EvidenceResolutionStatus.CORROBORATED
        ):
            return PhysicalOpeningIdentityResult(
                status=_source_failure_status(left, right),
                physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
                proven_same=False,
                reason_codes=_dedupe_reason_codes(left.reason_codes, right.reason_codes),
                left_source_observation=left,
                right_source_observation=right,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
            proven_same=False,
            reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE,),
            left_source_observation=left,
            right_source_observation=right,
            missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
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
    "PHYSICAL_OPENING_IDENTITY_UNRESOLVED",
    "PhysicalOpeningAuthority",
    "PhysicalOpeningExistenceRecord",
    "PhysicalOpeningExistenceResult",
    "PhysicalOpeningIdentityResult",
    "SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE",
    "STRUCTURAL_OPENING_CANDIDATE",
    "STRUCTURAL_OPENING_EXISTENCE_RESOLVED",
    "WALL_FACE_INTERRUPTION_KIND",
    "WEAK_PHYSICAL_OPENING_CANDIDATE_KINDS",
]