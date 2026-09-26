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
    _endpoints,
    _filled_terminators,
    _leader_paths,
    _page_visible_lines,
    _point_in_bbox_source_roundoff,
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


def _sequence_interval(receipt) -> Optional[tuple[int, int]]:
    values = tuple(
        int(value)
        for value in (
            tuple(getattr(receipt, "trace_sequence_numbers", ()) or ())
            or (
                ()
                if getattr(receipt, "sequence_number", None) is None
                else (int(receipt.sequence_number),)
            )
        )
    )
    if not values:
        return None
    return (min(values), max(values))


def _execution_words_are_neighbors(left, right) -> bool:
    """Positive source-execution + geometry proof that two words share a note.

    Source execution must overlap/touch. Geometry must independently prove
    either same-line adjacency or an immediately neighboring text line.
    This deliberately does not inspect text content or PyMuPDF block metadata.
    """
    l_start, l_end, _l_obs, l_box = left
    r_start, r_end, _r_obs, r_box = right
    if r_start > l_end + 1 or l_start > r_end + 1:
        return False

    lx0, ly0, lx1, ly1 = l_box
    rx0, ry0, rx1, ry1 = r_box
    lh = max(0.1, ly1 - ly0)
    rh = max(0.1, ry1 - ry0)
    scale = max(lh, rh)

    y_overlap = max(0.0, min(ly1, ry1) - max(ly0, ry0))
    same_line = y_overlap >= 0.5 * min(lh, rh)
    x_gap = max(0.0, max(lx0, rx0) - min(lx1, rx1))
    if same_line:
        return x_gap <= 2.5 * scale

    y_gap = max(0.0, max(ly0, ry0) - min(ly1, ry1))
    x_overlap = max(0.0, min(lx1, rx1) - max(lx0, rx0))
    left_edge_delta = abs(lx0 - rx0)
    return (
        y_gap <= 0.75 * scale
        and (x_overlap > 0.0 or left_edge_delta <= 2.0 * scale)
    )


def _compose_execution_annotation_blocks(rows):
    """Connected components of source-execution words with coherent layout."""
    ordered = tuple(
        sorted(
            rows,
            key=lambda row: (
                row[0],
                row[1],
                round(row[3][1], 6),
                round(row[3][0], 6),
                row[2],
            ),
        )
    )
    if not ordered:
        return ()

    parent = list(range(len(ordered)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left_index: int, right_index: int) -> None:
        left_root, right_root = find(left_index), find(right_index)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for left_index, left in enumerate(ordered):
        for right_index in range(left_index + 1, len(ordered)):
            right = ordered[right_index]
            if right[0] > left[1] + 1:
                break
            if _execution_words_are_neighbors(left, right):
                union(left_index, right_index)

    groups: dict[int, list[tuple]] = {}
    for index, row in enumerate(ordered):
        groups.setdefault(find(index), []).append(row)

    result = []
    for rows_in_group in groups.values():
        rows_in_group.sort(
            key=lambda row: (
                row[0],
                row[1],
                round(row[3][1], 6),
                round(row[3][0], 6),
                row[2],
            )
        )
        result.append(tuple(rows_in_group))
    return tuple(
        sorted(
            result,
            key=lambda group: (
                group[0][0],
                group[0][1],
                group[0][2],
            ),
        )
    )


def _source_annotation_blocks(source: SourceVisibilityProducer, published, page_id: str):
    """Compose annotation geometry from producer-owned source execution.

    PyMuPDF block/line/word indices are intentionally ignored. They are
    optional parser metadata and cannot define authority. Words are grouped by
    source execution continuity plus independently coherent source geometry.
    """
    authority = source.text_integrity_authority()
    by_partition: dict[str, list[tuple[int, int, str, tuple[float, ...]]]] = {}

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
            or len(receipt.geometry) != 4
        ):
            continue
        interval = _sequence_interval(receipt)
        if interval is None:
            continue
        by_partition.setdefault(str(receipt.source_partition_id), []).append((
            interval[0],
            interval[1],
            observation_id,
            tuple(float(value) for value in receipt.geometry),
        ))

    out = []
    for partition_id, rows in sorted(by_partition.items()):
        for component in _compose_execution_annotation_blocks(rows):
            geometries = [row[3] for row in component]
            bbox = _bbox_union(geometries)
            heights = [max(0.1, geometry[3] - geometry[1]) for geometry in geometries]
            sequence_numbers = tuple(
                sorted({seq for row in component for seq in range(row[0], row[1] + 1)})
            )
            observation_ids = tuple(row[2] for row in component)
            payload = {
                "document_id": published.revision.document_id,
                "revision_id": published.revision.revision_id,
                "source_sha256": published.revision.source_sha256,
                "snapshot_id": published.snapshot.snapshot_id,
                "page_id": page_id,
                "source_partition_id": partition_id,
                "observation_ids": observation_ids,
                "sequence_numbers": sequence_numbers,
                "bbox": tuple(round(float(value), 6) for value in bbox),
            }
            out.append((
                stable_contract_id(
                    "source_execution_annotation_block",
                    payload,
                    digest_chars=32,
                ),
                observation_ids,
                sequence_numbers,
                bbox,
                statistics.median(heights),
            ))
    return tuple(
        sorted(
            out,
            key=lambda row: (
                row[2][0] if row[2] else -1,
                row[0],
            ),
        )
    )


def _line_index_by_observation(page_lines):
    out: dict[str, list[object]] = {}
    for line in page_lines:
        out.setdefault(str(line.observation_id), []).append(line)
    return out


def _annotation_has_native_leader_contact(annotation_bbox, leader_lines) -> bool:
    return any(
        any(
            _point_in_bbox_source_roundoff(point, annotation_bbox)
            for point in _endpoints(line)
        )
        for line in leader_lines
    )


def _local_owner_universe_safe(
    *,
    terminator,
    page_lines,
    wall_scope,
    page_line_index=None,
) -> bool:
    questionable = tuple(dict.fromkeys((
        *tuple(getattr(wall_scope, "scope_boundary_observation_ids", ()) or ()),
        *tuple(getattr(wall_scope, "ambiguous_source_observation_ids", ()) or ()),
    )))
    if not questionable:
        return True
    by_observation = (
        page_line_index
        if page_line_index is not None
        else _line_index_by_observation(page_lines)
    )
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
                    page_line_index = _line_index_by_observation(page_lines)
                    viewport_context = {}

                    for block_id, annotation_ids, sequence_numbers, annotation_bbox, text_height in _source_annotation_blocks(
                        source_visibility_producer, published, page_id
                    ):
                        viewport = assign_bbox_to_viewport(annotation_bbox, viewports, allow_derived=True)
                        if viewport is None or viewport.bounding_box is None:
                            continue

                        context = viewport_context.get(viewport.view_id)
                        if context is None:
                            wall_selector = wall_authority.selector_for_viewport(
                                document_id=published.revision.document_id,
                                revision_id=published.revision.revision_id,
                                source_sha256=published.revision.source_sha256,
                                snapshot_id=published.snapshot.snapshot_id,
                                page_id=page_id,
                                viewport_id=viewport.view_id,
                            )
                            if wall_selector is None:
                                viewport_context[viewport.view_id] = False
                                continue
                            wall_scope = wall_authority.resolve_scope(wall_selector)
                            if wall_scope.status is not EvidenceResolutionStatus.CORROBORATED:
                                viewport_context[viewport.view_id] = False
                                continue
                            leader_lines = _viewport_owned_lines(page_lines, viewport, viewports)
                            wall_obs = set(wall_scope.source_observation_ids)
                            wall_lines = tuple(
                                line for line in page_lines
                                if line.observation_id in wall_obs
                            )
                            context = (wall_scope, leader_lines, wall_lines)
                            viewport_context[viewport.view_id] = context
                        elif context is False:
                            continue

                        wall_scope, leader_lines, wall_lines = context
                        if not _annotation_has_native_leader_contact(
                            annotation_bbox,
                            leader_lines,
                        ):
                            continue

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
                                terminator=terminator,
                                page_lines=page_lines,
                                wall_scope=wall_scope,
                                page_line_index=page_line_index,
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
