"""Live source-owned physical external net-wall integration.

This is the extractor-facing composition seam for perimeter walling. It ingests
the immutable PDF bytes through SourceVisibilityProducer, replays the complete
wall/opening authority chain, composes gross whole-wall geometry and source-owned
whole-wall roles, and publishes physical external net wall area.

Unlike finish/trade deductions, physical wall net geometry does not consume or
invent ODTARGET/ODRULE policy declarations. A proven physical opening in a
complete source opening universe is geometric absence from its proven host wall.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Optional, Sequence

import fitz

from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
    compose_live_external_physical_net_wall_publication,
)
from pb_live_gross_wall_geometry_composition import (
    compose_live_gross_wall_geometry,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_live_whole_wall_role_composition import (
    compose_live_whole_wall_roles,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION = "1.0.0"
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
    """Run the source-owned physical external wall chain for one PDF."""

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = _selected_page_indices(int(doc.page_count), pages)
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=tuple(str(index + 1) for index in selected),
    )
    page_ids = tuple(str(index + 1) for index in selected)

    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=page_ids,
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

    evidence = publication.quantity_evidence
    if (
        publication.status is EvidenceResolutionStatus.CORROBORATED
        and evidence is not None
        and evidence.value is not None
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
