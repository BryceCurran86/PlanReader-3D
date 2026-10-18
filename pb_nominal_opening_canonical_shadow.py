"""Owned nominal door/window dimensions for an unplaced canonical review item.

This reuses CanonicalOpening; it is not a second building graph. Nominal product
dimensions do not supply rough-opening geometry, wall placement, sill, storey,
scale, count or takeoff authority. The commercial flags always remain false.
"""
from __future__ import annotations

from pb_canonical_building import CanonicalOpening, Provenance, ReviewState
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


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
