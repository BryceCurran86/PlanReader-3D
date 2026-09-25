"""Shadow source-owned wall-finish / semantic-face binding authority (Item 19B).

Positive path:
trusted native finish annotation -> endpoint-connected native leader -> filled
native terminator -> unique authenticated physical wall -> independently
authenticated semantic face.

No quantity publication. No nearest-text / nearest-wall matching. Local notes
remain partial until a separate source-owned target-face universe proves
complete coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import math
import re
import statistics
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import NATIVE_PDF_VISIBLE_SEGMENT, SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    assign_bbox_to_viewport,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)
from pb_wall_role_authority import WallRoleClassification, WallRoleProducer, WallRoleSelector

WALL_FINISH_FACE_BINDING_SCHEMA_VERSION = "1.1.0"
SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT = "native_direct_finish_callout"

FINISH_BINDING_RESOLVED = "wall_finish_face_binding_resolved"
FINISH_BINDING_UNAVAILABLE = "wall_finish_face_binding_unavailable"
FINISH_BINDING_TARGET_CONFLICT = "wall_finish_face_binding_target_wall_conflict"
FINISH_BINDING_FACE_FINISH_CONFLICT = "wall_finish_face_binding_face_finish_conflict"
FINISH_SCOPE_PARTIAL = "wall_finish_scope_partial"
FINISH_SCOPE_COMPLETE = "wall_finish_scope_complete"
FINISH_SCOPE_UNIVERSE_UNAVAILABLE = "wall_finish_scope_target_face_universe_unavailable"
FINISH_SOURCE_INTEGRITY_FAILURE = "wall_finish_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()
_COORD_DIGITS = 6


class PhysicalFaceRole(str, Enum):
    EXTERIOR_FACE = "exterior_face"
    ROOM_FACING_INTERIOR_FACE = "room_facing_interior_face"


class FinishScopeStatus(str, Enum):
    PARTIAL = "partial"
    COMPLETE = "complete"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class WallFinishFaceBindingScopeSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "page_id", "viewport_id", "decision_scope_id",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be non-empty")

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.document_id, self.revision_id, self.source_sha256,
            self.snapshot_id, self.page_id, self.viewport_id, self.decision_scope_id,
        )


@dataclass(frozen=True)
class WallFinishFaceBindingRecord:
    binding_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str
    physical_wall_id: str
    physical_face_id: str
    physical_face_role: PhysicalFaceRole
    source_face_segment_ids: tuple[str, ...]
    trade_scope_id: str
    finish_material: str
    annotation_observation_ids: tuple[str, ...]
    leader_path_ids: tuple[str, ...]
    terminator_primitive_ids: tuple[str, ...]
    wall_role_record_id: str
    wall_role: WallRoleClassification
    source_evidence_ids: tuple[str, ...]
    source_evidence_kind: str
    decision_scope_complete: bool
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    physical_wall_decision_scope_id: str = ""
    schema_version: str = WALL_FINISH_FACE_BINDING_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFinishFaceBindingRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive binding record must be CORROBORATED")
        if self.decision_scope_complete:
            raise ValueError("direct local callout cannot self-certify complete finish scope")


@dataclass(frozen=True)
class WallFinishCompleteScopeRecord:
    scope_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str
    trade_scope_id: str
    finish_material: str
    target_face_ids: tuple[str, ...]
    covered_face_ids: tuple[str, ...]
    binding_ids: tuple[str, ...]
    decision_scope_complete: bool
    scope_status: FinishScopeStatus
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_FINISH_FACE_BINDING_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFinishCompleteScopeRecord is producer-owned")
        if self.decision_scope_complete and (
            not self.target_face_ids
            or set(self.target_face_ids) != set(self.covered_face_ids)
            or self.scope_status is not FinishScopeStatus.COMPLETE
        ):
            raise ValueError("complete scope requires an enumerated fully-covered face universe")


@dataclass(frozen=True)
class WallFinishFaceBindingScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    bindings: tuple[WallFinishFaceBindingRecord, ...] = ()
    scope_records: tuple[WallFinishCompleteScopeRecord, ...] = ()
    schema_version: str = WALL_FINISH_FACE_BINDING_SCHEMA_VERSION


@dataclass(frozen=True)
class _Semantic:
    trade_scope_id: str
    finish_material: str
    direction: str


@dataclass(frozen=True)
class _Line:
    observation_id: str
    raw_id: str
    geometry: tuple[float, float, float, float]


@dataclass(frozen=True)
class _Terminator:
    primitive_id: str
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _finish_semantics(text: str) -> tuple[_Semantic, ...]:
    text = _normalise_text(text)
    if "wall" not in text or "finish" not in text:
        return ()
    if "externally" in text and "key" in text:
        return (_Semantic("external_key_pointing", "key_pointing", "externally"),)
    if "internally" in text and "plaster" in text and "paint" in text:
        return (
            _Semantic("internal_plaster", "plaster", "internally"),
            _Semantic("internal_paint", "paint", "internally"),
        )
    return ()


def _semantic_face(role: WallRoleClassification, direction: str) -> Optional[PhysicalFaceRole]:
    if role is WallRoleClassification.EXTERNAL and direction == "externally":
        return PhysicalFaceRole.EXTERIOR_FACE
    if role is WallRoleClassification.EXTERNAL and direction == "internally":
        return PhysicalFaceRole.ROOM_FACING_INTERIOR_FACE
    return None


def _bbox_union(boxes: Sequence[Sequence[float]]) -> tuple[float, float, float, float]:
    return (
        min(float(b[0]) for b in boxes), min(float(b[1]) for b in boxes),
        max(float(b[2]) for b in boxes), max(float(b[3]) for b in boxes),
    )


def _point_in_bbox(point: Sequence[float], bbox: Sequence[float]) -> bool:
    """True only when the source point actually touches or lies inside bbox."""
    return (
        float(bbox[0]) <= float(point[0]) <= float(bbox[2])
        and float(bbox[1]) <= float(point[1]) <= float(bbox[3])
    )


def _segment_intersects_bbox(
    geometry: Sequence[float],
    bbox: Sequence[float],
) -> bool:
    """Exact inclusive segment/rectangle intersection with no proximity expansion."""
    x1, y1, x2, y2 = (float(v) for v in geometry)
    xmin, ymin, xmax, ymax = (float(v) for v in bbox)
    if _point_in_bbox((x1, y1), bbox) or _point_in_bbox((x2, y2), bbox):
        return True

    dx, dy = x2 - x1, y2 - y1
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, x1 - xmin),
        (dx, xmax - x1),
        (-dy, y1 - ymin),
        (dy, ymax - y1),
    ):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        ratio = q / p
        if p < 0.0:
            if ratio > upper:
                return False
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return False
            upper = min(upper, ratio)
    return lower <= upper


def _endpoints(line: _Line) -> tuple[tuple[float, float], tuple[float, float]]:
    x1, y1, x2, y2 = line.geometry
    return ((x1, y1), (x2, y2))


def _endpoint_key(point: Sequence[float]) -> tuple[float, float]:
    # Native leader continuity is authority-bearing. Do not round across a gap.
    return (float(point[0]), float(point[1]))


def _line_fully_inside_bbox(line: _Line, bbox: Sequence[float]) -> bool:
    return all(_point_in_bbox(point, bbox) for point in _endpoints(line))


def _viewport_owned_lines(
    lines: Sequence[_Line],
    viewport,
    viewports: Sequence[object],
) -> tuple[_Line, ...]:
    """Return lines with one exact authenticated viewport owner.

    Leader evidence is annotation geometry, not wall geometry. It therefore
    cannot be restricted to the physical-wall source-observation universe.
    Ownership is nevertheless fail-closed: a line is admitted only when both
    endpoints lie inside exactly one authenticated viewport and that owner is
    the target viewport. No nearest-view assignment or bbox expansion occurs.
    """
    target_id = str(getattr(viewport, "view_id", "") or "")
    if not target_id or getattr(viewport, "bounding_box", None) is None:
        return ()

    owned: list[_Line] = []
    for line in lines:
        owners = [
            candidate
            for candidate in viewports
            if getattr(candidate, "bounding_box", None) is not None
            and _line_fully_inside_bbox(line, candidate.bounding_box)
        ]
        if len(owners) != 1:
            continue
        if str(getattr(owners[0], "view_id", "") or "") != target_id:
            continue
        owned.append(line)
    return tuple(sorted(owned, key=lambda item: item.raw_id))


def _authoritative_viewports(page: fitz.Page, page_number: int):
    rows = tuple(segment_page_viewports(page, page_number=page_number))
    if any(not is_segment_page_viewports_product(viewport) for viewport in rows):
        return ()
    sibling_non_overlapping = validate_non_overlapping_viewports(rows)
    return tuple(
        viewport
        for viewport in rows
        if viewport.bounding_box is not None
        and (
            viewport.status == ViewportSegmentationStatus.RESOLVED.value
            or (
                sibling_non_overlapping
                and is_authoritative_derived_viewport(viewport)
            )
        )
    )


def _trusted_finish_blocks(source: SourceVisibilityProducer, published, page_id: str):
    authority = source.text_integrity_authority()
    blocks: dict[int, list[tuple[int, str, str, tuple[float, ...]]]] = {}
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
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or receipt is None or receipt.page_id != page_id
            or receipt.block_no is None or receipt.line_no is None or receipt.word_no is None
        ):
            continue
        blocks.setdefault(int(receipt.block_no), []).append((
            int(receipt.line_no) * 10000 + int(receipt.word_no),
            observation_id,
            str(result.trusted_text or ""),
            tuple(receipt.geometry),
        ))
    out = []
    for block_no, values in sorted(blocks.items()):
        ordered = sorted(values, key=lambda item: (item[0], item[1]))
        text = " ".join(item[2] for item in ordered)
        semantics = _finish_semantics(text)
        if not semantics:
            continue
        out.append((
            block_no, text, semantics, tuple(item[1] for item in ordered),
            _bbox_union([item[3] for item in ordered]),
            statistics.median(max(0.1, item[3][3] - item[3][1]) for item in ordered),
        ))
    return tuple(out)


def _page_visible_lines(source: SourceVisibilityProducer, published, page_id: str) -> tuple[_Line, ...]:
    authority = source.authority()
    prefix = "visible:segment:"
    out = []
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        obs = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or obs is None or obs.page_id != page_id
            or obs.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
            or not obs.source_primitive_ref.startswith(prefix)
            or len(obs.geometry) != 4
        ):
            continue
        out.append(_Line(
            observation_id=observation_id,
            raw_id=obs.source_primitive_ref[len(prefix):],
            geometry=tuple(float(v) for v in obs.geometry),
        ))
    return tuple(sorted(out, key=lambda item: item.raw_id))


def _filled_terminators(page: fitz.Page, text_height: float) -> tuple[_Terminator, ...]:
    max_span = max(2.0, text_height * 2.5)
    out = []
    for index, drawing in enumerate(page.get_drawings() or ()):
        rect, fill = drawing.get("rect"), drawing.get("fill")
        if rect is None or fill is None:
            continue
        bbox = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if width <= 0 or height <= 0 or max(width, height) > max_span:
            continue
        if not 0.65 <= width / height <= 1.55:
            continue
        items = drawing.get("items") or ()
        if not any(item and item[0] == "c" for item in items) and len(items) < 8:
            continue
        payload = {
            "page": int(page.number) + 1,
            "drawing_index": index,
            "bbox": tuple(round(v, 6) for v in bbox),
            "fill": tuple(round(float(v), 6) for v in fill),
        }
        out.append(_Terminator(
            primitive_id=stable_contract_id("finish_terminator", payload, digest_chars=32),
            bbox=bbox,
            center=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
        ))
    return tuple(sorted(out, key=lambda item: item.primitive_id))


def _leader_paths(
    annotation_bbox: Sequence[float],
    lines: Sequence[_Line],
    terminators: Sequence[_Terminator],
    epsilon: float = 0.0,
) -> tuple[tuple[tuple[str, ...], _Terminator], ...]:
    # epsilon is retained only for call-site compatibility. Positive authority
    # never expands source geometry: near-but-not-touching must fail closed.
    del epsilon
    by_endpoint: dict[tuple[float, float], list[int]] = {}
    for index, line in enumerate(lines):
        for point in _endpoints(line):
            by_endpoint.setdefault(_endpoint_key(point), []).append(index)
    starts = [
        index for index, line in enumerate(lines)
        if any(_point_in_bbox(point, annotation_bbox) for point in _endpoints(line))
    ]
    found = {}
    for start in starts:
        queue = [(start, (start,))]
        while queue:
            current, path = queue.pop(0)
            if len(path) > 12:
                continue
            line = lines[current]
            for endpoint in _endpoints(line):
                for term in terminators:
                    if _point_in_bbox(endpoint, term.bbox):
                        ids = tuple(lines[i].observation_id for i in path)
                        found[(ids, term.primitive_id)] = (ids, term)
                for nxt in by_endpoint.get(_endpoint_key(endpoint), ()):
                    if nxt not in path:
                        queue.append((nxt, (*path, nxt)))
    return tuple(found[key] for key in sorted(found))


def _target_from_terminator(
    terminator: _Terminator,
    lines: Sequence[_Line],
    wall_scope,
    epsilon: float = 0.0,
):
    # epsilon is retained only for compatibility. Wall ownership requires an
    # actual terminator/primitive intersection; proximity is never authority.
    del epsilon
    raw_hits = {
        line.raw_id for line in lines
        if _segment_intersects_bbox(line.geometry, terminator.bbox)
    }
    matching = [
        record for record in wall_scope.records
        if raw_hits & set(record.physical_identity.source_primitive_ids)
    ]
    if not matching:
        return None, (), EvidenceResolutionStatus.ABSTAINED
    representative_for: dict[str, str] = {}
    for group in tuple(getattr(wall_scope.equivalence, "equivalence_groups", ()) or ()):
        rep = sorted(group)[0]
        for wall_id in group:
            representative_for[wall_id] = rep
    normalized = {
        representative_for.get(record.wall_candidate_id, record.wall_candidate_id)
        for record in matching
    }
    if len(normalized) != 1:
        # Multiple physical-wall owners are ambiguous, not a positive conflict
        # proposition. The caller must abstain rather than select or rank them.
        return None, tuple(sorted(raw_hits)), EvidenceResolutionStatus.ABSTAINED
    target_id = next(iter(normalized))
    target = next((r for r in wall_scope.records if r.wall_candidate_id == target_id), None)
    resolved_target = target or sorted(matching, key=lambda r: r.wall_candidate_id)[0]

    # Provenance on a positive binding must contain only source primitives
    # actually owned by the resolved physical wall. A non-wall leader may
    # legitimately touch the same terminator, but it must remain leader
    # evidence rather than being mislabeled as wall-face evidence.
    target_owned_raw_hits: set[str] = set()
    for record in matching:
        normalized_id = representative_for.get(
            record.wall_candidate_id,
            record.wall_candidate_id,
        )
        if normalized_id != target_id:
            continue
        target_owned_raw_hits.update(
            raw_hits & set(record.physical_identity.source_primitive_ids)
        )
    if not target_owned_raw_hits:
        return None, (), EvidenceResolutionStatus.ABSTAINED
    return (
        resolved_target,
        tuple(sorted(target_owned_raw_hits)),
        EvidenceResolutionStatus.CORROBORATED,
    )


def _partial_scope(records: Sequence[WallFinishFaceBindingRecord]) -> WallFinishCompleteScopeRecord:
    first = records[0]
    covered = tuple(sorted({record.physical_face_id for record in records}))
    binding_ids = tuple(sorted(record.binding_id for record in records))
    payload = {
        "document_id": first.document_id, "revision_id": first.revision_id,
        "source_sha256": first.source_sha256, "snapshot_id": first.snapshot_id,
        "page_id": first.page_id, "viewport_id": first.viewport_id,
        "trade_scope_id": first.trade_scope_id, "finish_material": first.finish_material,
        "covered_face_ids": covered, "binding_ids": binding_ids,
    }
    return WallFinishCompleteScopeRecord(
        scope_id=stable_contract_id("wall_finish_scope", payload, digest_chars=32),
        document_id=first.document_id, revision_id=first.revision_id,
        source_sha256=first.source_sha256, snapshot_id=first.snapshot_id,
        page_id=first.page_id, viewport_id=first.viewport_id,
        decision_scope_id=first.decision_scope_id,
        trade_scope_id=first.trade_scope_id, finish_material=first.finish_material,
        target_face_ids=(), covered_face_ids=covered, binding_ids=binding_ids,
        decision_scope_complete=False, scope_status=FinishScopeStatus.PARTIAL,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(FINISH_SCOPE_PARTIAL, FINISH_SCOPE_UNIVERSE_UNAVAILABLE),
        _seal=_RECORD_SEAL,
    )


class WallFinishFaceBindingAuthority:
    def __init__(self, results: Mapping[tuple[str, ...], WallFinishFaceBindingScopeResult], *, _seal=None):
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishFaceBindingAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_scope(self, selector: WallFinishFaceBindingScopeSelector) -> WallFinishFaceBindingScopeResult:
        if type(selector) is not WallFinishFaceBindingScopeSelector:
            raise TypeError("selector must be WallFinishFaceBindingScopeSelector")
        return self._results.get(
            selector.key,
            WallFinishFaceBindingScopeResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(FINISH_BINDING_UNAVAILABLE,),
            ),
        )


class WallFinishFaceBindingProducer:
    def __init__(self, results: Mapping[tuple[str, ...], WallFinishFaceBindingScopeResult], *, _seal=None):
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallFinishFaceBindingProducer must be obtained from_source_visibility_producer()")
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "WallFinishFaceBindingProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be an actual SourceVisibilityProducer")
        selected = None if page_ids is None else tuple(sorted(
            {str(p).strip() for p in page_ids if str(p).strip()}, key=int
        ))
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one source page")

        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source_visibility_producer,
            page_ids=selected,
        ).authority()
        role_producer = WallRoleProducer.from_source_topology(
            physical_wall_candidate_authority=wall_authority
        )
        results: dict[tuple[str, ...], WallFinishFaceBindingScopeResult] = {}
        store = source_visibility_producer._producer._store

        for revision_id, published in sorted(source_visibility_producer._published_by_revision.items()):
            if source_visibility_producer._producer.current_revision_id(published.revision.document_id) != revision_id:
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
                raise RuntimeError(FINISH_SOURCE_INTEGRITY_FAILURE)
            page_list = selected or tuple(str(int(p)) for p in sorted(published.coverage.decoded_pages))
            doc = fitz.open(stream=source_bytes, filetype="pdf")
            try:
                for page_id in page_list:
                    page_number = int(page_id)
                    if not 1 <= page_number <= doc.page_count:
                        continue
                    page = doc.load_page(page_number - 1)
                    viewports = _authoritative_viewports(page, page_number)
                    lines = _page_visible_lines(source_visibility_producer, published, page_id)
                    for _, _, semantics, annotation_ids, annotation_bbox, text_height in _trusted_finish_blocks(
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
                        # Leader/callout geometry is not wall geometry. Discover
                        # leader paths from all native lines with one exact
                        # authenticated viewport owner, while retaining the
                        # wall scope as the sole authority for wall targeting.
                        leader_lines = _viewport_owned_lines(
                            lines,
                            viewport,
                            viewports,
                        )
                        wall_observation_ids = set(wall_scope.source_observation_ids)
                        wall_lines = tuple(
                            line for line in lines
                            if line.observation_id in wall_observation_ids
                        )
                        terminators = tuple(
                            term for term in _filled_terminators(page, text_height)
                            if viewport.bounding_box[0] <= term.center[0] <= viewport.bounding_box[2]
                            and viewport.bounding_box[1] <= term.center[1] <= viewport.bounding_box[3]
                        )
                        paths = _leader_paths(annotation_bbox, leader_lines, terminators)
                        if not paths:
                            continue

                        accepted: dict[tuple[str, str, str], WallFinishFaceBindingRecord] = {}
                        for leader_ids, terminator in paths:
                            target, source_segments, target_status = _target_from_terminator(
                                terminator, wall_lines, wall_scope
                            )
                            if (
                                target_status is not EvidenceResolutionStatus.CORROBORATED
                                or target is None
                            ):
                                continue
                            role_result = role_producer.publish(WallRoleSelector(
                                document_id=published.revision.document_id,
                                revision_id=published.revision.revision_id,
                                source_sha256=published.revision.source_sha256,
                                snapshot_id=published.snapshot.snapshot_id,
                                page_id=page_id,
                                decision_scope_id=wall_scope.decision_scope_id,
                                physical_wall_id=target.wall_candidate_id,
                            ))
                            if role_result.status is not EvidenceResolutionStatus.CORROBORATED or role_result.record is None:
                                continue
                            role_record = role_result.record
                            if (
                                role_record.document_id != published.revision.document_id
                                or role_record.revision_id != published.revision.revision_id
                                or role_record.source_sha256 != published.revision.source_sha256
                                or role_record.snapshot_id != published.snapshot.snapshot_id
                                or role_record.page_id != page_id
                                or role_record.decision_scope_id != wall_scope.decision_scope_id
                                or role_record.physical_wall_id != target.wall_candidate_id
                            ):
                                continue
                            for semantic in semantics:
                                face_role = _semantic_face(role_record.role, semantic.direction)
                                if face_role is None:
                                    continue
                                # Physical face identity belongs to the exact wall and
                                # semantic side, not to the current viewport segmentation.
                                # Viewport lineage remains on the record / selector, but
                                # viewport expansion must not mint a new physical face.
                                face_payload = {
                                    "document_id": published.revision.document_id,
                                    "revision_id": published.revision.revision_id,
                                    "source_sha256": published.revision.source_sha256,
                                    "snapshot_id": published.snapshot.snapshot_id,
                                    "page_id": page_id,
                                    "physical_wall_decision_scope_id": wall_scope.decision_scope_id,
                                    "physical_wall_id": target.wall_candidate_id,
                                    "physical_face_role": face_role.value,
                                }
                                face_id = stable_contract_id("physical_wall_semantic_face", face_payload, digest_chars=32)
                                evidence_ids = tuple(dict.fromkeys(
                                    (*annotation_ids, *leader_ids, terminator.primitive_id, role_record.record_id)
                                ))
                                bind_payload = {
                                    **face_payload,
                                    "trade_scope_id": semantic.trade_scope_id,
                                    "finish_material": semantic.finish_material,
                                }
                                record = WallFinishFaceBindingRecord(
                                    binding_id=stable_contract_id("wall_finish_face_binding", bind_payload, digest_chars=32),
                                    document_id=published.revision.document_id,
                                    revision_id=published.revision.revision_id,
                                    source_sha256=published.revision.source_sha256,
                                    snapshot_id=published.snapshot.snapshot_id,
                                    page_id=page_id, viewport_id=viewport.view_id,
                                    decision_scope_id=f"finish-callout:{viewport.view_id}",
                                    physical_wall_decision_scope_id=wall_scope.decision_scope_id,
                                    physical_wall_id=target.wall_candidate_id,
                                    physical_face_id=face_id, physical_face_role=face_role,
                                    source_face_segment_ids=tuple(sorted(source_segments)),
                                    trade_scope_id=semantic.trade_scope_id,
                                    finish_material=semantic.finish_material,
                                    annotation_observation_ids=tuple(annotation_ids),
                                    leader_path_ids=tuple(leader_ids),
                                    terminator_primitive_ids=(terminator.primitive_id,),
                                    wall_role_record_id=role_record.record_id,
                                    wall_role=role_record.role,
                                    source_evidence_ids=evidence_ids,
                                    source_evidence_kind=SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT,
                                    decision_scope_complete=False,
                                    status=EvidenceResolutionStatus.CORROBORATED,
                                    reason_codes=(FINISH_BINDING_RESOLVED,),
                                    _seal=_RECORD_SEAL,
                                )
                                signature = (face_id, semantic.trade_scope_id, semantic.finish_material)
                                prior = accepted.get(signature)
                                if prior is None or record.binding_id < prior.binding_id:
                                    accepted[signature] = record

                        records = tuple(sorted(accepted.values(), key=lambda r: r.binding_id))
                        grouped: dict[tuple[str, str], list[WallFinishFaceBindingRecord]] = {}
                        for record in records:
                            grouped.setdefault((record.trade_scope_id, record.finish_material), []).append(record)
                        scopes = tuple(_partial_scope(group) for _, group in sorted(grouped.items()))
                        selector = WallFinishFaceBindingScopeSelector(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id, viewport_id=viewport.view_id,
                            decision_scope_id=f"finish-callout:{viewport.view_id}",
                        )
                        if records:
                            result = WallFinishFaceBindingScopeResult(
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(FINISH_BINDING_RESOLVED, FINISH_SCOPE_PARTIAL),
                                bindings=records, scope_records=scopes,
                            )
                        else:
                            continue
                        previous = results.get(selector.key)
                        if previous is None:
                            results[selector.key] = result
                        else:
                            merged = tuple(sorted(
                                {record.binding_id: record for record in (*previous.bindings, *result.bindings)}.values(),
                                key=lambda r: r.binding_id,
                            ))
                            face_trade: dict[tuple[str, str], set[str]] = {}
                            for record in merged:
                                face_trade.setdefault(
                                    (record.physical_face_id, record.trade_scope_id), set()
                                ).add(record.finish_material)
                            material_conflict = any(len(materials) > 1 for materials in face_trade.values())
                            grouped = {}
                            for record in merged:
                                grouped.setdefault((record.trade_scope_id, record.finish_material), []).append(record)
                            results[selector.key] = WallFinishFaceBindingScopeResult(
                                status=(
                                    EvidenceResolutionStatus.CONFLICT
                                    if material_conflict
                                    or previous.status is EvidenceResolutionStatus.CONFLICT
                                    or result.status is EvidenceResolutionStatus.CONFLICT
                                    else EvidenceResolutionStatus.CORROBORATED
                                ),
                                reason_codes=tuple(dict.fromkeys((
                                    *previous.reason_codes,
                                    *result.reason_codes,
                                    *((FINISH_BINDING_FACE_FINISH_CONFLICT,) if material_conflict else ()),
                                ))),
                                bindings=merged,
                                scope_records=tuple(_partial_scope(group) for _, group in sorted(grouped.items())),
                            )
            finally:
                doc.close()

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallFinishFaceBindingAuthority:
        return WallFinishFaceBindingAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def published_results(self) -> tuple[WallFinishFaceBindingScopeResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "FINISH_BINDING_FACE_FINISH_CONFLICT",
    "FINISH_BINDING_RESOLVED",
    "FINISH_BINDING_TARGET_CONFLICT",
    "FINISH_BINDING_UNAVAILABLE",
    "FINISH_SCOPE_COMPLETE",
    "FINISH_SCOPE_PARTIAL",
    "FINISH_SCOPE_UNIVERSE_UNAVAILABLE",
    "FinishScopeStatus",
    "PhysicalFaceRole",
    "SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT",
    "WALL_FINISH_FACE_BINDING_SCHEMA_VERSION",
    "WallFinishCompleteScopeRecord",
    "WallFinishFaceBindingAuthority",
    "WallFinishFaceBindingProducer",
    "WallFinishFaceBindingRecord",
    "WallFinishFaceBindingScopeResult",
    "WallFinishFaceBindingScopeSelector",
]
