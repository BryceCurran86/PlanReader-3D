"""Producer-owned physical scale provenance for a canonical floor area.

This bridge does not detect scale or calculate area. Its input is the existing
CORROBORATED PhysicalScaleCalibrationBridgeResult and the already-FIRM exact
room->canonical-floor claim. Ordinary string metadata cannot mint a scale
record; without a congruent native scale witness, customer projection abstains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Optional

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, ScaleCalibration
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence, stable_contract_id
from pb_page_scale_calibration_authority import (
    ScaleCalibrationStatus,
    ScaleSourceType,
    measurement_authority_for_page_scale,
    scale_calibration_fingerprint,
)
from pb_physical_scale_authority import PhysicalScaleEvidence, PhysicalScaleSelector
from pb_physical_scale_calibration_bridge import (
    PHYSICAL_SCALE_CALIBRATION_RESOLVED,
    PhysicalScaleCalibrationBridgeResult,
)

_SOURCE_SEAL = object()


@dataclass(frozen=True)
class LiveFloorScaleSourceReceipt:
    """Exact one-floor binding to an already authenticated native scale bar."""

    canonical_floor_id: str
    physical_floor_surface_id: str
    room_entity_id: str
    source_room_face_record_id: str
    room_area_quantity_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    scale_fingerprint: str
    physical_scale_evidence: PhysicalScaleEvidence
    calibration: ScaleCalibration
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _SOURCE_SEAL:
            raise TypeError("floor scale receipt must come from producer-owned bridge")


def _canonical_page(value: object) -> Optional[str]:
    if type(value) is int:
        return str(value) if value > 0 else None
    if type(value) is str and value.isascii() and value.isdecimal() and not value.startswith("0"):
        return value
    return None


def _trusted_observations(values: object) -> bool:
    return (
        type(values) is tuple
        and bool(values)
        and all(type(value) is str and value and value == value.strip() for value in values)
        and len(set(values)) == len(values)
    )


def _source_physical_scale_record_id(physical: PhysicalScaleEvidence) -> str:
    """Replay the ORIGINAL physical-scale producer's sealed ID payload.

    The origin record was minted from authenticated bar ink and text. A copied
    label or a newly invented identifier cannot replace those exact members.
    """
    selector = physical.selector
    return stable_contract_id(
        "physical_scale_v1",
        {
            "selector": selector.key,
            "source_kind": physical.source_kind,
            "source_span_pt": round(physical.source_span_pt, 12),
            "physical_span_mm": round(physical.physical_span_mm, 9),
            "points_per_mm": round(physical.points_per_mm, 15),
            "source_segment_observation_ids": physical.source_segment_observation_ids,
            "source_text_observation_ids": physical.source_text_observation_ids,
        },
        digest_chars=32,
    )


def _same_original_owners(
    floor: LiveCanonicalFloorSurfaceObject,
    quantity: QuantityEvidence,
    physical: PhysicalScaleEvidence,
    calibration: ScaleCalibration,
) -> bool:
    if type(floor) is not LiveCanonicalFloorSurfaceObject:
        return False
    if type(quantity) is not QuantityEvidence:
        return False
    if type(physical) is not PhysicalScaleEvidence or type(physical.selector) is not PhysicalScaleSelector:
        return False
    if type(calibration) is not ScaleCalibration:
        return False
    selector = physical.selector
    meta = quantity.metadata if isinstance(quantity.metadata, dict) else dict(quantity.metadata or {})
    page = _canonical_page(meta.get("page_no"))
    if (
        floor.metric_area_authority != MeasurementAuthorityType.PDF_SCALED.value
        or quantity.authority != MeasurementAuthorityType.PDF_SCALED.value
        or quantity.status != AuthorityStatus.FIRM.value
        or quantity.abstained or quantity.blocking_reasons
        or quantity.quantity_id != floor.metric_area_quantity_id
        or quantity.family != "room_area"
        or not floor.physical_floor_surface_identity_resolved
        or not floor.canonical_floor_id or not floor.physical_floor_surface_id
        or not floor.room_entity_id or not floor.source_room_face_record_id
        or not floor.snapshot_id or not floor.document_id or not floor.revision_id
        or not floor.source_sha256 or not floor.page_id
        or (floor.viewport_id is not None and
            (type(floor.viewport_id) is not str or not floor.viewport_id))
        or page != floor.page_id
        or type(meta.get("viewport_id")) is not str or not meta.get("viewport_id")
        or (floor.viewport_id is not None and meta.get("viewport_id") != floor.viewport_id)
        or meta.get("source_sha256") != floor.source_sha256
        or meta.get("revision_id") != floor.revision_id
        or (meta.get("room_snapshot_id") is not None
            and meta.get("room_snapshot_id") != floor.snapshot_id)
        or (meta.get("source_room_face_record_id") is not None
            and meta.get("source_room_face_record_id") != floor.source_room_face_record_id)
        or (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
        ) != (
            floor.document_id, floor.revision_id, floor.source_sha256,
            floor.snapshot_id, floor.page_id,
        )
        or (selector.viewport_id is not None and selector.viewport_id != meta.get("viewport_id"))
        or physical.viewport_id != selector.viewport_id
        or physical.source_kind != "native_graphic_scale_bar"
        or type(physical.record_id) is not str or not physical.record_id
        or not _trusted_observations(physical.source_segment_observation_ids)
        or not _trusted_observations(physical.source_text_observation_ids)
        or _canonical_page(calibration.page_no) != floor.page_id
        or calibration.revision_id != floor.revision_id
        # A manual approval, title text, or OCR description cannot impersonate
        # the producer's one independently reconstructed native graphic bar.
        or calibration.source_type != ScaleSourceType.SCALE_BAR.value
        or calibration.status != ScaleCalibrationStatus.VALID.value
        or calibration.method != ScaleSourceType.SCALE_BAR.value.upper()
        or measurement_authority_for_page_scale(calibration) != AuthorityStatus.FIRM.value
        or not calibration.is_usable_for_firm_measurement()
        or meta.get("scale_fingerprint") != scale_calibration_fingerprint(calibration)
    ):
        return False
    try:
        return (
            type(physical.points_per_mm) is float
            and type(physical.source_span_pt) is float
            and type(physical.physical_span_mm) is float
            and all(math.isfinite(value) and value > 0 for value in (
                physical.points_per_mm, physical.source_span_pt, physical.physical_span_mm,
            ))
            and abs(physical.source_span_pt / physical.physical_span_mm - physical.points_per_mm)
            <= max(1e-9, physical.points_per_mm * 1e-12)
            and abs(calibration.px_per_m - physical.points_per_mm * 1000.0)
            <= max(1e-9, calibration.px_per_m * 1e-12)
            and abs(physical.mm_per_point * physical.points_per_mm - 1.0) <= 1e-12
            and physical.record_id == _source_physical_scale_record_id(physical)
        )
    except (ValueError, TypeError, OverflowError, ZeroDivisionError):
        return False


def source_owned_floor_scale_receipt(
    *,
    floor: LiveCanonicalFloorSurfaceObject,
    quantity: QuantityEvidence,
    bridge: PhysicalScaleCalibrationBridgeResult,
) -> Optional[LiveFloorScaleSourceReceipt]:
    """Issue only from the existing real physical-scale bridge and exact floor."""
    if type(bridge) is not PhysicalScaleCalibrationBridgeResult:
        return None
    if (
        bridge.status is not EvidenceResolutionStatus.CORROBORATED
        or bridge.reason_codes != (PHYSICAL_SCALE_CALIBRATION_RESOLVED,)
        or bridge.physical_scale_evidence is None
        or bridge.calibration is None
        or not _same_original_owners(floor, quantity, bridge.physical_scale_evidence, bridge.calibration)
    ):
        return None
    return LiveFloorScaleSourceReceipt(
        canonical_floor_id=floor.canonical_floor_id,
        physical_floor_surface_id=floor.physical_floor_surface_id,
        room_entity_id=floor.room_entity_id,
        source_room_face_record_id=floor.source_room_face_record_id,
        room_area_quantity_id=quantity.quantity_id,
        document_id=floor.document_id,
        revision_id=floor.revision_id,
        source_sha256=floor.source_sha256,
        snapshot_id=floor.snapshot_id,
        page_id=floor.page_id,
        viewport_id=str(quantity.metadata["viewport_id"]),
        scale_fingerprint=scale_calibration_fingerprint(bridge.calibration),
        physical_scale_evidence=bridge.physical_scale_evidence,
        calibration=bridge.calibration,
        _seal=_SOURCE_SEAL,
    )


def validated_floor_scale_metadata(
    receipt: object, *,
    floor: LiveCanonicalFloorSurfaceObject,
    source: QuantityEvidence,
) -> Optional[dict[str, object]]:
    """Return a customer-scale grant ONLY when original producer owners agree."""
    if type(receipt) is not LiveFloorScaleSourceReceipt or receipt._seal is not _SOURCE_SEAL:
        return None
    if (
        (receipt.canonical_floor_id, receipt.physical_floor_surface_id,
         receipt.room_entity_id, receipt.source_room_face_record_id,
         receipt.room_area_quantity_id, receipt.document_id,
         receipt.revision_id, receipt.source_sha256, receipt.snapshot_id,
         receipt.page_id, receipt.viewport_id)
        != (floor.canonical_floor_id, floor.physical_floor_surface_id,
            floor.room_entity_id, floor.source_room_face_record_id,
            source.quantity_id, floor.document_id, floor.revision_id,
            floor.source_sha256, floor.snapshot_id, floor.page_id,
            source.metadata.get("viewport_id"))
        or receipt.scale_fingerprint != scale_calibration_fingerprint(receipt.calibration)
        or not _same_original_owners(floor, source, receipt.physical_scale_evidence, receipt.calibration)
    ):
        return None
    return {
        "resolved_scale_id": receipt.physical_scale_evidence.record_id,
        "scale_status": "resolved",
        "scale_conflicts": (),
        "scale_fingerprint": receipt.scale_fingerprint,
    }


__all__ = [
    "LiveFloorScaleSourceReceipt",
    "source_owned_floor_scale_receipt",
    "validated_floor_scale_metadata",
]
