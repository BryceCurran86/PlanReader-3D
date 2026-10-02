"""Hardened publication gate for canonical openings and opening quantities.

The projector is deliberately downstream-only.  It cannot discover an opening,
pick a host, or invent dimensions.  It consumes already-authenticated:
observation/existence -> host topology -> physical identity -> measurement
authority, then emits one canonical opening and its area quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from pb_canonical_building import CanonicalOpening, Provenance, ReviewState
from pb_geometry_takeoff_model import AuthorityStatus
from pb_measurement_input_authority import MeasurementInputResolution
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingResult,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningExistenceRecord,
)


OPENING_PUBLICATION_SCHEMA_VERSION = "1.0.0"
OPENING_PUBLICATION_RESOLVED = "hardened_canonical_opening_quantity_resolved"
OPENING_PUBLICATION_EXISTENCE_REQUIRED = "authenticated_opening_existence_required"
OPENING_PUBLICATION_IDENTITY_REQUIRED = "physical_opening_identity_required"
OPENING_PUBLICATION_HOST_REQUIRED = "authenticated_opening_host_topology_required"
OPENING_PUBLICATION_HOST_IDENTITY_CONFLICT = "opening_host_physical_identity_conflict"
OPENING_PUBLICATION_LINEAGE_CONFLICT = "opening_publication_lineage_conflict"
OPENING_PUBLICATION_MEASUREMENT_REQUIRED = "firm_opening_measurement_required"


@dataclass(frozen=True)
class CanonicalOpeningQuantityPublication:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    canonical_opening: Optional[CanonicalOpening] = None
    quantity_m2: Optional[float] = None
    unit: str = "m2"
    schema_version: str = OPENING_PUBLICATION_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra: str,
) -> CanonicalOpeningQuantityPublication:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return CanonicalOpeningQuantityPublication(
        status=status,
        reason_codes=tuple(dict.fromkeys((reason, *(str(v) for v in extra if str(v))))),
    )


def _positive(value: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _measurement_matches(
    measurement: MeasurementInputResolution,
    *,
    existence: PhysicalOpeningExistenceRecord,
    physical_identity: str,
) -> bool:
    if (
        not isinstance(measurement, MeasurementInputResolution)
        or measurement.authority_status != AuthorityStatus.FIRM.value
        or _positive(measurement.value_m) is None
        or measurement.blocking_reasons
        or measurement.document_id != existence.document_id
        or measurement.source_sha256 != existence.source_sha256
        or measurement.revision_id != existence.revision_id
        or measurement.entity_id != physical_identity
    ):
        return False
    if existence.viewport_id is not None and measurement.viewport_id != existence.viewport_id:
        return False
    page_text = str(existence.page_id or "").strip()
    if page_text.isdigit() and measurement.page_no != int(page_text):
        return False
    return True


def publish_canonical_opening_quantity(
    *,
    existence: PhysicalOpeningExistenceRecord,
    host_binding: OpeningHostBindingResult,
    width: MeasurementInputResolution,
    height: MeasurementInputResolution,
    opening_type: str = "GENERIC",
    mark: Optional[str] = None,
) -> CanonicalOpeningQuantityPublication:
    """Publish only after the complete hardened opening authority chain passes."""
    if (
        not isinstance(existence, PhysicalOpeningExistenceRecord)
        or existence.status is not EvidenceResolutionStatus.CORROBORATED
        or existence.proposition != PHYSICAL_OPENING_EXISTS
    ):
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            OPENING_PUBLICATION_EXISTENCE_REQUIRED,
        )

    physical_identity = str(existence.physical_identity_fingerprint or "").strip()
    if not physical_identity:
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            OPENING_PUBLICATION_IDENTITY_REQUIRED,
        )

    if (
        not isinstance(host_binding, OpeningHostBindingResult)
        or host_binding.status is not EvidenceResolutionStatus.CORROBORATED
        or host_binding.record is None
        or OPENING_HOST_BINDING_RESOLVED not in host_binding.reason_codes
    ):
        reasons = getattr(host_binding, "reason_codes", ()) or ()
        return _blocked(
            getattr(host_binding, "status", EvidenceResolutionStatus.ABSTAINED),
            OPENING_PUBLICATION_HOST_REQUIRED,
            *reasons,
        )

    host = host_binding.record
    if host.opening_identity_id != physical_identity:
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            OPENING_PUBLICATION_HOST_IDENTITY_CONFLICT,
        )

    if any(
        (
            host.document_id != existence.document_id,
            host.revision_id != existence.revision_id,
            host.source_sha256 != existence.source_sha256,
            host.snapshot_id != existence.snapshot_id,
            host.page_id != existence.page_id,
        )
    ):
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            OPENING_PUBLICATION_LINEAGE_CONFLICT,
        )

    if not _measurement_matches(
        width, existence=existence, physical_identity=physical_identity
    ) or not _measurement_matches(
        height, existence=existence, physical_identity=physical_identity
    ):
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            OPENING_PUBLICATION_MEASUREMENT_REQUIRED,
        )

    width_m = _positive(width.value_m)
    height_m = _positive(height.value_m)
    if width_m is None or height_m is None:
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            OPENING_PUBLICATION_MEASUREMENT_REQUIRED,
        )

    evidence_ids = tuple(
        dict.fromkeys(
            (
                *existence.source_observation_ids,
                *host.source_observation_ids,
                *width.evidence_ids,
                *height.evidence_ids,
            )
        )
    )
    canonical_id = stable_contract_id(
        "canonical_opening_physical_identity",
        {"physical_identity_fingerprint": physical_identity},
        digest_chars=32,
    )
    canonical = CanonicalOpening(
        id=canonical_id,
        name=str(mark or opening_type or "Opening"),
        wall_id=host.host_wall_id,
        opening_type=str(opening_type or "GENERIC"),
        width_m=width_m,
        height_m=height_m,
        mark=mark,
        confidence=1.0,
        review_state=ReviewState.CONFIRMED,
        provenance=Provenance(
            document_id=existence.document_id,
            page_id=existence.page_id,
            wall_ref=host.host_wall_id,
            opening_instance_id=physical_identity,
            producer_module="pb_hardened_opening_publication",
            producer_version=OPENING_PUBLICATION_SCHEMA_VERSION,
            contributing_evidence=list(evidence_ids),
        ),
        takeoff_eligible=True,
        deduction_authority=False,
        metadata={
            "physical_identity_fingerprint": physical_identity,
            "evidence_fingerprint": existence.evidence_fingerprint,
            "existence_record_id": existence.record_id,
            "host_binding_record_id": host.record_id,
            "width_measurement_fingerprint": width.fingerprint(),
            "height_measurement_fingerprint": height.fingerprint(),
            "width_measurement_source": width.source_type,
            "height_measurement_source": height.source_type,
            "quantity_basis": "authenticated_opening_width_x_height",
        },
    )
    return CanonicalOpeningQuantityPublication(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(OPENING_PUBLICATION_RESOLVED,),
        canonical_opening=canonical,
        quantity_m2=width_m * height_m,
    )


__all__ = [
    "CanonicalOpeningQuantityPublication",
    "OPENING_PUBLICATION_EXISTENCE_REQUIRED",
    "OPENING_PUBLICATION_HOST_IDENTITY_CONFLICT",
    "OPENING_PUBLICATION_HOST_REQUIRED",
    "OPENING_PUBLICATION_IDENTITY_REQUIRED",
    "OPENING_PUBLICATION_LINEAGE_CONFLICT",
    "OPENING_PUBLICATION_MEASUREMENT_REQUIRED",
    "OPENING_PUBLICATION_RESOLVED",
    "OPENING_PUBLICATION_SCHEMA_VERSION",
    "publish_canonical_opening_quantity",
]
