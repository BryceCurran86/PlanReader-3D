"""Source-owned cross-view room-area authority.

This authority composes only already-authenticated evidence:
- a canonical physical room with an authenticated source room label;
- the exact same independently trusted native label line on another decoded view;
- one native-text-authenticated horizontal and one vertical dimension, each
  already sealed to a unique dimension line with witness geometry by
  RasterPlanDimensionProducer.

It never accepts caller-supplied room names, page numbers, dimensions, geometry,
expected quantities or benchmark identities. Scale status is deliberately not an
input: authenticated figured dimensions remain valid when page scale is absent
or conflicting.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_figured_dimension_authority import (
    DimensionParseError,
    parse_figured_dimension_mm,
)
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import (
    EvidenceAtom,
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_portable_raster_ocr_authority import MockOCRBackend
from pb_raster_plan_dimension_authority import (
    BoundRasterDimension,
    RasterPlanDimensionProducer,
    RasterPlanDimensionResult,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION = "1.0.0"
CROSS_VIEW_ROOM_AREA_RESOLVED = "cross_view_room_area_resolved"
CROSS_VIEW_ROOM_AREA_PARTIAL = "cross_view_room_area_partial"
CROSS_VIEW_ROOM_AREA_UNAVAILABLE = "cross_view_room_area_unavailable"
CROSS_VIEW_ROOM_AREA_CONFLICT = "cross_view_room_area_conflict"
CROSS_VIEW_ROOM_AREA_LABEL_UNAVAILABLE = "cross_view_room_area_label_unavailable"
CROSS_VIEW_ROOM_AREA_DIMENSIONS_UNAVAILABLE = (
    "cross_view_room_area_dimensions_unavailable"
)
CROSS_VIEW_ROOM_AREA_LINEAGE_CONFLICT = "cross_view_room_area_lineage_conflict"
CROSS_VIEW_ROOM_AREA_EVIDENCE_RESOLVED = (
    "authenticated_cross_view_room_area"
)

_PRODUCER_SEAL = object()
_RECORD_SEAL = object()


def _norm_label(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _finite_bbox(value: Sequence[object]) -> Optional[tuple[float, float, float, float]]:
    if len(value) < 4:
        return None
    try:
        out = tuple(float(value[index]) for index in range(4))
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(item) for item in out):
        return None
    if out[2] <= out[0] or out[3] <= out[1]:
        return None
    return out


@dataclass(frozen=True)
class _TrustedLine:
    page_id: str
    text: str
    bbox: tuple[float, float, float, float]
    observation_ids: tuple[str, ...]
    receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class CrossViewRoomAreaRecord:
    physical_room_id: str
    source_room_face_record_id: str
    room_label: str
    source_dimension_page_id: str
    source_label_observation_ids: tuple[str, ...]
    source_label_receipt_ids: tuple[str, ...]
    horizontal_dimension_id: str
    vertical_dimension_id: str
    area_evidence: EvidenceAtom
    schema_version: str = CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("CrossViewRoomAreaRecord is producer-owned")


@dataclass(frozen=True)
class CrossViewRoomAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[CrossViewRoomAreaRecord, ...]
    unresolved_physical_room_ids: tuple[str, ...]
    schema_version: str = CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION

    @property
    def evidence_by_physical_room_id(self) -> Mapping[str, EvidenceAtom]:
        return MappingProxyType(
            {
                record.physical_room_id: record.area_evidence
                for record in self.records
            }
        )

    @property
    def evidence_by_source_room_face_record_id(self) -> Mapping[str, EvidenceAtom]:
        return MappingProxyType(
            {
                record.source_room_face_record_id: record.area_evidence
                for record in self.records
            }
        )


def _trusted_lines_for_page(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
    page_id: str,
) -> tuple[_TrustedLine, ...]:
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        return ()
    text_authority = source.text_integrity_authority()
    grouped: dict[tuple[str, int, int], list[tuple[object, object]]] = {}

    for observation_id in published.text_observation_ids:
        result = text_authority.resolve_text(
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
            or str(receipt.page_id) != str(page_id)
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        grouped.setdefault(
            (
                str(receipt.source_partition_id),
                int(receipt.block_no),
                int(receipt.line_no),
            ),
            [],
        ).append((result, receipt))

    lines: list[_TrustedLine] = []
    for key in sorted(grouped):
        items = grouped[key]
        if any(
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or not result.trusted_text
            for result, _receipt in items
        ):
            continue
        word_nos = [int(receipt.word_no) for _result, receipt in items]
        if len(set(word_nos)) != len(word_nos):
            continue
        lo, hi = min(word_nos), max(word_nos)
        if set(word_nos) != set(range(lo, hi + 1)):
            continue
        ordered = sorted(items, key=lambda item: int(item[1].word_no))
        boxes = [_finite_bbox(item[1].geometry) for item in ordered]
        if any(box is None for box in boxes):
            continue
        concrete_boxes = tuple(box for box in boxes if box is not None)
        line_text = " ".join(str(item[0].trusted_text).strip() for item in ordered)
        if not _norm_label(line_text):
            continue
        lines.append(
            _TrustedLine(
                page_id=str(page_id),
                text=line_text,
                bbox=(
                    min(box[0] for box in concrete_boxes),
                    min(box[1] for box in concrete_boxes),
                    max(box[2] for box in concrete_boxes),
                    max(box[3] for box in concrete_boxes),
                ),
                observation_ids=tuple(str(item[1].parent_observation_id) for item in ordered),
                receipt_ids=tuple(str(item[1].receipt_id) for item in ordered),
            )
        )
    return tuple(lines)


def _native_trusted_dimension(
    source: SourceVisibilityProducer,
    result: RasterPlanDimensionResult,
    dimension: BoundRasterDimension,
) -> bool:
    if (
        not result.document_id
        or not result.revision_id
        or not result.source_sha256
        or not result.snapshot_id
        or not result.page_id
        or dimension.orientation
        not in {
            DimensionOrientation.HORIZONTAL.value,
            DimensionOrientation.VERTICAL.value,
        }
        or not dimension.dimension_line_observation_ids
        or not dimension.witness_observation_ids
        or len(dimension.endpoints_pt) != 2
    ):
        return False
    resolved = source.text_integrity_authority().resolve_text(
        ObservationSelector(
            document_id=str(result.document_id),
            revision_id=str(result.revision_id),
            source_sha256=str(result.source_sha256),
            snapshot_id=str(result.snapshot_id),
            observation_id=str(dimension.text_observation_id),
        )
    )
    if (
        resolved.status is not EvidenceResolutionStatus.CORROBORATED
        or not resolved.trusted_text
        or resolved.receipt is None
        or str(resolved.receipt.page_id) != str(result.page_id)
    ):
        return False
    try:
        parsed_mm = parse_figured_dimension_mm(str(resolved.trusted_text))
    except DimensionParseError:
        return False
    if abs(float(parsed_mm) - float(dimension.value_mm)) > 1e-6:
        return False
    return all(
        math.isfinite(float(value))
        for endpoint in dimension.endpoints_pt
        for value in endpoint
    )


def _line_inside_dimension_pair(
    line: _TrustedLine,
    horizontal: BoundRasterDimension,
    vertical: BoundRasterDimension,
) -> bool:
    hx = sorted(
        (
            float(horizontal.endpoints_pt[0][0]),
            float(horizontal.endpoints_pt[1][0]),
        )
    )
    vy = sorted(
        (
            float(vertical.endpoints_pt[0][1]),
            float(vertical.endpoints_pt[1][1]),
        )
    )
    x0, y0, x1, y1 = line.bbox
    eps = 1e-6
    return (
        hx[0] - eps <= x0 <= x1 <= hx[1] + eps
        and vy[0] - eps <= y0 <= y1 <= vy[1] + eps
    )


class CrossViewRoomAreaProducer:
    def __init__(
        self,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
        dimension_producer: RasterPlanDimensionProducer,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("CrossViewRoomAreaProducer must be obtained from a classmethod")
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be exact SourceVisibilityProducer")
        if type(rooms) is not LiveCanonicalRoomComposition:
            raise TypeError("rooms must be exact LiveCanonicalRoomComposition")
        if type(dimension_producer) is not RasterPlanDimensionProducer:
            raise TypeError("dimension_producer must be producer-owned")
        self._source = source
        self._rooms = rooms
        self._dimensions = dimension_producer

    @classmethod
    def from_source(
        cls,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
    ) -> "CrossViewRoomAreaProducer":
        return cls(
            source=source,
            rooms=rooms,
            dimension_producer=RasterPlanDimensionProducer.create(
                source_visibility=source
            ),
            _seal=_PRODUCER_SEAL,
        )

    @classmethod
    def from_source_for_tests(
        cls,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
        backend: MockOCRBackend,
    ) -> "CrossViewRoomAreaProducer":
        if type(backend) is not MockOCRBackend:
            raise TypeError("tests require exact MockOCRBackend")
        return cls(
            source=source,
            rooms=rooms,
            dimension_producer=RasterPlanDimensionProducer.create_for_tests(
                source_visibility=source,
                backend=backend,
            ),
            _seal=_PRODUCER_SEAL,
        )

    def publish(self) -> CrossViewRoomAreaResult:
        rooms = tuple(self._rooms.rooms)
        if not rooms:
            return CrossViewRoomAreaResult(
                EvidenceResolutionStatus.ABSTAINED,
                (CROSS_VIEW_ROOM_AREA_UNAVAILABLE,),
                (),
                (),
            )

        revision_ids = {str(room.revision_id) for room in rooms}
        document_ids = {str(room.document_id) for room in rooms}
        source_hashes = {str(room.source_sha256).lower() for room in rooms}
        if (
            len(revision_ids) != 1
            or len(document_ids) != 1
            or len(source_hashes) != 1
        ):
            return CrossViewRoomAreaResult(
                EvidenceResolutionStatus.CONFLICT,
                (CROSS_VIEW_ROOM_AREA_LINEAGE_CONFLICT,),
                (),
                tuple(sorted(str(room.physical_room_id) for room in rooms)),
            )
        revision_id = next(iter(revision_ids))
        published = self._source.published_snapshot_for_revision(revision_id)
        if (
            published is None
            or published.revision.document_id != next(iter(document_ids))
            or published.revision.source_sha256.lower() != next(iter(source_hashes))
        ):
            return CrossViewRoomAreaResult(
                EvidenceResolutionStatus.CONFLICT,
                (CROSS_VIEW_ROOM_AREA_LINEAGE_CONFLICT,),
                (),
                tuple(sorted(str(room.physical_room_id) for room in rooms)),
            )

        eligible: list[LiveCanonicalRoomObject] = [
            room
            for room in rooms
            if room.geometry_complete
            and str(room.physical_room_id or "").strip()
            and str(room.source_room_face_record_id or "").strip()
            and _norm_label(room.room_label)
            and str(room.room_label_binding_record_id or "").strip()
            and bool(room.room_label_evidence_ids)
        ]
        labels: dict[str, list[LiveCanonicalRoomObject]] = {}
        for room in eligible:
            labels.setdefault(_norm_label(room.room_label), []).append(room)

        duplicate_room_ids = {
            room.physical_room_id
            for group in labels.values()
            if len(group) != 1
            for room in group
        }

        page_results: dict[str, RasterPlanDimensionResult] = {}
        page_lines: dict[str, tuple[_TrustedLine, ...]] = {}
        for page_index in tuple(published.coverage.decoded_pages):
            page_id = str(int(page_index) + 1)
            dimension_result = self._dimensions.publish(
                revision_id=revision_id,
                page_id=page_id,
            )
            page_results[page_id] = dimension_result
            page_lines[page_id] = _trusted_lines_for_page(
                self._source,
                revision_id=revision_id,
                page_id=page_id,
            )

        records: list[CrossViewRoomAreaRecord] = []
        unresolved: set[str] = {
            str(room.physical_room_id)
            for room in rooms
            if room not in eligible
        }
        unresolved.update(str(value) for value in duplicate_room_ids)
        conflict_seen = bool(duplicate_room_ids)

        for label, grouped_rooms in sorted(labels.items()):
            if len(grouped_rooms) != 1:
                continue
            room = grouped_rooms[0]
            matches: list[
                tuple[
                    _TrustedLine,
                    RasterPlanDimensionResult,
                    BoundRasterDimension,
                    BoundRasterDimension,
                ]
            ] = []
            for page_id, trusted_lines in sorted(page_lines.items()):
                dimension_result = page_results[page_id]
                trusted_dimensions = tuple(
                    dimension
                    for dimension in dimension_result.bound_dimensions
                    if _native_trusted_dimension(
                        self._source,
                        dimension_result,
                        dimension,
                    )
                )
                horizontals = tuple(
                    item
                    for item in trusted_dimensions
                    if item.orientation == DimensionOrientation.HORIZONTAL.value
                )
                verticals = tuple(
                    item
                    for item in trusted_dimensions
                    if item.orientation == DimensionOrientation.VERTICAL.value
                )
                if not horizontals or not verticals:
                    continue
                for line in trusted_lines:
                    if _norm_label(line.text) != label:
                        continue
                    for horizontal in horizontals:
                        for vertical in verticals:
                            if _line_inside_dimension_pair(
                                line,
                                horizontal,
                                vertical,
                            ):
                                matches.append(
                                    (
                                        line,
                                        dimension_result,
                                        horizontal,
                                        vertical,
                                    )
                                )

            if len(matches) != 1:
                unresolved.add(str(room.physical_room_id))
                if len(matches) > 1:
                    conflict_seen = True
                continue

            line, dimension_result, horizontal, vertical = matches[0]
            area_m2 = round(
                float(horizontal.value_mm)
                * float(vertical.value_mm)
                / 1_000_000.0,
                6,
            )
            if not math.isfinite(area_m2) or area_m2 <= 0.0:
                unresolved.add(str(room.physical_room_id))
                continue
            evidence_id = stable_contract_id(
                "cross_view_room_area",
                {
                    "document_id": room.document_id,
                    "physical_room_id": room.physical_room_id,
                    "source_room_face_record_id": room.source_room_face_record_id,
                    "dimension_page_id": dimension_result.page_id,
                    "label_receipt_ids": line.receipt_ids,
                    "horizontal_dimension_id": horizontal.dimension_id,
                    "vertical_dimension_id": vertical.dimension_id,
                    "area_m2": area_m2,
                },
                digest_chars=32,
            )
            area_evidence = EvidenceAtom(
                evidence_id=evidence_id,
                document_id=str(room.document_id),
                page_id=str(room.page_id),
                viewport_id=room.viewport_id,
                kind="explicit_room_area",
                method="authenticated_cross_view_figured_dimensions",
                normalized_value=area_m2,
                unit="m2",
                confidence=1.0,
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(CROSS_VIEW_ROOM_AREA_EVIDENCE_RESOLVED,),
                metadata={
                    "physical_room_id": str(room.physical_room_id),
                    "source_room_face_record_id": str(
                        room.source_room_face_record_id
                    ),
                    "room_label_binding_record_id": str(
                        room.room_label_binding_record_id
                    ),
                    "room_label_evidence_ids": list(room.room_label_evidence_ids),
                    "source_dimension_page_id": str(dimension_result.page_id),
                    "source_dimension_snapshot_id": str(
                        dimension_result.snapshot_id or ""
                    ),
                    "source_label_text": line.text,
                    "source_label_observation_ids": list(line.observation_ids),
                    "source_label_receipt_ids": list(line.receipt_ids),
                    "horizontal_dimension_id": horizontal.dimension_id,
                    "horizontal_text_observation_id": (
                        horizontal.text_observation_id
                    ),
                    "horizontal_value_mm": int(horizontal.value_mm),
                    "horizontal_dimension_line_observation_ids": list(
                        horizontal.dimension_line_observation_ids
                    ),
                    "horizontal_witness_observation_ids": list(
                        horizontal.witness_observation_ids
                    ),
                    "vertical_dimension_id": vertical.dimension_id,
                    "vertical_text_observation_id": vertical.text_observation_id,
                    "vertical_value_mm": int(vertical.value_mm),
                    "vertical_dimension_line_observation_ids": list(
                        vertical.dimension_line_observation_ids
                    ),
                    "vertical_witness_observation_ids": list(
                        vertical.witness_observation_ids
                    ),
                    "room_revision_id": str(room.revision_id),
                    "room_snapshot_id": str(room.snapshot_id),
                    "source_sha256": str(room.source_sha256),
                },
            )
            records.append(
                CrossViewRoomAreaRecord(
                    physical_room_id=str(room.physical_room_id),
                    source_room_face_record_id=str(
                        room.source_room_face_record_id
                    ),
                    room_label=str(room.room_label),
                    source_dimension_page_id=str(dimension_result.page_id),
                    source_label_observation_ids=line.observation_ids,
                    source_label_receipt_ids=line.receipt_ids,
                    horizontal_dimension_id=horizontal.dimension_id,
                    vertical_dimension_id=vertical.dimension_id,
                    area_evidence=area_evidence,
                    _seal=_RECORD_SEAL,
                )
            )

        records.sort(key=lambda item: item.physical_room_id)
        unresolved_ids = tuple(sorted(unresolved))
        if records and not unresolved_ids:
            status = EvidenceResolutionStatus.CORROBORATED
            reasons = (CROSS_VIEW_ROOM_AREA_RESOLVED,)
        elif records:
            status = EvidenceResolutionStatus.CANDIDATE
            reasons = (CROSS_VIEW_ROOM_AREA_PARTIAL,)
        elif conflict_seen:
            status = EvidenceResolutionStatus.CONFLICT
            reasons = (CROSS_VIEW_ROOM_AREA_CONFLICT,)
        else:
            status = EvidenceResolutionStatus.ABSTAINED
            reasons = (
                CROSS_VIEW_ROOM_AREA_LABEL_UNAVAILABLE,
                CROSS_VIEW_ROOM_AREA_DIMENSIONS_UNAVAILABLE,
            )
        return CrossViewRoomAreaResult(
            status=status,
            reason_codes=reasons,
            records=tuple(records),
            unresolved_physical_room_ids=unresolved_ids,
        )


__all__ = [
    "CROSS_VIEW_ROOM_AREA_CONFLICT",
    "CROSS_VIEW_ROOM_AREA_DIMENSIONS_UNAVAILABLE",
    "CROSS_VIEW_ROOM_AREA_EVIDENCE_RESOLVED",
    "CROSS_VIEW_ROOM_AREA_LABEL_UNAVAILABLE",
    "CROSS_VIEW_ROOM_AREA_LINEAGE_CONFLICT",
    "CROSS_VIEW_ROOM_AREA_PARTIAL",
    "CROSS_VIEW_ROOM_AREA_RESOLVED",
    "CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION",
    "CROSS_VIEW_ROOM_AREA_UNAVAILABLE",
    "CrossViewRoomAreaProducer",
    "CrossViewRoomAreaRecord",
    "CrossViewRoomAreaResult",
]
