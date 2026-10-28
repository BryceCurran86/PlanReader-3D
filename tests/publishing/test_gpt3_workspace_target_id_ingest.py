"""Workspace destination IDs must not be cast into JobHub write authority.

Source-neutral actual SQLite workspace -> sealed package -> JobHub consumer tests.
These do not authenticate original drawings, signed FIRM, or frozen V2 score.
"""
from __future__ import annotations

import sqlite3

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _one_source_neutral_row(pr):
    pr.execute(
        """
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            commercial_authority_reviewed_by, source_page
        ) VALUES (
            1, 1, 'Internal walls', 'Unit 1', 'Plasterboard', 'PB01',
            'Internal Wall', 'm2', 10.0, 20.0, 200.0,
            'firm', 'documented_dimension', 'Source Estimator', 'A101'
        )
        """
    )
    pr.commit()


@pytest.mark.parametrize(("raw_id", "stored_type"), [
    (501.9, "real"),
    (501.1, "real"),
    (-501, "integer"),
    (0, "integer"),
    ("not-a-job", "text"),
    (sqlite3.Binary(b"501"), "blob"),
    (float("inf"), "real"),
])
@pytest.mark.parametrize("mode", [PublishingMode.DRAFT, PublishingMode.COMMERCIAL])
def test_noncanonical_workspace_id_cannot_be_sealed_or_published(
    test_dbs, raw_id, stored_type, mode,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    # SQLite's INTEGER affinity does NOT require every stored value to be int.
    # The old int(raw_id) truncated REAL 501.9 to the real target 501.
    pr.execute("UPDATE workspaces SET jobhub_job_id=? WHERE id=1", (raw_id,))
    pr.commit()
    assert pr.execute(
        "SELECT typeof(jobhub_job_id) FROM workspaces WHERE id=1"
    ).fetchone()[0] == stored_type
    hub.execute(
        "INSERT INTO jobs (id, status, notes, job_no) "
        "VALUES (1, 'Active', 'Same number other job', '26-017')"
    )
    hub.commit()

    with pytest.raises(ValueError, match="exact positive integer"):
        build_publishing_package_from_workspace(
            pr, workspace_id=1, mode=mode,
            acting_user="Source Estimator",
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize(("mode", "expected"), [
    (PublishingMode.COMMERCIAL, "Published"),
    (PublishingMode.DRAFT, "Draft"),
])
def test_real_workspace_integer_id_reaches_exact_destination(
    test_dbs, mode, expected,
):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    hub.execute(
        "INSERT INTO jobs (id, status, notes, job_no) "
        "VALUES (1, 'Active', 'Same number other job', '26-017')"
    )
    hub.commit()
    assert pr.execute(
        "SELECT typeof(jobhub_job_id) FROM workspaces WHERE id=1"
    ).fetchone()[0] == "integer"
    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=mode,
        acting_user="Source Estimator",
    )
    assert type(package.project_identity.target_jobhub_job_id) is int
    assert package.project_identity.target_jobhub_job_id == 501
    assert package.payload_hash == package.compute_payload_hash()
    assert validate_publishing_gate(package).is_publishable

    receipt = execute_jobhub_publishing(
        package, bridge, user_name="Source Estimator"
    )
    assert receipt["status"] == expected
    assert receipt["job_id"] == 501
    assert hub.execute(
        "SELECT job_id, status FROM painting_takeoff_packages"
    ).fetchall() == [(501, expected)]
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1


def test_missing_workspace_link_stays_missing_and_cannot_write(test_dbs):
    pr, hub, bridge = test_dbs
    _one_source_neutral_row(pr)
    pr.execute("UPDATE workspaces SET jobhub_job_id=NULL WHERE id=1")
    pr.commit()
    package = build_publishing_package_from_workspace(
        pr, workspace_id=1, mode=PublishingMode.DRAFT,
        acting_user="Source Estimator",
    )
    assert package.project_identity.target_jobhub_job_id is None
    assert package.payload_hash == package.compute_payload_hash()
    with pytest.raises(RuntimeError, match="Target JobHub job ID is required"):
        execute_jobhub_publishing(
            package, bridge, user_name="Source Estimator"
        )
    assert hub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
