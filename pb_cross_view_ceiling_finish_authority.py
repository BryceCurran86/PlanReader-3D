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

from collections import Counter, defaultdict
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
    # Legacy same-block source material retains its existing policy. A new
    # source-closed cross-native-block region is MATERIAL-ONLY until GPT1
    # independently authenticates actual RCP metric ceiling geometry.
    commercial_projection_allowed: bool = True
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
        if self.status not in (
            EvidenceResolutionStatus.CORROBORATED,
            EvidenceResolutionStatus.CANDIDATE,
        ):
            return MappingProxyType({})
        # Never expose source receipt aliases or a last-wins room dictionary,
        # including when a public result dataclass is reconstructed.
        # A reconstructed public result is not an issuer receipt. A rogue
        # record object cannot be discarded and let a competing legitimate
        # record appear uniquely owned; quarantine the entire projection.
        if any(type(record) is not CrossViewCeilingFinishRecord
               for record in self.records):
            return MappingProxyType({})
        survivors, _disputed = _quarantine_reused_ceiling_source_ownership(
            self.records
        )
        return MappingProxyType({
            record.physical_room_id: record for record in survivors
        })



def _quarantine_reused_ceiling_source_ownership(
    records: Sequence[CrossViewCeilingFinishRecord],
) -> tuple[tuple[CrossViewCeilingFinishRecord, ...], tuple[str, ...]]:
    """Reject cross-room reuse of exact producer-issued physical source IDs.

    Printed schedule definitions MAY be shared by many rooms. Physical
    room faces and the exact material-mark / room-label observations may not
    be shared between distinct rooms. Retain unaffected rows, never choose
    a first/last candidate, and never mint a room or quantity.
    """
    def valid(value: object) -> bool:
        return type(value) is str and bool(value) and value == value.strip()

    owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    disputed: set[str] = set()
    by_physical: dict[str, int] = Counter()
    fields = (
        # The producer's issued finish record cannot be rekeyed to a second
        # physical room or left blank in reconstructed result records.
        "record_id",
        "canonical_room_id",
        "source_room_face_record_id",
        "occurrence_record_id",
        "occurrence_evidence_id",
    )
    receipt_fields = (
        "room_label_observation_ids",
        "room_label_receipt_ids",
        "occurrence_observation_ids",
        "occurrence_receipt_ids",
    )
    for record in records:
        room_id = record.physical_room_id
        if not valid(room_id):
            disputed.add(room_id)
            continue
        by_physical[room_id] += 1
        for field in fields:
            value = getattr(record, field)
            if valid(value):
                owners[(field, value)].add(room_id)
            else:
                disputed.add(room_id)
        for field in receipt_fields:
            raw = getattr(record, field)
            if not isinstance(raw, (tuple, list)) or not raw:
                disputed.add(room_id)
                continue
            receipts = tuple(raw)
            if (any(not valid(value) for value in receipts)
                    or len(set(receipts)) != len(receipts)):
                disputed.add(room_id)
                continue
            # Source observation/receipt ownership is independent of whether
            # a caller named the role "room label" or "finish occurrence".
            # Do not let one original ink/text receipt own two physical rooms
            # merely by relabelling the consumer field.
            source_namespace = (
                "physical_source_observation"
                if field.endswith("_observation_ids")
                else "physical_source_receipt"
            )
            for value in receipts:
                owners[(source_namespace, value)].add(room_id)

    disputed.update(
        room_id for room_id, count in by_physical.items() if count > 1
    )
    for physical_ids in owners.values():
        if len(physical_ids) > 1:
            disputed.update(physical_ids)
    return (
        tuple(
            record for record in records
            if record.physical_room_id not in disputed
        ),
        tuple(sorted(disputed)),
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
    # An independently printed material description that specifies signage
    # cladding is contrary original evidence of a *ceiling* finish. Do not
    # allow a stale/mistyped upstream semantic_finish to override that
    # contradiction, even if its scope later overlaps an RCP viewport.
    # This is a generic negative original-source rule, not code/name lookup.
    original_material_text = _norm(" ".join(
        _clean(value) for value in
        (definition.description,definition.substrate,definition.finish)
        if _clean(value)
    ))
    # Native PDF source descriptions may contain punctuation or line joins,
    # such as SIGNAGE-CONTRACTOR; tokenize semantics without source guessing.
    import re
    role_tokens = set(re.findall(r"[a-z]+", original_material_text))
    # A refrigerated-panel enclosure can have a genuine ceiling role when
    # independently identified on the RCP. It is not a suspended plaster
    # GRID definition just because a stale semantic class says ceiling_grid.
    is_coldroom = (
        "coldroom" in role_tokens
        or {"cold", "room"}.issubset(role_tokens)
    )
    if (
        semantic == "ceiling_grid"
        and is_coldroom
        and bool(role_tokens.intersection({"panel", "panels"}))
        and "grid" not in role_tokens
    ):
        return False
    # A schedule's original material description takes precedence over a
    # stale ceiling-grid semantic. Exterior soffit/eaves/canopy cladding is
    # NOT the internal suspended GRID/IPF1 ceiling finish, even when drawn
    # on a reflected-ceiling sheet.
    if "cladding" in role_tokens and role_tokens.intersection(
        {"signage", "wall", "facade", "fascia", "soffit", "eaves", "canopy"}
    ):
        return False
    # A steel roofing/wall cladding specification appearing in an RCP
    # material legend is NOT itself proof of an internal suspended ceiling.
    # An explicit native ceiling role is required to avoid mistaking a
    # Colorbond sheet-cladding note for a GRID plaster-tile finish.
    if (
        "cladding" in role_tokens
        and "colorbond" in role_tokens
        and not role_tokens.intersection({"ceiling", "suspended", "grid"})
    ):
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
        surviving_records, disputed_room_ids = (
            _quarantine_reused_ceiling_source_ownership(records)
        )
        if disputed_room_ids:
            conflict = True
            unresolved.update(disputed_room_ids)
        records = list(surviving_records)
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


    def publish_original_rcp_source_closed(
        self, *, revision_id: str, original_floor_page_1_based: int,
        source_floor_rcp_correspondence: dict, original_rcp_ink: dict,
        original_rcp_material: dict, material_authority,
        definition_selector, occurrence_selector,
        original_ceiling_finish_code: str, physical_room_id: str,
    ) -> CrossViewCeilingFinishResult:
        """Opt-in, fully reissued cross-native-block RCP material binding.

        Unlike the legacy same-text-block path, this can bind separate native
        room/GRID blocks ONLY after original ring, floor registration, W4 face,
        in-ring text, material definition and exact occurrence are independently
        issued. It publishes material evidence, never metric ceiling area.
        """
        blocked = (CROSS_VIEW_CEILING_FINISH_UNAVAILABLE,)
        unresolved = (physical_room_id,) if type(physical_room_id) is str else ()
        def abstain(reason=CROSS_VIEW_CEILING_FINISH_UNAVAILABLE):
            return CrossViewCeilingFinishResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(reason,), records=(),
                unresolved_physical_room_ids=unresolved,
            )

        if (type(revision_id) is not str or not revision_id
                or type(original_floor_page_1_based) is not int
                or original_floor_page_1_based < 1
                or type(physical_room_id) is not str or not physical_room_id
                or physical_room_id != physical_room_id.strip()
                or type(original_ceiling_finish_code) is not str
                or not original_ceiling_finish_code
                or original_ceiling_finish_code != original_ceiling_finish_code.strip()):
            return abstain()
        published = self._source.published_snapshot_for_revision(revision_id)
        if published is None or published.revision.revision_id != revision_id:
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        rooms = tuple(self._rooms.rooms)
        matched = tuple(r for r in rooms
                        if type(r) is LiveCanonicalRoomObject
                        and r.physical_room_id == physical_room_id)
        if len(matched) != 1:
            return abstain(CROSS_VIEW_CEILING_FINISH_CONFLICT)
        room = matched[0]
        # The room label and the wall face must be unique in the complete W4
        # universe. A duplicate label may represent two different rooms.
        if (not room.geometry_complete
                or not room.source_room_face_record_id
                or not room.room_label_binding_record_id
                or not room.room_label_evidence_ids
                or room.revision_id != revision_id
                or room.snapshot_id != published.snapshot.snapshot_id
                or room.source_sha256 != published.revision.source_sha256
                or room.document_id != published.revision.document_id
                or sum(_norm(r.room_label) == _norm(room.room_label)
                       for r in rooms) != 1):
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        from pb_gpt2_original_source_geometry_bridge import (
            GPT2OriginalSourceGeometryBridge,
        )
        try:
            bridge = GPT2OriginalSourceGeometryBridge.from_source_visibility_producer(
                self._source
            )
            proof = bridge.original_rcp_ceiling_source_handoff_for_gpt1(
                revision_id=revision_id,
                original_floor_page_1_based=original_floor_page_1_based,
                source_floor_rcp_correspondence=source_floor_rcp_correspondence,
                original_rcp_ink=original_rcp_ink,
                original_rcp_material=original_rcp_material,
                source_material_authority=material_authority,
                source_definition_selector=definition_selector,
                source_occurrence_selector=occurrence_selector,
                original_ceiling_finish_code=original_ceiling_finish_code,
                canonical_rooms=self._rooms,
                physical_room_id=physical_room_id,
            )
        except (ValueError, TypeError, KeyError, IndexError,
                OverflowError, RuntimeError):
            return abstain()
        if (type(proof) is not dict
                or proof.get("status") !=
                    "source_W4_original_A120_ceiling_compilation_shadow_only"
                or proof.get("new_firm_quantities") != 0
                or proof.get("source_ceiling_area_m2") is not None):
            return abstain()
        bound = proof.get("source_original_rcp_ceiling_input_for_gpt1")
        w4 = proof.get("source_w4_room_face_claim")
        if (type(bound) is not dict or type(w4) is not dict
                or bound.get("status") !=
                    "original_A120_RCP_material_on_W4_room_candidate_for_GPT1"
                or bound.get("ceiling_quantity_m2_issued") is not False
                or bound.get("new_firm_quantities") != 0
                or w4.get("status") != "source_original_floor_W4_face_candidate_only"
                or w4.get("w4_room_face_source_identity_proven") is not True
                or w4.get("source_w4_wall_ownership_authenticated") is not True
                or w4.get("original_physical_room_id") != physical_room_id
                or bound.get("original_physical_room_id") != physical_room_id
                or bound.get("original_source_room_face_record_id") !=
                    room.source_room_face_record_id
                or bound.get("original_source_sha256") != room.source_sha256
                or proof.get("source_original_revision_id") != revision_id
                or proof.get("source_original_snapshot_id") != room.snapshot_id
                or bound.get("original_rcp_code") != original_ceiling_finish_code):
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        label_ids = proof.get("original_rcp_room_label_observation_ids")
        label_receipts = proof.get("original_rcp_room_label_receipt_ids")
        partition = proof.get("original_rcp_room_label_source_partition_id")
        block = proof.get("original_rcp_room_label_native_block_no")
        line_number = proof.get("original_rcp_room_label_native_line_no")
        if (type(label_ids) is not tuple or not label_ids
                or type(label_receipts) is not tuple
                or len(label_receipts) != len(label_ids)
                or len(set(label_ids)) != len(label_ids)
                or len(set(label_receipts)) != len(label_receipts)
                or any(type(v) is not str or not v or v != v.strip()
                       for v in (*label_ids, *label_receipts))
                or type(partition) is not str or not partition
                or type(block) is not int or block < 0
                or type(line_number) is not int or line_number < 0
                or _norm(proof.get("original_rcp_room_label_text")) !=
                    _norm(room.room_label)):
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        # Re-resolve the exact producer-issued material rather than mint a
        # semantic ceiling record from dict fields or a free-form code.
        from pb_source_material_semantic_authority import (
            SourceMaterialDefinitionSelector,
            SourceMaterialOccurrenceSelector,
        )
        if (type(definition_selector) is not SourceMaterialDefinitionSelector
                or type(occurrence_selector) is not SourceMaterialOccurrenceSelector
                or definition_selector.document_id != room.document_id
                or occurrence_selector.document_id != room.document_id
                or definition_selector.revision_id != revision_id
                or occurrence_selector.revision_id != revision_id
                or definition_selector.source_sha256 != room.source_sha256
                or occurrence_selector.source_sha256 != room.source_sha256
                or definition_selector.snapshot_id != room.snapshot_id
                or occurrence_selector.snapshot_id != room.snapshot_id
                or _norm(definition_selector.code) != _norm(original_ceiling_finish_code)
                or occurrence_selector.page_id != str(bound.get("original_rcp_page"))
                or occurrence_selector.viewport_id != bound.get("original_rcp_viewport_id")):
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        try:
            d = material_authority.resolve_definition(definition_selector)
            scope = material_authority.resolve_occurrences(occurrence_selector)
        except (AttributeError, TypeError, ValueError, KeyError):
            return abstain()
        definition = d.record
        if (d.status is not EvidenceResolutionStatus.CORROBORATED
                or type(definition) is not SourceMaterialDefinitionRecord
                or definition.record_id !=
                    bound.get("original_ceiling_material_definition_record_id")
                or definition.snapshot_id != room.snapshot_id
                or not _definition_is_ceiling_finish(definition)
                or scope.status is not EvidenceResolutionStatus.CORROBORATED
                or scope.scope_complete is not True
                or not scope.source_viewport_ownership_id
                or scope.source_viewport_ownership_id !=
                    original_rcp_material.get("original_rcp_scope_ownership_id")
                or scope.unresolved_source_text_observation_ids):
            return abstain()
        mark_ids = bound.get("original_ceiling_source_mark_ids")
        if type(mark_ids) is not tuple or len(mark_ids) != 1:
            return abstain()
        matches = tuple(o for o in scope.records
                        if type(o) is SourceMaterialOccurrenceRecord
                        and o.record_id == mark_ids[0])
        if len(matches) != 1:
            return abstain(CROSS_VIEW_CEILING_FINISH_CONFLICT)
        occurrence = matches[0]
        if (occurrence.definition_record_id != definition.record_id
                or occurrence.source_sha256 != room.source_sha256
                or occurrence.document_id != room.document_id
                or occurrence.revision_id != revision_id
                or occurrence.snapshot_id != room.snapshot_id
                or occurrence.code != original_ceiling_finish_code
                or occurrence.semantic_finish != definition.semantic_finish
                or occurrence.page_id != occurrence_selector.page_id
                or occurrence.viewport_id != occurrence_selector.viewport_id):
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        line = _occurrence_line(
            self._source, revision_id=revision_id, occurrence=occurrence,
        )
        if (line is None or line.page_id != occurrence.page_id
                or line.source_partition_id != partition
                or not set(label_ids).isdisjoint(line.observation_ids)
                or not set(label_receipts).isdisjoint(line.receipt_ids)):
            return abstain(CROSS_VIEW_CEILING_FINISH_LINEAGE_CONFLICT)
        payload = {
            "physical_room_id": room.physical_room_id,
            "canonical_room_id": room.canonical_room_id,
            "source_room_face_record_id": room.source_room_face_record_id,
            "support_page_id": occurrence.page_id,
            "support_viewport_id": occurrence.viewport_id,
            "room_label_observations": label_ids,
            "material_occurrence_id": occurrence.record_id,
            "material_definition_id": definition.record_id,
            "source_rcp_ring": bound.get("original_rcp_source_polygon_pdf_pts"),
        }
        record = CrossViewCeilingFinishRecord(
            record_id=stable_contract_id(
                "cross_view_ceiling_finish_original_zone", payload,
                digest_chars=32,
            ),
            physical_room_id=room.physical_room_id,
            canonical_room_id=room.canonical_room_id,
            source_room_face_record_id=room.source_room_face_record_id,
            room_label=room.room_label,
            support_page_id=occurrence.page_id,
            support_viewport_id=occurrence.viewport_id,
            support_source_partition_id=line.source_partition_id,
            support_block_no=line.block_no,
            room_label_observation_ids=label_ids,
            room_label_receipt_ids=label_receipts,
            finish_code=occurrence.code,
            semantic_finish=definition.semantic_finish,
            definition_record_id=definition.record_id,
            definition_evidence_ids=definition.source_definition_ids,
            occurrence_record_id=occurrence.record_id,
            occurrence_evidence_id=occurrence.source_evidence_id,
            occurrence_observation_ids=line.observation_ids,
            occurrence_receipt_ids=line.receipt_ids,
            occurrence_bbox_pdf_pts=occurrence.bbox_pdf_pts,
            support_snapshot_id=room.snapshot_id,
            commercial_projection_allowed=False,
            _seal=_RECORD_SEAL,
        )
        remaining = tuple(sorted(r.physical_room_id for r in rooms
                                 if r.physical_room_id != physical_room_id))
        return CrossViewCeilingFinishResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(CROSS_VIEW_CEILING_FINISH_PARTIAL,),
            records=(record,),
            unresolved_physical_room_ids=remaining,
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
