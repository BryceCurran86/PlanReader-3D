"""Authenticated internal-elevation -> source room-facing wall-face mapping.

This authority composes existing producer-owned evidence; it does not discover
walls, rooms, elevations, finishes, or quantities itself.

Positive path:
source-backed cross-sheet registration
-> exact authenticated source physical wall
-> complete authenticated source room-face universe
-> the registration callout lies strictly inside exactly one room face bounded
   by that wall
-> the independently registered target wall belongs wholly to exactly one
   authenticated ELEVATION viewport
-> room-facing physical-face mapping.

Caller input addresses the source wall only. It never chooses a room face or an
elevation target. No nearest-room, nearest-wall, page-title default, or quantity
publication path exists here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_cross_sheet_callout_evidence import find_callout_references
from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationSelector,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_source_room_face_authority import (
    SourceRoomFaceAuthority,
    SourceRoomFaceSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

INTERNAL_ELEVATION_WALL_FACE_SCHEMA_VERSION = "1.0.0"

INTERNAL_ELEVATION_WALL_FACE_RESOLVED = "internal_elevation_wall_face_resolved"
INTERNAL_ELEVATION_WALL_FACE_UNAVAILABLE = "internal_elevation_wall_face_unavailable"
INTERNAL_ELEVATION_CROSS_SHEET_UNRESOLVED = "internal_elevation_cross_sheet_unresolved"
INTERNAL_ELEVATION_SOURCE_WALL_UNRESOLVED = "internal_elevation_source_wall_unresolved"
INTERNAL_ELEVATION_ROOM_FACE_UNIVERSE_INCOMPLETE = (
    "internal_elevation_room_face_universe_incomplete"
)
INTERNAL_ELEVATION_ROOM_FACE_UNRESOLVED = "internal_elevation_room_face_unresolved"
INTERNAL_ELEVATION_ROOM_FACE_AMBIGUOUS = "internal_elevation_room_face_ambiguous"
INTERNAL_ELEVATION_CALLOUT_UNRESOLVED = "internal_elevation_callout_unresolved"
INTERNAL_ELEVATION_TARGET_WALL_UNRESOLVED = "internal_elevation_target_wall_unresolved"
INTERNAL_ELEVATION_VIEWPORT_UNRESOLVED = "internal_elevation_viewport_unresolved"
INTERNAL_ELEVATION_TARGET_NOT_ELEVATION = "internal_elevation_target_not_elevation"
INTERNAL_ELEVATION_SOURCE_INTEGRITY_FAILURE = "internal_elevation_source_integrity_failure"
INTERNAL_ELEVATION_LINEAGE_MISMATCH = "internal_elevation_lineage_mismatch"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class InternalElevationWallFaceSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    source_page_id: str
    target_page_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "source_page_id",
            "target_page_id",
            "physical_wall_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.source_page_id,
            self.target_page_id,
            self.physical_wall_id,
        )


@dataclass(frozen=True)
class InternalElevationWallFaceRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    source_page_id: str
    target_page_id: str
    physical_wall_id: str
    physical_face_id: str
    physical_wall_decision_scope_id: str
    source_room_face_id: str
    source_room_face_record_id: str
    target_physical_wall_id: str
    target_viewport_id: str
    target_view_type: str
    cross_sheet_registration_record_id: str
    callout_mark: str
    referenced_sheet_code: str
    callout_evidence_id: str
    physical_face_role: str = "room_facing_interior_face"
    schema_version: str = INTERNAL_ELEVATION_WALL_FACE_SCHEMA_VERSION


@dataclass(frozen=True)
class InternalElevationWallFaceResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[InternalElevationWallFaceRecord] = None
    schema_version: str = INTERNAL_ELEVATION_WALL_FACE_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra: str,
) -> InternalElevationWallFaceResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return InternalElevationWallFaceResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(r for r in extra if r)])),
        record=None,
    )


def _point_on_segment(
    point: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
    *,
    tolerance: float = 1e-7,
) -> bool:
    px, py = point
    ax, ay = first
    bx, by = second
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 <= tolerance * tolerance:
        return False
    cross = abs((px - ax) * dy - (py - ay) * dx)
    if cross > tolerance * max(1.0, length2 ** 0.5):
        return False
    dot = (px - ax) * dx + (py - ay) * dy
    return -tolerance <= dot <= length2 + tolerance


def _strict_point_in_polygon(
    point: tuple[float, float],
    polygon: Sequence[Sequence[float]],
) -> bool:
    """Strict interior test: boundary contact is not room-side authority."""
    pts = tuple((float(p[0]), float(p[1])) for p in polygon)
    if len(pts) < 3:
        return False
    for first, second in zip(pts, (*pts[1:], pts[0])):
        if _point_on_segment(point, first, second):
            return False

    x, y = point
    inside = False
    for first, second in zip(pts, (*pts[1:], pts[0])):
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) == (y2 > y):
            continue
        x_cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        if x_cross > x:
            inside = not inside
    return inside


def _bbox_center(bbox: Sequence[float]) -> tuple[float, float]:
    return (
        (float(bbox[0]) + float(bbox[2])) / 2.0,
        (float(bbox[1]) + float(bbox[3])) / 2.0,
    )


def _canonical_polygon_identity(
    polygon: Sequence[Sequence[float]],
) -> tuple[tuple[float, float], ...]:
    """Canonicalize one already-authenticated room polygon for side identity.

    Vertex start/order is representation detail, not physical identity.
    """
    points = tuple(
        (round(float(point[0]), 6), round(float(point[1]), 6))
        for point in polygon
    )
    if len(points) < 3:
        return ()
    variants = []
    for start in range(len(points)):
        variants.append(
            tuple(points[(start + offset) % len(points)] for offset in range(len(points)))
        )
        variants.append(
            tuple(points[(start - offset) % len(points)] for offset in range(len(points)))
        )
    return min(variants)


def _room_side_identity(record: object) -> str:
    polygon = _canonical_polygon_identity(
        tuple(getattr(record, "polygon_pdf_pts", ()) or ())
    )
    if not polygon:
        return ""
    return stable_contract_id(
        "physical_room_side",
        {
            "document_id": str(getattr(record, "document_id", "") or ""),
            "page_id": str(getattr(record, "page_id", "") or ""),
            "polygon_pdf_pts": polygon,
        },
        digest_chars=32,
    )


def _candidate_aliases(record: object) -> tuple[str, ...]:
    identity = getattr(record, "physical_identity", None)
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in (
                    getattr(record, "wall_candidate_id", ""),
                    getattr(identity, "physical_wall_id", ""),
                    getattr(identity, "candidate_identity_id", ""),
                )
                if str(value or "").strip()
            }
        )
    )


def _candidate_bbox(record: object) -> Optional[tuple[float, float, float, float]]:
    candidate = getattr(record, "wall_candidate", None)
    points = tuple(getattr(candidate, "centerline_pts", ()) or ())
    if len(points) < 2:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_fully_inside(
    inner: Sequence[float],
    outer: Sequence[float],
) -> bool:
    return (
        float(outer[0]) <= float(inner[0])
        and float(outer[1]) <= float(inner[1])
        and float(outer[2]) >= float(inner[2])
        and float(outer[3]) >= float(inner[3])
    )


class InternalElevationWallFaceAuthority:
    def __init__(
        self,
        results: Mapping[_Key, InternalElevationWallFaceResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("InternalElevationWallFaceAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: InternalElevationWallFaceSelector,
    ) -> InternalElevationWallFaceResult:
        if type(selector) is not InternalElevationWallFaceSelector:
            raise TypeError("selector must be InternalElevationWallFaceSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                INTERNAL_ELEVATION_WALL_FACE_UNAVAILABLE,
            ),
        )


class InternalElevationWallFaceProducer:
    def __init__(
        self,
        *,
        cross_sheet_authority: CrossSheetRegistrationAuthority,
        physical_wall_authority: PhysicalWallCandidateAuthority,
        room_face_authority: SourceRoomFaceAuthority,
        source_visibility_producer: SourceVisibilityProducer,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "InternalElevationWallFaceProducer must be obtained via from_authorities()"
            )
        if type(cross_sheet_authority) is not CrossSheetRegistrationAuthority:
            raise TypeError("cross_sheet_authority must be producer-owned")
        if type(physical_wall_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_authority must be producer-owned")
        if type(room_face_authority) is not SourceRoomFaceAuthority:
            raise TypeError("room_face_authority must be producer-owned")
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._cross_sheet = cross_sheet_authority
        self._walls = physical_wall_authority
        self._rooms = room_face_authority
        self._source = source_visibility_producer
        self._results: dict[_Key, InternalElevationWallFaceResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        cross_sheet_authority: CrossSheetRegistrationAuthority,
        physical_wall_authority: PhysicalWallCandidateAuthority,
        room_face_authority: SourceRoomFaceAuthority,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "InternalElevationWallFaceProducer":
        return cls(
            cross_sheet_authority=cross_sheet_authority,
            physical_wall_authority=physical_wall_authority,
            room_face_authority=room_face_authority,
            source_visibility_producer=source_visibility_producer,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> InternalElevationWallFaceAuthority:
        return InternalElevationWallFaceAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: InternalElevationWallFaceSelector,
        result: InternalElevationWallFaceResult,
    ) -> InternalElevationWallFaceResult:
        self._results[selector.key] = result
        return result

    def _source_bytes(
        self,
        selector: InternalElevationWallFaceSelector,
    ) -> Optional[bytes]:
        published = self._source.published_snapshot_for_revision(selector.revision_id)
        if published is None:
            return None
        if (
            published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or self._source._producer.current_revision_id(selector.document_id)
            != selector.revision_id
        ):
            return None
        source_bytes = self._source._producer._store.source_bytes_by_revision.get(
            selector.revision_id
        )
        if source_bytes is None:
            return None
        if hashlib.sha256(source_bytes).hexdigest() != selector.source_sha256:
            raise RuntimeError(INTERNAL_ELEVATION_SOURCE_INTEGRITY_FAILURE)
        return bytes(source_bytes)

    def _wall_scope(
        self,
        selector: InternalElevationWallFaceSelector,
        page_id: str,
    ):
        wall_selector = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        return self._walls.resolve_scope(wall_selector)

    def publish(
        self,
        selector: InternalElevationWallFaceSelector,
    ) -> InternalElevationWallFaceResult:
        if type(selector) is not InternalElevationWallFaceSelector:
            raise TypeError("selector must be InternalElevationWallFaceSelector")

        cross_selector = CrossSheetRegistrationSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            source_page_id=selector.source_page_id,
            target_page_id=selector.target_page_id,
            physical_element_id=selector.physical_wall_id,
        )
        cross = self._cross_sheet.resolve(cross_selector)
        if (
            cross.status is not EvidenceResolutionStatus.CORROBORATED
            or cross.record is None
        ):
            return self._store(
                selector,
                _blocked(
                    cross.status,
                    INTERNAL_ELEVATION_CROSS_SHEET_UNRESOLVED,
                    *cross.reason_codes,
                ),
            )
        registration = cross.record
        if (
            registration.document_id != selector.document_id
            or registration.revision_id != selector.revision_id
            or registration.source_sha256 != selector.source_sha256
            or registration.snapshot_id != selector.snapshot_id
            or registration.source_page_id != selector.source_page_id
            or registration.target_page_id != selector.target_page_id
            or registration.physical_element_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    INTERNAL_ELEVATION_LINEAGE_MISMATCH,
                ),
            )

        source_scope = self._wall_scope(selector, selector.source_page_id)
        if (
            source_scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not source_scope.records
        ):
            return self._store(
                selector,
                _blocked(
                    source_scope.status,
                    INTERNAL_ELEVATION_SOURCE_WALL_UNRESOLVED,
                    *source_scope.reason_codes,
                ),
            )
        source_matches = [
            record
            for record in source_scope.records
            if selector.physical_wall_id in _candidate_aliases(record)
        ]
        if len(source_matches) != 1:
            status = (
                EvidenceResolutionStatus.CONFLICT
                if len(source_matches) > 1
                else EvidenceResolutionStatus.ABSTAINED
            )
            return self._store(
                selector,
                _blocked(status, INTERNAL_ELEVATION_SOURCE_WALL_UNRESOLVED),
            )
        wall_aliases = set(_candidate_aliases(source_matches[0]))

        room_selector = SourceRoomFaceSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.source_page_id,
            decision_scope_id=f"wall-source:page-{selector.source_page_id}",
        )
        room_scope = self._rooms.resolve_scope(room_selector)
        if not room_scope.face_universe_complete:
            return self._store(
                selector,
                _blocked(
                    room_scope.status,
                    INTERNAL_ELEVATION_ROOM_FACE_UNIVERSE_INCOMPLETE,
                    *room_scope.reason_codes,
                ),
            )

        source_bytes = self._source_bytes(selector)
        if source_bytes is None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    INTERNAL_ELEVATION_SOURCE_INTEGRITY_FAILURE,
                ),
            )

        try:
            source_page_num = int(selector.source_page_id)
            target_page_num = int(selector.target_page_id)
        except ValueError:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    INTERNAL_ELEVATION_CALLOUT_UNRESOLVED,
                ),
            )

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            if (
                source_page_num < 1
                or source_page_num > pdf.page_count
                or target_page_num < 1
                or target_page_num > pdf.page_count
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_CALLOUT_UNRESOLVED,
                    ),
                )
            source_page = pdf.load_page(source_page_num - 1)
            target_page = pdf.load_page(target_page_num - 1)

            matching_callouts = [
                callout
                for callout in find_callout_references(
                    source_page, page_num=source_page_num
                )
                if callout.mark == registration.callout_mark
                and callout.referenced_sheet_code
                == registration.referenced_sheet_code
            ]
            if len(matching_callouts) != 1:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_CALLOUT_UNRESOLVED,
                    ),
                )
            callout = matching_callouts[0]
            callout_center = _bbox_center(callout.callout_bbox)

            adjacent_room_faces = [
                room
                for room in room_scope.records
                if wall_aliases.intersection(room.bounding_wall_ids)
            ]
            if len(adjacent_room_faces) not in (1, 2):
                return self._store(
                    selector,
                    _blocked(
                        (
                            EvidenceResolutionStatus.CONFLICT
                            if len(adjacent_room_faces) > 2
                            else EvidenceResolutionStatus.ABSTAINED
                        ),
                        INTERNAL_ELEVATION_ROOM_FACE_UNRESOLVED,
                    ),
                )

            room_matches = [
                room
                for room in adjacent_room_faces
                if _strict_point_in_polygon(
                    callout_center,
                    room.polygon_pdf_pts,
                )
            ]
            if not room_matches:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_ROOM_FACE_UNRESOLVED,
                    ),
                )
            if len(room_matches) != 1:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        INTERNAL_ELEVATION_ROOM_FACE_AMBIGUOUS,
                    ),
                )
            source_room_face = room_matches[0]

            target_scope = self._wall_scope(selector, selector.target_page_id)
            if (
                target_scope.status is not EvidenceResolutionStatus.CORROBORATED
                or not target_scope.records
            ):
                return self._store(
                    selector,
                    _blocked(
                        target_scope.status,
                        INTERNAL_ELEVATION_TARGET_WALL_UNRESOLVED,
                        *target_scope.reason_codes,
                    ),
                )
            target_matches = [
                record
                for record in target_scope.records
                if registration.target_physical_element_id
                in _candidate_aliases(record)
            ]
            if len(target_matches) != 1:
                status = (
                    EvidenceResolutionStatus.CONFLICT
                    if len(target_matches) > 1
                    else EvidenceResolutionStatus.ABSTAINED
                )
                return self._store(
                    selector,
                    _blocked(status, INTERNAL_ELEVATION_TARGET_WALL_UNRESOLVED),
                )
            target_bbox = _candidate_bbox(target_matches[0])
            if target_bbox is None:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_TARGET_WALL_UNRESOLVED,
                    ),
                )

            viewports = tuple(
                segment_page_viewports(target_page, page_number=target_page_num)
            )
            if not viewports or any(
                not is_segment_page_viewports_product(viewport)
                for viewport in viewports
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_VIEWPORT_UNRESOLVED,
                    ),
                )
            sibling_non_overlapping = validate_non_overlapping_viewports(viewports)
            authoritative = tuple(
                viewport
                for viewport in viewports
                if viewport.bounding_box is not None
                and (
                    viewport.status == ViewportSegmentationStatus.RESOLVED.value
                    or (
                        sibling_non_overlapping
                        and is_authoritative_derived_viewport(viewport)
                    )
                )
            )
            owners = [
                viewport
                for viewport in authoritative
                if _bbox_fully_inside(target_bbox, viewport.bounding_box)
            ]
            if len(owners) != 1:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_VIEWPORT_UNRESOLVED,
                    ),
                )
            target_viewport = owners[0]
            if target_viewport.view_type != DrawingViewType.ELEVATION.value:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_TARGET_NOT_ELEVATION,
                    ),
                )
        finally:
            pdf.close()

        callout_payload = {
            "source_sha256": selector.source_sha256,
            "page_id": selector.source_page_id,
            "mark": callout.mark,
            "referenced_sheet_code": callout.referenced_sheet_code,
            "bbox": tuple(round(float(value), 6) for value in callout.callout_bbox),
        }
        callout_evidence_id = stable_contract_id(
            "internal_elevation_callout",
            callout_payload,
            digest_chars=32,
        )
        face_payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.source_page_id,
            "physical_wall_decision_scope_id": source_scope.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "physical_face_role": "room_facing_interior_face",
        }
        # One-room boundary walls retain the existing semantic-face identity so
        # this cross-view path remains compatible with direct source callouts.
        # A proven two-room divider has two distinct room-facing physical sides;
        # add a stable, revision-independent room-side discriminator only there.
        if len(adjacent_room_faces) == 2:
            room_side_identity = _room_side_identity(source_room_face)
            if not room_side_identity:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        INTERNAL_ELEVATION_ROOM_FACE_UNRESOLVED,
                    ),
                )
            face_payload["room_side_identity"] = room_side_identity
        physical_face_id = stable_contract_id(
            "physical_wall_semantic_face",
            face_payload,
            digest_chars=32,
        )
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "source_page_id": selector.source_page_id,
            "target_page_id": selector.target_page_id,
            "physical_wall_id": selector.physical_wall_id,
            "physical_face_id": physical_face_id,
            "physical_wall_decision_scope_id": source_scope.decision_scope_id,
            "source_room_face_id": source_room_face.face_id,
            "source_room_face_record_id": source_room_face.record_id,
            "target_physical_wall_id": registration.target_physical_element_id,
            "target_viewport_id": target_viewport.view_id,
            "target_view_type": target_viewport.view_type,
            "cross_sheet_registration_record_id": registration.record_id,
            "callout_mark": registration.callout_mark,
            "referenced_sheet_code": registration.referenced_sheet_code,
            "callout_evidence_id": callout_evidence_id,
        }
        record = InternalElevationWallFaceRecord(
            record_id=stable_contract_id(
                "internal_elevation_wall_face",
                payload,
                digest_chars=32,
            ),
            **payload,
        )
        return self._store(
            selector,
            InternalElevationWallFaceResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(INTERNAL_ELEVATION_WALL_FACE_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "INTERNAL_ELEVATION_CALLOUT_UNRESOLVED",
    "INTERNAL_ELEVATION_CROSS_SHEET_UNRESOLVED",
    "INTERNAL_ELEVATION_LINEAGE_MISMATCH",
    "INTERNAL_ELEVATION_ROOM_FACE_AMBIGUOUS",
    "INTERNAL_ELEVATION_ROOM_FACE_UNIVERSE_INCOMPLETE",
    "INTERNAL_ELEVATION_ROOM_FACE_UNRESOLVED",
    "INTERNAL_ELEVATION_SOURCE_INTEGRITY_FAILURE",
    "INTERNAL_ELEVATION_SOURCE_WALL_UNRESOLVED",
    "INTERNAL_ELEVATION_TARGET_NOT_ELEVATION",
    "INTERNAL_ELEVATION_TARGET_WALL_UNRESOLVED",
    "INTERNAL_ELEVATION_VIEWPORT_UNRESOLVED",
    "INTERNAL_ELEVATION_WALL_FACE_RESOLVED",
    "INTERNAL_ELEVATION_WALL_FACE_SCHEMA_VERSION",
    "INTERNAL_ELEVATION_WALL_FACE_UNAVAILABLE",
    "InternalElevationWallFaceAuthority",
    "InternalElevationWallFaceProducer",
    "InternalElevationWallFaceRecord",
    "InternalElevationWallFaceResult",
    "InternalElevationWallFaceSelector",
]
