"""Commercial identity default safety regressions."""
from __future__ import annotations

from pb_jobhub_publishing_contract import (
    DrawingRevisionPayload,
    ProjectIdentityPayload,
    PublishingGateStatus,
    PublishingMode,
    PublishingPackagePayload,
    QuantityLineItemPayload,
    validate_publishing_gate,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_takeoff_output_authority import AuthorityStatus


def _minimal_commercial_package(
    *,
    estimator: str | None = None,
    created_by: str | None = None,
    approved_by: str | None = None,
) -> PublishingPackagePayload:
    return PublishingPackagePayload(
        workspace_id=1,
        mode=PublishingMode.COMMERCIAL.value,
        project_identity=ProjectIdentityPayload(
            job_no="26-001",
            job_name="Sample Project",
            site_address="1 Example Street",
            builder_client="Example Builder",
            estimator=estimator,
        ),
        drawing_revision=DrawingRevisionPayload(
            drawing_issue="A",
            drawing_date="2026-01-01",
            sheet_count=1,
            source_files_hash="abc123",
        ),
        quantities=[
            QuantityLineItemPayload(
                row_id=1,
                section="Walls",
                location="Level 1",
                substrate="Masonry",
                finish_tag="P01",
                element="Internal wall",
                unit="m2",
                quantity=10.0,
                rate=1.0,
                total_price=10.0,
                authority_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                authority_status=AuthorityStatus.FIRM.value,
                confidence=1.0,
                approved_by=approved_by,
            )
        ],
        created_by=created_by,
    )


def test_missing_estimator_and_created_by_default_to_none() -> None:
    ident = ProjectIdentityPayload(
        job_no="26-001",
        job_name="Sample",
        site_address="1 Example Street",
        builder_client="Builder",
    )
    package = _minimal_commercial_package()
    assert ident.estimator is None
    assert package.created_by is None


def test_commercial_publish_blocks_without_estimator_or_created_by() -> None:
    result = validate_publishing_gate(_minimal_commercial_package())
    assert result.status == PublishingGateStatus.BLOCKED.value
    assert not result.is_publishable
    assert any("Missing estimator attribution" in reason for reason in result.blocking_reasons)
    assert any("Missing created_by attribution" in reason for reason in result.blocking_reasons)


def test_explicit_attribution_preserved_for_commercial_publish() -> None:
    result = validate_publishing_gate(
        _minimal_commercial_package(
            estimator="Jane Estimator",
            created_by="Jane Estimator",
            approved_by="Jane Estimator",
        )
    )
    assert result.is_publishable
    assert result.status == PublishingGateStatus.APPROVED.value
