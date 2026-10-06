"""Live source-owned physical external net-wall integration.

This is the extractor-facing composition seam for perimeter walling. It ingests
immutable PDF bytes through SourceVisibilityProducer, replays the complete
wall/opening authority chain, composes gross whole-wall geometry plus source-owned
whole-wall roles, and publishes physical external net wall area.

No caller-supplied wall ids, areas, counts, expected quantities, benchmark truth,
or trade deduction policy enters the numeric path.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Optional, Sequence

import fitz

from pb_canonical_building import CanonicalSpace
from pb_live_canonical_space_bridge import compose_live_canonical_spaces
from pb_live_canonical_floor_surface import (
    LiveCanonicalFloorSurfaceObject,
    compose_live_canonical_floor_surfaces,
    enrich_live_canonical_floor_metric_areas,
)
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomObject,
    compose_live_canonical_rooms,
)
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_external_physical_net_wall_publication import (
    LiveCanonicalWallObject,
    LiveExternalPhysicalNetWallPublication,
    compose_live_external_physical_net_wall_publication,
)
from pb_live_gross_wall_geometry_composition import compose_live_gross_wall_geometry
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    compose_live_physical_opening_voids,
)
from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_opening_count_quantity_publication import (
    publish_live_authenticated_opening_count_quantities,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_live_whole_wall_role_composition import compose_live_whole_wall_roles
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_scale_authority import (
    PHYSICAL_SCALE_VIEWPORT_REQUIRED,
    PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE,
    PhysicalScaleProducer,
    PhysicalScaleSelector,
)
from pb_physical_scale_calibration_bridge import build_physical_scale_calibration
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_area_bridge import build_source_room_area_bridge
from pb_source_room_face_authority import SourceRoomFaceSelector
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION = "1.3.0"
LIVE_PHYSICAL_NET_WALL_INTEGRATION_RESOLVED = (
    "live_physical_net_wall_integration_resolved"
)
LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE = (
    "live_physical_net_wall_integration_unavailable"
)


@dataclass(frozen=True)
class LivePhysicalNetWallClaim:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    quantity_m2: Optional[float]
    source_pages: tuple[int, ...]
    canonical_walls: tuple[LiveCanonicalWallObject, ...]
    canonical_wall_status: EvidenceResolutionStatus
    canonical_wall_reason_codes: tuple[str, ...]
    canonical_wall_source_pages: tuple[int, ...]
    unresolved_wall_candidate_ids: tuple[str, ...]
    canonical_openings: tuple[LiveCanonicalOpeningObject, ...]
    canonical_rooms: tuple[LiveCanonicalRoomObject, ...]
    canonical_floors: tuple[LiveCanonicalFloorSurfaceObject, ...]
    canonical_floor_status: EvidenceResolutionStatus
    canonical_floor_reason_codes: tuple[str, ...]
    canonical_floor_source_pages: tuple[int, ...]
    canonical_room_status: EvidenceResolutionStatus
    canonical_room_reason_codes: tuple[str, ...]
    canonical_room_source_pages: tuple[int, ...]
    external_wall_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    quantity_id: Optional[str]
    confidence: float
    publication: LiveExternalPhysicalNetWallPublication
    canonical_spaces: tuple[CanonicalSpace, ...] = ()
    canonical_space_status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED
    canonical_space_reason_codes: tuple[str, ...] = ()
    opening_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    opening_count_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    room_area_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    schema_version: str = LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION


def _selected_page_indices(
    page_count: int,
    pages: Optional[Sequence[int]],
) -> tuple[int, ...]:
    if pages is None:
        return tuple(range(page_count))
    selected = tuple(
        sorted(
            {
                int(page)
                for page in pages
                if isinstance(page, int) and 0 <= int(page) < page_count
            }
        )
    )
    if not selected:
        raise ValueError("pages must select at least one valid PDF page")
    return selected


def collect_live_physical_net_wall_claim(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
    topology_pages: Optional[Sequence[int]] = None,
    room_area_support_pages: Optional[Sequence[int]] = None,
) -> LivePhysicalNetWallClaim:
    """Run the complete source-owned physical external wall chain for one PDF.

    ``pages`` is the decoded evidence universe. ``topology_pages`` defaults to
    all selected pages and, when supplied, must be a non-empty subset whose
    linework may mint walls, openings, rooms and canonical objects.
    """

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        page_count = int(doc.page_count)
        selected = _selected_page_indices(page_count, pages)
        if topology_pages is None:
            topology_selected = selected
        else:
            topology_selected = _selected_page_indices(
                page_count, topology_pages
            )
            if not set(topology_selected) <= set(selected):
                raise ValueError("topology_pages must be a subset of pages")
        if room_area_support_pages is None:
            room_area_support_selected: tuple[int, ...] = ()
        else:
            room_area_support_selected = _selected_page_indices(
                page_count,
                room_area_support_pages,
            )
        decoded_selected = tuple(
            sorted(set(selected) | set(room_area_support_selected))
        )
        page_extents = {
            str(index + 1): (
                float(doc[index].rect.width),
                float(doc[index].rect.height),
            )
            for index in topology_selected
        }
    finally:
        doc.close()

    selected_page_ids = tuple(str(index + 1) for index in selected)
    decoded_page_ids = tuple(str(index + 1) for index in decoded_selected)
    topology_page_ids = tuple(
        str(index + 1) for index in topology_selected
    )
    evidence_page_ids = tuple(
        page_id
        for page_id in selected_page_ids
        if page_id not in topology_page_ids
    )
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=decoded_page_ids,
    )

    try:
        wall_opening = compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=published.revision.revision_id,
            page_ids=topology_page_ids,
            evidence_page_ids=evidence_page_ids,
        )
    except Exception as exc:
        from pb_live_wall_opening_authority_composition import (
            LiveWallOpeningScopeComplexityExceeded,
        )

        if not isinstance(exc, LiveWallOpeningScopeComplexityExceeded):
            raise
        reason = str(exc) or LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE
        publication = LiveExternalPhysicalNetWallPublication(
            revision_id=published.revision.revision_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(reason,),
            quantity_evidence=None,
            canonical_walls=(),
            external_wall_ids=(),
            gross_geometry_record_ids=(),
            whole_wall_role_record_ids=(),
            physical_void_record_ids=(),
            opening_universe_record_ids=(),
        )
        return LivePhysicalNetWallClaim(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(
                LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE,
                reason,
            ),
            quantity_m2=None,
            source_pages=(),
            canonical_walls=(),
            canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
            canonical_wall_reason_codes=(reason,),
            canonical_wall_source_pages=(),
            unresolved_wall_candidate_ids=(),
            canonical_openings=(),
            canonical_rooms=(),
            canonical_floors=(),
            canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
            canonical_floor_reason_codes=(reason,),
            canonical_floor_source_pages=(),
            canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
            canonical_room_reason_codes=(reason,),
            canonical_room_source_pages=(),
            external_wall_ids=(),
            evidence_ids=(),
            quantity_id=None,
            confidence=0.0,
            publication=publication,
        )
    canonical_wall_core = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    canonical_rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=(
            canonical_wall_core.candidate_to_canonical_wall_id
        ),
        unresolved_wall_candidate_ids=(
            canonical_wall_core.unresolved_wall_candidate_ids
        ),
    )
    canonical_space_core = compose_live_canonical_spaces(canonical_rooms)
    canonical_floors = compose_live_canonical_floor_surfaces(
        canonical_rooms
    )

    room_area_quantity_evidence: list[QuantityEvidence] = []
    if canonical_rooms.rooms:
        evidence_by_record = {}
        if room_area_support_selected:
            cross_view_area = CrossViewRoomAreaProducer.from_source(
                source=source,
                rooms=canonical_rooms,
            ).publish()
            if cross_view_area.records:
                evidence_by_record = dict(
                    cross_view_area.evidence_by_source_room_face_record_id
                )

        scale_producer = PhysicalScaleProducer.from_source_visibility_producer(
            source
        )
        rooms_by_scope: dict[
            tuple[str, str, str], list[LiveCanonicalRoomObject]
        ] = {}
        for room in canonical_rooms.rooms:
            rooms_by_scope.setdefault(
                (
                    str(room.page_id),
                    str(room.snapshot_id),
                    str(room.decision_scope_id),
                ),
                [],
            ).append(room)

        for (page_id, snapshot_id, decision_scope_id), scope_rooms in sorted(
            rooms_by_scope.items()
        ):
            try:
                page_no = int(page_id)
            except (TypeError, ValueError):
                continue
            extent = page_extents.get(page_id)
            if extent is None:
                continue

            room_binding = canonical_rooms.room_face_authority_binding_for(
                scope_rooms[0]
            )
            if room_binding is None or any(
                canonical_rooms.room_face_authority_binding_for(room)
                is not room_binding
                for room in scope_rooms[1:]
            ):
                continue
            room_face_authority = room_binding.authority

            selector = SourceRoomFaceSelector(
                document_id=scope_rooms[0].document_id,
                revision_id=scope_rooms[0].revision_id,
                source_sha256=scope_rooms[0].source_sha256,
                snapshot_id=snapshot_id,
                page_id=page_id,
                decision_scope_id=decision_scope_id,
            )
            room_scope = room_face_authority.resolve_scope(selector)
            if (
                room_scope.status is not EvidenceResolutionStatus.CORROBORATED
                or not room_scope.records
            ):
                continue

            face_id_by_record = {
                str(record.record_id): str(record.face_id)
                for record in room_scope.records
            }
            matching_evidence = {
                str(room.source_room_face_record_id): evidence_by_record[
                    str(room.source_room_face_record_id)
                ]
                for room in scope_rooms
                if str(room.source_room_face_record_id) in evidence_by_record
            }
            explicit_by_face_id = {
                face_id_by_record[record_id]: evidence
                for record_id, evidence in matching_evidence.items()
                if record_id in face_id_by_record
            }

            if (
                room_binding.viewport_id is not None
                and room_binding.viewport_bbox is not None
            ):
                viewport_id = str(room_binding.viewport_id)
                viewport_bbox = tuple(
                    float(value) for value in room_binding.viewport_bbox
                )
                viewport_status = ViewportResolutionStatus.RESOLVED
                viewport_reason_codes = (
                    "producer_owned_room_face_viewport_scope",
                )
                scale_viewport_id = viewport_id
            else:
                viewport_id = stable_contract_id(
                    "room_area_page_scope",
                    {
                        "document_id": scope_rooms[0].document_id,
                        "page_id": page_id,
                        "decision_scope_id": decision_scope_id,
                    },
                    digest_chars=24,
                )
                viewport_bbox = (0.0, 0.0, extent[0], extent[1])
                viewport_status = ViewportResolutionStatus.DERIVED
                viewport_reason_codes = (
                    "producer_owned_full_page_room_area_scope",
                )
                scale_viewport_id = None

            viewport = ViewportEvidence(
                viewport_id=viewport_id,
                document_id=scope_rooms[0].document_id,
                page_id=page_id,
                bbox=viewport_bbox,
                view_type=DrawingViewType.FLOOR_PLAN.value,
                status=viewport_status,
                evidence_ids=(),
                confidence=1.0,
                reason_codes=viewport_reason_codes,
            )
            context = ProviderContext(
                run_id=stable_contract_id(
                    "live_room_area_run",
                    {
                        "document_id": scope_rooms[0].document_id,
                        "revision_id": scope_rooms[0].revision_id,
                        "snapshot_id": snapshot_id,
                        "page_id": page_id,
                        "decision_scope_id": decision_scope_id,
                    },
                ),
                workspace_id="live-extractor",
                project_id="live-extractor",
                document_id=scope_rooms[0].document_id,
                source_sha256=scope_rooms[0].source_sha256,
                revision_id=scope_rooms[0].revision_id,
                current_revision_id=scope_rooms[0].revision_id,
                selected_pages=(page_no - 1,),
                owned_viewport_ids=(viewport_id,),
                evidence_snapshot_id=snapshot_id,
                owned_page_numbers=(page_no,),
                viewport_page_ownership=((viewport_id, page_no),),
            )
            document = DocumentEvidence(
                document_id=scope_rooms[0].document_id,
                source_sha256=scope_rooms[0].source_sha256,
                page_count=page_count,
                evidence_ids=(),
                producer="live-physical-net-wall",
                producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
            )

            scale_calibration = None
            scale_selector = PhysicalScaleSelector(
                document_id=scope_rooms[0].document_id,
                revision_id=scope_rooms[0].revision_id,
                source_sha256=scope_rooms[0].source_sha256,
                snapshot_id=snapshot_id,
                page_id=page_id,
                viewport_id=scale_viewport_id,
            )
            scale_result = scale_producer.publish_scope(scale_selector)
            selected_scale_selector = scale_selector

            # Page-wide room geometry may coexist with one authenticated
            # drawing viewport. PhysicalScaleAuthority correctly refuses a
            # page-wide calibration in that case. Bridge only through the
            # existing producer-owned floor-plan viewport universe when there
            # is exactly one corroborated viewport whose bbox fully contains
            # every room polygon in this exact room scope.
            if (
                scale_viewport_id is None
                and scale_result.reason_codes == (
                    PHYSICAL_SCALE_VIEWPORT_REQUIRED,
                )
            ):
                viewport_wall_producer = (
                    PhysicalWallCandidateProducer.from_authenticated_viewports(
                        source,
                        page_ids=(page_id,),
                    )
                )
                viewport_wall_authority = viewport_wall_producer.authority()
                viewport_selectors = (
                    viewport_wall_authority.selectors_for_authenticated_viewports(
                        document_id=scope_rooms[0].document_id,
                        revision_id=scope_rooms[0].revision_id,
                        source_sha256=scope_rooms[0].source_sha256,
                        snapshot_id=snapshot_id,
                        page_id=page_id,
                        view_type=DrawingViewType.FLOOR_PLAN.value,
                    )
                )
                containing_viewports = []
                for viewport_wall_selector in viewport_selectors:
                    viewport_wall_scope = viewport_wall_authority.resolve_scope(
                        viewport_wall_selector
                    )
                    bbox = getattr(viewport_wall_scope, "viewport_bbox", None)
                    viewport_candidate_id = getattr(
                        viewport_wall_scope, "viewport_id", None
                    )
                    if (
                        viewport_wall_scope.status
                        is not EvidenceResolutionStatus.CORROBORATED
                        or not viewport_candidate_id
                        or bbox is None
                    ):
                        continue
                    try:
                        x0, y0, x1, y1 = tuple(float(value) for value in bbox)
                    except (TypeError, ValueError):
                        continue
                    if x1 <= x0 or y1 <= y0:
                        continue
                    if all(
                        all(
                            x0 <= float(point[0]) <= x1
                            and y0 <= float(point[1]) <= y1
                            for point in room.polygon_pdf_pts
                        )
                        for room in scope_rooms
                    ):
                        containing_viewports.append(str(viewport_candidate_id))
                if len(set(containing_viewports)) == 1:
                    resolved_viewport_id = next(iter(set(containing_viewports)))
                    selected_scale_selector = PhysicalScaleSelector(
                        document_id=scope_rooms[0].document_id,
                        revision_id=scope_rooms[0].revision_id,
                        source_sha256=scope_rooms[0].source_sha256,
                        snapshot_id=snapshot_id,
                        page_id=page_id,
                        viewport_id=resolved_viewport_id,
                    )
                    scale_result = scale_producer.publish_scope(
                        selected_scale_selector
                    )

            if scale_result.reason_codes == (
                PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE,
            ):
                page_scale_selector = PhysicalScaleSelector(
                    document_id=scope_rooms[0].document_id,
                    revision_id=scope_rooms[0].revision_id,
                    source_sha256=scope_rooms[0].source_sha256,
                    snapshot_id=snapshot_id,
                    page_id=page_id,
                    viewport_id=None,
                )
                scale_result = scale_producer.publish_scope(page_scale_selector)
                selected_scale_selector = page_scale_selector

            if scale_result.status is EvidenceResolutionStatus.CORROBORATED:
                scale_bridge = build_physical_scale_calibration(
                    physical_scale_authority=scale_producer.authority(),
                    selector=selected_scale_selector,
                    context=context,
                    viewport=viewport,
                    page_no=page_no,
                )
                if (
                    scale_bridge.status is EvidenceResolutionStatus.CORROBORATED
                    and scale_bridge.calibration is not None
                ):
                    scale_calibration = scale_bridge.calibration

            if not explicit_by_face_id and scale_calibration is None:
                continue

            bridge = build_source_room_area_bridge(
                room_face_authority=room_face_authority,
                selector=selector,
                context=context,
                document=document,
                viewport=viewport,
                page_no=page_no,
                scale_calibration=scale_calibration,
                explicit_area_evidence_by_room_id=(
                    explicit_by_face_id if explicit_by_face_id else None
                ),
            )
            canonical_floors = enrich_live_canonical_floor_metric_areas(
                canonical_floors,
                bridge,
            )
            room_area_quantity_evidence.extend(bridge.quantities)

    physical_void = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    opening_quantity_evidence = publish_live_opening_area_quantities(
        physical_void
    )
    opening_count_quantity_evidence = (
        publish_live_authenticated_opening_count_quantities(
            source_visibility_producer=source,
            wall_opening_composition=wall_opening,
        )
    )
    gross = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )
    roles = compose_live_whole_wall_roles(
        gross_wall_composition=gross,
    )
    publication = compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        gross_wall_composition=gross,
        whole_wall_role_composition=roles,
    )

    canonical_walls_by_id = {
        wall.canonical_wall_id: wall for wall in canonical_wall_core.walls
    }
    for wall in publication.canonical_walls:
        canonical_walls_by_id[wall.canonical_wall_id] = wall
    canonical_walls = tuple(
        canonical_walls_by_id[wall_id]
        for wall_id in sorted(canonical_walls_by_id)
    )

    evidence = publication.quantity_evidence
    if (
        publication.status is EvidenceResolutionStatus.CORROBORATED
        and evidence is not None
        and evidence.value is not None
        and not evidence.abstained
        and evidence.status == "corroborated"
    ):
        source_pages = tuple(
            sorted(
                {
                    int(gross.gross_selectors[wall_id].page_id)
                    for wall_id in publication.external_wall_ids
                    if wall_id in gross.gross_selectors
                    and str(gross.gross_selectors[wall_id].page_id).isdigit()
                }
            )
        )
        return LivePhysicalNetWallClaim(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(
                LIVE_PHYSICAL_NET_WALL_INTEGRATION_RESOLVED,
                *publication.reason_codes,
            ),
            quantity_m2=float(evidence.value),
            source_pages=source_pages,
            canonical_walls=canonical_walls,
            canonical_wall_status=canonical_wall_core.status,
            canonical_wall_reason_codes=canonical_wall_core.reason_codes,
            canonical_wall_source_pages=canonical_wall_core.source_pages,
            unresolved_wall_candidate_ids=(
                canonical_wall_core.unresolved_wall_candidate_ids
            ),
            canonical_openings=physical_void.canonical_openings,
            canonical_rooms=canonical_rooms.rooms,
            canonical_floors=canonical_floors.floors,
            canonical_floor_status=canonical_floors.status,
            canonical_floor_reason_codes=canonical_floors.reason_codes,
            canonical_floor_source_pages=canonical_floors.source_pages,
            canonical_room_status=canonical_rooms.status,
            canonical_room_reason_codes=canonical_rooms.reason_codes,
            canonical_room_source_pages=canonical_rooms.source_pages,
            external_wall_ids=publication.external_wall_ids,
            evidence_ids=tuple(evidence.evidence_ids),
            quantity_id=evidence.quantity_id,
            confidence=float(evidence.confidence),
            publication=publication,
            canonical_spaces=canonical_space_core.spaces,
            canonical_space_status=canonical_space_core.status,
            canonical_space_reason_codes=canonical_space_core.reason_codes,
            opening_quantity_evidence=opening_quantity_evidence,
            opening_count_quantity_evidence=opening_count_quantity_evidence,
            room_area_quantity_evidence=tuple(room_area_quantity_evidence),
        )

    return LivePhysicalNetWallClaim(
        status=publication.status,
        reason_codes=(
            LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE,
            *publication.reason_codes,
        ),
        quantity_m2=None,
        source_pages=(),
        canonical_walls=canonical_walls,
        canonical_wall_status=canonical_wall_core.status,
        canonical_wall_reason_codes=canonical_wall_core.reason_codes,
        canonical_wall_source_pages=canonical_wall_core.source_pages,
        unresolved_wall_candidate_ids=(
            canonical_wall_core.unresolved_wall_candidate_ids
        ),
        canonical_openings=physical_void.canonical_openings,
        canonical_rooms=canonical_rooms.rooms,
        canonical_floors=canonical_floors.floors,
        canonical_floor_status=canonical_floors.status,
        canonical_floor_reason_codes=canonical_floors.reason_codes,
        canonical_floor_source_pages=canonical_floors.source_pages,
        canonical_room_status=canonical_rooms.status,
        canonical_room_reason_codes=canonical_rooms.reason_codes,
        canonical_room_source_pages=canonical_rooms.source_pages,
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=publication,
        canonical_spaces=canonical_space_core.spaces,
        canonical_space_status=canonical_space_core.status,
        canonical_space_reason_codes=canonical_space_core.reason_codes,
        opening_quantity_evidence=opening_quantity_evidence,
        opening_count_quantity_evidence=opening_count_quantity_evidence,
        room_area_quantity_evidence=tuple(room_area_quantity_evidence),
    )


__all__ = [
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_RESOLVED",
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION",
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE",
    "LivePhysicalNetWallClaim",
    "collect_live_physical_net_wall_claim",
]
