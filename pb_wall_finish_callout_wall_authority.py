"""Shadow source-owned finish-callout -> physical-wall binding authority.

This is the wall-identity stage immediately upstream of Item 19B semantic-face
binding.  It deliberately stops before wall role, physical face identity,
finish-scope completeness, opening deductions, net wall, or quantity
publication.

Positive path:
trusted native finish annotation
-> endpoint-connected native leader
-> filled native terminator
-> locally complete terminator owner universe
-> one physical-wall equivalence group.

Global viewport completeness is not required for this *local* proposition.
Instead, every structural source primitive that wall authority withheld because
it crossed / ambiguously occupied the viewport boundary is replayed at the
terminator.  If any such primitive intersects the terminator, or its geometry
cannot be replayed, the local owner universe is not proven and this authority
abstains.

No nearest-wall, first-candidate, confidence ranking, caller geometry, project
identity, benchmark value, or quantity participates.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_execution_callout_authority import SourceExecutionCalloutProducer
from pb_viewport_segmentation import assign_bbox_to_viewport
from pb_wall_finish_face_binding_authority import (
    SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT,
    _authoritative_viewports,
    _filled_terminators,
    _leader_paths,
    _page_visible_lines,
    _segment_intersects_bbox,
    _target_from_terminator,
    _viewport_owned_lines,
)


WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION = "1.1.0"
FINISH_CALLOUT_WALL_BINDING_RESOLVED = "wall_finish_callout_wall_binding_resolved"
FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE = "wall_finish_callout_wall_binding_unavailable"
FINISH_CALLOUT_WALL_LOCAL_UNIVERSE_INCOMPLETE = (
    "wall_finish_callout_wall_local_owner_universe_incomplete"
)
FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE = (
    "wall_finish_callout_wall_source_integrity_failure"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class WallFinishCalloutWallScopeSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "viewport_id",
            "decision_scope_id",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be non-empty")

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
            self.decision_scope_id,
        )


@dataclass(frozen=True)
class WallFinishCalloutWallBindingRecord:
    binding_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str
    physical_wall_decision_scope_id: str
    physical_wall_id: str
    raw_owner_wall_ids: tuple[str, ...]
    equivalence_group_wall_ids: tuple[str, ...]
    equivalence_pair_classifications: tuple[tuple[str, str, str], ...]
    source_wall_primitive_ids: tuple[str, ...]
    source_execution_callout_record_id: str
    source_execution_sequence_start: int
    source_execution_sequence_end: int
    trade_scope_id: str
    finish_material: str
    semantic_direction: str
    annotation_observation_ids: tuple[str, ...]
    leader_path_ids: tuple[str, ...]
    terminator_primitive_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    source_evidence_kind: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFinishCalloutWallBindingRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive wall binding record must be CORROBORATED")
        if not self.raw_owner_wall_ids:
            raise ValueError("raw_owner_wall_ids must retain target provenance")
        if not self.equivalence_group_wall_ids:
            raise ValueError("equivalence_group_wall_ids must retain target identity")
        if self.physical_wall_id not in self.equivalence_group_wall_ids:
            raise ValueError("physical_wall_id must belong to equivalence group")
        if not self.source_wall_primitive_ids:
            raise ValueError("source wall primitive evidence is required")


@dataclass(frozen=True)
class WallFinishCalloutWallScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    bindings: tuple[WallFinishCalloutWallBindingRecord, ...] = ()
    schema_version: str = WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION


def _blocked(reason: str) -> WallFinishCalloutWallScopeResult:
    return WallFinishCalloutWallScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(reason,),
        bindings=(),
    )


def _local_owner_universe_safe(*, terminator, page_lines, wall_scope) -> bool:
    """Prove that no source primitive omitted by viewport ownership hits target.

    This is intentionally local.  It never upgrades wall_scope.scope_complete.
    A globally cropped viewport can still prove a local callout owner only when
    every boundary/ambiguous structural observation can be replayed and none of
    those exact primitives intersects the terminator.
    """
    questionable = tuple(
        dict.fromkeys(
            (
                *tuple(getattr(wall_scope, "scope_boundary_observation_ids", ()) or ()),
                *tuple(getattr(wall_scope, "ambiguous_source_observation_ids", ()) or ()),
            )
        )
    )
    if not questionable:
        return True

    by_observation: dict[str, list[object]] = {}
    for line in page_lines:
        by_observation.setdefault(str(line.observation_id), []).append(line)

    for observation_id in questionable:
        candidates = by_observation.get(str(observation_id))
        if not candidates:
            # The withheld structural primitive cannot be replayed here.  Its
            # relationship to the terminator is unknown, so uniqueness cannot
            # be certified.
            return False
        if any(
            _segment_intersects_bbox(line.geometry, terminator.bbox)
            for line in candidates
        ):
            return False
    return True


def _target_provenance(*, terminator, wall_lines, wall_scope, target):
    raw_hits = {
        line.raw_id
        for line in wall_lines
        if _segment_intersects_bbox(line.geometry, terminator.bbox)
    }
    matching = [
        record
        for record in wall_scope.records
        if raw_hits & set(record.physical_identity.source_primitive_ids)
    ]
    raw_owner_ids = tuple(sorted({record.wall_candidate_id for record in matching}))

    target_id = str(target.wall_candidate_id)
    group = (target_id,)
    equivalence = getattr(wall_scope, "equivalence", None)
    if equivalence is not None:
        for candidate_group in tuple(equivalence.equivalence_groups or ()):
            if target_id in candidate_group:
                group = tuple(sorted(candidate_group))
                break

    relevant = set(group) | set(raw_owner_ids)
    pair_classifications = ()
    if equivalence is not None:
        pair_classifications = tuple(
            sorted(
                row
                for row in tuple(equivalence.pair_classifications or ())
                if row[0] in relevant and row[1] in relevant
            )
        )
    return raw_owner_ids, group, pair_classifications


class WallFinishCalloutWallAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, ...], WallFinishCalloutWallScopeResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishCalloutWallAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_scope(
        self,
        selector: WallFinishCalloutWallScopeSelector,
    ) -> WallFinishCalloutWallScopeResult:
        if type(selector) is not WallFinishCalloutWallScopeSelector:
            raise TypeError("selector must be WallFinishCalloutWallScopeSelector")
        return self._results.get(
            selector.key,
            _blocked(FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE),
        )


class WallFinishCalloutWallProducer:
    def __init__(
        self,
        results: Mapping[tuple[str, ...], WallFinishCalloutWallScopeResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "WallFinishCalloutWallProducer must be obtained "
                "from_source_visibility_producer()"
            )
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "WallFinishCalloutWallProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be an actual SourceVisibilityProducer"
            )
        selected = (
            None
            if page_ids is None
            else tuple(
                sorted(
                    {str(page).strip() for page in page_ids if str(page).strip()},
                    key=int,
                )
            )
        )
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one source page")

        # Build wall authority first because it may add producer-owned raster
        # visible-segment observations and therefore advance the source snapshot.
        # Source-execution callouts must be minted against that final lineage.
        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source_visibility_producer,
            page_ids=selected,
        ).authority()
        callout_producer = SourceExecutionCalloutProducer.from_source_visibility_producer(
            source_visibility_producer,
            page_ids=selected,
        )
        callout_authority = callout_producer.authority()
        results: dict[tuple[str, ...], WallFinishCalloutWallScopeResult] = {}
        store = source_visibility_producer._producer._store

        for revision_id, published in sorted(
            source_visibility_producer._published_by_revision.items()
        ):
            if (
                source_visibility_producer._producer.current_revision_id(
                    published.revision.document_id
                )
                != revision_id
            ):
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if (
                source_bytes is None
                or hashlib.sha256(source_bytes).hexdigest()
                != published.revision.source_sha256
            ):
                raise RuntimeError(FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE)

            page_list = selected or tuple(
                str(int(page_number))
                for page_number in sorted(published.coverage.decoded_pages)
            )
            doc = fitz.open(stream=source_bytes, filetype="pdf")
            try:
                for page_id in page_list:
                    page_number = int(page_id)
                    if not 1 <= page_number <= doc.page_count:
                        continue
                    page = doc.load_page(page_number - 1)
                    viewports = _authoritative_viewports(page, page_number)
                    page_lines = _page_visible_lines(
                        source_visibility_producer,
                        published,
                        page_id,
                    )

                    callout_page = callout_authority.resolve_page(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        page_id=page_id,
                    )
                    if callout_page.status is not EvidenceResolutionStatus.CORROBORATED:
                        continue

                    for callout in callout_page.records:
                        semantics = callout.semantics
                        annotation_ids = callout.observation_ids
                        annotation_bbox = callout.source_bbox
                        text_height = callout.text_height
                        viewport = assign_bbox_to_viewport(
                            annotation_bbox,
                            viewports,
                            allow_derived=True,
                        )
                        if viewport is None or viewport.bounding_box is None:
                            continue
                        wall_selector = wall_authority.selector_for_viewport(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            viewport_id=viewport.view_id,
                        )
                        if wall_selector is None:
                            continue
                        wall_scope = wall_authority.resolve_scope(wall_selector)
                        if wall_scope.status is not EvidenceResolutionStatus.CORROBORATED:
                            continue

                        leader_lines = _viewport_owned_lines(
                            page_lines,
                            viewport,
                            viewports,
                        )
                        wall_observation_ids = set(wall_scope.source_observation_ids)
                        wall_lines = tuple(
                            line
                            for line in page_lines
                            if line.observation_id in wall_observation_ids
                        )
                        terminators = tuple(
                            term
                            for term in _filled_terminators(page, text_height)
                            if viewport.bounding_box[0]
                            <= term.center[0]
                            <= viewport.bounding_box[2]
                            and viewport.bounding_box[1]
                            <= term.center[1]
                            <= viewport.bounding_box[3]
                        )
                        paths = _leader_paths(
                            annotation_bbox,
                            leader_lines,
                            terminators,
                        )
                        if not paths:
                            continue

                        accepted: dict[
                            tuple[str, str, str, str],
                            WallFinishCalloutWallBindingRecord,
                        ] = {}
                        for leader_ids, terminator in paths:
                            if not _local_owner_universe_safe(
                                terminator=terminator,
                                page_lines=page_lines,
                                wall_scope=wall_scope,
                            ):
                                continue

                            target, source_segments, target_status = (
                                _target_from_terminator(
                                    terminator,
                                    wall_lines,
                                    wall_scope,
                                )
                            )
                            if (
                                target_status
                                is not EvidenceResolutionStatus.CORROBORATED
                                or target is None
                            ):
                                continue

                            (
                                raw_owner_ids,
                                equivalence_group,
                                pair_classifications,
                            ) = _target_provenance(
                                terminator=terminator,
                                wall_lines=wall_lines,
                                wall_scope=wall_scope,
                                target=target,
                            )
                            if not raw_owner_ids:
                                continue

                            for semantic in semantics:
                                payload = {
                                    "document_id": published.revision.document_id,
                                    "revision_id": published.revision.revision_id,
                                    "source_sha256": published.revision.source_sha256,
                                    "snapshot_id": published.snapshot.snapshot_id,
                                    "page_id": page_id,
                                    "viewport_id": viewport.view_id,
                                    "physical_wall_decision_scope_id": (
                                        wall_scope.decision_scope_id
                                    ),
                                    "physical_wall_id": target.wall_candidate_id,
                                    "raw_owner_wall_ids": raw_owner_ids,
                                    "equivalence_group_wall_ids": equivalence_group,
                                    "source_wall_primitive_ids": tuple(
                                        sorted(source_segments)
                                    ),
                                    "trade_scope_id": semantic.trade_scope_id,
                                    "finish_material": semantic.finish_material,
                                    "semantic_direction": semantic.direction,
                                    "annotation_observation_ids": tuple(
                                        annotation_ids
                                    ),
                                    "leader_path_ids": tuple(leader_ids),
                                    "terminator_primitive_ids": (
                                        terminator.primitive_id,
                                    ),
                                    "source_execution_callout_record_id": (
                                        callout.record_id
                                    ),
                                }
                                binding_id = stable_contract_id(
                                    "wall_finish_callout_wall_binding",
                                    payload,
                                    digest_chars=32,
                                )
                                evidence_ids = tuple(
                                    dict.fromkeys(
                                        (
                                            callout.record_id,
                                            *tuple(
                                                word.authority_record_id
                                                for word in callout.word_evidence
                                            ),
                                            *annotation_ids,
                                            *leader_ids,
                                            terminator.primitive_id,
                                            *tuple(sorted(source_segments)),
                                        )
                                    )
                                )
                                record = WallFinishCalloutWallBindingRecord(
                                    binding_id=binding_id,
                                    document_id=published.revision.document_id,
                                    revision_id=published.revision.revision_id,
                                    source_sha256=published.revision.source_sha256,
                                    snapshot_id=published.snapshot.snapshot_id,
                                    page_id=page_id,
                                    viewport_id=viewport.view_id,
                                    decision_scope_id=(
                                        f"finish-callout-wall:{viewport.view_id}"
                                    ),
                                    physical_wall_decision_scope_id=(
                                        wall_scope.decision_scope_id
                                    ),
                                    physical_wall_id=target.wall_candidate_id,
                                    raw_owner_wall_ids=raw_owner_ids,
                                    equivalence_group_wall_ids=equivalence_group,
                                    equivalence_pair_classifications=(
                                        pair_classifications
                                    ),
                                    source_wall_primitive_ids=tuple(
                                        sorted(source_segments)
                                    ),
                                    source_execution_callout_record_id=callout.record_id,
                                    source_execution_sequence_start=callout.sequence_start,
                                    source_execution_sequence_end=callout.sequence_end,
                                    trade_scope_id=semantic.trade_scope_id,
                                    finish_material=semantic.finish_material,
                                    semantic_direction=semantic.direction,
                                    annotation_observation_ids=tuple(
                                        annotation_ids
                                    ),
                                    leader_path_ids=tuple(leader_ids),
                                    terminator_primitive_ids=(
                                        terminator.primitive_id,
                                    ),
                                    source_evidence_ids=evidence_ids,
                                    source_evidence_kind=(
                                        SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT
                                    ),
                                    status=EvidenceResolutionStatus.CORROBORATED,
                                    reason_codes=(
                                        FINISH_CALLOUT_WALL_BINDING_RESOLVED,
                                    ),
                                    _seal=_RECORD_SEAL,
                                )
                                signature = (
                                    record.physical_wall_id,
                                    record.trade_scope_id,
                                    record.finish_material,
                                    record.semantic_direction,
                                )
                                prior = accepted.get(signature)
                                if prior is None or record.binding_id < prior.binding_id:
                                    accepted[signature] = record

                        bindings = tuple(
                            sorted(
                                accepted.values(),
                                key=lambda record: record.binding_id,
                            )
                        )
                        if not bindings:
                            continue
                        selector = WallFinishCalloutWallScopeSelector(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            viewport_id=viewport.view_id,
                            decision_scope_id=(
                                f"finish-callout-wall:{viewport.view_id}"
                            ),
                        )
                        result = WallFinishCalloutWallScopeResult(
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=(
                                FINISH_CALLOUT_WALL_BINDING_RESOLVED,
                            ),
                            bindings=bindings,
                        )
                        previous = results.get(selector.key)
                        if previous is None:
                            results[selector.key] = result
                        else:
                            merged = {
                                record.binding_id: record
                                for record in (
                                    *previous.bindings,
                                    *result.bindings,
                                )
                            }
                            results[selector.key] = WallFinishCalloutWallScopeResult(
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(
                                    FINISH_CALLOUT_WALL_BINDING_RESOLVED,
                                ),
                                bindings=tuple(
                                    sorted(
                                        merged.values(),
                                        key=lambda record: record.binding_id,
                                    )
                                ),
                            )
            finally:
                doc.close()

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallFinishCalloutWallAuthority:
        return WallFinishCalloutWallAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def published_results(self) -> tuple[WallFinishCalloutWallScopeResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "FINISH_CALLOUT_WALL_BINDING_RESOLVED",
    "FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE",
    "FINISH_CALLOUT_WALL_LOCAL_UNIVERSE_INCOMPLETE",
    "FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE",
    "WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION",
    "WallFinishCalloutWallAuthority",
    "WallFinishCalloutWallBindingRecord",
    "WallFinishCalloutWallProducer",
    "WallFinishCalloutWallScopeResult",
    "WallFinishCalloutWallScopeSelector",
]
