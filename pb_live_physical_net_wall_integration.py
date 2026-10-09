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
from typing import Mapping, Optional, Sequence

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
from pb_live_ceiling_lining_integration import LiveCanonicalCeilingSurfaceObject
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
from pb_cross_view_floor_finish_authority import (
    CrossViewFloorFinishProducer,
    enrich_live_canonical_floor_finishes,
)
from pb_cross_view_ceiling_finish_authority import CrossViewCeilingFinishProducer
from pb_cross_view_ceiling_quantity_authority import (
    publish_cross_view_ceiling_quantities,
)
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
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
    canonical_ceilings: tuple[LiveCanonicalCeilingSurfaceObject, ...] = ()
    canonical_space_status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED
    canonical_space_reason_codes: tuple[str, ...] = ()
    opening_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    opening_count_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    room_area_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    floor_finish_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    ceiling_lining_quantity_evidence: tuple[QuantityEvidence, ...] = ()
    # Source-authenticated same-view measurement first-gate receipts; a separate
    # cross-view or scaled authority may independently resolve the room area.
    same_view_room_area_first_failure_codes: tuple[tuple[str, str], ...] = ()
    # The support-sheet producer independently owns exact cross-view failures.
    cross_view_room_area_first_failure_codes: tuple[tuple[str, str], ...] = ()
    # Source-owned physical-scale failures are independent of documented area.
    # Each entry owns an exact physical-room ID and the scale producer's reasons.
    physical_scale_first_failure_codes: tuple[tuple[str, tuple[str, ...]], ...] = ()
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


def _unique_authenticated_containing_floor_plan_viewport(
    *,
    source: SourceVisibilityProducer,
    scope_rooms: Sequence[LiveCanonicalRoomObject],
    page_id: str,
    snapshot_id: str,
) -> Optional[tuple[str, tuple[float, float, float, float]]]:
    """Return one producer-owned floor-plan viewport that owns the whole room scope.

    Page-scoped room faces can be valid even when viewport segmentation was not
    needed to mint them. Downstream surface families, however, require exact
    viewport identity. Reuse that identity only when the existing authenticated
    viewport authority proves exactly one floor-plan viewport whose bounds
    contain every polygon in this room scope. Zero or multiple owners remain
    unresolved.
    """
    if not scope_rooms:
        return None
    first = scope_rooms[0]
    viewport_wall_producer = (
        PhysicalWallCandidateProducer.from_authenticated_viewports(
            source,
            page_ids=(str(page_id),),
        )
    )
    viewport_wall_authority = viewport_wall_producer.authority()
    selectors = viewport_wall_authority.selectors_for_authenticated_viewports(
        document_id=first.document_id,
        revision_id=first.revision_id,
        source_sha256=first.source_sha256,
        snapshot_id=str(snapshot_id),
        page_id=str(page_id),
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    containing: dict[str, tuple[float, float, float, float]] = {}
    for viewport_selector in selectors:
        scope = viewport_wall_authority.resolve_scope(viewport_selector)
        bbox = getattr(scope, "viewport_bbox", None)
        viewport_id = getattr(scope, "viewport_id", None)
        if (
            scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not viewport_id
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
            containing[str(viewport_id)] = (x0, y0, x1, y1)
    if len(containing) != 1:
        return None
    return next(iter(containing.items()))


def _merge_documented_room_area_evidence(
    *,
    same_view_by_record: dict[str, object],
    cross_view_by_record: dict[str, object],
) -> dict[str, object]:
    """Layer same-view room areas as fallback without regressing proven output.

    Cross-view figured-dimension authority predates same-view support and is
    independently source-owned. A newly-added same-view candidate must never
    erase an already-corroborated cross-view room area merely because the two
    producers selected different dimension annotations. Same-view evidence is
    therefore additive only for source-room records that have no cross-view
    record. This preserves fail-closed behavior inside each producer while
    preventing a supplemental authority from destroying valid existing output.
    """
    merged = {
        str(record_id): evidence
        for record_id, evidence in same_view_by_record.items()
        if evidence is not None
    }
    for record_id, evidence in cross_view_by_record.items():
        if evidence is not None:
            merged[str(record_id)] = evidence
    return {
        record_id: merged[record_id]
        for record_id in sorted(merged)
    }


def _uniquely_owned_explicit_area_by_source_face(
    *,
    source_face_records: Sequence[object],
    canonical_rooms: Sequence[LiveCanonicalRoomObject],
    evidence_by_source_record: Mapping[str, object],
) -> dict[str, object]:
    """Resolve figured area only through unique record, room and face ownership.

    SourceRoomFaceAuthority may expose several source records in one page scope.
    A direct {face_id: evidence} comprehension would silently select the last
    record if several documented source records mapped to the same physical
    face. A duplicated source record with competing face IDs or canonical room
    owners is equally ambiguous. Quarantine these claims rather than picking
    a stable-but-unproven winner. Identical source-record replays are harmless.
    """
    face_ids_by_record: dict[str, set[str]] = {}
    for record in source_face_records:
        record_id = str(record.record_id or "").strip()
        face_id = str(record.face_id or "").strip()
        if record_id and face_id:
            face_ids_by_record.setdefault(record_id, set()).add(face_id)

    rooms_by_record: dict[str, list[str]] = {}
    records_by_physical_room: dict[str, set[str]] = {}
    for room in canonical_rooms:
        record_id = str(room.source_room_face_record_id or "").strip()
        physical_id = str(room.physical_room_id or "").strip()
        if record_id and physical_id:
            # Competing face records for one physical room must invalidate
            # every claimant, including a record without figured-area evidence.
            # Do not let a unique face lookup conceal this identity conflict.
            records_by_physical_room.setdefault(physical_id, set()).add(
                record_id
            )
            if record_id in evidence_by_source_record:
                rooms_by_record.setdefault(record_id, []).append(physical_id)
    conflicting_physical_rooms = {
        physical_id
        for physical_id, record_ids in records_by_physical_room.items()
        if len(record_ids) != 1
    }

    claims_by_face: dict[str, list[tuple[str, object]]] = {}
    for record_id, owners in sorted(rooms_by_record.items()):
        if (
            len(owners) != 1
            or owners[0] in conflicting_physical_rooms
            or len(face_ids_by_record.get(record_id, ())) != 1
        ):
            continue
        face_id = next(iter(face_ids_by_record[record_id]))
        evidence = evidence_by_source_record[record_id]
        if evidence is not None:
            claims_by_face.setdefault(face_id, []).append((record_id, evidence))

    return {
        face_id: claims[0][1]
        for face_id, claims in sorted(claims_by_face.items())
        if len(claims) == 1
    }


def collect_live_physical_net_wall_claim(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
    topology_pages: Optional[Sequence[int]] = None,
    room_area_support_pages: Optional[Sequence[int]] = None,
    surface_semantic_pages: Optional[Sequence[int]] = None,
) -> LivePhysicalNetWallClaim:
    """Run the complete source-owned physical external wall chain for one PDF.

    ``pages`` is the decoded geometry/evidence universe. ``topology_pages``
    defaults to all selected pages and, when supplied, must be a non-empty subset
    whose linework may mint walls, openings, rooms and canonical objects.
    ``surface_semantic_pages`` is an optional independent source-only semantic
    scope for material/floor-finish/RCP binding. Those pages are never added to
    wall/opening topology or room-area support authority.
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
        if surface_semantic_pages is None:
            surface_semantic_selected: tuple[int, ...] = ()
        else:
            surface_semantic_selected = _selected_page_indices(
                page_count,
                surface_semantic_pages,
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
    floor_finish_quantity_evidence: list[QuantityEvidence] = []
    ceiling_lining_quantity_evidence: list[QuantityEvidence] = []
    canonical_ceiling_objects: list[LiveCanonicalCeilingSurfaceObject] = []
    room_area_bridges = []
    physical_scale_failures_by_room: dict[str, tuple[str, ...]] = {}
    same_view_area = None
    cross_view_area = None
    if canonical_rooms.rooms:
        same_view_area = SameViewRoomAreaProducer.from_source(
            source=source,
            rooms=canonical_rooms,
        ).publish()
        same_view_by_record = dict(
            same_view_area.evidence_by_source_room_face_record_id
        )

        cross_view_by_record = {}
        if room_area_support_selected:
            cross_view_area = CrossViewRoomAreaProducer.from_source(
                source=source,
                rooms=canonical_rooms,
            ).publish()
            if cross_view_area.records:
                cross_view_by_record = dict(
                    cross_view_area.evidence_by_source_room_face_record_id
                )

        evidence_by_record = _merge_documented_room_area_evidence(
            same_view_by_record=same_view_by_record,
            cross_view_by_record=cross_view_by_record,
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

            explicit_by_face_id = _uniquely_owned_explicit_area_by_source_face(
                source_face_records=room_scope.records,
                canonical_rooms=scope_rooms,
                evidence_by_source_record=evidence_by_record,
            )

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
                containing_viewport = (
                    _unique_authenticated_containing_floor_plan_viewport(
                        source=source,
                        scope_rooms=scope_rooms,
                        page_id=page_id,
                        snapshot_id=snapshot_id,
                    )
                )
                if containing_viewport is not None:
                    viewport_id, viewport_bbox = containing_viewport
                    viewport_status = ViewportResolutionStatus.RESOLVED
                    viewport_reason_codes = (
                        "producer_owned_authenticated_floor_plan_viewport",
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
                    viewport_view_type = DrawingViewType.FLOOR_PLAN.value
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
            scale_bridge_reasons: tuple[str, ...] = ()
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
                containing_viewport = (
                    _unique_authenticated_containing_floor_plan_viewport(
                        source=source,
                        scope_rooms=scope_rooms,
                        page_id=page_id,
                        snapshot_id=snapshot_id,
                    )
                )
                if containing_viewport is not None:
                    resolved_viewport_id, resolved_viewport_bbox = (
                        containing_viewport
                    )
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
                    if (
                        scale_result.status
                        is EvidenceResolutionStatus.CORROBORATED
                    ):
                        viewport = ViewportEvidence(
                            viewport_id=resolved_viewport_id,
                            document_id=scope_rooms[0].document_id,
                            page_id=page_id,
                            bbox=resolved_viewport_bbox,
                            view_type=DrawingViewType.FLOOR_PLAN.value,
                            status=ViewportResolutionStatus.RESOLVED,
                            evidence_ids=(),
                            confidence=1.0,
                            reason_codes=(
                                "producer_owned_authenticated_floor_plan_viewport",
                            ),
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
                                    "viewport_id": resolved_viewport_id,
                                },
                            ),
                            workspace_id="live-extractor",
                            project_id="live-extractor",
                            document_id=scope_rooms[0].document_id,
                            source_sha256=scope_rooms[0].source_sha256,
                            revision_id=scope_rooms[0].revision_id,
                            current_revision_id=scope_rooms[0].revision_id,
                            selected_pages=(page_no - 1,),
                            owned_viewport_ids=(resolved_viewport_id,),
                            evidence_snapshot_id=snapshot_id,
                            owned_page_numbers=(page_no,),
                            viewport_page_ownership=(
                                (resolved_viewport_id, page_no),
                            ),
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
                scale_bridge_reasons = tuple(scale_bridge.reason_codes)
                if (
                    scale_bridge.status is EvidenceResolutionStatus.CORROBORATED
                    and scale_bridge.calibration is not None
                ):
                    scale_calibration = scale_bridge.calibration

            if scale_calibration is None:
                # A documented figured area can resolve without physical
                # scale, so preserve this as an independent failure receipt.
                failure_reasons = (
                    scale_bridge_reasons
                    or tuple(scale_result.reason_codes)
                    or ("physical_scale_calibration_unavailable",)
                )
                for room in scope_rooms:
                    physical_id = str(room.physical_room_id or "").strip()
                    if not physical_id:
                        continue
                    prior = physical_scale_failures_by_room.get(physical_id)
                    if prior is not None and prior != failure_reasons:
                        physical_scale_failures_by_room[physical_id] = (
                            "physical_scale_conflicting_room_scope_receipts",
                        )
                    else:
                        physical_scale_failures_by_room[physical_id] = failure_reasons

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
            room_area_bridges.append(bridge)
            canonical_floors = enrich_live_canonical_floor_metric_areas(
                canonical_floors,
                bridge,
            )
            room_area_quantity_evidence.extend(bridge.quantities)

    # Surface finish semantics may live on schedules/RCP/support sheets that
    # are intentionally excluded from the expensive geometry claim. Decode one
    # independent semantic snapshot only after documented room-area authority
    # exists, and share it across floor-finish and ceiling semantic consumers.
    has_documented_surface_area = bool(
        (same_view_area is not None and same_view_area.records)
        or (cross_view_area is not None and cross_view_area.records)
        or room_area_bridges
    )
    surface_semantic_source = source
    if has_documented_surface_area and surface_semantic_selected:
        surface_semantic_page_ids = tuple(
            str(index + 1) for index in surface_semantic_selected
        )
        if not set(surface_semantic_page_ids).issubset(set(decoded_page_ids)):
            surface_semantic_source = SourceVisibilityProducer(
                producer_method="live-surface-semantic",
                producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
            )
            semantic_published = surface_semantic_source.ingest_native_pdf_bytes(
                document_id=document_id,
                source_bytes=payload,
                source_locator="memory://live-surface-semantic-source.pdf",
                page_ids=tuple(sorted(set(decoded_page_ids) | set(surface_semantic_page_ids), key=int)),
            )
            if (
                semantic_published.revision.document_id
                != published.revision.document_id
                or semantic_published.revision.revision_id
                != published.revision.revision_id
                or semantic_published.revision.source_sha256
                != published.revision.source_sha256
            ):
                raise ValueError(
                    "surface semantic source revision does not match geometry source"
                )

    # Floor-finish authority is a downstream consumer of already-authenticated
    # documented room areas. It must not remeasure or infer a finish.
    if (
        (same_view_area is not None and same_view_area.records)
        or (cross_view_area is not None and cross_view_area.records)
    ):
        floor_finishes = CrossViewFloorFinishProducer.from_source(
            source=surface_semantic_source,
            room_areas=cross_view_area,
            same_view_room_areas=same_view_area,
            floors=canonical_floors,
        ).publish()
        canonical_floors = enrich_live_canonical_floor_finishes(
            canonical_floors,
            floor_finishes,
        )
        floor_finish_quantity_evidence.extend(floor_finishes.quantities)

    if room_area_bridges:
        ceiling_finishes = CrossViewCeilingFinishProducer.from_source(
            source=surface_semantic_source,
            rooms=canonical_rooms,
        ).publish()
        if ceiling_finishes.records:
            ceiling_quantities = publish_cross_view_ceiling_quantities(
                rooms=canonical_rooms,
                room_area_bridges=tuple(room_area_bridges),
                finishes=ceiling_finishes,
            )
            canonical_ceiling_objects.extend(
                ceiling_quantities.canonical_ceilings
            )
            ceiling_lining_quantity_evidence.extend(
                ceiling_quantities.quantities
            )

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
            canonical_ceilings=tuple(canonical_ceiling_objects),
            canonical_space_status=canonical_space_core.status,
            canonical_space_reason_codes=canonical_space_core.reason_codes,
            opening_quantity_evidence=opening_quantity_evidence,
            opening_count_quantity_evidence=opening_count_quantity_evidence,
            room_area_quantity_evidence=tuple(room_area_quantity_evidence),
            floor_finish_quantity_evidence=tuple(floor_finish_quantity_evidence),
            ceiling_lining_quantity_evidence=tuple(
                ceiling_lining_quantity_evidence
            ),
            same_view_room_area_first_failure_codes=(
                same_view_area.unresolved_first_failure_codes
                if same_view_area is not None else ()
            ),
            cross_view_room_area_first_failure_codes=(
                cross_view_area.unresolved_first_failure_codes
                if cross_view_area is not None else ()
            ),
            physical_scale_first_failure_codes=tuple(sorted(
                physical_scale_failures_by_room.items()
            )),
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
        canonical_ceilings=tuple(canonical_ceiling_objects),
        canonical_space_status=canonical_space_core.status,
        canonical_space_reason_codes=canonical_space_core.reason_codes,
        opening_quantity_evidence=opening_quantity_evidence,
        opening_count_quantity_evidence=opening_count_quantity_evidence,
        room_area_quantity_evidence=tuple(room_area_quantity_evidence),
        floor_finish_quantity_evidence=tuple(floor_finish_quantity_evidence),
        ceiling_lining_quantity_evidence=tuple(
            ceiling_lining_quantity_evidence
        ),
        same_view_room_area_first_failure_codes=(
            same_view_area.unresolved_first_failure_codes
            if same_view_area is not None else ()
        ),
        cross_view_room_area_first_failure_codes=(
            cross_view_area.unresolved_first_failure_codes
            if cross_view_area is not None else ()
        ),
        physical_scale_first_failure_codes=tuple(sorted(
            physical_scale_failures_by_room.items()
        )),
    )


__all__ = [
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_RESOLVED",
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION",
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE",
    "LivePhysicalNetWallClaim",
    "collect_live_physical_net_wall_claim",
]
