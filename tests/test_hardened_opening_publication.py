from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_hardened_opening_publication import (
    OPENING_PUBLICATION_RESOLVED,
    publish_canonical_opening_quantity,
)
from pb_measurement_input_authority import MeasurementInputResolution
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingRecord,
    OpeningHostBindingResult,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningExistenceRecord,
)


SHA = "a" * 64


def _existence(physical_id: str = "physical-opening-1") -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id="evidence-record-v2",
        source_observation_ids=("obs-a", "obs-b"),
        source_lineage_root_ids=("root-a",),
        document_id="doc",
        revision_id="R2",
        source_sha256=SHA,
        snapshot_id="snapshot-v2",
        page_id="3",
        viewport_id="plan-vp",
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern="paired_jamb_gap",
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=("physical_opening_exists",),
        producer_method="opening-detector",
        producer_version="2.0",
        producer_generation=2,
        physical_identity_fingerprint=physical_id,
        evidence_fingerprint="evidence-fingerprint-v2",
    )


def _host(opening_identity_id: str = "physical-opening-1") -> OpeningHostBindingResult:
    return OpeningHostBindingResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(OPENING_HOST_BINDING_RESOLVED,),
        record=OpeningHostBindingRecord(
            record_id="host-binding-v2",
            document_id="doc",
            revision_id="R2",
            source_sha256=SHA,
            snapshot_id="snapshot-v2",
            page_id="3",
            decision_scope_id="host-scope",
            opening_identity_id=opening_identity_id,
            host_wall_id="physical-host-wall-1",
            member_wall_candidate_ids=("wall-face-a", "wall-face-b"),
            member_candidate_identity_ids=("wall-a", "wall-b"),
            member_equivalence_groups=(("wall-a",), ("wall-b",)),
            source_observation_ids=("wall-obs-a", "wall-obs-b"),
        ),
    )


def _measurement(value_m: float, evidence_id: str) -> MeasurementInputResolution:
    return MeasurementInputResolution(
        value_m=value_m,
        source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        authority_status=AuthorityStatus.FIRM.value,
        document_id="doc",
        source_sha256=SHA,
        revision_id="R2",
        page_no=3,
        viewport_id="plan-vp",
        entity_id="physical-opening-1",
        evidence_ids=(evidence_id,),
        figured_evidence_id=evidence_id,
        blocking_reasons=(),
        notes="authenticated figured dimension",
    )


def test_opening_gate_publishes_only_after_host_identity_and_measurements() -> None:
    result = publish_canonical_opening_quantity(
        existence=_existence(),
        host_binding=_host(),
        width=_measurement(0.9, "dim-width"),
        height=_measurement(2.1, "dim-height"),
        opening_type="DOOR",
        mark="D01",
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_PUBLICATION_RESOLVED,)
    assert result.canonical_opening is not None
    assert result.canonical_opening.wall_id == "physical-host-wall-1"
    assert result.canonical_opening.width_m == pytest.approx(0.9)
    assert result.canonical_opening.height_m == pytest.approx(2.1)
    assert result.canonical_opening.metadata["physical_identity_fingerprint"] == "physical-opening-1"
    assert result.quantity_m2 == pytest.approx(1.89)


def test_opening_gate_rejects_host_bound_to_different_physical_identity() -> None:
    result = publish_canonical_opening_quantity(
        existence=_existence(),
        host_binding=_host("different-physical-opening"),
        width=_measurement(0.9, "dim-width"),
        height=_measurement(2.1, "dim-height"),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.canonical_opening is None
    assert result.quantity_m2 is None
