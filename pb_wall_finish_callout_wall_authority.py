"""Shadow source-owned annotation-callout -> physical-wall binding authority.

This authority proves only a geometry/identity proposition:

    producer-owned native text-block geometry
    -> endpoint-connected native leader
    -> filled native terminator
    -> locally complete wall-owner universe
    -> one physical-wall equivalence group.

It does NOT interpret annotation text and therefore does not depend on OCR,
font/glyph trust, finish semantics, wall role, opening deductions, net wall, or
quantity publication.

Global viewport completeness is intentionally not upgraded. A local callout may
still have a complete owner universe when every structural observation withheld
at the viewport boundary can be replayed and none intersects the terminator.

No nearest-wall, first-candidate, confidence ranking, caller geometry, project
identity, benchmark value, or quantity participates.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import statistics
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import assign_bbox_to_viewport
from pb_wall_finish_face_binding_authority import (
    _authoritative_viewports,
    _bbox_union,
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
FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE = "wall_finish_callout_wall_source_integrity_failure"

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

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.document_id, self.revision_id, self.source_sha256,
            self.snapshot_id, self.page_id, self.viewport_id,
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
    annotation_block_id: str
    annotation_observation_ids: tuple[str, ...]
    annotation_sequence_numbers: tuple[int, ...]
    leader_path_ids: tuple[str, ...]
    terminator_primitive_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFinishCalloutWallBindingRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive wall binding must be CORROBORATED")
        if not self.raw_owner_wall_ids:
            raise ValueError("raw owner provenance is required")
        if not self.equivalence_group_wall_ids:
            raise ValueError("equivalence group provenance is required")
        if self.physical_wall_id not in self.equivalence_group_wall_ids:
            raise ValueError("physical wall must belong to equivalence group")
        if not self.source_wall_primitive_ids:
            raise ValueError("source wall primitive provenance is required")
        if not self.annotation_observation_ids:
            raise ValueError("annotation source observations are required")


@dataclass(frozen=True)
class WallFinishCalloutWallScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    bindings: tuple[WallFinishCalloutWallBindingRecord, ...] = ()


def _blocked(reason: str) -> WallFinishCalloutWallScopeResult:
    return WallFinishCalloutWallScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(reason,),
    )


def _source_annotation_blocks(source: SourceVisibilityProducer, published, page_id: str):
    """Group producer-owned native word geometry without trusting its text.

    block_no is used only as producer extraction grouping metadata. Word
    ordering inside the block is source execution sequence_number; block/line/
    word indices are never used to manufacture semantic text authority.
    """
    authority = source.text_integrity_authority()
    groups: dict[tuple[str, int], list[tuple[int, str, tuple[float, ...]]]] = {}
    for observation_id in published.text_observation_ids:
        result = authority.resolve_text(ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        receipt = result.receipt
        if (
            receipt is None
            or receipt.page_id != page_id
            or receipt.block_no is None
            or receipt.sequence_number is None
            or len(receipt.geometry) != 4
        ):
            continue
        groups.setdefault(
            (str(receipt.source_partition_id), int(receipt.block_no)), []
        ).append((
            int(receipt.sequence_number),
            observation_id,
            tuple(float(v) for v in receipt.geometry),
        ))

    out = []
    for (partition_id, block_no), values in sorted(groups.items()):
        ordered = sorted(values, key=lambda row: (row[0], row[1]))
        geometries = [row[2] for row in ordered]
        bbox = _bbox_union(geometries)
        heights = [max(0.1, g[3] - g[1]) for g in geometries]
        payload = {
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "page_id": page_id,
            "source_partition_id": partition_id,
            "block_no": block_no,
            "observation_ids": tuple(row[1] for row in ordered),
            "sequence_numbers": tuple(row[0] for row in ordered),
            "bbox": tuple(round(float(v), 6) for v in bbox),
        }
        out.append((
            stable_contract_id("source_annotation_block", payload, digest_chars=32),
            tuple(row[1] for row in ordered),
            tuple(row[0] for row in ordered),
            bbox,
            statistics.median(heights),
        ))
    return tuple(out)


def _local_owner_universe_safe(*, terminator, page_lines, wall_scope) -> bool:
    questionable = tuple(dict.fromkeys((
        *tuple(getattr(wall_scope, "scope_boundary_observation_ids", ()) or ()),
        *tuple(getattr(wall_scope, "ambiguous_source_observation_ids", ()) or ()),
    )))
    if not questionable:
        return True
    by_observation: dict[str, list[object]] = {}
    for line in page_lines:
        by_observation.setdefault(str(line.observation_id), []).append(line)
    for observation_id in questionable:
        candidates = by_observation.get(str(observation_id))
        if not candidates:
            return False
        if any(_segment_intersects_bbox(line.geometry, terminator.bbox) for line in candidates):
            return False
    return True


def _target_provenance(*, terminator, wall_lines, wall_scope, target):
    raw_hits = {
        line.raw_id for line in wall_lines
        if _segment_intersects_bbox(line.geometry, terminator.bbox)
    }
    matching = [
        record for record in wall_scope.records
        if raw_hits & set(record.physical_identity.source_primitive_ids)
    ]
    raw_owner_ids = tuple(sorted({record.wall_candidate_id for record in matching}))
    target_id = str(target.wall_candidate_id)
    group = (target_id,)
    eq = getattr(wall_scope, "equivalence", None)
    if eq is not None:
        for candidate_group in tuple(eq.equivalence_groups or ()):
            if target_id in candidate_group:
                group = tuple(sorted(candidate_group))
                break
    relevant = set(group) | set(raw_owner_ids)
    pairs = ()
    if eq is not None:
        pairs = tuple(sorted(
            row for row in tuple(eq.pair_classifications or ())
            if row[0] in relevant and row[1] in relevant
        ))
    return raw_owner_ids, group, pairs


class WallFinishCalloutWallAuthority:
    def __init__(self, results: Mapping[tuple[str, ...], WallFinishCalloutWallScopeResult], *, _seal=None):
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishCalloutWallAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_scope(self, selector: WallFinishCalloutWallScopeSelector) -> WallFinishCalloutWallScopeResult:
        if type(selector) is not WallFinishCalloutWallScopeSelector:
            raise TypeError("selector must be WallFinishCalloutWallScopeSelector")
        return self._results.get(selector.key, _blocked(FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE))


class WallFinishCalloutWallProducer:
    def __init__(self, results: Mapping[tuple[str, ...], WallFinishCalloutWallScopeResult], *, _seal=None):
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("use from_source_visibility_producer()")
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "WallFinishCalloutWallProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        selected = None if page_ids is None else tuple(sorted(
            {str(p).strip() for p in page_ids if str(p).strip()}, key=int
        ))
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one source page")

        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source_visibility_producer, page_ids=selected
        ).authority()
        results: dict[tuple[str, ...], WallFinishCalloutWallScopeResult] = {}
        store = source_visibility_producer._producer._store

        for revision_id, published in sorted(source_visibility_producer._published_by_revision.items()):
            if source_visibility_producer._producer.current_revision_id(published.revision.document_id) != revision_id:
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
                raise RuntimeError(FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE)
            page_list = selected or tuple(str(int(p)) for p in sorted(published.coverage.decoded_pages))
            doc = fitz.open(stream=source_bytes, filetype="pdf")
            try:
                for page_id in page_list:
                    page_number = int(page_id)
                    if not 1 <= page_number <= doc.page_count:
                        continue
                    page = doc.load_page(page_number - 1)
                    viewports = _authoritative_viewports(page, page_number)
                    page_lines = _page_visible_lines(source_visibility_producer, published, page_id)

                    for block_id, annotation_ids, sequence_numbers, annotation_bbox, text_height in _source_annotation_blocks(
                        source_visibility_producer, published, page_id
                    ):
                        viewport = assign_bbox_to_viewport(annotation_bbox, viewports, allow_derived=True)
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

                        leader_lines = _viewport_owned_lines(page_lines, viewport, viewports)
                        wall_obs = set(wall_scope.source_observation_ids)
                        wall_lines = tuple(line for line in page_lines if line.observation_id in wall_obs)
                        terms = tuple(
                            term for term in _filled_terminators(page, text_height)
                            if viewport.bounding_box[0] <= term.center[0] <= viewport.bounding_box[2]
                            and viewport.bounding_box[1] <= term.center[1] <= viewport.bounding_box[3]
                        )
                        paths = _leader_paths(annotation_bbox, leader_lines, terms)
                        if not paths:
                            continue

                        accepted: dict[tuple[str, str], WallFinishCalloutWallBindingRecord] = {}
                        for leader_ids, terminator in paths:
                            if not _local_owner_universe_safe(
                                terminator=terminator, page_lines=page_lines, wall_scope=wall_scope
                            ):
                                continue
                            target, source_segments, target_status = _target_from_terminator(
                                terminator, wall_lines, wall_scope
                            )
                            if target_status is not EvidenceResolutionStatus.CORROBORATED or target is None:
                                continue
                            raw_owners, group, pairs = _target_provenance(
                                terminator=terminator,
                                wall_lines=wall_lines,
                                wall_scope=wall_scope,
                                target=target,
                            )
                            if not raw_owners:
                                continue
                            payload = {
                                "document_id": published.revision.document_id,
                                "revision_id": published.revision.revision_id,
                                "source_sha256": published.revision.source_sha256,
                                "snapshot_id": published.snapshot.snapshot_id,
                                "page_id": page_id,
                                "viewport_id": viewport.view_id,
                                "annotation_block_id": block_id,
                                "physical_wall_id": target.wall_candidate_id,
                                "wall_scope": wall_scope.decision_scope_id,
                                "terminator": terminator.primitive_id,
                            }
                            record = WallFinishCalloutWallBindingRecord(
                                binding_id=stable_contract_id("finish_callout_wall_binding", payload, digest_chars=32),
                                document_id=published.revision.document_id,
                                revision_id=published.revision.revision_id,
                                source_sha256=published.revision.source_sha256,
                                snapshot_id=published.snapshot.snapshot_id,
                                page_id=page_id,
                                viewport_id=viewport.view_id,
                                decision_scope_id=f"finish-callout-wall:{viewport.view_id}",
                                physical_wall_decision_scope_id=wall_scope.decision_scope_id,
                                physical_wall_id=target.wall_candidate_id,
                                raw_owner_wall_ids=raw_owners,
                                equivalence_group_wall_ids=group,
                                equivalence_pair_classifications=pairs,
                                source_wall_primitive_ids=tuple(sorted(source_segments)),
                                annotation_block_id=block_id,
                                annotation_observation_ids=tuple(annotation_ids),
                                annotation_sequence_numbers=tuple(sequence_numbers),
                                leader_path_ids=tuple(leader_ids),
                                terminator_primitive_ids=(terminator.primitive_id,),
                                source_evidence_ids=tuple(dict.fromkeys((
                                    *annotation_ids, *leader_ids,
                                    terminator.primitive_id, *tuple(sorted(source_segments)),
                                ))),
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(FINISH_CALLOUT_WALL_BINDING_RESOLVED,),
                                _seal=_RECORD_SEAL,
                            )
                            accepted[(block_id, record.physical_wall_id)] = record

                        if not accepted:
                            continue
                        selector = WallFinishCalloutWallScopeSelector(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            viewport_id=viewport.view_id,
                            decision_scope_id=f"finish-callout-wall:{viewport.view_id}",
                        )
                        previous = results.get(selector.key)
                        merged = {} if previous is None else {
                            r.binding_id: r for r in previous.bindings
                        }
                        merged.update({r.binding_id: r for r in accepted.values()})
                        results[selector.key] = WallFinishCalloutWallScopeResult(
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=(FINISH_CALLOUT_WALL_BINDING_RESOLVED,),
                            bindings=tuple(sorted(merged.values(), key=lambda r: r.binding_id)),
                        )
            finally:
                doc.close()
        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallFinishCalloutWallAuthority:
        return WallFinishCalloutWallAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def published_results(self) -> tuple[WallFinishCalloutWallScopeResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "FINISH_CALLOUT_WALL_BINDING_RESOLVED",
    "FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE",
    "FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE",
    "WallFinishCalloutWallAuthority",
    "WallFinishCalloutWallBindingRecord",
    "WallFinishCalloutWallProducer",
    "WallFinishCalloutWallScopeResult",
    "WallFinishCalloutWallScopeSelector",
]
