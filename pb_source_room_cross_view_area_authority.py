"""Source-owned cross-view room area evidence.

This authority binds an already-authenticated plan room to figured dimensions in
another authenticated drawing viewport. It emits evidence only; numeric quantity
publication remains owned by pb_room_area_quantity.

No nearest-label, edit-distance, scale inference, benchmark values, project names,
page constants or caller-authored dimensions are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from typing import Optional, Sequence

import fitz

from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_authority import resolve_measurement_authority
from pb_geometry_takeoff_model import AuthorityStatus
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_migration_contracts import (
    EvidenceAtom,
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_pdf_text_integrity_authority import TRUSTED_PDF_TEXT
from pb_raster_plan_dimension_authority import (
    BoundRasterDimension,
    RasterDimensionTextObservation,
    RasterPlanDimensionProducer,
    RasterPlanDimensionResult,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import (
    SourceRoomFaceAuthority,
    SourceRoomFaceSelector,
)
from pb_source_room_label_authority import _normalized_room_line
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    segment_page_viewports,
)


SOURCE_ROOM_CROSS_VIEW_AREA_SCHEMA_VERSION = "1.0.0"
SOURCE_ROOM_CROSS_VIEW_AREA_METHOD = "source_owned_cross_view_figured_dimensions"
SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED = "source_room_cross_view_area_resolved"
SOURCE_ROOM_CROSS_VIEW_AREA_UNAVAILABLE = "source_room_cross_view_area_unavailable"
SOURCE_ROOM_CROSS_VIEW_AREA_LINEAGE_CONFLICT = "source_room_cross_view_area_lineage_conflict"
SOURCE_ROOM_CROSS_VIEW_AREA_ROOM_LABEL_AMBIGUOUS = "source_room_cross_view_area_room_label_ambiguous"
SOURCE_ROOM_CROSS_VIEW_AREA_VIEW_LABEL_AMBIGUOUS = "source_room_cross_view_area_view_label_ambiguous"
SOURCE_ROOM_CROSS_VIEW_AREA_DIMENSIONS_AMBIGUOUS = "source_room_cross_view_area_dimensions_ambiguous"

_PRODUCER_SEAL = object()
_RECORD_SEAL = object()

_ALLOWED_VIEW_TYPES = frozenset(
    {
        DrawingViewType.FLOOR_PLAN.value,
        DrawingViewType.ELEVATION.value,
        DrawingViewType.SECTION.value,
        DrawingViewType.DETAIL.value,
    }
)


@dataclass(frozen=True)
class SourceRoomCrossViewAreaRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    room_ref: str
    physical_room_id: str
    source_room_face_record_id: str
    room_label: str
    topology_page_id: str
    dimension_page_id: str
    dimension_viewport_id: str
    horizontal_dimension_id: str
    vertical_dimension_id: str
    horizontal_value_m: float
    vertical_value_m: float
    area_m2: float
    room_label_receipt_ids: tuple[str, ...]
    dimension_text_observation_ids: tuple[str, ...]
    witness_observation_ids: tuple[str, ...]
    evidence: EvidenceAtom
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED
    reason_codes: tuple[str, ...] = (SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED,)
    schema_version: str = SOURCE_ROOM_CROSS_VIEW_AREA_SCHEMA_VERSION
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceRoomCrossViewAreaRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive cross-view room area record must be CORROBORATED")
        if self.evidence.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("cross-view room area evidence must be CORROBORATED")
        if self.evidence.method != SOURCE_ROOM_CROSS_VIEW_AREA_METHOD:
            raise ValueError("cross-view room area evidence method mismatch")
        if not math.isfinite(self.area_m2) or self.area_m2 <= 0.0:
            raise ValueError("cross-view room area must be positive and finite")


@dataclass(frozen=True)
class SourceRoomCrossViewAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SourceRoomCrossViewAreaRecord, ...]
    schema_version: str = SOURCE_ROOM_CROSS_VIEW_AREA_SCHEMA_VERSION


@dataclass(frozen=True)
class _TrustedViewLabel:
    normalized_label: str
    source_label: str
    page_id: str
    viewport_id: str
    receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class _RoomBinding:
    room: LiveCanonicalRoomObject
    room_ref: str


def _normalise_label(value: str) -> Optional[str]:
    accepted = _normalized_room_line(str(value or ""))
    if accepted is None:
        return None
    return " ".join(accepted.strip().lower().split())


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


def _point_in_bbox(
    point: tuple[float, float],
    bbox: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        float(bbox[0]) - tolerance <= float(point[0]) <= float(bbox[2]) + tolerance
        and float(bbox[1]) - tolerance <= float(point[1]) <= float(bbox[3]) + tolerance
    )


def _dimension_inside_viewport(
    dimension: BoundRasterDimension,
    viewport: SegmentedViewport,
) -> bool:
    bbox = viewport.bounding_box
    return (
        bbox is not None
        and _point_in_bbox(dimension.endpoints_pt[0], bbox)
        and _point_in_bbox(dimension.endpoints_pt[1], bbox)
    )


def _trusted_dimension_text(
    observation: RasterDimensionTextObservation,
) -> bool:
    backend = str(observation.backend_name or "")
    return backend == "pdf_text_integrity" or backend.startswith("raster_text:")


def _select_axis_dimension(
    result: RasterPlanDimensionResult,
    viewport: SegmentedViewport,
    orientation: str,
) -> Optional[BoundRasterDimension]:
    trusted_text = {
        observation.observation_id: observation
        for observation in result.text_observations
        if _trusted_dimension_text(observation)
    }
    candidates = [
        dimension
        for dimension in result.bound_dimensions
        if dimension.orientation == orientation
        and dimension.text_observation_id in trusted_text
        and dimension.dimension_line_observation_ids
        and dimension.witness_observation_ids
        and _dimension_inside_viewport(dimension, viewport)
    ]
    if len(candidates) == 1:
        return candidates[0]

    overall = (
        result.horizontal
        if orientation == DimensionOrientation.HORIZONTAL.value
        else result.vertical
        if orientation == DimensionOrientation.VERTICAL.value
        else None
    )
    if overall is None:
        return None
    matching = [
        dimension
        for dimension in candidates
        if dimension.dimension_id == overall.overall_dimension_id
    ]
    return matching[0] if len(matching) == 1 else None


def _trusted_view_labels(
    *,
    source: SourceVisibilityProducer,
    revision_id: str,
    page_id: str,
    viewports: Sequence[SegmentedViewport],
) -> tuple[_TrustedViewLabel, ...]:
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        return ()
    usable = [
        viewport
        for viewport in viewports
        if viewport.status == ViewportSegmentationStatus.RESOLVED.value
        and viewport.bounding_box is not None
        and viewport.view_type in _ALLOWED_VIEW_TYPES
    ]
    if not usable:
        return ()

    text_authority = source.text_integrity_authority()
    grouped: dict[tuple[str, int, int], list[tuple[int, str, str]]] = {}
    for observation_id in published.text_observation_ids:
        resolved = text_authority.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = resolved.receipt
        if (
            resolved.status is not EvidenceResolutionStatus.CORROBORATED
            or resolved.proposition != TRUSTED_PDF_TEXT
            or not resolved.trusted_text
            or receipt is None
            or str(receipt.page_id) != str(page_id)
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
            or len(receipt.geometry) < 4
        ):
            continue
        owners = [
            viewport
            for viewport in usable
            if viewport.bounding_box is not None
            and _bbox_fully_inside(receipt.geometry[:4], viewport.bounding_box)
        ]
        if len(owners) != 1:
            continue
        owner = owners[0]
        grouped.setdefault(
            (owner.view_id, int(receipt.block_no), int(receipt.line_no)),
            [],
        ).append(
            (
                int(receipt.word_no),
                str(resolved.trusted_text),
                str(receipt.receipt_id),
            )
        )

    candidates_by_view: dict[str, list[_TrustedViewLabel]] = {}
    for (viewport_id, _block_no, _line_no), words in sorted(grouped.items()):
        word_numbers = [item[0] for item in words]
        if len(set(word_numbers)) != len(word_numbers):
            continue
        ordered = sorted(words, key=lambda item: item[0])
        source_label = " ".join(item[1].strip() for item in ordered if item[1].strip())
        normalized = _normalise_label(source_label)
        if normalized is None:
            continue
        candidates_by_view.setdefault(viewport_id, []).append(
            _TrustedViewLabel(
                normalized_label=normalized,
                source_label=source_label,
                page_id=str(page_id),
                viewport_id=viewport_id,
                receipt_ids=tuple(item[2] for item in ordered),
            )
        )

    output: list[_TrustedViewLabel] = []
    for viewport_id, candidates in sorted(candidates_by_view.items()):
        unique = {
            (candidate.normalized_label, candidate.receipt_ids): candidate
            for candidate in candidates
        }
        if len(unique) == 1:
            output.append(next(iter(unique.values())))
    return tuple(output)


class SourceRoomCrossViewAreaProducer:
    def __init__(
        self,
        *,
        source_visibility: SourceVisibilityProducer,
        room_face_authority: SourceRoomFaceAuthority,
        canonical_rooms: Sequence[LiveCanonicalRoomObject],
        source_bytes: bytes,
        dimension_producer: RasterPlanDimensionProducer,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SourceRoomCrossViewAreaProducer must be obtained from create()")
        if type(source_visibility) is not SourceVisibilityProducer:
            raise TypeError("source_visibility must be exact SourceVisibilityProducer")
        if type(room_face_authority) is not SourceRoomFaceAuthority:
            raise TypeError("room_face_authority must be exact SourceRoomFaceAuthority")
        if type(dimension_producer) is not RasterPlanDimensionProducer:
            raise TypeError("dimension_producer must be producer-owned")
        if any(type(room) is not LiveCanonicalRoomObject for room in canonical_rooms):
            raise TypeError("canonical_rooms must contain LiveCanonicalRoomObject")
        self._source = source_visibility
        self._room_faces = room_face_authority
        self._rooms = tuple(canonical_rooms)
        self._source_bytes = bytes(source_bytes)
        self._dimensions = dimension_producer

    @classmethod
    def create(
        cls,
        *,
        source_visibility: SourceVisibilityProducer,
        room_face_authority: SourceRoomFaceAuthority,
        canonical_rooms: Sequence[LiveCanonicalRoomObject],
        source_bytes: bytes,
    ) -> "SourceRoomCrossViewAreaProducer":
        return cls(
            source_visibility=source_visibility,
            room_face_authority=room_face_authority,
            canonical_rooms=canonical_rooms,
            source_bytes=source_bytes,
            dimension_producer=RasterPlanDimensionProducer.create(
                source_visibility=source_visibility
            ),
            _seal=_PRODUCER_SEAL,
        )

    @classmethod
    def create_for_tests(
        cls,
        *,
        source_visibility: SourceVisibilityProducer,
        room_face_authority: SourceRoomFaceAuthority,
        canonical_rooms: Sequence[LiveCanonicalRoomObject],
        source_bytes: bytes,
        dimension_producer: RasterPlanDimensionProducer,
    ) -> "SourceRoomCrossViewAreaProducer":
        return cls(
            source_visibility=source_visibility,
            room_face_authority=room_face_authority,
            canonical_rooms=canonical_rooms,
            source_bytes=source_bytes,
            dimension_producer=dimension_producer,
            _seal=_PRODUCER_SEAL,
        )

    def _rooms_by_label(
        self,
        *,
        revision_id: str,
    ) -> tuple[dict[str, _RoomBinding], set[str]]:
        candidates: dict[str, list[_RoomBinding]] = {}
        for room in self._rooms:
            normalized = _normalise_label(str(room.room_label or ""))
            if normalized is None:
                continue
            if room.revision_id != revision_id:
                continue
            result = self._room_faces.resolve_scope(
                SourceRoomFaceSelector(
                    document_id=room.document_id,
                    revision_id=room.revision_id,
                    source_sha256=room.source_sha256,
                    snapshot_id=room.snapshot_id,
                    page_id=room.page_id,
                    decision_scope_id=room.decision_scope_id,
                )
            )
            matching = [
                record
                for record in result.records
                if record.record_id == room.source_room_face_record_id
            ]
            if len(matching) != 1:
                continue
            candidates.setdefault(normalized, []).append(
                _RoomBinding(room=room, room_ref=str(matching[0].face_id))
            )

        ambiguous = {label for label, values in candidates.items() if len(values) != 1}
        unique = {
            label: values[0]
            for label, values in candidates.items()
            if len(values) == 1
        }
        return unique, ambiguous

    def publish(self, *, revision_id: str) -> SourceRoomCrossViewAreaResult:
        revision_id = str(revision_id or "").strip()
        if not revision_id:
            raise ValueError("revision_id is required")
        published = self._source.published_snapshot_for_revision(revision_id)
        if published is None:
            return SourceRoomCrossViewAreaResult(
                EvidenceResolutionStatus.ABSTAINED,
                (SOURCE_ROOM_CROSS_VIEW_AREA_UNAVAILABLE,),
                (),
            )
        if hashlib.sha256(self._source_bytes).hexdigest() != published.revision.source_sha256:
            return SourceRoomCrossViewAreaResult(
                EvidenceResolutionStatus.CONFLICT,
                (SOURCE_ROOM_CROSS_VIEW_AREA_LINEAGE_CONFLICT,),
                (),
            )
        if any(
            room.document_id != published.revision.document_id
            or room.revision_id != published.revision.revision_id
            or room.source_sha256.lower() != published.revision.source_sha256.lower()
            for room in self._rooms
        ):
            return SourceRoomCrossViewAreaResult(
                EvidenceResolutionStatus.CONFLICT,
                (SOURCE_ROOM_CROSS_VIEW_AREA_LINEAGE_CONFLICT,),
                (),
            )

        rooms_by_label, ambiguous_room_labels = self._rooms_by_label(
            revision_id=revision_id
        )
        reasons: set[str] = set()
        if ambiguous_room_labels:
            reasons.add(SOURCE_ROOM_CROSS_VIEW_AREA_ROOM_LABEL_AMBIGUOUS)
        if not rooms_by_label:
            return SourceRoomCrossViewAreaResult(
                EvidenceResolutionStatus.ABSTAINED,
                tuple(sorted(reasons | {SOURCE_ROOM_CROSS_VIEW_AREA_UNAVAILABLE})),
                (),
            )

        candidates_by_room: dict[str, list[SourceRoomCrossViewAreaRecord]] = {}
        doc = fitz.open(stream=self._source_bytes, filetype="pdf")
        try:
            for page_no in published.coverage.decoded_pages:
                page_id = str(int(page_no))
                page = doc[int(page_no) - 1]
                viewports = tuple(
                    viewport
                    for viewport in segment_page_viewports(
                        page,
                        page_number=int(page_no),
                    )
                    if viewport.status == ViewportSegmentationStatus.RESOLVED.value
                    and viewport.bounding_box is not None
                    and viewport.view_type in _ALLOWED_VIEW_TYPES
                )
                if not viewports:
                    continue

                dimension_result = self._dimensions.publish(
                    revision_id=revision_id,
                    page_id=page_id,
                )
                refreshed = self._source.published_snapshot_for_revision(revision_id)
                if (
                    refreshed is None
                    or dimension_result.document_id not in (None, refreshed.revision.document_id)
                    or dimension_result.revision_id not in (None, refreshed.revision.revision_id)
                    or dimension_result.source_sha256 not in (None, refreshed.revision.source_sha256)
                ):
                    reasons.add(SOURCE_ROOM_CROSS_VIEW_AREA_LINEAGE_CONFLICT)
                    continue

                labels = _trusted_view_labels(
                    source=self._source,
                    revision_id=revision_id,
                    page_id=page_id,
                    viewports=viewports,
                )
                by_view = {viewport.view_id: viewport for viewport in viewports}
                for label in labels:
                    binding = rooms_by_label.get(label.normalized_label)
                    if binding is None:
                        continue
                    room = binding.room
                    # Cross-view evidence must not recycle the topology page.
                    if str(room.page_id) == page_id:
                        continue
                    viewport = by_view.get(label.viewport_id)
                    if viewport is None:
                        continue
                    horizontal = _select_axis_dimension(
                        dimension_result,
                        viewport,
                        DimensionOrientation.HORIZONTAL.value,
                    )
                    vertical = _select_axis_dimension(
                        dimension_result,
                        viewport,
                        DimensionOrientation.VERTICAL.value,
                    )
                    if horizontal is None or vertical is None:
                        reasons.add(SOURCE_ROOM_CROSS_VIEW_AREA_DIMENSIONS_AMBIGUOUS)
                        continue

                    h_auth = resolve_measurement_authority(
                        figured_mm=float(horizontal.value_mm),
                        scale_reliable=False,
                    )
                    v_auth = resolve_measurement_authority(
                        figured_mm=float(vertical.value_mm),
                        scale_reliable=False,
                    )
                    if (
                        h_auth.authority_status != AuthorityStatus.FIRM.value
                        or v_auth.authority_status != AuthorityStatus.FIRM.value
                        or h_auth.value_m is None
                        or v_auth.value_m is None
                    ):
                        continue
                    area_m2 = float(h_auth.value_m) * float(v_auth.value_m)
                    if not math.isfinite(area_m2) or area_m2 <= 0.0:
                        continue
                    area_m2 = round(area_m2, 6)

                    text_by_id = {
                        observation.observation_id: observation
                        for observation in dimension_result.text_observations
                    }
                    h_text = text_by_id.get(horizontal.text_observation_id)
                    v_text = text_by_id.get(vertical.text_observation_id)
                    if (
                        h_text is None
                        or v_text is None
                        or not _trusted_dimension_text(h_text)
                        or not _trusted_dimension_text(v_text)
                    ):
                        continue

                    payload = {
                        "document_id": refreshed.revision.document_id,
                        "room_ref": binding.room_ref,
                        "physical_room_id": room.physical_room_id,
                        "source_room_face_record_id": room.source_room_face_record_id,
                        "room_label": label.normalized_label,
                        "topology_page_id": str(room.page_id),
                        "dimension_page_id": page_id,
                        "dimension_viewport_id": viewport.view_id,
                        "horizontal_dimension_id": horizontal.dimension_id,
                        "vertical_dimension_id": vertical.dimension_id,
                        "horizontal_value_mm": int(horizontal.value_mm),
                        "vertical_value_mm": int(vertical.value_mm),
                    }
                    record_id = stable_contract_id(
                        "source_room_cross_view_area",
                        payload,
                        digest_chars=32,
                    )
                    evidence_id = stable_contract_id(
                        "ev_room_cross_view_area",
                        {**payload, "record_id": record_id},
                        digest_chars=32,
                    )
                    witness_ids = tuple(
                        sorted(
                            set(horizontal.witness_observation_ids)
                            | set(vertical.witness_observation_ids)
                        )
                    )
                    evidence = EvidenceAtom(
                        evidence_id=evidence_id,
                        document_id=refreshed.revision.document_id,
                        page_id=page_id,
                        viewport_id=viewport.view_id,
                        kind="explicit_room_area",
                        method=SOURCE_ROOM_CROSS_VIEW_AREA_METHOD,
                        raw_text=(
                            f"{int(horizontal.value_mm)} x "
                            f"{int(vertical.value_mm)} mm"
                        ),
                        normalized_value=area_m2,
                        unit="m2",
                        confidence=min(
                            float(h_text.confidence)
                            if h_text.confidence is not None
                            else 1.0,
                            float(v_text.confidence)
                            if v_text.confidence is not None
                            else 1.0,
                        ),
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED,),
                        metadata={
                            **payload,
                            "cross_view_binding_record_id": record_id,
                            "bound_room_ref": binding.room_ref,
                            "dimension_text_observation_ids": [
                                horizontal.text_observation_id,
                                vertical.text_observation_id,
                            ],
                            "room_label_receipt_ids": list(label.receipt_ids),
                            "witness_observation_ids": list(witness_ids),
                            "dimension_text_backends": [
                                h_text.backend_name,
                                v_text.backend_name,
                            ],
                        },
                    )
                    record = SourceRoomCrossViewAreaRecord(
                        record_id=record_id,
                        document_id=refreshed.revision.document_id,
                        revision_id=refreshed.revision.revision_id,
                        source_sha256=refreshed.revision.source_sha256,
                        snapshot_id=refreshed.snapshot.snapshot_id,
                        room_ref=binding.room_ref,
                        physical_room_id=room.physical_room_id,
                        source_room_face_record_id=room.source_room_face_record_id,
                        room_label=str(room.room_label or label.source_label),
                        topology_page_id=str(room.page_id),
                        dimension_page_id=page_id,
                        dimension_viewport_id=viewport.view_id,
                        horizontal_dimension_id=horizontal.dimension_id,
                        vertical_dimension_id=vertical.dimension_id,
                        horizontal_value_m=float(h_auth.value_m),
                        vertical_value_m=float(v_auth.value_m),
                        area_m2=area_m2,
                        room_label_receipt_ids=label.receipt_ids,
                        dimension_text_observation_ids=(
                            horizontal.text_observation_id,
                            vertical.text_observation_id,
                        ),
                        witness_observation_ids=witness_ids,
                        evidence=evidence,
                        _seal=_RECORD_SEAL,
                    )
                    candidates_by_room.setdefault(binding.room_ref, []).append(record)
        finally:
            doc.close()

        records: list[SourceRoomCrossViewAreaRecord] = []
        for room_ref, candidates in sorted(candidates_by_room.items()):
            unique = {
                (
                    candidate.dimension_page_id,
                    candidate.dimension_viewport_id,
                    candidate.horizontal_dimension_id,
                    candidate.vertical_dimension_id,
                    candidate.area_m2,
                ): candidate
                for candidate in candidates
            }
            if len(unique) == 1:
                records.append(next(iter(unique.values())))
            elif unique:
                reasons.add(SOURCE_ROOM_CROSS_VIEW_AREA_VIEW_LABEL_AMBIGUOUS)

        if not records:
            reasons.add(SOURCE_ROOM_CROSS_VIEW_AREA_UNAVAILABLE)
            return SourceRoomCrossViewAreaResult(
                EvidenceResolutionStatus.ABSTAINED,
                tuple(sorted(reasons)),
                (),
            )
        reasons.add(SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED)
        return SourceRoomCrossViewAreaResult(
            EvidenceResolutionStatus.CORROBORATED,
            tuple(sorted(reasons)),
            tuple(sorted(records, key=lambda record: record.room_ref)),
        )


__all__ = [
    "SOURCE_ROOM_CROSS_VIEW_AREA_DIMENSIONS_AMBIGUOUS",
    "SOURCE_ROOM_CROSS_VIEW_AREA_LINEAGE_CONFLICT",
    "SOURCE_ROOM_CROSS_VIEW_AREA_METHOD",
    "SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED",
    "SOURCE_ROOM_CROSS_VIEW_AREA_ROOM_LABEL_AMBIGUOUS",
    "SOURCE_ROOM_CROSS_VIEW_AREA_SCHEMA_VERSION",
    "SOURCE_ROOM_CROSS_VIEW_AREA_UNAVAILABLE",
    "SOURCE_ROOM_CROSS_VIEW_AREA_VIEW_LABEL_AMBIGUOUS",
    "SourceRoomCrossViewAreaProducer",
    "SourceRoomCrossViewAreaRecord",
    "SourceRoomCrossViewAreaResult",
]
