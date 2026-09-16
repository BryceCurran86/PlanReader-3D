"""Producer-owned source-backed physical-wall candidate authority.

This module proves one narrow proposition only: the physical wall candidates
produced by the existing W2/W3/W4 wall pipeline for a complete exact
producer-owned visible PDF page scope.

It does NOT prove opening host binding, wall role, wall height, wall thickness,
opening deductions, net wall area, FIRM/commercial publication or JobHub data.
Ordinary callers can address a scope only by lineage; they cannot supply walls,
segments, graphs, candidate lists/counts or completeness flags.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
    collect_physical_wall_identities,
    resolve_physical_wall_equivalence,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    SourceVisibilityProducer,
    classify_native_segment_visibility,
)
from pb_vector_geometry_v130 import extract_native_page
from pb_wall_room_topology_contracts import WallCandidate
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import assemble_wall_topology


PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION = "1.0.0"
PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED = "physical_wall_candidate_scope_resolved"
PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE = "physical_wall_candidate_scope_unavailable"
PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE = (
    "physical_wall_candidate_source_integrity_failure"
)
PHYSICAL_WALL_CANDIDATE_IDENTITY_UNRESOLVED = (
    "physical_wall_candidate_identity_unresolved"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()


@dataclass(frozen=True)
class PhysicalWallCandidateSelector:
    """Consumer addressing only; never a caller-authored wall universe."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str


@dataclass(frozen=True)
class PhysicalWallCandidateRecord:
    wall_candidate_id: str
    wall_candidate: WallCandidate
    physical_identity: PhysicalWallIdentity
    schema_version: str = PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalWallCandidateScopeResult:
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
    schema_version: str = PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class _ScopeKey:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str


def _decision_scope_id(page_id: str) -> str:
    return f"wall-source:page-{str(page_id)}"


def _blocked(selector: PhysicalWallCandidateSelector, reason: str) -> PhysicalWallCandidateScopeResult:
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        scope_complete=False,
        records=(),
        source_observation_ids=(),
        document_id=str(selector.document_id),
        revision_id=str(selector.revision_id),
        source_sha256=str(selector.source_sha256),
        snapshot_id=str(selector.snapshot_id),
        page_id=str(selector.page_id),
        decision_scope_id=str(selector.decision_scope_id),
        reason_codes=(reason,),
    )


def _source_page_segments(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
    decision_scope_id: str,
) -> tuple[list[dict], tuple[str, ...]]:
    """Rebuild W2 inputs from exact bytes and exact receipted visible membership."""

    visibility = source_producer.authority()
    visible_by_raw_id: dict[str, tuple[str, tuple[float, ...]]] = {}
    page_visible_ids: list[str] = []

    for observation_id in published.visible_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
        ):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        if observation.page_id != page_id:
            continue
        prefix = "visible:segment:"
        if not observation.source_primitive_ref.startswith(prefix):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        raw_id = observation.source_primitive_ref[len(prefix) :]
        if not raw_id or raw_id in visible_by_raw_id:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        visible_by_raw_id[raw_id] = (
            observation_id,
            tuple(float(value) for value in observation.geometry),
        )
        page_visible_ids.append(observation_id)

    try:
        page_number = int(page_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE) from exc
    if page_number < 1:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        if page_number > int(pdf.page_count):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        native = extract_native_page(pdf.load_page(page_number - 1))
    finally:
        pdf.close()

    segments: list[dict] = []
    native_visible_ids: set[str] = set()
    for source_segment in native.get("segments") or ():
        decision = classify_native_segment_visibility(source_segment)
        if not decision.visible:
            continue
        raw_id = str(source_segment.get("id") or "").strip()
        if not raw_id:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        expected = visible_by_raw_id.get(raw_id)
        if expected is None:
            # Exact source says this primitive is visible but the producer-owned
            # visible inventory omitted it: completeness cannot be claimed.
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        observation_id, observation_geometry = expected
        geometry = (
            float(source_segment["x1"]),
            float(source_segment["y1"]),
            float(source_segment["x2"]),
            float(source_segment["y2"]),
        )
        if tuple(geometry) != tuple(observation_geometry):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        native_visible_ids.add(observation_id)
        segment = dict(source_segment)
        segment["document_id"] = published.revision.document_id
        segment["page_id"] = page_id
        segment["viewport_id"] = decision_scope_id
        segments.append(segment)

    if native_visible_ids != set(page_visible_ids):
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    return segments, tuple(sorted(page_visible_ids))


def _build_scope_result(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
) -> PhysicalWallCandidateScopeResult:
    scope_id = _decision_scope_id(page_id)
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )

    page_number = int(page_id)
    if (
        published.coverage.state != "complete"
        or published.coverage.failed_pages
        or page_number not in published.coverage.decoded_pages
    ):
        return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)

    segments, source_observation_ids = _source_page_segments(
        source_producer=source_producer,
        published=published,
        source_bytes=source_bytes,
        page_id=page_id,
        decision_scope_id=scope_id,
    )

    graph = build_wall_graph_for_viewport(segments)
    junctions, relationships = classify_junctions(
        graph,
        document_id=published.revision.document_id,
        page_id=page_id,
        viewport_id=scope_id,
    )
    walls, _rekeyed_junctions = assemble_wall_topology(
        graph,
        junctions,
        relationships,
        viewport_id=scope_id,
    )
    identities = collect_physical_wall_identities(walls, graph)

    ordered_walls = sorted(walls, key=lambda item: item.candidate_id)
    records: list[PhysicalWallCandidateRecord] = []
    ordered_identities: list[PhysicalWallIdentity] = []
    for wall in ordered_walls:
        identity = identities.get(wall.candidate_id)
        if identity is None or not identity.usable:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_IDENTITY_UNRESOLVED)
        records.append(
            PhysicalWallCandidateRecord(
                wall_candidate_id=wall.candidate_id,
                wall_candidate=wall,
                physical_identity=identity,
            )
        )
        ordered_identities.append(identity)

    equivalence = resolve_physical_wall_equivalence(
        tuple(ordered_identities),
        walls_by_id={wall.candidate_id: wall for wall in ordered_walls},
    )

    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        source_observation_ids=source_observation_ids,
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
        reason_codes=(PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,),
        equivalence=equivalence,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    )


class PhysicalWallCandidateProducer:
    """Trusted writer derived only from an already-ingested visibility producer."""

    def __init__(self, scopes: Mapping[_ScopeKey, PhysicalWallCandidateScopeResult], *, _seal=None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "PhysicalWallCandidateProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        self._scopes = MappingProxyType(dict(scopes))

    @classmethod
    def from_source_visibility_producer(cls, source_visibility_producer):
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be an actual SourceVisibilityProducer"
            )

        published_by_revision = dict(source_visibility_producer._published_by_revision)
        store = source_visibility_producer._producer._store
        scopes: dict[_ScopeKey, PhysicalWallCandidateScopeResult] = {}

        for revision_id, published in sorted(published_by_revision.items()):
            if source_visibility_producer._producer.current_revision_id(
                published.revision.document_id
            ) != revision_id:
                # Stale revisions never become current wall-candidate authority.
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if source_bytes is None:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            digest = hashlib.sha256(source_bytes).hexdigest()
            if digest != published.revision.source_sha256:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

            for page_number in published.coverage.decoded_pages:
                page_id = str(page_number)
                result = _build_scope_result(
                    source_producer=source_visibility_producer,
                    published=published,
                    source_bytes=source_bytes,
                    page_id=page_id,
                )
                key = _ScopeKey(
                    document_id=result.document_id,
                    revision_id=result.revision_id,
                    source_sha256=result.source_sha256,
                    snapshot_id=result.snapshot_id,
                    page_id=result.page_id,
                    decision_scope_id=result.decision_scope_id,
                )
                scopes[key] = result

        return cls(scopes, _seal=_PRODUCER_SEAL)

    def authority(self):
        return PhysicalWallCandidateAuthority(self._scopes, _seal=_AUTHORITY_SEAL)


class PhysicalWallCandidateAuthority:
    """Read-only exact-scope resolver. Construction is producer-sealed."""

    def __init__(self, scopes: Mapping[_ScopeKey, PhysicalWallCandidateScopeResult], *, _seal=None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "PhysicalWallCandidateAuthority must be obtained from "
                "PhysicalWallCandidateProducer.authority()"
            )
        self._scopes = MappingProxyType(dict(scopes))

    def resolve_scope(self, selector):
        if not isinstance(selector, PhysicalWallCandidateSelector):
            raise TypeError("selector must be PhysicalWallCandidateSelector")

        if selector.decision_scope_id != _decision_scope_id(selector.page_id):
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)

        key = _ScopeKey(
            document_id=str(selector.document_id),
            revision_id=str(selector.revision_id),
            source_sha256=str(selector.source_sha256),
            snapshot_id=str(selector.snapshot_id),
            page_id=str(selector.page_id),
            decision_scope_id=str(selector.decision_scope_id),
        )
        result = self._scopes.get(key)
        if result is None:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
        return result


__all__ = [
    "PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE",
    "PhysicalWallCandidateAuthority",
    "PhysicalWallCandidateProducer",
    "PhysicalWallCandidateRecord",
    "PhysicalWallCandidateScopeResult",
    "PhysicalWallCandidateSelector",
]
