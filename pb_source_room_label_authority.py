"""Source-owned room-label binding for already-proven canonical room geometry.

Text never creates or closes a room. This authority consumes only producer-owned
native word observations, requires native PdfTextIntegrity or independent raster
text corroboration, and spatially binds resulting room-label candidates to
existing room polygons. Ambiguous position or competing label text fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_room_face_takeoff import filter_room_label_candidates
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_room_faces import _point_in_polygon


SOURCE_ROOM_LABEL_SCHEMA_VERSION = "1.0.0"
SOURCE_ROOM_LABEL_RESOLVED = "source_room_label_resolved"
SOURCE_ROOM_LABEL_UNAVAILABLE = "source_room_label_unavailable"
SOURCE_ROOM_LABEL_POSITION_AMBIGUOUS = "source_room_label_position_ambiguous"
SOURCE_ROOM_LABEL_TEXT_CONFLICT = "source_room_label_text_conflict"


@dataclass(frozen=True)
class SourceRoomLabelBinding:
    room_id: str
    status: EvidenceResolutionStatus
    label: Optional[str]
    record_id: Optional[str]
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    schema_version: str = SOURCE_ROOM_LABEL_SCHEMA_VERSION


def _normalise_label(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _bbox_center(bbox: Sequence[float]) -> Optional[tuple[float, float]]:
    if len(bbox) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return None
    if x1 < x0 or y1 < y0:
        return None
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _rooms_for_point(
    point: tuple[float, float],
    rooms: Sequence[object],
) -> tuple[str, ...]:
    matched: list[str] = []
    for room in rooms:
        room_id = str(getattr(room, "canonical_room_id", "") or "")
        polygon = tuple(getattr(room, "polygon_pdf_pts", ()) or ())
        if room_id and polygon and _point_in_polygon(point, polygon):
            matched.append(room_id)
    return tuple(sorted(set(matched)))


def _line_candidates(
    source: SourceVisibilityProducer,
    *,
    published,
    page_id: str,
    rooms: Sequence[object],
) -> tuple[list[dict], set[str]]:
    """Authenticate source text and build room-scoped label candidates.

    Grouping is room-scoped as well as block/line-scoped. Words from two
    adjacent rooms can never be combined into one semantic label.
    """
    integrity = source.text_integrity_authority()
    raster_producer = None
    line_entries: dict[
        tuple[int, int, str],
        list[tuple[int, dict, tuple[str, ...]]],
    ] = {}
    unresolved_lines: set[tuple[int, int, str]] = set()
    ambiguous_rooms: set[str] = set()

    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        native = integrity.resolve_text(selector)
        receipt = native.receipt
        if receipt is None or str(receipt.page_id) != str(page_id):
            continue
        if (
            receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue

        point = _bbox_center(receipt.geometry)
        if point is None:
            continue
        room_ids = _rooms_for_point(point, rooms)
        if not room_ids:
            continue
        if len(room_ids) != 1:
            ambiguous_rooms.update(room_ids)
            continue
        room_id = room_ids[0]
        key = (int(receipt.block_no), int(receipt.line_no), room_id)

        text = None
        evidence_ids: tuple[str, ...] = (str(observation_id),)
        if (
            native.status is EvidenceResolutionStatus.CORROBORATED
            and str(native.trusted_text or "").strip()
        ):
            text = str(native.trusted_text).strip()
        else:
            if raster_producer is None:
                raster_producer = (
                    RasterTextCorroborationProducer.from_source_visibility_producer(
                        source
                    )
                )
            raster = raster_producer.publish(
                RasterTextCorroborationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=selector.observation_id,
                )
            )
            if (
                raster.status is EvidenceResolutionStatus.CORROBORATED
                and raster.record is not None
                and str(raster.corroborated_text or "").strip()
            ):
                text = str(raster.corroborated_text).strip()
                evidence_ids = (
                    str(observation_id),
                    str(raster.record.record_id),
                )

        if not text:
            unresolved_lines.add(key)
            continue

        line_entries.setdefault(key, []).append(
            (
                int(receipt.word_no),
                {
                    "text": text,
                    "bbox": tuple(float(value) for value in receipt.geometry),
                },
                evidence_ids,
            )
        )

    candidates: list[dict] = []
    for key in sorted(line_entries):
        if key in unresolved_lines:
            continue
        entries = sorted(line_entries[key], key=lambda item: item[0])
        word_numbers = [item[0] for item in entries]
        if len(word_numbers) != len(set(word_numbers)):
            continue

        line_words = [item[1] for item in entries]
        line_evidence = tuple(
            sorted(
                {
                    evidence_id
                    for _number, _word, evidence_ids in entries
                    for evidence_id in evidence_ids
                    if evidence_id
                }
            )
        )
        scoped_room_id = key[2]
        for candidate in filter_room_label_candidates(line_words):
            point = (float(candidate["x"]), float(candidate["y"]))
            room_ids = _rooms_for_point(point, rooms)
            if room_ids != (scoped_room_id,):
                ambiguous_rooms.update(room_ids)
                ambiguous_rooms.add(scoped_room_id)
                continue
            candidates.append(
                {
                    "room_id": scoped_room_id,
                    "label": str(candidate["label"]).strip(),
                    "evidence_ids": line_evidence,
                }
            )

    return candidates, ambiguous_rooms


def bind_source_room_labels(
    source_visibility_producer: SourceVisibilityProducer,
    rooms: Sequence[object],
) -> Mapping[str, SourceRoomLabelBinding]:
    """Bind authenticated source labels to existing room objects, fail closed."""
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")

    bindings: dict[str, SourceRoomLabelBinding] = {}
    by_scope: dict[tuple[str, str], list[object]] = {}
    for room in rooms:
        room_id = str(getattr(room, "canonical_room_id", "") or "")
        revision_id = str(getattr(room, "revision_id", "") or "")
        page_id = str(getattr(room, "page_id", "") or "")
        if not room_id or not revision_id or not page_id:
            continue
        by_scope.setdefault((revision_id, page_id), []).append(room)

    for (revision_id, page_id), scoped_rooms in sorted(by_scope.items()):
        published = source_visibility_producer.published_snapshot_for_revision(
            revision_id
        )
        if published is None:
            continue
        exact_rooms = [
            room
            for room in scoped_rooms
            if str(getattr(room, "document_id", "") or "")
            == published.revision.document_id
            and str(getattr(room, "source_sha256", "") or "")
            == published.revision.source_sha256
            and str(getattr(room, "snapshot_id", "") or "")
            == published.snapshot.snapshot_id
        ]
        if not exact_rooms:
            continue

        candidates, ambiguous_rooms = _line_candidates(
            source_visibility_producer,
            published=published,
            page_id=page_id,
            rooms=exact_rooms,
        )
        candidates_by_room: dict[str, list[dict]] = {}
        for candidate in candidates:
            candidates_by_room.setdefault(candidate["room_id"], []).append(
                candidate
            )

        for room in exact_rooms:
            room_id = str(room.canonical_room_id)
            if room_id in ambiguous_rooms:
                bindings[room_id] = SourceRoomLabelBinding(
                    room_id=room_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    label=None,
                    record_id=None,
                    evidence_ids=(),
                    reason_codes=(SOURCE_ROOM_LABEL_POSITION_AMBIGUOUS,),
                )
                continue

            by_label: dict[str, list[dict]] = {}
            for candidate in candidates_by_room.get(room_id, []):
                label = str(candidate.get("label") or "").strip()
                key = _normalise_label(label)
                if key:
                    by_label.setdefault(key, []).append(candidate)

            if not by_label:
                bindings[room_id] = SourceRoomLabelBinding(
                    room_id=room_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    label=None,
                    record_id=None,
                    evidence_ids=(),
                    reason_codes=(SOURCE_ROOM_LABEL_UNAVAILABLE,),
                )
                continue

            if len(by_label) != 1:
                evidence = tuple(
                    sorted(
                        {
                            evidence_id
                            for items in by_label.values()
                            for candidate in items
                            for evidence_id in candidate["evidence_ids"]
                        }
                    )
                )
                bindings[room_id] = SourceRoomLabelBinding(
                    room_id=room_id,
                    status=EvidenceResolutionStatus.CONFLICT,
                    label=None,
                    record_id=None,
                    evidence_ids=evidence,
                    reason_codes=(SOURCE_ROOM_LABEL_TEXT_CONFLICT,),
                )
                continue

            items = next(iter(by_label.values()))
            label = sorted(str(item["label"]).strip() for item in items)[0]
            evidence = tuple(
                sorted(
                    {
                        evidence_id
                        for item in items
                        for evidence_id in item["evidence_ids"]
                    }
                )
            )
            payload = {
                "room_id": room_id,
                "label": _normalise_label(label),
                "evidence_ids": evidence,
                "document_id": published.revision.document_id,
                "revision_id": published.revision.revision_id,
                "source_sha256": published.revision.source_sha256,
                "snapshot_id": published.snapshot.snapshot_id,
                "page_id": page_id,
            }
            bindings[room_id] = SourceRoomLabelBinding(
                room_id=room_id,
                status=EvidenceResolutionStatus.CORROBORATED,
                label=label,
                record_id=stable_contract_id(
                    "source_room_label_binding",
                    payload,
                    digest_chars=32,
                ),
                evidence_ids=evidence,
                reason_codes=(SOURCE_ROOM_LABEL_RESOLVED,),
            )

    return bindings


__all__ = [
    "SOURCE_ROOM_LABEL_POSITION_AMBIGUOUS",
    "SOURCE_ROOM_LABEL_RESOLVED",
    "SOURCE_ROOM_LABEL_SCHEMA_VERSION",
    "SOURCE_ROOM_LABEL_TEXT_CONFLICT",
    "SOURCE_ROOM_LABEL_UNAVAILABLE",
    "SourceRoomLabelBinding",
    "bind_source_room_labels",
]
