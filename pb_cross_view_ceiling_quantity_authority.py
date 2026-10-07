"""Publish canonical ceiling-lining quantities from cross-view source authority.

This module composes already-proven facts only:
- one source-owned canonical physical room;
- one authenticated cross-view figured-dimension room area;
- one fail-closed cross-view RCP ceiling-finish binding.

It does not remeasure geometry, infer room identity, infer a finish from a raw
abbreviation, invent scale, or create customer rows.  The physical ceiling
surface identity is stable from the physical room identity plus the role
"ceiling", matching the room-owned floor-surface identity pattern.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Optional

from pb_cross_view_ceiling_finish_authority import (
    CrossViewCeilingFinishRecord,
    CrossViewCeilingFinishResult,
)
from pb_cross_view_room_area_authority import (
    CrossViewRoomAreaRecord,
    CrossViewRoomAreaResult,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)


CROSS_VIEW_CEILING_QUANTITY_SCHEMA_VERSION = "1.0.0"
CROSS_VIEW_CEILING_QUANTITY_RESOLVED = "cross_view_ceiling_quantity_resolved"
CROSS_VIEW_CEILING_QUANTITY_PARTIAL = "cross_view_ceiling_quantity_partial"
CROSS_VIEW_CEILING_QUANTITY_UNAVAILABLE = "cross_view_ceiling_quantity_unavailable"
CROSS_VIEW_CEILING_QUANTITY_CONFLICT = "cross_view_ceiling_quantity_conflict"
CROSS_VIEW_CEILING_QUANTITY_LINEAGE_CONFLICT = (
    "cross_view_ceiling_quantity_lineage_conflict"
)
CROSS_VIEW_CEILING_QUANTITY_FIRM = "authenticated_cross_view_ceiling_lining_area"

_RECORD_SEAL = object()


def _clean(value: object) -> str:
    return str(value or "").strip()


def _area_value(record: CrossViewRoomAreaRecord) -> Optional[float]:
    evidence = record.area_evidence
    if (
        evidence.status is not EvidenceResolutionStatus.CORROBORATED
        or evidence.kind != "explicit_room_area"
        or evidence.method != "authenticated_cross_view_figured_dimensions"
        or _clean(evidence.unit).lower() not in {"m2", "m²"}
    ):
        return None
    try:
        value = float(evidence.normalized_value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None
    return value


def _ceiling_id(room: LiveCanonicalRoomObject) -> str:
    return stable_contract_id(
        "physical_room_ceiling_surface",
        {
            "document_id": room.document_id,
            "physical_room_id": room.physical_room_id,
            "surface_role": "ceiling",
        },
        digest_chars=32,
    )


@dataclass(frozen=True)
class CrossViewCeilingQuantityRecord:
    canonical_ceiling_id: str
    physical_ceiling_surface_id: str
    physical_room_id: str
    canonical_room_id: str
    source_room_face_record_id: str
    room_label: str
    finish_code: str
    semantic_finish: str
    support_page_id: str
    support_viewport_id: str
    source_dimension_page_id: str
    quantity: QuantityEvidence
    schema_version: str = CROSS_VIEW_CEILING_QUANTITY_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("CrossViewCeilingQuantityRecord is producer-owned")


@dataclass(frozen=True)
class CrossViewCeilingQuantityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[CrossViewCeilingQuantityRecord, ...]
    unresolved_physical_room_ids: tuple[str, ...]
    schema_version: str = CROSS_VIEW_CEILING_QUANTITY_SCHEMA_VERSION

    @property
    def quantities(self) -> tuple[QuantityEvidence, ...]:
        return tuple(record.quantity for record in self.records)

    @property
    def records_by_ceiling_id(
        self,
    ) -> Mapping[str, CrossViewCeilingQuantityRecord]:
        return MappingProxyType(
            {record.canonical_ceiling_id: record for record in self.records}
        )


def publish_cross_view_ceiling_quantities(
    *,
    rooms: LiveCanonicalRoomComposition,
    room_areas: CrossViewRoomAreaResult,
    finishes: CrossViewCeilingFinishResult,
) -> CrossViewCeilingQuantityResult:
    if type(rooms) is not LiveCanonicalRoomComposition:
        raise TypeError("rooms must be LiveCanonicalRoomComposition")
    if type(room_areas) is not CrossViewRoomAreaResult:
        raise TypeError("room_areas must be CrossViewRoomAreaResult")
    if type(finishes) is not CrossViewCeilingFinishResult:
        raise TypeError("finishes must be CrossViewCeilingFinishResult")

    rooms_by_physical: dict[str, list[LiveCanonicalRoomObject]] = {}
    for room in rooms.rooms:
        physical_id = _clean(room.physical_room_id)
        if physical_id:
            rooms_by_physical.setdefault(physical_id, []).append(room)

    areas_by_physical: dict[str, list[CrossViewRoomAreaRecord]] = {}
    for record in room_areas.records:
        physical_id = _clean(record.physical_room_id)
        if physical_id:
            areas_by_physical.setdefault(physical_id, []).append(record)

    finishes_by_physical: dict[str, list[CrossViewCeilingFinishRecord]] = {}
    for record in finishes.records:
        physical_id = _clean(record.physical_room_id)
        if physical_id:
            finishes_by_physical.setdefault(physical_id, []).append(record)

    candidate_ids = tuple(
        sorted(
            set(rooms_by_physical)
            & set(areas_by_physical)
            & set(finishes_by_physical)
        )
    )
    if not candidate_ids:
        unresolved = tuple(
            sorted(
                set(rooms_by_physical)
                | set(areas_by_physical)
                | set(finishes_by_physical)
            )
        )
        return CrossViewCeilingQuantityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(CROSS_VIEW_CEILING_QUANTITY_UNAVAILABLE,),
            records=(),
            unresolved_physical_room_ids=unresolved,
        )

    records: list[CrossViewCeilingQuantityRecord] = []
    unresolved: set[str] = set()
    conflict = False

    for physical_id in sorted(
        set(rooms_by_physical)
        | set(areas_by_physical)
        | set(finishes_by_physical)
    ):
        room_rows = rooms_by_physical.get(physical_id, ())
        area_rows = areas_by_physical.get(physical_id, ())
        finish_rows = finishes_by_physical.get(physical_id, ())
        if (
            len(room_rows) != 1
            or len(area_rows) != 1
            or len(finish_rows) != 1
        ):
            unresolved.add(physical_id)
            if len(room_rows) > 1 or len(area_rows) > 1 or len(finish_rows) > 1:
                conflict = True
            continue

        room = room_rows[0]
        area = area_rows[0]
        finish = finish_rows[0]
        value = _area_value(area)
        area_meta = (
            area.area_evidence.metadata
            if isinstance(area.area_evidence.metadata, Mapping)
            else {}
        )
        figured_dimension_ids = tuple(
            sorted(
                {
                    _clean(item)
                    for item in (area_meta.get("figured_dimension_ids") or ())
                    if _clean(item)
                }
            )
        )

        if (
            value is None
            or len(figured_dimension_ids) != 2
            or not room.geometry_complete
            or not _clean(room.canonical_room_id)
            or not _clean(room.source_room_face_record_id)
            or area.source_room_face_record_id != room.source_room_face_record_id
            or finish.source_room_face_record_id != room.source_room_face_record_id
            or finish.canonical_room_id != room.canonical_room_id
            or _clean(area.room_label).casefold()
            != _clean(room.room_label).casefold()
            or _clean(finish.room_label).casefold()
            != _clean(room.room_label).casefold()
            or area.area_evidence.document_id != room.document_id
            or _clean(area_meta.get("source_sha256")).lower()
            != room.source_sha256.lower()
            or _clean(area_meta.get("room_revision_id")) != room.revision_id
            or finish.definition_evidence_ids == ()
            or not _clean(finish.occurrence_evidence_id)
        ):
            unresolved.add(physical_id)
            continue

        canonical_ceiling_id = _ceiling_id(room)
        evidence_ids = tuple(
            dict.fromkeys(
                (
                    *(
                        _clean(item)
                        for item in room.evidence_ids
                        if _clean(item)
                    ),
                    *(
                        _clean(item)
                        for item in room.room_label_evidence_ids
                        if _clean(item)
                    ),
                    area.area_evidence.evidence_id,
                    *(
                        _clean(item)
                        for item in area.source_label_observation_ids
                        if _clean(item)
                    ),
                    finish.occurrence_evidence_id,
                    *(
                        _clean(item)
                        for item in finish.definition_evidence_ids
                        if _clean(item)
                    ),
                )
            )
        )
        payload = {
            "family": "ceiling_lining",
            "canonical_ceiling_id": canonical_ceiling_id,
            "area_evidence_id": area.area_evidence.evidence_id,
            "finish_occurrence_record_id": finish.occurrence_record_id,
            "finish_definition_record_id": finish.definition_record_id,
            "value_m2": round(value, 6),
        }
        quantity = QuantityEvidence(
            quantity_id=stable_contract_id(
                "qty_ceiling_lining_area",
                payload,
                digest_chars=32,
            ),
            family="ceiling_lining",
            semantic_key=(
                f"ceiling_lining:{canonical_ceiling_id}:"
                f"{finish.finish_code}:{finish.semantic_finish}"
            ),
            value=round(value, 6),
            unit="m2",
            input_entity_ids=(canonical_ceiling_id,),
            formula="authenticated_cross_view_room_area_with_source_ceiling_finish",
            formula_version=CROSS_VIEW_CEILING_QUANTITY_SCHEMA_VERSION,
            evidence_ids=evidence_ids,
            authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            status=AuthorityStatus.FIRM.value,
            confidence=1.0,
            abstained=False,
            reason_codes=(CROSS_VIEW_CEILING_QUANTITY_FIRM,),
            metadata={
                "source_sha256": room.source_sha256,
                "revision_id": room.revision_id,
                "page_no": room.page_id,
                "viewport_id": room.viewport_id,
                "source_dimension_page_id": area.source_dimension_page_id,
                "support_page_id": finish.support_page_id,
                "support_viewport_id": finish.support_viewport_id,
                "support_source_partition_id": finish.support_source_partition_id,
                "support_block_no": finish.support_block_no,
                "room_label": room.room_label,
                "physical_room_id": room.physical_room_id,
                "canonical_room_id": room.canonical_room_id,
                "canonical_ceiling_id": canonical_ceiling_id,
                "physical_ceiling_surface_id": canonical_ceiling_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "figured_dimension_ids": list(figured_dimension_ids),
                "finish_code": finish.finish_code,
                "semantic_finish": finish.semantic_finish,
                "finish_definition_record_id": finish.definition_record_id,
                "finish_occurrence_record_id": finish.occurrence_record_id,
                "finish_occurrence_evidence_id": finish.occurrence_evidence_id,
                "finish_occurrence_bbox_pdf_pts": list(
                    finish.occurrence_bbox_pdf_pts
                ),
                "section": "Internal",
                "element": "Ceiling lining area",
                "location": room.room_label,
                "substrate": "Other",
                "finish_system": finish.semantic_finish,
                "inclusion_status": "INCLUSION",
                "row_role": "ceiling_area",
                "quantity_handoff_only": True,
            },
        )
        records.append(
            CrossViewCeilingQuantityRecord(
                canonical_ceiling_id=canonical_ceiling_id,
                physical_ceiling_surface_id=canonical_ceiling_id,
                physical_room_id=physical_id,
                canonical_room_id=room.canonical_room_id,
                source_room_face_record_id=room.source_room_face_record_id,
                room_label=_clean(room.room_label),
                finish_code=finish.finish_code,
                semantic_finish=finish.semantic_finish,
                support_page_id=finish.support_page_id,
                support_viewport_id=finish.support_viewport_id,
                source_dimension_page_id=area.source_dimension_page_id,
                quantity=quantity,
                _seal=_RECORD_SEAL,
            )
        )

    records.sort(key=lambda record: record.canonical_ceiling_id)
    unresolved_ids = tuple(sorted(unresolved))
    if records and not unresolved_ids and not conflict:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (CROSS_VIEW_CEILING_QUANTITY_RESOLVED,)
    elif records:
        status = EvidenceResolutionStatus.CANDIDATE
        reasons = (CROSS_VIEW_CEILING_QUANTITY_PARTIAL,)
    elif conflict:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (CROSS_VIEW_CEILING_QUANTITY_CONFLICT,)
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (CROSS_VIEW_CEILING_QUANTITY_UNAVAILABLE,)

    return CrossViewCeilingQuantityResult(
        status=status,
        reason_codes=reasons,
        records=tuple(records),
        unresolved_physical_room_ids=unresolved_ids,
    )


__all__ = [
    "CROSS_VIEW_CEILING_QUANTITY_CONFLICT",
    "CROSS_VIEW_CEILING_QUANTITY_FIRM",
    "CROSS_VIEW_CEILING_QUANTITY_LINEAGE_CONFLICT",
    "CROSS_VIEW_CEILING_QUANTITY_PARTIAL",
    "CROSS_VIEW_CEILING_QUANTITY_RESOLVED",
    "CROSS_VIEW_CEILING_QUANTITY_SCHEMA_VERSION",
    "CROSS_VIEW_CEILING_QUANTITY_UNAVAILABLE",
    "CrossViewCeilingQuantityRecord",
    "CrossViewCeilingQuantityResult",
    "publish_cross_view_ceiling_quantities",
]
