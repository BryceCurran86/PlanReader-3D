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
    QuantityEvidence,
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
LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT = (
    "live_ceiling_canonical_identity_conflict"
)


@dataclass(frozen=True)
class LiveCanonicalCeilingSurfaceObject:
    canonical_ceiling_id: str
    document_id: str
    snapshot_id: str
    room_entity_id: str
    source_page: int
    viewport_id: str
    source_sha256: str
    revision_id: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    area_m2: float
    finish_descriptor: str
    room_area_quantity_id: str
    ceiling_quantity_id: str
    source_room_index_id: str
    evidence_ids: tuple[str, ...]
    physical_scale_record_id: str
    measurement_authority: str = ""
    figured_dimension_ids: tuple[str, ...] = ()
    geometry_complete: bool = True
    metric_area_complete: bool = True
    metric_geometry_complete: bool = False
    coordinate_space: str = "source_page_points"
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_ceiling_id": self.canonical_ceiling_id,
            "document_id": self.document_id,
            "snapshot_id": self.snapshot_id,
            "room_entity_id": self.room_entity_id,
            "source_page": self.source_page,
            "viewport_id": self.viewport_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "polygon_pdf_pts": [list(point) for point in self.polygon_pdf_pts],
            "area_m2": self.area_m2,
            "finish_descriptor": self.finish_descriptor,
            "room_area_quantity_id": self.room_area_quantity_id,
            "ceiling_quantity_id": self.ceiling_quantity_id,
            "source_room_index_id": self.source_room_index_id,
            "evidence_ids": list(self.evidence_ids),
            "physical_scale_record_id": self.physical_scale_record_id,
            "measurement_authority": self.measurement_authority,
            "figured_dimension_ids": list(self.figured_dimension_ids),
            "geometry_complete": self.geometry_complete,
            "metric_area_complete": self.metric_area_complete,
            "metric_geometry_complete": self.metric_geometry_complete,
            "coordinate_space": self.coordinate_space,
            "schema_version": self.schema_version,
        }


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
    measurement_authority: str = ""
    figured_dimension_ids: tuple[str, ...] = ()
    status: str = AuthorityStatus.PROVISIONAL.value
    schema_version: str = LIVE_CEILING_LINING_SCHEMA_VERSION


@dataclass(frozen=True)
class LiveCeilingLiningResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    claims: tuple[LiveCeilingLiningClaim, ...]
    canonical_ceilings: tuple[LiveCanonicalCeilingSurfaceObject, ...] = ()
    quantity_evidence: tuple[QuantityEvidence, ...] = ()
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
) -> Optional[
    tuple[
        str,
        str,
        float,
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        str,
        str,
        tuple[str, ...],
    ]
]:
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
        or area.authority
        not in {
            MeasurementAuthorityType.PDF_SCALED.value,
            MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        }
        or tuple(area.input_entity_ids) != (scope,)
        or float(area.value) != float(quantity.value)
        or area.blocking_reasons
    ):
        return None

    scale_record_id = ""
    figured_dimension_ids: tuple[str, ...] = ()
    if area.authority == MeasurementAuthorityType.PDF_SCALED.value:
        bridge = source_result.scale_bridge
        calibration = bridge.calibration
        physical = bridge.physical_scale_evidence
        if (
            bridge.status is not EvidenceResolutionStatus.CORROBORATED
            or calibration is None
            or physical is None
            or not physical.record_id
            or measurement_authority_for_page_scale(calibration)
            != AuthorityStatus.FIRM.value
        ):
            return None
        scale_record_id = str(physical.record_id)
    else:
        area_meta = area.metadata if isinstance(area.metadata, dict) else {}
        figured_dimension_ids = tuple(
            sorted(
                {
                    _clean(value)
                    for value in (area_meta.get("figured_dimension_ids") or ())
                    if _clean(value)
                }
            )
        )
        if not figured_dimension_ids:
            return None

    return (
        _tag_for_descriptor(finish_descriptor),
        finish_descriptor,
        float(quantity.value),
        (quantity.quantity_id,),
        tuple(quantity.input_entity_ids),
        tuple(quantity.evidence_ids),
        scale_record_id,
        str(area.authority),
        figured_dimension_ids,
    )


def canonical_ceiling_from_shadow_quantity(
    *,
    quantity: QuantityEvidence,
    source_result,
    page_no: int,
    viewport_id: str,
) -> Optional[LiveCanonicalCeilingSurfaceObject]:
    """Project one already-validated shadow quantity onto canonical ceiling identity.

    This performs no extraction, measurement or commercial promotion.  It is
    intentionally reusable by the estimator-review collector so AG-09 can see
    the same canonical object without replaying the ceiling pipeline.
    """
    resolved = _claim_from_quantity(
        quantity=quantity,
        source_result=source_result,
        page_no=page_no,
        viewport_id=viewport_id,
    )
    if resolved is None:
        return None
    (
        _tag,
        descriptor,
        value,
        _quantity_ids,
        room_ids,
        evidence_ids,
        scale_record_id,
        measurement_authority,
        figured_dimension_ids,
    ) = resolved
    if len(room_ids) != 1:
        return None

    room_index = source_result.pipeline.room_area_bridge.room_index
    if room_index is None:
        return None
    room_id = room_ids[0]
    room = room_index.room(room_id)
    if room is None or len(room.polygon_pdf_pts) < 3:
        return None

    quantity_meta = (
        quantity.metadata if isinstance(quantity.metadata, dict) else {}
    )
    upstream_area_id = _clean(
        quantity_meta.get("upstream_area_quantity_id")
    )
    if not upstream_area_id:
        return None

    context = source_result.effective_context
    document_id = _clean(context.document_id)
    source_sha256 = _clean(context.source_sha256)
    revision_id = _clean(context.current_revision_id)
    snapshot_id = _clean(context.evidence_snapshot_id)
    if not all((document_id, source_sha256, revision_id, snapshot_id)):
        return None

    canonical_id = stable_contract_id(
        "live_canonical_ceiling_surface",
        {
            "source_sha256": source_sha256,
            "revision_id": revision_id,
            "page_no": int(page_no),
            "viewport_id": viewport_id,
            "room_entity_id": room_id,
        },
    )
    return LiveCanonicalCeilingSurfaceObject(
        canonical_ceiling_id=canonical_id,
        document_id=document_id,
        snapshot_id=snapshot_id,
        room_entity_id=room_id,
        source_page=int(page_no),
        viewport_id=viewport_id,
        source_sha256=source_sha256,
        revision_id=revision_id,
        polygon_pdf_pts=tuple(
            (float(point[0]), float(point[1]))
            for point in room.polygon_pdf_pts
        ),
        area_m2=float(value),
        finish_descriptor=descriptor,
        room_area_quantity_id=upstream_area_id,
        ceiling_quantity_id=quantity.quantity_id,
        source_room_index_id=room_index.index_id,
        evidence_ids=tuple(evidence_ids),
        physical_scale_record_id=scale_record_id,
        measurement_authority=measurement_authority,
        figured_dimension_ids=figured_dimension_ids,
    )


def collect_live_ceiling_lining_claims(
    pdf_path: Path | str,
    *,
    pages: Optional[Sequence[int]] = None,
    topology_pages: Optional[Sequence[int]] = None,
    authoritative_room_area_quantities: Optional[Sequence[QuantityEvidence]] = None,
) -> LiveCeilingLiningResult:
    """Collect live provisional ceiling claims from authoritative source viewports."""

    path = Path(pdf_path)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    document_id = f"live-source:{source_sha[:32]}"

    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = _selected_page_indices(len(doc), pages)
        topology_selected = (
            selected
            if topology_pages is None
            else _selected_page_indices(len(doc), topology_pages)
        )
        if any(index not in set(selected) for index in topology_selected):
            raise ValueError("topology_pages must be a subset of pages")
        page_ids = tuple(str(index + 1) for index in selected)
        source = SourceVisibilityProducer(
            producer_method="live-ceiling-lining",
            producer_version=LIVE_CEILING_LINING_SCHEMA_VERSION,
        )
        published = source.ingest_native_pdf_bytes(
            document_id=document_id,
            source_bytes=payload,
            source_locator="memory://live-source.pdf",
            page_ids=page_ids,
        )
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
        canonical_ceilings_by_id: dict[
            str, LiveCanonicalCeilingSurfaceObject
        ] = {}
        canonical_conflicts: set[str] = set()
        validated_quantities: dict[str, QuantityEvidence] = {}
        upstream_room_areas = tuple(authoritative_room_area_quantities or ())

        for page_index in topology_selected:
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

                scoped_room_areas = tuple(
                    area
                    for area in upstream_room_areas
                    if (
                        isinstance(area.metadata, dict)
                        and _clean(area.metadata.get("source_sha256")).lower()
                        == current.revision.source_sha256.lower()
                        and _clean(area.metadata.get("revision_id"))
                        == current.revision.revision_id
                        and _clean(area.metadata.get("viewport_id")) == viewport_id
                        and _clean(area.metadata.get("page_no")) == str(page_no)
                    )
                )

                try:
                    result = run_source_owned_ceiling_lining_shadow(
                        source_visibility_producer=source,
                        context=context,
                        viewport=viewport,
                        page_no=page_no,
                        authoritative_area_quantities=(
                            scoped_room_areas if scoped_room_areas else None
                        ),
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
                        measurement_authority,
                        figured_dimension_ids,
                    ) = resolved
                    validated_quantities[quantity.quantity_id] = quantity
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
                            measurement_authority,
                            figured_dimension_ids,
                            float(quantity.confidence),
                        )
                    )

                    ceiling_object = canonical_ceiling_from_shadow_quantity(
                        quantity=quantity,
                        source_result=result,
                        page_no=page_no,
                        viewport_id=viewport_id,
                    )
                    if ceiling_object is not None:
                        canonical_id = ceiling_object.canonical_ceiling_id
                        prior = canonical_ceilings_by_id.get(canonical_id)
                        if prior is not None and prior != ceiling_object:
                            canonical_conflicts.add(canonical_id)
                        else:
                            canonical_ceilings_by_id[canonical_id] = ceiling_object

        for canonical_id in canonical_conflicts:
            canonical_ceilings_by_id.pop(canonical_id, None)

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
            confidence = min(row[10] for row in rows)
            tag = next(iter(tag_values))
            scale_record_id = next(iter(scale_ids))
            measurement_authorities = {row[8] for row in rows}
            figured_dimension_ids = tuple(
                sorted({value for row in rows for value in row[9]})
            )
            if len(measurement_authorities) != 1:
                continue
            measurement_authority = next(iter(measurement_authorities))
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
                    "measurement_authority": measurement_authority,
                    "figured_dimension_ids": figured_dimension_ids,
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
                    measurement_authority=measurement_authority,
                    figured_dimension_ids=figured_dimension_ids,
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

        canonical_ceilings = tuple(
            sorted(
                canonical_ceilings_by_id.values(),
                key=lambda item: item.canonical_ceiling_id,
            )
        )
        claim_quantity_ids = {
            quantity_id
            for claim in claims
            for quantity_id in claim.room_quantity_ids
        }
        canonical_quantity_ids = {
            ceiling.ceiling_quantity_id for ceiling in canonical_ceilings
        }
        surviving_quantity_ids = claim_quantity_ids & canonical_quantity_ids
        surviving_quantities = tuple(
            validated_quantities[quantity_id]
            for quantity_id in sorted(surviving_quantity_ids)
            if quantity_id in validated_quantities
        )

        if claims:
            reasons = [LIVE_CEILING_LINING_RESOLVED]
            if multi_viewport_blocked:
                reasons.append(LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
            if tag_conflict_blocked:
                reasons.append(LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT)
            if canonical_conflicts:
                reasons.append(LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT)
            return LiveCeilingLiningResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=tuple(reasons),
                claims=tuple(sorted(claims, key=lambda item: item.claim_id)),
                canonical_ceilings=canonical_ceilings,
                quantity_evidence=surviving_quantities,
            )

        reasons = [LIVE_CEILING_LINING_UNAVAILABLE]
        if multi_viewport_blocked:
            reasons.append(LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED)
        if tag_conflict_blocked:
            reasons.append(LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT)
        if canonical_conflicts:
            reasons.append(LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT)
        return LiveCeilingLiningResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=tuple(reasons),
            claims=(),
            canonical_ceilings=canonical_ceilings,
            quantity_evidence=surviving_quantities,
        )
    finally:
        doc.close()


__all__ = [
    "LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT",
    "LIVE_CEILING_LINING_MULTI_VIEWPORT_IDENTITY_UNRESOLVED",
    "LIVE_CEILING_LINING_RESOLVED",
    "LIVE_CEILING_LINING_SCHEMA_VERSION",
    "LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT",
    "LIVE_CEILING_LINING_UNAVAILABLE",
    "LiveCanonicalCeilingSurfaceObject",
    "LiveCeilingLiningClaim",
    "LiveCeilingLiningResult",
    "canonical_ceiling_from_shadow_quantity",
    "collect_live_ceiling_lining_claims",
]
