"""Source-sealed nominal gross frame TYPE area, not installed opening takeoff.

One original A610-like figured elevation can prove the gross OUTER FRAME area
of one named window TYPE.  That does not prove a physical aperture, installed
unit, host, installation count, wall void or customer installed-area total.
The installed publisher remains pb_live_opening_area_quantity_publication.
"""
from __future__ import annotations

import math
import re

from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence, stable_contract_id
from pb_opening_elevation_frame_area_authority import (
    OpeningElevationFrameAreaAuthority,
    OpeningElevationFrameAreaRecord,
    OpeningElevationFrameAreaSelector,
)


SOURCE_ELEVATION_FRAME_TYPE_AREA_SCHEMA_VERSION = "1.0.0"
SOURCE_ELEVATION_FRAME_TYPE_AREA_CORROBORATED = "source_elevation_frame_type_area_corrob"
SOURCE_ELEVATION_FRAME_TYPE_AREA_AUTHORITY = (
    "pb_opening_elevation_frame_area_authority.source_owned_nominal_outer_frame_type"
)
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _ids(values) -> tuple[str, ...] | None:
    if type(values) not in (list, tuple):
        return None
    if any(type(v) is not str or not v or v != v.strip() for v in values):
        return None
    if len(set(values)) != len(values):
        return None
    return tuple(values)


def publish_nominal_elevation_frame_type_area(
    record: OpeningElevationFrameAreaRecord,
    *,
    authority: OpeningElevationFrameAreaAuthority,
) -> QuantityEvidence | None:
    """Reissue only a real sealed frame type with independent exact source IDs.

    This quantity has a distinct family and an explicit non-installed scope:
    it can populate a reference schedule, but cannot be merged into installed
    door/window counts, frame deductions or commercial opening-area totals.
    """
    if type(record) is not OpeningElevationFrameAreaRecord:
        raise TypeError("producer-owned OpeningElevationFrameAreaRecord required")
    if type(authority) is not OpeningElevationFrameAreaAuthority:
        raise TypeError("producer-owned OpeningElevationFrameAreaAuthority required")
    # The record dataclass's private constructor seal survives dataclasses.replace.
    # A copied receipt can carry altered witness/frame fields and still look
    # CORROBORATED. Re-resolve exact source/snapshot/type from the producer-owned
    # authority and compare the WHOLE record before any numeric evidence issues.
    parent = authority.resolve(OpeningElevationFrameAreaSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        type_mark=record.type_mark,
    ))
    if (
        parent.status is not EvidenceResolutionStatus.CORROBORATED
        or parent.record is None
        or parent.record != record
    ):
        return None
    source_ids = _ids(record.source_observation_ids)
    frame_ids = _ids(record.frame_geometry_ids)
    title_ids = _ids(record.title_observation_ids)
    dimension_word_ids = _ids(record.dimension_observation_ids)
    dimension_line_ids = _ids(record.dimension_line_ids)
    witness_ids = _ids(record.witness_line_ids)
    required = (
        record.record_id,record.document_id,record.revision_id,record.snapshot_id,
        record.page_id,record.type_mark,record.mark_observation_id,
    )
    if (
        record.status is not EvidenceResolutionStatus.CORROBORATED
        or record.opening_kind not in {"window","door"}
        or any(type(v) is not str or not v or v != v.strip() for v in required)
        or type(record.source_sha256) is not str
        or _SHA256.fullmatch(record.source_sha256) is None
        or not record.page_id.isdecimal()
        or not source_ids or not frame_ids or not title_ids
        or not dimension_word_ids or len(dimension_word_ids)!=2
        or not dimension_line_ids or len(dimension_line_ids)!=2
        or not witness_ids
        or record.mark_observation_id not in source_ids
        or not set(title_ids).issubset(source_ids)
        or not set(dimension_word_ids).issubset(source_ids)
    ):
        return None
    if any(type(v) not in (int,float) for v in
           (record.axis_x_mm,record.axis_y_mm,record.area_m2)):
        return None
    x,y,area = record.axis_x_mm,record.axis_y_mm,record.area_m2
    if (not all(math.isfinite(v) and v>0 for v in (x,y,area))
            or not math.isclose(area,x*y/1_000_000.0,rel_tol=0,abs_tol=1e-9)):
        return None

    payload={
        "schema":SOURCE_ELEVATION_FRAME_TYPE_AREA_SCHEMA_VERSION,
        "record_id":record.record_id,
        "document_id":record.document_id,
        "revision_id":record.revision_id,
        "source_sha256":record.source_sha256,
        "snapshot_id":record.snapshot_id,
        "type_mark":record.type_mark,
        "opening_kind":record.opening_kind,
        "area_m2":area,
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("source_elevation_frame_type_area",payload,digest_chars=32),
        family="opening_nominal_frame_type_area",
        semantic_key=f"{record.opening_kind}_frame_type:{record.type_mark}",
        value=area,
        unit="m2",
        input_entity_ids=(record.record_id,),
        formula="source-authenticated outer-frame figured axis_x_mm * axis_y_mm / 1_000_000",
        formula_version=SOURCE_ELEVATION_FRAME_TYPE_AREA_SCHEMA_VERSION,
        evidence_ids=tuple(sorted({
            record.record_id,*source_ids,*frame_ids,*dimension_line_ids,*witness_ids,
        })),
        authority=SOURCE_ELEVATION_FRAME_TYPE_AREA_AUTHORITY,
        status="corroborated_type_only",
        confidence=1.0,
        abstained=False,
        reason_codes=(SOURCE_ELEVATION_FRAME_TYPE_AREA_CORROBORATED,),
        metadata={
            "document_id":record.document_id,
            "revision_id":record.revision_id,
            "source_sha256":record.source_sha256,
            "snapshot_id":record.snapshot_id,
            "source_page_id":record.page_id,
            "type_mark":record.type_mark,
            "opening_kind":record.opening_kind,
            "source_frame_area_record_id":record.record_id,
            "axis_x_mm":x,
            "axis_y_mm":y,
            "quantity_scope":"single_nominal_frame_type",
            "installed_opening_count_granted":False,
            "physical_opening_identity_granted":False,
            "host_wall_binding_granted":False,
            "commercial_installed_quantity_granted":False,
            "customer_installed_takeoff_eligible":False,
        },
    )


__all__=[
    "SOURCE_ELEVATION_FRAME_TYPE_AREA_SCHEMA_VERSION",
    "SOURCE_ELEVATION_FRAME_TYPE_AREA_AUTHORITY",
    "SOURCE_ELEVATION_FRAME_TYPE_AREA_CORROBORATED",
    "publish_nominal_elevation_frame_type_area",
]
