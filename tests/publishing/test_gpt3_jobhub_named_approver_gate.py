"""Source-neutral real JobHub regression for named estimator approval.

Synthetic FIRM fixtures only exercise the commercial gate and SQLite writer.
They do not authenticate original drawings, mint FIRM, or change frozen V2.
"""
from __future__ import annotations

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _insert(conn, *, status, source, approver):
    conn.execute(
        """
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (
            1, 1, 'Internal walls', 'Level 1', 'Plasterboard', 'PB01',
            'Measured wall', 'm2', 1.25, 20.0, 25.0, ?, ?, ?
        )
        """,
        (status, source, approver),
    )
    conn.commit()


def _package(conn, mode=PublishingMode.COMMERCIAL):
    return build_publishing_package_from_workspace(
        conn,
        1,
        mode,
        preflight_fingerprint="source-neutral-named-estimator-regression",
        acting_user="Package Estimator",
    )


_APPROVAL_REQUIRED = (
    ("user_approved", "user_approved"),
    ("user_approved", "documented_dimension"),
    ("firm", "user_corrected"),
    ("firm", "user_approved"),
    ("user_approved", "user_corrected"),
    ("firm", "ai_detected"),
    ("firm", "model_derived"),
    ("firm", "pdf_scaled"),
)


@pytest.mark.parametrize("status,source", _APPROVAL_REQUIRED)
@pytest.mark.parametrize("blank_actor", ["", "   ", "\t\n", None])
def test_blank_approval_cannot_reach_real_jobhub(
    test_dbs, status, source, blank_actor,
):
    planreader, jobhub, bridge = test_dbs
    _insert(planreader, status=status, source=source, approver=blank_actor)
    package = _package(planreader)
    assert package.quantities[0].approved_by == blank_actor
    assert package.payload_hash == package.compute_payload_hash()

    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any(
        "approval" in reason.lower() for reason in gate.blocking_reasons
    )
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Delivery Estimator")
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 0


@pytest.mark.parametrize("status,source", _APPROVAL_REQUIRED)
def test_real_named_estimator_approval_still_publishes(
    test_dbs, status, source,
):
    planreader, jobhub, bridge = test_dbs
    _insert(planreader, status=status, source=source, approver="Estimator A")
    package = _package(planreader)
    gate = validate_publishing_gate(package)
    assert gate.is_publishable
    result = execute_jobhub_publishing(package, bridge, "Delivery Estimator")
    assert result["status"] == "Published"
    assert result["total_lines"] == 1
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(package, bridge, "Delivery Estimator")


@pytest.mark.parametrize("bad_actor", [True, 1, ["Estimator A"]])
def test_non_string_approval_cannot_self_authorize_by_truthiness(
    test_dbs, bad_actor,
):
    planreader, jobhub, bridge = test_dbs
    _insert(planreader, status="user_approved", source="user_approved",
            approver="Estimator A")
    package = _package(planreader)
    package.quantities[0].approved_by = bad_actor
    package.payload_hash = package.compute_payload_hash()
    assert not validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Delivery Estimator")
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 0


def test_documented_firm_does_not_require_manual_approval(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _insert(planreader, status="firm", source="documented_dimension", approver=None)
    package = _package(planreader)
    assert validate_publishing_gate(package).is_publishable
    assert execute_jobhub_publishing(
        package, bridge, "Delivery Estimator"
    )["status"] == "Published"
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1


def test_provisional_draft_remains_draft_without_named_approver(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _insert(planreader, status="provisional", source="ai_detected", approver="   ")
    package = _package(planreader, PublishingMode.DRAFT)
    gate = validate_publishing_gate(package)
    assert gate.is_publishable
    assert gate.warnings
    receipt = execute_jobhub_publishing(package, bridge, "Delivery Estimator")
    assert receipt["status"] == "Draft"
    assert jobhub.execute(
        "SELECT status FROM painting_takeoff_packages"
    ).fetchone()[0] == "Draft"
