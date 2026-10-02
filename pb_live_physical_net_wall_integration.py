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

from pb_live_canonical_floor_surface import (
    LiveCanonicalFloorSurfaceObject,
    compose_live_canonical_floor_surfaces,
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
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_live_whole_wall_role_composition import compose_live_whole_wall_roles
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION = "1.2.0"
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
) -> LivePhysicalNetWallClaim:
    """Run the complete source-owned physical external wall chain for one PDF."""

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = _selected_page_indices(int(doc.page_count), pages)
    finally:
        doc.close()

    page_ids = tuple(str(index + 1) for index in selected)
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=page_ids,
    )

    try:
        wall_opening = compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=published.revision.revision_id,
            page_ids=page_ids,
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
    canonical_floors = compose_live_canonical_floor_surfaces(
        canonical_rooms
    )
    physical_void = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
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
    )


__all__ = [
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_RESOLVED",
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION",
    "LIVE_PHYSICAL_NET_WALL_INTEGRATION_UNAVAILABLE",
    "LivePhysicalNetWallClaim",
    "collect_live_physical_net_wall_claim",
]
