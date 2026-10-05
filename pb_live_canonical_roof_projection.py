"""Canonical roof projection from source-owned gable roof measurement.

Preserves only geometry already proven by SourceRoofCoveringMeasurement. The
projection does not invent a plan polygon, elevation, overhang, framing layout,
or engineering design. It is a parametric physical-roof object that downstream
systems may enrich when stronger source evidence arrives.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_roof_covering_authority import SourceRoofCoveringMeasurement


LIVE_CANONICAL_ROOF_SCHEMA_VERSION = "1.1.0"
LIVE_CANONICAL_ROOF_RESOLVED = "live_canonical_roof_resolved"
LIVE_CANONICAL_ROOF_UNAVAILABLE = "live_canonical_roof_unavailable"
LIVE_CANONICAL_ROOF_LINEAGE_INVALID = "live_canonical_roof_lineage_invalid"


@dataclass(frozen=True)
class LiveCanonicalRoofObject:
    canonical_roof_id: str
    physical_roof_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    roof_type: str
    source_page: int
    source_viewport_id: Optional[str]
    pitch_deg: float
    cross_ridge_span_m: float
    ridge_length_m: float
    slope_length_m: float
    covering_area_m2: float
    apex_xy_source_pts: tuple[float, float]
    left_support_xy_source_pts: tuple[float, float]
    right_support_xy_source_pts: tuple[float, float]
    matched_footprint_axis: Optional[str]
    scaled_structural_span_m: Optional[float]
    material_annotations: tuple[str, ...]
    quantity_id: str
    evidence_ids: tuple[str, ...]
    provenance: Mapping[str, object]
    elevation_profile_complete: bool = True
    metric_parameter_geometry_complete: bool = True
    plan_geometry_complete: bool = False
    overhang_included: bool = False
    schema_version: str = LIVE_CANONICAL_ROOF_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_roof_id": self.canonical_roof_id,
            "physical_roof_id": self.physical_roof_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "roof_type": self.roof_type,
            "source_page": self.source_page,
            "source_viewport_id": self.source_viewport_id,
            "pitch_deg": self.pitch_deg,
            "cross_ridge_span_m": self.cross_ridge_span_m,
            "ridge_length_m": self.ridge_length_m,
            "slope_length_m": self.slope_length_m,
            "covering_area_m2": self.covering_area_m2,
            "apex_xy_source_pts": list(self.apex_xy_source_pts),
            "left_support_xy_source_pts": list(self.left_support_xy_source_pts),
            "right_support_xy_source_pts": list(self.right_support_xy_source_pts),
            "matched_footprint_axis": self.matched_footprint_axis,
            "scaled_structural_span_m": self.scaled_structural_span_m,
            "material_annotations": list(self.material_annotations),
            "quantity_id": self.quantity_id,
            "evidence_ids": list(self.evidence_ids),
            "provenance": dict(self.provenance),
            "elevation_profile_complete": self.elevation_profile_complete,
            "metric_parameter_geometry_complete": self.metric_parameter_geometry_complete,
            "plan_geometry_complete": self.plan_geometry_complete,
            "overhang_included": self.overhang_included,
            "schema_version": self.schema_version,
        }

@dataclass(frozen=True)
class LiveCanonicalRoofProjection:
    object: Optional[LiveCanonicalRoofObject]
    reason_codes: tuple[str, ...]


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0.0


def project_source_gable_roof(
    measurement: SourceRoofCoveringMeasurement,
) -> LiveCanonicalRoofProjection:
    """Preserve one corroborated gable roof as a parametric canonical object."""

    if type(measurement) is not SourceRoofCoveringMeasurement:
        raise TypeError("measurement must be SourceRoofCoveringMeasurement")

    evidence = measurement.gable_evidence
    quantity = measurement.quantity_evidence
    if (
        measurement.status is not EvidenceResolutionStatus.CORROBORATED
        or evidence is None
        or quantity is None
        or quantity.abstained
        or quantity.value is None
        or str(quantity.status) != EvidenceResolutionStatus.CORROBORATED.value
        or not quantity.evidence_ids
        or not measurement.document_id
        or not measurement.revision_id
        or not measurement.source_sha256
        or not measurement.snapshot_id
        or not measurement.physical_roof_id
        or quantity.input_entity_ids != (measurement.physical_roof_id,)
        or not _finite_positive(measurement.pitch_deg)
        or not _finite_positive(measurement.cross_ridge_span_m)
        or not _finite_positive(measurement.ridge_length_m)
        or not _finite_positive(measurement.slope_length_m)
        or not _finite_positive(measurement.roof_covering_area_m2)
    ):
        return LiveCanonicalRoofProjection(
            object=None,
            reason_codes=(LIVE_CANONICAL_ROOF_UNAVAILABLE,),
        )
    if (
        int(evidence.source_page) <= 0
        or len(evidence.apex_xy) != 2
        or len(evidence.left_support_xy) != 2
        or len(evidence.right_support_xy) != 2
        or not all(
            math.isfinite(float(value))
            for point in (
                evidence.apex_xy,
                evidence.left_support_xy,
                evidence.right_support_xy,
            )
            for value in point
        )
    ):
        return LiveCanonicalRoofProjection(
            object=None,
            reason_codes=(LIVE_CANONICAL_ROOF_LINEAGE_INVALID,),
        )

    quantity_value = float(quantity.value)
    if not math.isclose(
        quantity_value,
        float(measurement.roof_covering_area_m2),
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        return LiveCanonicalRoofProjection(
            object=None,
            reason_codes=(LIVE_CANONICAL_ROOF_LINEAGE_INVALID,),
        )

    metadata = dict(measurement.metadata or {})
    matched_axis = metadata.get("matched_footprint_axis")
    scaled_span = metadata.get("scaled_structural_span_m")
    if scaled_span is not None:
        try:
            scaled_span = float(scaled_span)
        except (TypeError, ValueError, OverflowError):
            return LiveCanonicalRoofProjection(
                object=None,
                reason_codes=(LIVE_CANONICAL_ROOF_LINEAGE_INVALID,),
            )
        if not math.isfinite(scaled_span) or scaled_span <= 0.0:
            return LiveCanonicalRoofProjection(
                object=None,
                reason_codes=(LIVE_CANONICAL_ROOF_LINEAGE_INVALID,),
            )
    canonical_id = str(measurement.physical_roof_id)
    provenance = {
        "authority": quantity.authority,
        "formula": quantity.formula,
        "formula_version": quantity.formula_version,
        "reason_codes": list(measurement.reason_codes),
        "source_scale_denominator": evidence.source_scale_denominator,
        "evidence_ids": list(quantity.evidence_ids),
    }

    return LiveCanonicalRoofProjection(
        object=LiveCanonicalRoofObject(
            canonical_roof_id=canonical_id,
            physical_roof_id=str(measurement.physical_roof_id),
            document_id=str(measurement.document_id),
            revision_id=str(measurement.revision_id),
            source_sha256=str(measurement.source_sha256),
            snapshot_id=str(measurement.snapshot_id),
            roof_type="gable",
            source_page=int(evidence.source_page),
            source_viewport_id=evidence.source_viewport_id,
            pitch_deg=float(measurement.pitch_deg),
            cross_ridge_span_m=float(measurement.cross_ridge_span_m),
            ridge_length_m=float(measurement.ridge_length_m),
            slope_length_m=float(measurement.slope_length_m),
            covering_area_m2=float(measurement.roof_covering_area_m2),
            apex_xy_source_pts=tuple(float(v) for v in evidence.apex_xy),
            left_support_xy_source_pts=tuple(
                float(v) for v in evidence.left_support_xy
            ),
            right_support_xy_source_pts=tuple(
                float(v) for v in evidence.right_support_xy
            ),
            matched_footprint_axis=(
                str(matched_axis) if matched_axis is not None else None
            ),
            scaled_structural_span_m=scaled_span,
            material_annotations=tuple(evidence.material_annotations),
            quantity_id=str(quantity.quantity_id),
            evidence_ids=tuple(quantity.evidence_ids),
            provenance=provenance,
        ),
        reason_codes=(LIVE_CANONICAL_ROOF_RESOLVED,),
    )


__all__ = [
    "LIVE_CANONICAL_ROOF_LINEAGE_INVALID",
    "LIVE_CANONICAL_ROOF_RESOLVED",
    "LIVE_CANONICAL_ROOF_SCHEMA_VERSION",
    "LIVE_CANONICAL_ROOF_UNAVAILABLE",
    "LiveCanonicalRoofObject",
    "LiveCanonicalRoofProjection",
    "project_source_gable_roof",
]
