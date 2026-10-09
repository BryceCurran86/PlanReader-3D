"""Fail-closed cross-view ceiling-finish binding.

This authority binds an already-authenticated canonical room to an authenticated
material occurrence on a reflected ceiling plan (RCP) without reusing geometry
coordinates between sheets.

Positive binding requires all of the following:
- the canonical room carries an upstream source-owned room-label binding;
- the room label is unique in the canonical room universe;
- the exact same label is independently trusted as a complete native PDF line
  inside an authenticated RCP viewport;
- the material occurrence was published by SourceMaterialSemanticProducer from
  that exact RCP viewport and its schedule definition explicitly has a ceiling
  role;
- the room-label line and material-occurrence line share one native PDF source
  partition and block;
- that block contains exactly one eligible canonical-room label and exactly one
  ceiling-finish occurrence.

There is no nearest-neighbour selection, cross-sheet coordinate transfer,
benchmark vocabulary, room-name special case, page constant, raw-code meaning,
or metric measurement in this module.  When the source does not encode the
relationship strongly enough, the result remains unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_cross_view_room_area_authority import (
    _trusted_lines_for_page as _trusted_room_lines_for_page,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_material_semantic_authority import (
    SourceMaterialDefinitionRecord,
    SourceMaterialDefinitionSelector,
    SourceMaterialOccurrenceRecord,
    SourceMaterialOccurrenceScopeResult,
    SourceMaterialSemanticProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)


CROSS_VIEW_CEILING_FINISH_SCHEMA_VERSION = "1.1.0"
CROSS_VIEW_CEILING_FINISH_RESOLVED = "cross_view_ceiling_finish_resolved"
CROSS_VIEW_CEILING_FINISH_PARTIAL = "cross_view_ceiling_finish_partial"
CROSS_VIEW_CEILING_FINISH_UNAVAILABLE = "cross_view_ceiling_finish_unavailable"
CROSS_VIEW_CEILING_FINISH_CONFLICT = "cross_view_ceiling_finish_conflict"
CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT = (
    "cross_view_ceiling_finish_lineage_conflict"
)
CROSS_VIEW_CEILING_FINISH_RCP_UNAVAILABLE = (
    "cross_view_ceiling_finish_rcp_unavailable"
)
CROSS_VIEW_CEILING_FINISH_NATIVE_BLOCK_UNAVAILABLE = (
    "cross_view_ceiling_finish_native_block_unavailable"
)

_PRODUCER_SEAL = object()
_RECORD_SEAL = object()

# Material meaning comes from the authenticated schedule definition. Ceiling
# role comes from the independently authenticated RCP occurrence, so the
# definition does not need to repeat the word "ceiling".
_CEILING_LINING_SEMANTICS = frozenset(
    {
        "ceiling_grid",
        "plasterboard",
        "fibre_cement",
        "insulated_panel",
        "sandwich_panel",
    }
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return " ".join(_clean(value).casefold().split())


def _finite_bbox(
    value: Sequence[object],
) -> Optional[tuple[float, float, float, float]]:
    if len(value) != 4:
        return None
    try:
        out = tuple(float(item) for item in value)
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        not all(math.isfinite(item) for item in out)
        or out[2] <= out[0]
        or out[3] <= out[1]
    ):
        return None
    return out  # type: ignore[return-value]


def _bbox_fully_inside(
    inner: Sequence[float],
    outer: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _bbox_key(value: Sequence[object]) -> Optional[tuple[float, float, float, float]]:
    bbox = _finite_bbox(value)
    if bbox is None:
        return None
    return tuple(round(item, 6) for item in bbox)


def _viewport_is_authoritative(
    viewport: SegmentedViewport,
    *,
    sibling_non_overlapping: bool,
) -> bool:
    return bool(
        viewport.bounding_box is not None
        and (
            viewport.status == ViewportSegmentationStatus.RESOLVED.value
            or (
                sibling_non_overlapping
                and is_authoritative_derived_viewport(viewport)
            )
        )
    )


@dataclass(frozen=True)
class _TrustedLine:
    page_id: str
    source_partition_id: str
    block_no: int
    line_no: int
    text: str
    bbox: tuple[float, float, float, float]
    observation_ids: tuple[str, ...]
    receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class CrossViewCeilingFinishRecord:
    record_id: str
    physical_room_id: str
    canonical_room_id: str
    source_room_face_record_id: str
    room_label: str
    support_page_id: str
    support_viewport_id: str
    support_source_partition_id: str
    support_block_no: int
    room_label_observation_ids: tuple[str, ...]
    room_label_receipt_ids: tuple[str, ...]
    finish_code: str
    semantic_finish: str
    definition_record_id: str
    definition_evidence_ids: tuple[str, ...]
    occurrence_record_id: str
    occurrence_evidence_id: str
    occurrence_observation_ids: tuple[str, ...]
    occurrence_receipt_ids: tuple[str, ...]
    occurrence_bbox_pdf_pts: tuple[float, float, float, float]
    # The semantic/material source may be a page-scoped snapshot distinct from
    # the topology snapshot that minted the canonical room. It is admissible
    # only when both snapshots belong to the exact same immutable revision.
    support_snapshot_id: str = ""
    schema_version: str = CROSS_VIEW_CEILING_FINISH_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("CrossViewCeilingFinishRecord is producer-owned")


@dataclass(frozen=True)
class CrossViewCeilingFinishResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[CrossViewCeilingFinishRecord, ...]
    unresolved_physical_room_ids: tuple[str, ...]
    schema_version: str = CROSS_VIEW_CEILING_FINISH_SCHEMA_VERSION

    @property
    def records_by_physical_room_id(
        self,
    ) -> Mapping[str, CrossViewCeilingFinishRecord]:
        return MappingProxyType(
            {record.physical_room_id: record for record in self.records}
        )


def _trusted_room_labels_for_pages(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
    page_ids: Sequence[str],
    candidate_labels: Sequence[str],
) -> Mapping[str, tuple[_TrustedLine, ...]]:
    """Reuse the hardened cross-view room-label text authority on RCP pages."""

    rows: dict[str, tuple[_TrustedLine, ...]] = {}
    for page_id in sorted({_clean(value) for value in page_ids if _clean(value)}):
        trusted = _trusted_room_lines_for_page(
            source,
            revision_id=revision_id,
            page_id=page_id,
            candidate_labels=candidate_labels,
        )
        converted = tuple(
            _TrustedLine(
                page_id=_clean(line.page_id),
                source_partition_id=_clean(line.source_partition_id),
                block_no=int(line.block_no),
                line_no=int(line.line_no),
                text=_clean(line.text),
                bbox=tuple(float(value) for value in line.bbox),
                observation_ids=tuple(
                    _clean(value)
                    for value in line.observation_ids
                    if _clean(value)
                ),
                receipt_ids=tuple(
                    _clean(value)
                    for value in line.receipt_ids
                    if _clean(value)
                ),
            )
            for line in trusted
        )
        if converted:
            rows[page_id] = converted
    return MappingProxyType(rows)

def _source_bytes(
    source: SourceVisibilityProducer,
    revision_id: str,
) -> Optional[bytes]:
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        return None
    payload = source._producer._store.source_bytes_by_revision.get(str(revision_id))
    if payload is None:
        return None
    data = bytes(payload)
    if hashlib.sha256(data).hexdigest() != published.revision.source_sha256:
        return None
    return data


def _rcp_viewports(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
) -> Mapping[tuple[str, str], tuple[float, float, float, float]]:
    published = source.published_snapshot_for_revision(revision_id)
    payload = _source_bytes(source, revision_id)
    if published is None or payload is None:
        return MappingProxyType({})

    decoded = sorted({int(value) for value in published.coverage.decoded_pages})
    output: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        for page_number in decoded:
            if page_number < 1 or page_number > pdf.page_count:
                continue
            viewports = tuple(
                segment_page_viewports(
                    pdf.load_page(page_number - 1),
                    page_number=page_number,
                )
            )
            if (
                not viewports
                or any(
                    not is_segment_page_viewports_product(viewport)
                    for viewport in viewports
                )
            ):
                continue
            sibling_non_overlapping = validate_non_overlapping_viewports(viewports)
            for viewport in viewports:
                if (
                    viewport.view_type
                    != DrawingViewType.REFLECTED_CEILING_PLAN.value
                    or not _viewport_is_authoritative(
                        viewport,
                        sibling_non_overlapping=sibling_non_overlapping,
                    )
                    or viewport.bounding_box is None
                ):
                    continue
                bbox = _finite_bbox(viewport.bounding_box)
                if bbox is not None:
                    output[(str(page_number), _clean(viewport.view_id))] = bbox
    finally:
        pdf.close()
    return MappingProxyType(output)


def _definition_is_ceiling_finish(
    definition: SourceMaterialDefinitionRecord,
) -> bool:
    semantic = _norm(definition.semantic_finish)
    if semantic not in _CEILING_LINING_SEMANTICS:
        return False
    # The semantic family must still come from a non-empty authenticated
    # schedule meaning. The occurrence's authenticated RCP viewport supplies
    # the ceiling role; a bare raw code can never reach this function.
    return bool(
        _norm(
            " ".join(
                _clean(value)
                for value in (
                    definition.description,
                    definition.substrate,
                    definition.finish,
                )
                if _clean(value)
            )
        )
    )


def _occurrence_line(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
    occurrence: SourceMaterialOccurrenceRecord,
) -> Optional[_TrustedLine]:
    """Recover the exact producer-owned native line behind one occurrence.

    The material semantic producer already authenticated the occurrence, which
    may have required raster corroboration.  This function therefore does not
    re-decide text trust.  It verifies that the preserved source observation IDs
    still resolve to one exact native PDF partition/block/line and that their
    union geometry/text matches the published occurrence.
    """

    published = source.published_snapshot_for_revision(revision_id)
    observation_ids = tuple(
        dict.fromkeys(
            _clean(value)
            for value in occurrence.source_text_observation_ids
            if _clean(value)
        )
    )
    if published is None or not observation_ids:
        return None

    authority = source.text_integrity_authority()
    resolved_rows: list[tuple[str, object]] = []
    for observation_id in observation_ids:
        result = authority.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if (
            receipt is None
            or _clean(receipt.page_id) != _clean(occurrence.page_id)
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            return None
        resolved_rows.append((observation_id, receipt))

    keys = {
        (
            _clean(receipt.source_partition_id),
            int(receipt.block_no),
            int(receipt.line_no),
        )
        for _observation_id, receipt in resolved_rows
    }
    if len(keys) != 1:
        return None
    partition_id, block_no, line_no = next(iter(keys))

    word_nos = [int(receipt.word_no) for _obs, receipt in resolved_rows]
    if (
        len(set(word_nos)) != len(word_nos)
        or set(word_nos) != set(range(min(word_nos), max(word_nos) + 1))
    ):
        return None
    ordered = sorted(resolved_rows, key=lambda item: int(item[1].word_no))
    boxes = [_finite_bbox(receipt.geometry) for _obs, receipt in ordered]
    if any(box is None for box in boxes):
        return None
    concrete = tuple(box for box in boxes if box is not None)
    bbox = (
        min(box[0] for box in concrete),
        min(box[1] for box in concrete),
        max(box[2] for box in concrete),
        max(box[3] for box in concrete),
    )
    if _bbox_key(bbox) != _bbox_key(occurrence.bbox_pdf_pts):
        return None

    raw_text = " ".join(
        _clean(receipt.raw_text)
        for _obs, receipt in ordered
        if _clean(receipt.raw_text)
    )
    if _norm(raw_text) != _norm(occurrence.raw_text):
        return None

    return _TrustedLine(
        page_id=_clean(occurrence.page_id),
        source_partition_id=partition_id,
        block_no=block_no,
        line_no=line_no,
        text=occurrence.raw_text,
        bbox=bbox,
        observation_ids=tuple(observation_id for observation_id, _ in ordered),
        receipt_ids=tuple(_clean(receipt.receipt_id) for _obs, receipt in ordered),
    )


class CrossViewCeilingFinishProducer:
    def __init__(
        self,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "CrossViewCeilingFinishProducer must be obtained from from_source()"
            )
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be exact SourceVisibilityProducer")
        if type(rooms) is not LiveCanonicalRoomComposition:
            raise TypeError("rooms must be LiveCanonicalRoomComposition")
        self._source = source
        self._rooms = rooms

    @classmethod
    def from_source(
        cls,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
    ) -> "CrossViewCeilingFinishProducer":
        return cls(source=source, rooms=rooms, _seal=_PRODUCER_SEAL)

    def publish(self) -> CrossViewCeilingFinishResult:
        eligible_rooms = tuple(
            room
            for room in self._rooms.rooms
            if (
                room.geometry_complete
                and _clean(room.room_label)
                and _clean(room.room_label_binding_record_id)
                and tuple(room.room_label_evidence_ids or ())
            )
        )
        if not eligible_rooms:
            return CrossViewCeilingFinishResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(CROSS_VIEW_CEILING_FINISH_UNAVAILABLE,),
                records=(),
                unresolved_physical_room_ids=(),
            )

        lineage = {
            (
                room.document_id,
                room.revision_id,
                room.source_sha256.lower(),
                room.snapshot_id,
            )
            for room in eligible_rooms
        }
        if len(lineage) != 1:
            return CrossViewCeilingFinishResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT,),
                records=(),
                unresolved_physical_room_ids=tuple(
                    sorted(room.physical_room_id for room in eligible_rooms)
                ),
            )
        document_id, revision_id, source_sha256, snapshot_id = next(iter(lineage))
        published = self._source.published_snapshot_for_revision(revision_id)
        if (
            published is None
            or published.revision.document_id != document_id
            or published.revision.revision_id != revision_id
            or published.revision.source_sha256.lower() != source_sha256
        ):
            return CrossViewCeilingFinishResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT,),
                records=(),
                unresolved_physical_room_ids=tuple(
                    sorted(room.physical_room_id for room in eligible_rooms)
                ),
            )

        by_label: dict[str, list[LiveCanonicalRoomObject]] = {}
        for room in eligible_rooms:
            by_label.setdefault(_norm(room.room_label), []).append(room)
        unique_rooms = {
            label: rows[0]
            for label, rows in by_label.items()
            if label and len(rows) == 1
        }
        duplicate_room_ids = {
            room.physical_room_id
            for rows in by_label.values()
            if len(rows) != 1
            for room in rows
        }

        rcp_viewports = _rcp_viewports(self._source, revision_id=revision_id)
        if not rcp_viewports:
            return CrossViewCeilingFinishResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(CROSS_VIEW_CEILING_FINISH_RCP_UNAVAILABLE,),
                records=(),
                unresolved_physical_room_ids=tuple(
                    sorted(room.physical_room_id for room in eligible_rooms)
                ),
            )
        page_ids = tuple(sorted({page_id for page_id, _ in rcp_viewports}))
        trusted_lines = _trusted_room_labels_for_pages(
            self._source,
            revision_id=revision_id,
            page_ids=page_ids,
            candidate_labels=tuple(unique_rooms),
        )

        material_producer = (
            SourceMaterialSemanticProducer.from_source_visibility_producer(
                self._source
            )
        )
        material_authority = material_producer.publish(revision_id)
        occurrence_results: tuple[SourceMaterialOccurrenceScopeResult, ...] = (
            material_producer.published_occurrence_results()
        )

        room_label_lines: dict[
            tuple[str, str],
            list[tuple[_TrustedLine, str]],
        ] = {}
        for (page_id, viewport_id), viewport_bbox in rcp_viewports.items():
            for line in trusted_lines.get(page_id, ()):
                label = _norm(line.text)
                if (
                    label not in unique_rooms
                    or not _bbox_fully_inside(line.bbox, viewport_bbox)
                ):
                    continue
                room_label_lines.setdefault((page_id, viewport_id), []).append(
                    (line, label)
                )

        candidates_by_room: dict[
            str,
            list[
                tuple[
                    SourceMaterialOccurrenceRecord,
                    SourceMaterialDefinitionRecord,
                    _TrustedLine,
                    _TrustedLine,
                ]
            ],
        ] = {}
        conflict = bool(duplicate_room_ids)

        for result in occurrence_results:
            if (
                result.status is not EvidenceResolutionStatus.CORROBORATED
                or not result.scope_complete
            ):
                continue
            for occurrence in result.records:
                key = (_clean(occurrence.page_id), _clean(occurrence.viewport_id))
                viewport_bbox = rcp_viewports.get(key)
                if viewport_bbox is None:
                    continue
                definition_result = material_authority.resolve_definition(
                    SourceMaterialDefinitionSelector(
                        document_id=occurrence.document_id,
                        revision_id=occurrence.revision_id,
                        source_sha256=occurrence.source_sha256,
                        snapshot_id=occurrence.snapshot_id,
                        code=occurrence.code,
                    )
                )
                definition = definition_result.record
                if (
                    definition_result.status
                    is not EvidenceResolutionStatus.CORROBORATED
                    or definition is None
                    or occurrence.snapshot_id != published.snapshot.snapshot_id
                    or definition.snapshot_id != published.snapshot.snapshot_id
                    or definition.record_id != occurrence.definition_record_id
                    or definition.semantic_finish != occurrence.semantic_finish
                    or not _definition_is_ceiling_finish(definition)
                    or not _bbox_fully_inside(
                        occurrence.bbox_pdf_pts,
                        viewport_bbox,
                    )
                ):
                    continue

                occurrence_line = _occurrence_line(
                    self._source,
                    revision_id=revision_id,
                    occurrence=occurrence,
                )
                if occurrence_line is None:
                    continue

                same_block_labels = [
                    (line, label)
                    for line, label in room_label_lines.get(key, ())
                    if (
                        line.source_partition_id
                        == occurrence_line.source_partition_id
                        and line.block_no == occurrence_line.block_no
                    )
                ]
                labels = {label for _line, label in same_block_labels}
                if len(labels) != 1:
                    if len(labels) > 1:
                        conflict = True
                    continue
                label = next(iter(labels))
                matching_label_lines = [
                    line for line, candidate_label in same_block_labels
                    if candidate_label == label
                ]
                if len(matching_label_lines) != 1:
                    conflict = True
                    continue
                room = unique_rooms[label]
                candidates_by_room.setdefault(room.physical_room_id, []).append(
                    (
                        occurrence,
                        definition,
                        occurrence_line,
                        matching_label_lines[0],
                    )
                )

        records: list[CrossViewCeilingFinishRecord] = []
        unresolved = {
            room.physical_room_id for room in eligible_rooms
        }
        for label, room in sorted(
            unique_rooms.items(),
            key=lambda item: item[1].physical_room_id,
        ):
            candidates = candidates_by_room.get(room.physical_room_id, ())
            if len(candidates) != 1:
                if len(candidates) > 1:
                    conflict = True
                continue
            occurrence, definition, occurrence_line, label_line = candidates[0]
            payload = {
                "physical_room_id": room.physical_room_id,
                "canonical_room_id": room.canonical_room_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "support_page_id": occurrence.page_id,
                "support_viewport_id": occurrence.viewport_id,
                "support_source_partition_id": occurrence_line.source_partition_id,
                "support_block_no": occurrence_line.block_no,
                "room_label": room.room_label,
                "finish_occurrence_record_id": occurrence.record_id,
                "finish_definition_record_id": definition.record_id,
            }
            records.append(
                CrossViewCeilingFinishRecord(
                    record_id=stable_contract_id(
                        "cross_view_ceiling_finish",
                        payload,
                        digest_chars=32,
                    ),
                    physical_room_id=room.physical_room_id,
                    canonical_room_id=room.canonical_room_id,
                    source_room_face_record_id=room.source_room_face_record_id,
                    room_label=_clean(room.room_label),
                    support_page_id=_clean(occurrence.page_id),
                    support_viewport_id=_clean(occurrence.viewport_id),
                    support_source_partition_id=occurrence_line.source_partition_id,
                    support_block_no=occurrence_line.block_no,
                    room_label_observation_ids=label_line.observation_ids,
                    room_label_receipt_ids=label_line.receipt_ids,
                    finish_code=occurrence.code,
                    semantic_finish=occurrence.semantic_finish,
                    definition_record_id=definition.record_id,
                    definition_evidence_ids=definition.source_definition_ids,
                    occurrence_record_id=occurrence.record_id,
                    occurrence_evidence_id=occurrence.source_evidence_id,
                    occurrence_observation_ids=occurrence_line.observation_ids,
                    occurrence_receipt_ids=occurrence_line.receipt_ids,
                    occurrence_bbox_pdf_pts=occurrence.bbox_pdf_pts,
                    support_snapshot_id=published.snapshot.snapshot_id,
                    _seal=_RECORD_SEAL,
                )
            )
            unresolved.discard(room.physical_room_id)

        records.sort(key=lambda record: record.physical_room_id)
        unresolved_ids = tuple(sorted(unresolved))
        if records and not unresolved_ids and not conflict:
            status = EvidenceResolutionStatus.CORROBORATED
            reasons = (CROSS_VIEW_CEILING_FINISH_RESOLVED,)
        elif records:
            status = EvidenceResolutionStatus.CANDIDATE
            reasons = (CROSS_VIEW_CEILING_FINISH_PARTIAL,)
        elif conflict:
            status = EvidenceResolutionStatus.CONFLICT
            reasons = (CROSS_VIEW_CEILING_FINISH_CONFLICT,)
        else:
            status = EvidenceResolutionStatus.ABSTAINED
            reasons = (CROSS_VIEW_CEILING_FINISH_NATIVE_BLOCK_UNAVAILABLE,)

        return CrossViewCeilingFinishResult(
            status=status,
            reason_codes=reasons,
            records=tuple(records),
            unresolved_physical_room_ids=unresolved_ids,
        )


__all__ = [
    "CROSS_VIEW_CEILING_FINISH_CONFLICT",
    "CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT",
    "CROSS_VIEW_CEILING_FINISH_NATIVE_BLOCK_UNAVAILABLE",
    "CROSS_VIEW_CEILING_FINISH_PARTIAL",
    "CROSS_VIEW_CEILING_FINISH_RCP_UNAVAILABLE",
    "CROSS_VIEW_CEILING_FINISH_RESOLVED",
    "CROSS_VIEW_CEILING_FINISH_SCHEMA_VERSION",
    "CROSS_VIEW_CEILING_FINISH_UNAVAILABLE",
    "CrossViewCeilingFinishProducer",
    "CrossViewCeilingFinishRecord",
    "CrossViewCeilingFinishResult",
]
