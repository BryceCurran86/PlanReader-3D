import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_pipeline_failure_recovery_shadow import (
    PipelineFailureRecoveryShadowAuthority,
    PartialPlanRecoveryReport,
    SubsystemKind,
    SubsystemStatus,
    SCHEMA_VERSION,
)


def test_guarded_subsystem_success():
    authority = PipelineFailureRecoveryShadowAuthority()

    def dummy_walls_extractor():
        return [{"wall_id": "W1"}, {"wall_id": "W2"}]

    res = authority.execute_guarded_subsystem(
        SubsystemKind.WALLS,
        dummy_walls_extractor,
    )

    assert res.subsystem == SubsystemKind.WALLS
    assert res.status == SubsystemStatus.SUCCESS
    assert res.recovered_object_count == 2
    assert res.error_reason_code is None
    assert "successfully" in res.diagnostic_message
    assert len(res.payload) == 2


def test_guarded_subsystem_quarantined_on_exception():
    authority = PipelineFailureRecoveryShadowAuthority()

    def failing_openings_extractor():
        raise ValueError("Malformed opening polygon geometry")

    res = authority.execute_guarded_subsystem(
        SubsystemKind.OPENINGS,
        failing_openings_extractor,
    )

    assert res.subsystem == SubsystemKind.OPENINGS
    assert res.status == SubsystemStatus.QUARANTINED
    assert res.recovered_object_count == 0
    assert res.error_reason_code == "SUBSYSTEM_QUARANTINED_VALUEERROR"
    assert "Malformed opening polygon geometry" in res.diagnostic_message
    assert res.payload is None


def test_compile_recovery_report_partial_success():
    authority = PipelineFailureRecoveryShadowAuthority()

    authority.execute_guarded_subsystem(
        SubsystemKind.WALLS,
        lambda: [{"wall_id": "W1"}],
    )
    authority.execute_guarded_subsystem(
        SubsystemKind.OPENINGS,
        lambda: (_ for _ in ()).throw(RuntimeError("Timeout waiting for schedule")),
    )
    authority.execute_guarded_subsystem(
        SubsystemKind.ROOMS,
        lambda: [{"room_id": "R1"}, {"room_id": "R2"}],
    )

    report = authority.compile_recovery_report(
        document_id="DOC_LOT16",
        revision_id="REV_C",
        source_sha256="deadbeef" * 8,
    )

    assert isinstance(report, PartialPlanRecoveryReport)
    assert report.total_subsystems_count == 3
    assert report.healthy_subsystems_count == 2
    assert report.quarantined_subsystems_count == 1
    assert report.is_partial_recovery is True
    assert report.status == EvidenceResolutionStatus.CORROBORATED
    assert report.commercial_projection_allowed is False
    assert report.takeoff_eligible is False
    assert report.schema_version == SCHEMA_VERSION

    d = report.to_dict()
    assert d["document_id"] == "DOC_LOT16"
    assert len(d["subsystems"]) == 3
    assert d["is_partial_recovery"] is True


def test_compile_recovery_report_total_quarantine():
    authority = PipelineFailureRecoveryShadowAuthority()

    authority.execute_guarded_subsystem(
        SubsystemKind.WALLS,
        lambda: (_ for _ in ()).throw(ValueError("Corrupt PDF")),
    )

    report = authority.compile_recovery_report(
        document_id="DOC_FAIL",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
    )

    assert report.total_subsystems_count == 1
    assert report.healthy_subsystems_count == 0
    assert report.quarantined_subsystems_count == 1
    assert report.is_partial_recovery is False
    assert report.status == EvidenceResolutionStatus.ABSTAINED


def test_partial_plan_recovery_report_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        PartialPlanRecoveryReport(
            report_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_subsystems_count=0,
            healthy_subsystems_count=0,
            quarantined_subsystems_count=0,
            subsystems=(),
            is_partial_recovery=False,
            status=EvidenceResolutionStatus.ABSTAINED,
        )
