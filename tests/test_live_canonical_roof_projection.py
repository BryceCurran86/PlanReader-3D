from __future__ import annotations

from dataclasses import replace

from pb_live_canonical_roof_projection import (
    LIVE_CANONICAL_ROOF_LINEAGE_INVALID,
    LIVE_CANONICAL_ROOF_RESOLVED,
    LIVE_CANONICAL_ROOF_UNAVAILABLE,
    project_source_gable_roof,
)
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_migration_contracts import EvidenceResolutionStatus
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication
from pb_source_roof_covering_authority import (
    GableRoofApexEvidence,
    SourceRoofCoveringMeasurement,
    measure_source_roof_covering,
)


def _measurement() -> SourceRoofCoveringMeasurement:
    evidence = GableRoofApexEvidence(
        apex_xy=(150.0, 40.0),
        pitch_deg=30.0,
        left_pitch_deg=30.0,
        right_pitch_deg=30.0,
        left_run_pt=80.0,
        right_run_pt=80.0,
        left_support_xy=(70.0, 86.188),
        right_support_xy=(230.0, 86.188),
        member_count=2,
        source_viewport_id="elevation-1",
        source_page=3,
        source_scale_denominator=(8.0 * 1000.0 * 72.0) / (160.0 * 25.4),
        material_annotations=("METAL ROOF SHEETING",),
        reason_codes=("authenticated_gable_roofline",),
    )
    return measure_source_roof_covering(
        evidence,
        building_length_m=12.0,
        building_width_m=8.0,
        source_sha256="a" * 64,
        document_id="roof-projection-test",
    )

def test_corroborated_gable_measurement_projects_to_canonical_roof() -> None:
    measurement = _measurement()
    assert measurement.status is EvidenceResolutionStatus.CORROBORATED

    result = project_source_gable_roof(measurement)

    assert result.reason_codes == (LIVE_CANONICAL_ROOF_RESOLVED,)
    assert result.object is not None
    roof = result.object
    assert roof.canonical_roof_id == roof.physical_roof_id
    assert roof.physical_roof_id == measurement.physical_roof_id
    assert roof.document_id == "roof-projection-test"
    assert roof.revision_id == "source:" + ("a" * 64)
    assert roof.source_sha256 == "a" * 64
    assert roof.snapshot_id == "source:" + ("a" * 64)
    assert roof.roof_type == "gable"
    assert roof.source_page == 3
    assert roof.source_viewport_id == "elevation-1"
    assert roof.pitch_deg == 30.0
    assert roof.cross_ridge_span_m == 8.0
    assert roof.ridge_length_m == 12.0
    assert roof.slope_length_m > roof.cross_ridge_span_m
    assert roof.covering_area_m2 == measurement.roof_covering_area_m2
    assert roof.evidence_ids == measurement.quantity_evidence.evidence_ids
    assert roof.quantity_id == measurement.quantity_evidence.quantity_id
    assert roof.elevation_profile_complete is True
    assert roof.metric_parameter_geometry_complete is True
    assert roof.plan_geometry_complete is False
    assert roof.overhang_included is False
    assert roof.material_annotations == ("METAL ROOF SHEETING",)

def test_roof_projection_is_deterministic_for_same_source_evidence() -> None:
    measurement = _measurement()

    first = project_source_gable_roof(measurement)
    second = project_source_gable_roof(measurement)

    assert first.object is not None
    assert second.object is not None
    assert first.object.to_dict() == second.object.to_dict()


def test_physical_roof_identity_is_stable_across_source_revision_evidence_churn() -> None:
    first_measurement = _measurement()
    evidence = first_measurement.gable_evidence
    assert evidence is not None

    second_measurement = measure_source_roof_covering(
        evidence,
        building_length_m=12.0,
        building_width_m=8.0,
        source_sha256="b" * 64,
        document_id="roof-projection-test",
        revision_id="revision-2",
        snapshot_id="snapshot-2",
    )

    first = project_source_gable_roof(first_measurement)
    second = project_source_gable_roof(second_measurement)
    assert first.object is not None
    assert second.object is not None
    assert first.object.physical_roof_id == second.object.physical_roof_id
    assert first.object.canonical_roof_id == second.object.canonical_roof_id
    assert first.object.source_sha256 != second.object.source_sha256
    assert first.object.quantity_id != second.object.quantity_id


def test_roof_quantity_is_attached_to_canonical_roof_in_coverage_registry() -> None:
    measurement = _measurement()
    projection = project_source_gable_roof(measurement)
    assert projection.object is not None
    assert measurement.quantity_evidence is not None

    summaries, gaps = collect_live_canonical_coverage(
        objects=(projection.object,),
        quantities=(measurement.quantity_evidence,),
        registry_run_scope="roof-quantity-link",
    )
    assert gaps == {}
    assert len(summaries) == 1
    record = summaries[0].object_records[0]
    assert record.object_id == projection.object.physical_roof_id
    assert record.quantity_ids == (measurement.quantity_evidence.quantity_id,)
    assert record.quantity_contribution[measurement.quantity_evidence.quantity_id] == measurement.quantity_evidence.value

    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    family = report["family_reports"]["roof"]
    assert family["classification"] == "PARTIAL"
    assert family["stage_counts"]["CANONICALIZED"] == 1
    assert family["stage_counts"]["QUANTIFIED"] == 1
    assert family["stage_counts"]["PUBLISHED"] == 0


def test_quantity_geometry_mismatch_fails_closed() -> None:
    measurement = _measurement()
    altered = replace(
        measurement,
        roof_covering_area_m2=float(measurement.roof_covering_area_m2) + 1.0,
    )

    result = project_source_gable_roof(altered)

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_ROOF_LINEAGE_INVALID,)


def test_abstained_measurement_does_not_become_canonical_roof() -> None:
    measurement = _measurement()
    blocked = replace(
        measurement,
        status=EvidenceResolutionStatus.ABSTAINED,
        pitch_deg=None,
        roof_covering_area_m2=None,
        quantity_evidence=None,
    )

    result = project_source_gable_roof(blocked)

    assert result.object is None
    assert result.reason_codes == (LIVE_CANONICAL_ROOF_UNAVAILABLE,)
