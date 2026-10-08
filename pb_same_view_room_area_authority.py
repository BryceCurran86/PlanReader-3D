"""Source-owned same-view room-area authority.

This authority is intentionally separate from CrossViewRoomAreaProducer. It
uses only an already-authenticated canonical room label on the room's own source
page plus one uniquely witnessed horizontal/vertical figured-dimension pair on
that same page.

No scale is required. Authenticated figured dimensions are an independent
measurement authority. Ambiguous labels or dimension pairs remain fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from pb_cross_view_room_area_authority import (
    _dimension_is_immediate_label_annotation,
    _figured_pair_scale_consistent,
    _line_inside_dimension_pair,
    _norm_label,
    _trusted_lines_for_page,
    _trusted_native_dimensions_for_page,
    _witness_systems_intersect,
)
from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_drawing_evidence_binding import DrawingViewType
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import (
    EvidenceAtom,
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_source_visibility_authority import SourceVisibilityProducer


SAME_VIEW_ROOM_AREA_SCHEMA_VERSION = "1.0.0"
SAME_VIEW_ROOM_AREA_RESOLVED = "same_view_room_area_resolved"
SAME_VIEW_ROOM_AREA_PARTIAL = "same_view_room_area_partial"
SAME_VIEW_ROOM_AREA_UNAVAILABLE = "same_view_room_area_unavailable"
SAME_VIEW_ROOM_AREA_CONFLICT = "same_view_room_area_conflict"
SAME_VIEW_ROOM_AREA_LINEAGE_CONFLICT = "same_view_room_area_lineage_conflict"
SAME_VIEW_ROOM_AREA_EVIDENCE_RESOLVED = "authenticated_same_view_room_area"

_PRODUCER_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class SameViewRoomAreaRecord:
    physical_room_id: str
    source_room_face_record_id: str
    room_label: str
    source_dimension_page_id: str
    source_label_observation_ids: tuple[str, ...]
    source_label_receipt_ids: tuple[str, ...]
    horizontal_dimension_id: str
    vertical_dimension_id: str
    area_evidence: EvidenceAtom
    schema_version: str = SAME_VIEW_ROOM_AREA_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SameViewRoomAreaRecord is producer-owned")


@dataclass(frozen=True)
class SameViewRoomAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SameViewRoomAreaRecord, ...]
    unresolved_physical_room_ids: tuple[str, ...]
    schema_version: str = SAME_VIEW_ROOM_AREA_SCHEMA_VERSION

    @property
    def evidence_by_source_room_face_record_id(self) -> Mapping[str, EvidenceAtom]:
        return MappingProxyType(
            {
                record.source_room_face_record_id: record.area_evidence
                for record in self.records
            }
        )


class SameViewRoomAreaProducer:
    def __init__(
        self,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SameViewRoomAreaProducer must be obtained from a classmethod")
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be exact SourceVisibilityProducer")
        if type(rooms) is not LiveCanonicalRoomComposition:
            raise TypeError("rooms must be exact LiveCanonicalRoomComposition")
        self._source = source
        self._rooms = rooms

    @classmethod
    def from_source(
        cls,
        *,
        source: SourceVisibilityProducer,
        rooms: LiveCanonicalRoomComposition,
    ) -> "SameViewRoomAreaProducer":
        return cls(source=source, rooms=rooms, _seal=_PRODUCER_SEAL)

    def publish(self) -> SameViewRoomAreaResult:
        rooms = tuple(self._rooms.rooms)
        if not rooms:
            return SameViewRoomAreaResult(
                EvidenceResolutionStatus.ABSTAINED,
                (SAME_VIEW_ROOM_AREA_UNAVAILABLE,),
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
            return SameViewRoomAreaResult(
                EvidenceResolutionStatus.CONFLICT,
                (SAME_VIEW_ROOM_AREA_LINEAGE_CONFLICT,),
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
            return SameViewRoomAreaResult(
                EvidenceResolutionStatus.CONFLICT,
                (SAME_VIEW_ROOM_AREA_LINEAGE_CONFLICT,),
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
        labels: dict[tuple[str, str], list[LiveCanonicalRoomObject]] = {}
        for room in eligible:
            labels.setdefault(
                (str(room.page_id), _norm_label(room.room_label)),
                [],
            ).append(room)

        duplicate_room_ids = {
            str(room.physical_room_id)
            for group in labels.values()
            if len(group) != 1
            for room in group
        }
        unresolved: set[str] = {
            str(room.physical_room_id)
            for room in rooms
            if room not in eligible
        }
        unresolved.update(duplicate_room_ids)
        conflict_seen = bool(duplicate_room_ids)
        records: list[SameViewRoomAreaRecord] = []

        for (page_id, label), grouped_rooms in sorted(labels.items()):
            if len(grouped_rooms) != 1:
                continue
            room = grouped_rooms[0]

            lines = tuple(
                line
                for line in _trusted_lines_for_page(
                    self._source,
                    revision_id=revision_id,
                    page_id=page_id,
                    candidate_labels=(room.room_label,),
                )
                if _norm_label(line.text) == label
            )
            # Same-view ownership is stricter than cross-view: the already
            # room-owned semantic label must resolve to one exact trusted native
            # line on this physical room page.
            if len(lines) != 1:
                unresolved.add(str(room.physical_room_id))
                if len(lines) > 1:
                    conflict_seen = True
                continue

            dimensions = _trusted_native_dimensions_for_page(
                self._source,
                revision_id=revision_id,
                page_id=page_id,
                candidate_lines=lines,
                view_type=DrawingViewType.FLOOR_PLAN.value,
            )
            horizontals = tuple(
                item
                for item in dimensions
                if item.orientation == DimensionOrientation.HORIZONTAL.value
            )
            verticals = tuple(
                item
                for item in dimensions
                if item.orientation == DimensionOrientation.VERTICAL.value
            )

            matches = []
            line = lines[0]
            for horizontal in horizontals:
                for vertical in verticals:
                    if (
                        _line_inside_dimension_pair(line, horizontal, vertical)
                        and _figured_pair_scale_consistent(
                            page_id=page_id,
                            horizontal=horizontal,
                            vertical=vertical,
                        )
                        and _witness_systems_intersect(horizontal, vertical)
                    ):
                        matches.append((line, horizontal, vertical))

            if not matches:
                owned_horizontals = tuple(
                    dimension
                    for dimension in horizontals
                    if _dimension_is_immediate_label_annotation(line, dimension)
                )
                owned_verticals = tuple(
                    dimension
                    for dimension in verticals
                    if _dimension_is_immediate_label_annotation(line, dimension)
                )
                for horizontal in owned_horizontals:
                    for vertical in owned_verticals:
                        if _figured_pair_scale_consistent(
                            page_id=page_id,
                            horizontal=horizontal,
                            vertical=vertical,
                        ):
                            matches.append((line, horizontal, vertical))

            deduped = {
                (
                    horizontal.dimension_id,
                    vertical.dimension_id,
                ): (owned_line, horizontal, vertical)
                for owned_line, horizontal, vertical in matches
            }
            if len(deduped) != 1:
                unresolved.add(str(room.physical_room_id))
                if len(deduped) > 1:
                    conflict_seen = True
                continue

            owned_line, horizontal, vertical = next(iter(deduped.values()))
            area_m2 = round(
                float(horizontal.value_mm)
                * float(vertical.value_mm)
                / 1_000_000.0,
                6,
            )
            if not math.isfinite(area_m2) or area_m2 <= 0.0:
                unresolved.add(str(room.physical_room_id))
                continue

            horizontal_x = sorted(
                (
                    float(horizontal.endpoints_pt[0][0]),
                    float(horizontal.endpoints_pt[1][0]),
                )
            )
            vertical_y = sorted(
                (
                    float(vertical.endpoints_pt[0][1]),
                    float(vertical.endpoints_pt[1][1]),
                )
            )
            source_dimension_box = (
                horizontal_x[0],
                vertical_y[0],
                horizontal_x[1],
                vertical_y[1],
            )
            evidence_id = stable_contract_id(
                "same_view_room_area",
                {
                    "document_id": room.document_id,
                    "physical_room_id": room.physical_room_id,
                    "source_room_face_record_id": room.source_room_face_record_id,
                    "dimension_page_id": page_id,
                    "label_receipt_ids": owned_line.receipt_ids,
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
                method="authenticated_same_view_figured_dimensions",
                normalized_value=area_m2,
                unit="m2",
                confidence=1.0,
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(SAME_VIEW_ROOM_AREA_EVIDENCE_RESOLVED,),
                metadata={
                    "physical_room_id": str(room.physical_room_id),
                    "source_room_face_record_id": str(
                        room.source_room_face_record_id
                    ),
                    "room_label_binding_record_id": str(
                        room.room_label_binding_record_id
                    ),
                    "room_label_evidence_ids": list(room.room_label_evidence_ids),
                    "source_dimension_page_id": str(page_id),
                    "source_dimension_snapshot_id": str(
                        published.snapshot.snapshot_id
                    ),
                    "source_label_text": owned_line.text,
                    "source_label_observation_ids": list(
                        owned_line.observation_ids
                    ),
                    "source_label_receipt_ids": list(owned_line.receipt_ids),
                    "source_label_bbox_pdf_pts": list(owned_line.bbox),
                    "source_dimension_box_pdf_pts": list(source_dimension_box),
                    "figured_dimension_ids": [
                        horizontal.dimension_id,
                        vertical.dimension_id,
                    ],
                    "horizontal_dimension_id": horizontal.dimension_id,
                    "horizontal_value_mm": int(horizontal.value_mm),
                    "horizontal_dimension_line_observation_ids": list(
                        horizontal.dimension_line_observation_ids
                    ),
                    "horizontal_witness_observation_ids": list(
                        horizontal.witness_observation_ids
                    ),
                    "vertical_dimension_id": vertical.dimension_id,
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
                SameViewRoomAreaRecord(
                    physical_room_id=str(room.physical_room_id),
                    source_room_face_record_id=str(
                        room.source_room_face_record_id
                    ),
                    room_label=str(room.room_label),
                    source_dimension_page_id=str(page_id),
                    source_label_observation_ids=tuple(
                        owned_line.observation_ids
                    ),
                    source_label_receipt_ids=tuple(owned_line.receipt_ids),
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
            reasons = (SAME_VIEW_ROOM_AREA_RESOLVED,)
        elif records:
            status = EvidenceResolutionStatus.CANDIDATE
            reasons = (SAME_VIEW_ROOM_AREA_PARTIAL,)
        elif conflict_seen:
            status = EvidenceResolutionStatus.CONFLICT
            reasons = (SAME_VIEW_ROOM_AREA_CONFLICT,)
        else:
            status = EvidenceResolutionStatus.ABSTAINED
            reasons = (SAME_VIEW_ROOM_AREA_UNAVAILABLE,)
        return SameViewRoomAreaResult(
            status=status,
            reason_codes=reasons,
            records=tuple(records),
            unresolved_physical_room_ids=unresolved_ids,
        )


__all__ = [
    "SAME_VIEW_ROOM_AREA_CONFLICT",
    "SAME_VIEW_ROOM_AREA_EVIDENCE_RESOLVED",
    "SAME_VIEW_ROOM_AREA_LINEAGE_CONFLICT",
    "SAME_VIEW_ROOM_AREA_PARTIAL",
    "SAME_VIEW_ROOM_AREA_RESOLVED",
    "SAME_VIEW_ROOM_AREA_SCHEMA_VERSION",
    "SAME_VIEW_ROOM_AREA_UNAVAILABLE",
    "SameViewRoomAreaProducer",
    "SameViewRoomAreaRecord",
    "SameViewRoomAreaResult",
]
