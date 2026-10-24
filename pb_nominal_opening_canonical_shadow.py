"""Owned nominal door/window dimensions for an unplaced canonical review item.

This reuses CanonicalOpening; it is not a second building graph. Nominal product
dimensions do not supply rough-opening geometry, wall placement, sill, storey,
scale, count or takeoff authority. The commercial flags always remain false.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import math

from pb_canonical_building import CanonicalOpening, Provenance, ReviewState
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, MeasurementRecord
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _build_approved_single_width_review(source, selector, *, approval, current_opening):
    """Bind an explicit width approval to one current single-figure source item.

    This is an unplaced review annotation. It does not change the source width
    authority, infer a height, override a schedule, or authorize a quantity.
    The caller supplies an existing MeasurementRecord, never a project-wide
    convention inferred from a number or a door's appearance.
    """
    from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject

    if (type(source) is not SourceVisibilityProducer or type(selector) is not ObservationSelector
            or type(approval) is not MeasurementRecord
            or type(current_opening) is not LiveCanonicalOpeningObject):
        raise TypeError("source-owned opening and explicit measurement approval required")
    physical = source.physical_opening_authority().prove_existence(selector)
    opening = physical.existence_record
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(selector)
    label = result.evidence
    if (physical.status is not EvidenceResolutionStatus.CORROBORATED or opening is None
            or result.status is not EvidenceResolutionStatus.CORROBORATED or label is None
            or label.opening_record_id != opening.record_id
            or len(label.dimension_values_mm) != 1
            or label.semantic_kind not in (None, "door", "window")):
        raise ValueError("one authenticated single-figure opening label required")
    owners = ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id")
    if (current_opening.physical_opening_id != opening.record_id
            or any(getattr(current_opening, k) != getattr(opening, k) for k in owners)):
        raise ValueError("current opening and source approval target disagree")
    if (current_opening.schedule_binding_record_id is not None
            or current_opening.schedule_declared_width_mm is not None
            or current_opening.schedule_declared_height_mm is not None
            or current_opening.width_record_id is not None
            or current_opening.width_m is not None):
        raise ValueError("nominal width review cannot override a schedule or resolved source width")
    metadata = approval.metadata
    if (approval.source_type != MeasurementAuthorityType.USER_APPROVED.value
            or approval.authority_status != AuthorityStatus.USER_APPROVED.value
            or type(approval.approved_by) is not str or not approval.approved_by.strip()
            or type(approval.approved_at) is not str
            or type(approval.value) not in (int, float) or not math.isfinite(approval.value)
            or approval.value <= 0 or approval.unit != "mm"
            or type(approval.page) is not int or str(approval.page) != opening.page_id
            or approval.geometry_ref != opening.record_id
            or type(metadata) is not dict
            or metadata.get("axis") != "width"
            or any(metadata.get(k) != getattr(opening, k) for k in owners)
            or metadata.get("label_evidence_id") != label.evidence_id
            or type(metadata.get("source_text_observation_ids")) not in (tuple, list)
            or any(type(v) is not str for v in metadata["source_text_observation_ids"])
            or len(metadata["source_text_observation_ids"]) != len(label.source_text_observation_ids)
            or set(metadata["source_text_observation_ids"]) != set(label.source_text_observation_ids)
            or approval.value != label.dimension_values_mm[0]):
        raise ValueError("explicit width approval must retain exact value, owner and label evidence")
    try:
        stamp = datetime.fromisoformat(approval.approved_at)
    except ValueError as exc:
        raise ValueError("approval requires a dated, timezone-aware owner record") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("approval requires a dated, timezone-aware owner record")
    approved = asdict(approval)
    approved["value"] = float(approved["value"])
    approved["metadata"]["source_text_observation_ids"] = sorted(label.source_text_observation_ids)
    approval_id = stable_contract_id("opening_nominal_width_approval", approved, digest_chars=32)
    return CanonicalOpening(
        id=opening.record_id, name=label.raw_text,
        opening_type="GENERIC" if label.semantic_kind is None else label.semantic_kind.upper(),
        width_m=approval.value / 1000.0, height_m=None,
        wall_id=None, offset_along_wall_m=None, sill_height_m=None,
        review_state=ReviewState.REVIEW_REQUIRED, takeoff_eligible=False, deduction_authority=False,
        provenance=Provenance(
            document_id=opening.document_id, page_id=opening.page_id,
            opening_instance_id=opening.record_id, coordinate_space="unplaced_nominal",
            producer_module=__name__, producer_version="1.1.0",
            contributing_evidence=[label.evidence_id, approval_id, *label.source_text_observation_ids]),
        metadata={**{k: getattr(opening, k) for k in owners},
                  "dimension_basis": "user_approved_single_nominal_width",
                  "nominal_width_approval_id": approval_id, "nominal_width_approval": approved,
                  "source_text_observation_ids": list(label.source_text_observation_ids),
                  "physical_opening_source_observation_ids": list(opening.source_observation_ids),
                  "source_width_authority_granted": False, "height_resolved": False,
                  "opening_kind_resolved": label.semantic_kind is not None,
                  "metric_wall_placement_resolved": False, "rough_opening_geometry_resolved": False,
                  "opening_count_resolved": False})


def build_nominal_opening_canonical_shadow(source, selector):
    if type(source) is not SourceVisibilityProducer or type(selector) is not ObservationSelector:
        raise TypeError("producer-owned source and exact observation selector required")
    physical = source.physical_opening_authority().prove_existence(selector)
    opening = physical.existence_record
    if physical.status is not EvidenceResolutionStatus.CORROBORATED or opening is None:
        return None
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source).ordered_compact_axes_shadow(selector)
    axes = result.evidence
    if (result.status is not EvidenceResolutionStatus.CORROBORATED or axes is None
            or axes.opening_record_id != opening.record_id
            or axes.semantic_kind not in ("door", "window")
            or axes.width_mm is None or axes.height_mm is None):
        return None
    return CanonicalOpening(
        id=opening.record_id, name=axes.raw_text, opening_type=axes.semantic_kind.upper(),
        width_m=axes.width_mm/1000.0, height_m=axes.height_mm/1000.0,
        wall_id=None, offset_along_wall_m=None, sill_height_m=None,
        review_state=ReviewState.REVIEW_REQUIRED,
        takeoff_eligible=False, deduction_authority=False,
        provenance=Provenance(
            document_id=opening.document_id, page_id=opening.page_id,
            opening_instance_id=opening.record_id, coordinate_space="unplaced_nominal",
            producer_module=__name__, producer_version="1.0.0",
            contributing_evidence=[axes.evidence_id, *axes.source_text_observation_ids]),
        metadata={"source_sha256":opening.source_sha256,
                  "revision_id":opening.revision_id, "snapshot_id":opening.snapshot_id,
                  "dimension_basis":"nominal_compact_HHWW",
                  "source_text_observation_ids":list(axes.source_text_observation_ids),
                  "physical_opening_source_observation_ids":list(opening.source_observation_ids),
                  "metric_wall_placement_resolved":False,
                  "rough_opening_geometry_resolved":False,
                  "opening_count_resolved":False})
