"""Source-owned cross-view room-area authority.

This authority composes only already-authenticated evidence:
- a canonical physical room with an authenticated source room label;
- the exact same independently trusted native label line on another decoded view;
- one native-text-authenticated horizontal and one vertical figured dimension,
  each WITNESS_BOUND by the existing native vector binder and independently
  mapped back to unique producer-owned visible source observations.

It never accepts caller-supplied room names, page numbers, dimensions, geometry,
expected quantities or benchmark identities. Scale status is deliberately not an
input: authenticated figured dimensions remain valid when page scale is absent
or conflicting.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType

import fitz
from typing import Mapping, Optional, Sequence

from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_figured_dimension_authority import (
    DimensionParseError,
    parse_figured_dimension_mm,
)
from pb_figured_dimension_evidence import (
    BindingStatus,
    extract_dimension_evidence_bundle,
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
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


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
class _TrustedBoundDimension:
    dimension_id: str
    text_observation_id: str
    text_receipt_id: str
    value_mm: float
    orientation: str
    endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    dimension_line_observation_ids: tuple[str, ...]
    witness_observation_ids: tuple[str, ...]


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
    grouped: dict[
        tuple[str, int, int],
        list[tuple[str, object, object]],
    ] = {}

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
        ).append((str(observation_id), result, receipt))

    lines: list[_TrustedLine] = []
    for key in sorted(grouped):
        items = grouped[key]
        if any(
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or not result.trusted_text
            for _observation_id, result, _receipt in items
        ):
            continue
        word_nos = [
            int(receipt.word_no)
            for _observation_id, _result, receipt in items
        ]
        if len(set(word_nos)) != len(word_nos):
            continue
        lo, hi = min(word_nos), max(word_nos)
        if set(word_nos) != set(range(lo, hi + 1)):
            continue
        ordered = sorted(items, key=lambda item: int(item[2].word_no))
        boxes = [_finite_bbox(item[2].geometry) for item in ordered]
        if any(box is None for box in boxes):
            continue
        concrete_boxes = tuple(box for box in boxes if box is not None)
        line_text = " ".join(
            str(item[1].trusted_text).strip()
            for item in ordered
        )
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
                observation_ids=tuple(str(item[0]) for item in ordered),
                receipt_ids=tuple(str(item[2].receipt_id) for item in ordered),
            )
        )
    return tuple(lines)


def _canonical_segment_geometry(
    values: Sequence[object],
) -> Optional[tuple[float, float, float, float]]:
    if len(values) != 4:
        return None
    try:
        coords = tuple(float(value) for value in values)
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in coords):
        return None
    first = (coords[0], coords[1])
    second = (coords[2], coords[3])
    if second < first:
        first, second = second, first
    if first == second:
        return None
    return (first[0], first[1], second[0], second[1])


def _bbox_key(
    values: Sequence[object],
) -> Optional[tuple[float, float, float, float]]:
    bbox = _finite_bbox(values)
    if bbox is None:
        return None
    return tuple(round(value, 4) for value in bbox)


def _trusted_native_dimensions_for_page(
    source: SourceVisibilityProducer,
    *,
    revision_id: str,
    page_id: str,
) -> tuple[_TrustedBoundDimension, ...]:
    """Resolve source-owned native figured dimensions without trusting raw text.

    Geometry is derived only from the immutable PDF bytes held by the source
    producer. Positive dimensions additionally require PdfTextIntegrity for the
    exact word and a unique mapping of every bound vector segment back to a
    producer-owned native visible observation.
    """
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        return ()
    try:
        page_number = int(str(page_id))
    except (TypeError, ValueError):
        return ()
    if page_number not in set(published.coverage.decoded_pages):
        return ()

    writer = source._producer
    source_bytes = writer._store.source_bytes_by_revision.get(revision_id)
    if (
        not isinstance(source_bytes, bytes)
        or not writer._store.source_bytes_match_revision(
            revision_id,
            source_bytes,
            published.revision.source_sha256,
        )
    ):
        return ()

    try:
        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        if page_number < 1 or page_number > pdf.page_count:
            pdf.close()
            return ()
        try:
            bundle = extract_dimension_evidence_bundle(
                pdf.load_page(page_number - 1),
                page_num=page_number,
            )
        finally:
            pdf.close()
    except Exception:
        return ()

    text_authority = source.text_integrity_authority()
    trusted_by_bbox: dict[
        tuple[float, float, float, float],
        list[tuple[str, str, str]],
    ] = {}
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
            or not resolved.trusted_text
            or receipt is None
            or str(receipt.page_id) != str(page_id)
        ):
            continue
        key = _bbox_key(receipt.geometry)
        if key is None:
            continue
        trusted_by_bbox.setdefault(key, []).append(
            (
                str(resolved.trusted_text),
                str(observation_id),
                str(receipt.receipt_id),
            )
        )

    visibility = source.authority()
    source_ids_by_geometry: dict[
        tuple[float, float, float, float],
        list[str],
    ] = {}
    for observation_id in published.visible_observation_ids:
        resolved = visibility.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = resolved.observation
        if (
            resolved.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
            or str(observation.page_id) != str(page_id)
            or observation.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
        ):
            continue
        geometry = _canonical_segment_geometry(observation.geometry)
        if geometry is None:
            continue
        source_ids_by_geometry.setdefault(geometry, []).append(
            str(observation.observation_id)
        )

    geometry_by_segment_id = {
        segment.segment_id: _canonical_segment_geometry(
            (
                segment.start[0],
                segment.start[1],
                segment.end[0],
                segment.end[1],
            )
        )
        for segment in bundle.observed_geometry
    }

    def source_ids_for_segment(segment_id: str) -> tuple[str, ...]:
        parts = tuple(
            part
            for part in str(segment_id or "").split("+")
            if part
        )
        if not parts:
            return ()
        out: list[str] = []
        for part in parts:
            geometry = geometry_by_segment_id.get(part)
            if geometry is None:
                return ()
            matches = source_ids_by_geometry.get(geometry, ())
            if len(matches) != 1:
                return ()
            out.append(matches[0])
        return tuple(dict.fromkeys(out))

    observations = {
        observation.dimension_id: observation
        for observation in bundle.observations
    }
    positive: list[_TrustedBoundDimension] = []
    for binding in bundle.bindings:
        if (
            binding.status != BindingStatus.WITNESS_BOUND.value
            or binding.endpoints is None
            or not binding.dimension_line_id
            or len(binding.witness_line_ids) < 2
        ):
            continue
        observation = observations.get(binding.observation_id)
        if (
            observation is None
            or observation.bbox is None
            or observation.orientation
            not in {
                DimensionOrientation.HORIZONTAL.value,
                DimensionOrientation.VERTICAL.value,
            }
        ):
            continue

        trusted = trusted_by_bbox.get(_bbox_key(observation.bbox), ())
        if len(trusted) != 1:
            continue
        trusted_text, text_observation_id, text_receipt_id = trusted[0]
        try:
            parsed_mm = parse_figured_dimension_mm(trusted_text)
            observation_mm = float(observation.value_m) * 1000.0
        except (DimensionParseError, TypeError, ValueError):
            continue
        if abs(float(parsed_mm) - observation_mm) > 1e-6:
            continue

        dimension_line_ids = source_ids_for_segment(binding.dimension_line_id)
        if not dimension_line_ids:
            continue
        witness_ids: list[str] = []
        failed = False
        for witness_line_id in binding.witness_line_ids:
            mapped = source_ids_for_segment(witness_line_id)
            if not mapped:
                failed = True
                break
            witness_ids.extend(mapped)
        if failed or len(set(witness_ids)) < 2:
            continue

        endpoints = (
            (
                float(binding.endpoints[0][0]),
                float(binding.endpoints[0][1]),
            ),
            (
                float(binding.endpoints[1][0]),
                float(binding.endpoints[1][1]),
            ),
        )
        if not all(
            math.isfinite(value)
            for endpoint in endpoints
            for value in endpoint
        ):
            continue
        dimension_id = stable_contract_id(
            "cross_view_native_dimension",
            {
                "document_id": published.revision.document_id,
                "revision_id": published.revision.revision_id,
                "source_sha256": published.revision.source_sha256,
                "snapshot_id": published.snapshot.snapshot_id,
                "page_id": str(page_id),
                "text_observation_id": text_observation_id,
                "text_receipt_id": text_receipt_id,
                "value_mm": float(parsed_mm),
                "orientation": observation.orientation,
                "endpoints_pt": endpoints,
                "dimension_line_observation_ids": dimension_line_ids,
                "witness_observation_ids": tuple(sorted(set(witness_ids))),
            },
            digest_chars=32,
        )
        positive.append(
            _TrustedBoundDimension(
                dimension_id=dimension_id,
                text_observation_id=text_observation_id,
                text_receipt_id=text_receipt_id,
                value_mm=float(parsed_mm),
                orientation=str(observation.orientation),
                endpoints_pt=endpoints,
                dimension_line_observation_ids=dimension_line_ids,
                witness_observation_ids=tuple(sorted(set(witness_ids))),
            )
        )

    return tuple(
        sorted(
            positive,
            key=lambda item: (
                item.orientation,
                item.endpoints_pt,
                item.value_mm,
                item.dimension_id,
            ),
        )
    )

def _line_inside_dimension_pair(
    line: _TrustedLine,
    horizontal: _TrustedBoundDimension,
    vertical: _TrustedBoundDimension,
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
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("CrossViewRoomAreaProducer must be obtained from a classmethod")
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
    ) -> "CrossViewRoomAreaProducer":
        return cls(
            source=source,
            rooms=rooms,
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

        # Source decode coverage is already 1-based. Resolve trusted label
        # lines first and run the expensive dimension/OCR authority only on
        # source pages that can actually support a unique cross-view room
        # proposition. This is both fail-closed and important for large plan
        # sets with dozens or hundreds of irrelevant sheets.
        unique_labels = {
            label: grouped_rooms[0]
            for label, grouped_rooms in labels.items()
            if len(grouped_rooms) == 1
        }
        page_results: dict[str, tuple[_TrustedBoundDimension, ...]] = {}
        page_lines: dict[str, tuple[_TrustedLine, ...]] = {}
        for page_number in tuple(published.coverage.decoded_pages):
            page_id = str(int(page_number))
            trusted_lines = _trusted_lines_for_page(
                self._source,
                revision_id=revision_id,
                page_id=page_id,
            )
            relevant_lines = tuple(
                line
                for line in trusted_lines
                if (
                    _norm_label(line.text) in unique_labels
                    and str(unique_labels[_norm_label(line.text)].page_id)
                    != page_id
                )
            )
            if not relevant_lines:
                continue
            trusted_dimensions = _trusted_native_dimensions_for_page(
                self._source,
                revision_id=revision_id,
                page_id=page_id,
            )
            if not trusted_dimensions:
                continue
            page_results[page_id] = trusted_dimensions
            page_lines[page_id] = relevant_lines

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
                    str,
                    _TrustedBoundDimension,
                    _TrustedBoundDimension,
                ]
            ] = []
            for page_id, trusted_lines in sorted(page_lines.items()):
                if page_id == str(room.page_id):
                    continue
                trusted_dimensions = page_results[page_id]
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
                                        page_id,
                                        horizontal,
                                        vertical,
                                    )
                                )

            if len(matches) != 1:
                unresolved.add(str(room.physical_room_id))
                if len(matches) > 1:
                    conflict_seen = True
                continue

            line, dimension_page_id, horizontal, vertical = matches[0]
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
                    "dimension_page_id": dimension_page_id,
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
                    "source_dimension_page_id": str(dimension_page_id),
                    "source_dimension_snapshot_id": str(
                        published.snapshot.snapshot_id
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
                    source_dimension_page_id=str(dimension_page_id),
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
