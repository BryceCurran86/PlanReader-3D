"""Fail-closed live ceiling-lining claims from the source-owned authority chain.

This is the live-prediction boundary reviewed after the shadow and estimator-review
promotion seams were completed.  It does not project commercial rows and it never
turns ceiling lining into FIRM authority.

Inputs are the source PDF bytes plus normal page selection.  The module:
1. ingests the bytes through SourceVisibilityProducer;
2. accepts only F.07 RESOLVED floor-plan vector-frame viewports;
3. runs the fully source-owned ceiling shadow composition per exact viewport;
4. revalidates every resolved ceiling claim against its FIRM same-scope room area,
   producer-owned finish evidence, current source identity and physical scale;
5. emits a separate live PROVISIONAL claim;
6. refuses to add the same finish across multiple independent viewports because
   cross-viewport physical identity is not yet proven.

No benchmark ID, expected quantity, filename, project name or BOQ mapping is used.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path
from typing import Optional, Sequence

import fitz

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import measurement_authority_for_page_scale
from pb_source_ceiling_finish_evidence import SOURCE_CEILING_FINISH_METHOD
from pb_source_owned_ceiling_lining_pipeline import run_source_owned_ceiling_lining_shadow
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_CEILING_LINING_SCHEMA_VERSION = "1.0.0"
LIVE_CEILING_LINING_RESOLVED = "live_ceiling_lining_resolved"
LIVE_CEILING_LINING_UNAVAILABLE = "live_ceiling_lining_unavailable"
LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED = (
    "live_ceiling_lining_multi_viewport_identity_unresolved"
)
LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT = "live_ceiling_lining_tag_family_conflict"


@dataclass(frozen=True)
class LiveCeilingLiningClaim:
    claim_id: str
    tag: str
    finish_descriptor: str
    quantity_m2: float
    confidence: float
    source_page: int
    viewport_id: str
    source_sha256: str
    revision_id: str
    room_quantity_ids: tuple[str, ...]
    room_entity_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    physical_scale_record_id: str
    status: str = AuthorityStatus.PROVISIONAL.value
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION


@dataclass(frozen=True)
class LiveCeilingLiningResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    claims: tuple[LiveCeilingLiningClaim, ...]
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: object) -> str:
    return _clean(value).lower().replace("-", "_").replace(" ", "_")


def _tag_for_descriptor(descriptor: str) -> str:
    """Return a generic material-family tag derived only from source finish text."""
    text = _norm(descriptor)
    families = (
        ("chipboard", ("chipboard", "chip_board")),
        ("gypsum", ("gypsum",)),
        ("plasterboard", ("plasterboard", "plaster_board")),
        ("fibre_cement", ("fibre_cement", "fiber_cement", "fibrecement", "fibercement")),
        ("acoustic", ("acoustic", "acoustical")),
        ("pvc", ("pvc", "polyvinyl")),
        ("timber", ("timber", "wood", "wooden")),
        ("board", ("board",)),
    )
    for family, needles in families:
        if any(needle in text for needle in needles):
            return f"ceiling_{family}"
    return "ceiling_lining"


def _selected_page_indices(page_count: int, pages: Optional[Sequence[int]]) -> tuple[int, ...]:
    if pages is None:
        return tuple(range(page_count))
    return tuple(
        sorted(
            {
                int(index)
                for index in pages
                if not isinstance(index, bool) and 0 <= int(index) < page_count
            }
        )
    )


def _claim_from_quantity(
    *,
    quantity,
    source_result,
    page_no: int,
    viewport_id: str,
) -> Optional[tuple[str, str, float, tuple[str, ...], tuple[str, ...], tuple[str, ...], str]]:
    if (
        quantity.family != "ceiling_lining"
        or quantity.abstained
        or quantity.value is None
        or quantity.status != AuthorityStatus.PROVISIONAL.value
        or quantity.authority != MeasurementAuthorityType.MODEL_DERIVED.value
        or quantity.blocking_reasons
        or len(quantity.input_entity_ids) != 1
    ):
        return None

    meta = quantity.metadata if isinstance(quantity.metadata, dict) else {}
    if (
        meta.get("shadow_only") is not True
        or meta.get("commercial_projection_allowed") is not False
        or _clean(meta.get("viewport_id")) != viewport_id
        or int(meta.get("page_no", -1)) != int(page_no)
    ):
        return None

    finish_descriptor = _clean(meta.get("finish_descriptor"))
    finish_methods = tuple(_clean(value) for value in (meta.get("finish_source_methods") or ()))
    finish_ids = tuple(_clean(value) for value in (meta.get("finish_evidence_ids") or ()))
    if (
        not finish_descriptor
        or SOURCE_CEILING_FINISH_METHOD not in finish_methods
        or not finish_ids
        or not set(finish_ids).issubset(set(quantity.evidence_ids))
    ):
        return None

    upstream_id = _clean(meta.get("upstream_area_quantity_id"))
    area_by_id = {
        item.quantity_id: item for item in source_result.room_area_quantities
    }
    area = area_by_id.get(upstream_id)
    scope = quantity.input_entity_ids[0]
    if (
        area is None
        or area.abstained
        or area.value is None
        or area.status != AuthorityStatus.FIRM.value
        or area.authority != MeasurementAuthorityType.PDF_SCALED.value
        or tuple(area.input_entity_ids) != (scope,)
        or float(area.value) != float(quantity.value)
        or area.blocking_reasons
    ):
        return None

    bridge = source_result.scale_bridge
    calibration = bridge.calibration
    physical = bridge.physical_scale_evidence
    if (
        bridge.status is not EvidenceResolutionStatus.CORROBORATED
        or calibration is None
        or physical is None
        or not physical.record_id
        or measurement_authority_for_page_scale(calibration) != AuthorityStatus.FIRM.value
    ):
        return None

    return (
        _tag_for_descriptor(finish_descriptor),
        finish_descriptor,
        float(quantity.value),
        (quantity.quantity_id,),
        tuple(quantity.input_entity_ids),
        tuple(quantity.evidence_ids),
        physical.record_id,
    )


def collect_live_ceiling_lining_claims(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
) -> LiveCeilingLiningResult:
    """Collect live provisional ceiling claims from authoritative source viewports."""

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    source = SourceVisibilityProducer(
        producer_method="live-ceiling-lining",
        producer_version=LIVE_CEILING_LINING_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-source.pdf",
    )

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = _selected_page_indices(len(doc), pages)
        by_descriptor: dict[
            str,
            list[
                tuple[
                    int,
                    str,
                    str,
                    float,
                    tuple[str, ...],
                    tuple[str, ...],
                    tuple[str, ...],
                    str,
                    float,
                ]
            ],
        ] = {}

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
                bbox = tuple(float(value) for value in segmented.bounding_box)
                viewport = ViewportEvidence(
                    viewport_id=viewport_id,
                    document_id=published.revision.document_id,
                    page_id=str(page_no),
                    bbox=bbox,
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
                    run_id=f"live-ceiling:{current.snapshot.snapshot_id}:{viewport_id}",
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

                for quantity in result.ceiling_quantities:
                    resolved = _claim_from_quantity(
                        quantity=quantity,
                        source_result=result,
                        page_no=page_no,
                        viewport_id=viewport_id,
                    )
                    if resolved is None:
                        continue
                    (
                        tag,
                        descriptor,
                        value,
                        quantity_ids,
                        room_ids,
                        evidence_ids,
                        scale_record_id,
                    ) = resolved
                    by_descriptor.setdefault(descriptor, []).append(
                        (
                            page_no,
                            viewport_id,
                            tag,
                            value,
                            quantity_ids,
                            room_ids,
                            evidence_ids,
                            scale_record_id,
                            float(quantity.confidence),
                        )
                    )

        claims: list[LiveCeilingLiningClaim] = []
        multi_viewport_blocked = False
        for descriptor in sorted(by_descriptor):
            rows = by_descriptor[descriptor]
            viewport_keys = {(row[0], row[1]) for row in rows}
            if len(viewport_keys) != 1:
                # Do not sum potentially duplicated plans across viewports.
                multi_viewport_blocked = True
                continue

            page_no, viewport_id = next(iter(viewport_keys))
            tag_values = {row[2] for row in rows}
            scale_ids = {row[7] for row in rows}
            if len(tag_values) != 1 or len(scale_ids) != 1:
                continue

            quantity_m2 = sum(row[3] for row in rows)
            room_quantity_ids = tuple(
                sorted({qid for row in rows for qid in row[4]})
            )
            room_entity_ids = tuple(
                sorted({rid for row in rows for rid in row[5]})
            )
            evidence_ids = tuple(
                sorted({eid for row in rows for eid in row[6]})
            )
            confidence = min(row[8] for row in rows)
            tag = next(iter(tag_values))
            scale_record_id = next(iter(scale_ids))
            claim_id = stable_contract_id(
                "live_ceiling",
                {
                    "tag": tag,
                    "finish_descriptor": descriptor,
                    "quantity_m2": quantity_m2,
                    "source_sha256": source_sha,
                    "revision_id": published.revision.revision_id,
                    "page_no": page_no,
                    "viewport_id": viewport_id,
                    "room_quantity_ids": room_quantity_ids,
                    "room_entity_ids": room_entity_ids,
                    "evidence_ids": evidence_ids,
                    "physical_scale_record_id": scale_record_id,
                },
            )
            claims.append(
                LiveCeilingLiningClaim(
                    claim_id=claim_id,
                    tag=tag,
                    finish_descriptor=descriptor,
                    quantity_m2=quantity_m2,
                    confidence=confidence,
                    source_page=page_no,
                    viewport_id=viewport_id,
                    source_sha256=source_sha,
                    revision_id=published.revision.revision_id,
                    room_quantity_ids=room_quantity_ids,
                    room_entity_ids=room_entity_ids,
                    evidence_ids=evidence_ids,
                    physical_scale_record_id=scale_record_id,
                )
            )

        # A family tag is a publication identity. If distinct explicit
        # descriptors collapse to the same family tag, do not let confidence
        # or iteration order pick one. Cross-descriptor identity is unresolved.
        tag_to_descriptors: dict[str, set[str]] = {}
        for claim in claims:
            tag_to_descriptors.setdefault(claim.tag, set()).add(claim.finish_descriptor)
        conflicted_tags = {
            tag for tag, descriptors in tag_to_descriptors.items()
            if len(descriptors) > 1
        }
        tag_conflict_blocked = bool(conflicted_tags)
        if conflicted_tags:
            claims = [claim for claim in claims if claim.tag not in conflicted_tags]

        if claims:
            reasons = [LIVE_CEILING_LINING_RESOLVED]
            if multi_viewport_blocked:
                reasons.append(LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
            if tag_conflict_blocked:
                reasons.append(LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT)
            return LiveCeilingLiningResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=tuple(reasons),
                claims=tuple(sorted(claims, key=lambda item: item.claim_id)),
            )

        reasons = [LIVE_CEILING_LINING_UNAVAILABLE]
        if multi_viewport_blocked:
            reasons.append(LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
        if tag_conflict_blocked:
            reasons.append(LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT)
        return LiveCeilingLiningResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=tuple(reasons),
            claims=(),
        )
    finally:
        doc.close()


__all__ = [
    "LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED",
    "LIVE_CEILING_LINING_RESOLVED",
    "LIVE_CEILING_LINING_SCHEMA_VERSION",
    "LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT",
    "LIVE_CEILING_LINING_UNAVAILABLE",
    "LiveCeilingLiningClaim",
    "LiveCeilingLiningResult",
    "collect_live_ceiling_lining_claims",
]
