"""Live source-owned room-area claims for extractor/runtime consumption.

Publishes only FIRM room-area quantities already proven by the reviewed
source-owned wall -> room-face -> physical-scale chain.  No room labels,
finish mappings, commercial rows, benchmark values, or inferred boundaries
enter this seam.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Optional, Sequence

import fitz

from pb_geometry_takeoff_model import AuthorityStatus
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_source_owned_ceiling_lining_pipeline import (
    run_source_owned_ceiling_lining_shadow,
)
from pb_source_visibility_authority import SourceVisibilityProducer

LIVE_ROOM_AREA_SCHEMA_VERSION = "1.0.0"
LIVE_ROOM_AREA_RESOLVED = "live_room_area_resolved"
LIVE_ROOM_AREA_UNAVAILABLE = "live_room_area_unavailable"
LIVE_ROOM_AREA_MULTI_VIEWPORT_IDENTITY_UNRESOLVED = (
    "live_room_area_multi_viewport_identity_unresolved"
)


@dataclass(frozen=True)
class LiveRoomAreaClaim:
    claim_id: str
    room_entity_id: str
    room_quantity_id: str
    quantity_m2: float
    confidence: float
    source_page: int
    viewport_id: str
    source_sha256: str
    revision_id: str
    evidence_ids: tuple[str, ...]
    authority: str
    physical_scale_record_id: Optional[str]
    status: str = AuthorityStatus.FIRM.value
    schema_version: str = LIVE_ROOM_AREA_SCHEMA_VERSION


@dataclass(frozen=True)
class LiveRoomAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    claims: tuple[LiveRoomAreaClaim, ...]
    schema_version: str = LIVE_ROOM_AREA_SCHEMA_VERSION

def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _selected_page_indices(
    page_count: int,
    pages: Optional[Sequence[int]],
) -> tuple[int, ...]:
    if pages is None:
        return tuple(range(page_count))
    selected = tuple(
        sorted(
            {
                int(index)
                for index in pages
                if not isinstance(index, bool)
                and 0 <= int(index) < page_count
            }
        )
    )
    if pages is not None and not selected:
        raise ValueError("pages must select at least one valid PDF page")
    return selected


def _eligible_room_quantity(quantity, *, page_no: int, viewport_id: str) -> bool:
    meta = quantity.metadata if isinstance(quantity.metadata, dict) else {}
    return bool(
        quantity.family == "room_area"
        and not quantity.abstained
        and quantity.value is not None
        and float(quantity.value) > 0.0
        and quantity.status == AuthorityStatus.FIRM.value
        and not quantity.blocking_reasons
        and len(quantity.input_entity_ids) == 1
        and int(meta.get("page_no", -1)) == int(page_no)
        and _clean(meta.get("viewport_id")) == viewport_id
    )

def collect_live_room_area_claims(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
) -> LiveRoomAreaResult:
    """Collect non-commercial FIRM room areas from source-owned floor-plan views."""

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = _selected_page_indices(len(doc), pages)
        page_ids = tuple(str(index + 1) for index in selected)
        source = SourceVisibilityProducer(
            producer_method="live-room-area",
            producer_version=LIVE_ROOM_AREA_SCHEMA_VERSION,
        )
        published = source.ingest_native_pdf_bytes(
            document_id=document_id,
            source_bytes=payload,
            source_locator="memory://live-room-area-source.pdf",
            page_ids=page_ids,
        )

        rows: list[tuple[int, str, object, object]] = []
        for page_index in selected:
            page_no = page_index + 1
            page = doc[page_index]
            for segmented in authoritative_floor_plan_viewports(
                page, page_number=page_no
            ):

                if segmented.bounding_box is None:
                    continue
                viewport_id = _clean(segmented.view_id)
                if not viewport_id:
                    continue
                viewport = ViewportEvidence(
                    viewport_id=viewport_id,
                    document_id=published.revision.document_id,
                    page_id=str(page_no),
                    bbox=tuple(float(v) for v in segmented.bounding_box),
                    view_type="floor_plan",
                    status=ViewportResolutionStatus.RESOLVED,
                    evidence_ids=(),
                    confidence=float(segmented.confidence),
                )
                current = source.published_snapshot_for_revision(
                    published.revision.revision_id
                )
                if current is None:
                    continue
                context = ProviderContext(
                    run_id=f"live-room:{current.snapshot.snapshot_id}:{viewport_id}",
                    workspace_id="live-extractor",
                    project_id="live-extractor",
                    document_id=current.revision.document_id,
                    source_sha256=current.revision.source_sha256,
                    revision_id=current.revision.revision_id,
                    current_revision_id=current.revision.revision_id,
                    selected_pages=(page_index,),
                    owned_viewport_ids=(viewport_id,),
                    evidence_snapshot_id=current.snapshot.snapshot_id,
                    owned_page_numbers=(page_no,),
                    viewport_page_ownership=((viewport_id, page_no),),
                )

                try:
                    result = run_source_owned_ceiling_lining_shadow(
                        source_visibility_producer=source,
                        context=context,
                        viewport=viewport,
                        page_no=page_no,
                    )
                except Exception:
                    continue

                for quantity in result.room_area_quantities:
                    if _eligible_room_quantity(
                        quantity,
                        page_no=page_no,
                        viewport_id=viewport_id,
                    ):
                        rows.append((page_no, viewport_id, quantity, result))

        if not rows:
            return LiveRoomAreaResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(LIVE_ROOM_AREA_UNAVAILABLE,),
                claims=(),
            )

        # The same physical room can appear on multiple independent plan views.
        # Until cross-viewport physical identity is proven, never publish such
        # duplicate-looking room entities as additive customer geometry.
        by_room: dict[str, list[tuple[int, str, object, object]]] = {}
        for row in rows:
            room_id = str(row[2].input_entity_ids[0])
            by_room.setdefault(room_id, []).append(row)

        claims: list[LiveRoomAreaClaim] = []
        multi_viewport_blocked = False
        for room_id in sorted(by_room):
            room_rows = by_room[room_id]
            viewport_keys = {(row[0], row[1]) for row in room_rows}
            if len(viewport_keys) != 1:
                multi_viewport_blocked = True
                continue
            page_no, viewport_id, quantity, result = room_rows[0]
            scale_id = None
            physical = result.scale_bridge.physical_scale_evidence
            if physical is not None and physical.record_id:
                scale_id = physical.record_id
            claim_id = stable_contract_id(
                "live_room_area",
                {
                    "room_entity_id": room_id,
                    "room_quantity_id": quantity.quantity_id,
                    "quantity_m2": float(quantity.value),
                    "source_sha256": source_sha,
                    "revision_id": published.revision.revision_id,
                    "page_no": page_no,
                    "viewport_id": viewport_id,
                    "evidence_ids": tuple(quantity.evidence_ids),
                },
            )
            claims.append(
                LiveRoomAreaClaim(
                    claim_id=claim_id,
                    room_entity_id=room_id,
                    room_quantity_id=quantity.quantity_id,

                    quantity_m2=float(quantity.value),
                    confidence=float(quantity.confidence),
                    source_page=int(page_no),
                    viewport_id=viewport_id,
                    source_sha256=source_sha,
                    revision_id=published.revision.revision_id,
                    evidence_ids=tuple(quantity.evidence_ids),
                    authority=str(quantity.authority),
                    physical_scale_record_id=scale_id,
                )
            )

        reasons = [LIVE_ROOM_AREA_RESOLVED]
        if multi_viewport_blocked:
            reasons.append(LIVE_ROOM_AREA_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
        if not claims:
            return LiveRoomAreaResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=tuple(reasons),
                claims=(),
            )
        return LiveRoomAreaResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=tuple(reasons),
            claims=tuple(claims),
        )
    finally:
        doc.close()


__all__ = [
    "LIVE_ROOM_AREA_MULTI_VIEWPORT_IDENTITY_UNRESOLVED",
    "LIVE_ROOM_AREA_RESOLVED",
    "LIVE_ROOM_AREA_SCHEMA_VERSION",
    "LIVE_ROOM_AREA_UNAVAILABLE",
    "LiveRoomAreaClaim",
    "LiveRoomAreaResult",
    "collect_live_room_area_claims",
]
