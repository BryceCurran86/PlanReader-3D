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


def test_pipeline_without_acting_user_leaves_created_by_missing() -> None:
    """Package construction must not invent created_by when acting_user is omitted."""
    import sqlite3

    from pb_jobhub_publishing_pipeline import build_publishing_package_from_workspace
    from pb_jobhub_publishing_contract import PublishingMode

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE workspaces (
            id INTEGER PRIMARY KEY, job_no TEXT, job_name TEXT, builder_client TEXT,
            site_address TEXT, drawing_issue TEXT, jobhub_job_id INTEGER, estimator TEXT
        );
        CREATE TABLE documents (id INTEGER PRIMARY KEY, workspace_id INTEGER, file_name TEXT);
        CREATE TABLE pages (id INTEGER PRIMARY KEY, workspace_id INTEGER, page_no INTEGER);
        CREATE TABLE takeoff_rows (
            id INTEGER PRIMARY KEY, workspace_id INTEGER, section TEXT, location TEXT,
            substrate TEXT, finish_tag TEXT, element TEXT, unit TEXT, quantity REAL,
            rate REAL, total_price REAL, commercial_authority_status TEXT,
            commercial_authority_source TEXT, commercial_authority_reviewed_by TEXT,
            commercial_authority_reviewed_at TEXT, source_page TEXT, notes TEXT
        );
        INSERT INTO workspaces VALUES (1,'26-001','Sample','Builder','1 St','A',1,NULL);
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag, element, unit,
            quantity, rate, total_price, commercial_authority_status, commercial_authority_source
        ) VALUES (1,1,'Walls','L1','PB','P01','Wall','m2',10,1,10,'firm','documented_dimension');
        """
    )
    pkg = build_publishing_package_from_workspace(
        conn=conn,
        workspace_id=1,
        mode=PublishingMode.COMMERCIAL,
    )
    assert pkg.created_by is None
    assert pkg.project_identity.estimator is None
    result = validate_publishing_gate(pkg)
    assert result.status == PublishingGateStatus.BLOCKED.value


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
